"""Jira issue hierarchy resolver for extracting parent/epic relationships."""

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from ..utils.logging_config import get_logger
from ..utils.validators import InputValidator


@dataclass
class HierarchyNode:
    """Represents a node in the issue hierarchy."""

    key: str
    issue_type: str
    summary: str
    status: str
    labels: List[str]
    parent_key: Optional[str] = None
    hierarchy_level: int = 0  # -1=subtask, 0=story/task, 1=epic
    children: List[str] = None

    def __post_init__(self):
        if self.children is None:
            self.children = []


class HierarchyCache:
    """Cache for issue hierarchy data with TTL support."""

    def __init__(self, ttl: int = 3600, max_size: int = 1000):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl = ttl
        self.max_size = max_size
        self.logger = get_logger(__name__)
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached item if not expired."""
        async with self._lock:
            if key in self.cache:
                item = self.cache[key]
                if time.time() - item["timestamp"] < self.ttl:
                    self.logger.debug(f"Cache hit for {key}")
                    return item["data"]
                else:
                    # Remove expired item
                    del self.cache[key]
                    self.logger.debug(f"Cache expired for {key}")
            return None

    async def set(self, key: str, data: Dict[str, Any]) -> None:
        """Set cache item with timestamp."""
        async with self._lock:
            # Implement simple LRU by removing oldest items if at capacity
            if len(self.cache) >= self.max_size:
                oldest_key = min(
                    self.cache.keys(), key=lambda k: self.cache[k]["timestamp"]
                )
                del self.cache[oldest_key]
                self.logger.debug(f"Evicted {oldest_key} from cache (LRU)")

            self.cache[key] = {"data": data, "timestamp": time.time()}
            self.logger.debug(f"Cached {key}")

    async def get_multiple(self, keys: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get multiple items from cache."""
        result = {}
        for key in keys:
            cached = await self.get(key)
            if cached:
                result[key] = cached
        return result

    async def clear(self) -> None:
        """Clear all cached items."""
        async with self._lock:
            self.cache.clear()
            self.logger.info("Cache cleared")


class JiraHierarchyResolver:
    """Resolves issue hierarchies and organizational context from Jira."""

    def __init__(self, jira_client: Any, config: Optional[Dict[str, Any]] = None):
        self.jira_client = jira_client
        self.logger = get_logger(__name__)

        # Default configuration
        default_config = {
            "epic_link_field": "customfield_10007",
            "fetch_parents": True,
            "max_hierarchy_depth": 3,
            "cache_ttl": 3600,
            "strategy_labels": ["strategy:", "initiative:"],
            "outcome_labels": ["outcome:", "goal:", "objective:"],
            "include_components": True,
            "include_fix_versions": True,
        }

        self.config = {**default_config, **(config or {})}
        self.cache = HierarchyCache(ttl=self.config["cache_ttl"], max_size=1000)

    async def enrich_activities_with_hierarchy(
        self, activities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Enrich activity data with hierarchy and organizational context."""
        if not activities:
            return activities

        self.logger.info(f"Enriching {len(activities)} activities with hierarchy data")

        # Phase 1: Collect all unique parent/epic references
        parent_keys = await self._collect_parent_references(activities)

        if parent_keys:
            # Phase 2: Batch fetch parent/epic details
            parent_data = await self._fetch_hierarchy_batch(list(parent_keys))

            # Phase 3: Build hierarchy for each activity
            for activity in activities:
                activity["hierarchy"] = await self._build_hierarchy_context(
                    activity, parent_data
                )
                activity["organizational_context"] = (
                    self._extract_organizational_context(activity)
                )
                activity["related_issues"] = self._extract_related_issues(activity)

        return activities

    async def _collect_parent_references(
        self, activities: List[Dict[str, Any]]
    ) -> Set[str]:
        """Collect all unique parent/epic issue keys."""
        parent_keys = set()

        for activity in activities:
            # Check modern parent field
            if "parent" in activity and activity["parent"]:
                parent_key = activity["parent"].get("key")
                if parent_key:
                    parent_keys.add(parent_key)

            # Check legacy epic link field
            epic_field = self.config["epic_link_field"]
            if epic_field in activity and activity[epic_field]:
                parent_keys.add(activity[epic_field])

            # Check issue links for parent relationships
            if "issuelinks" in activity:
                for link in activity["issuelinks"]:
                    if link.get("type", {}).get("name") in [
                        "Epic-Story Link",
                        "Parent",
                        "Hierarchy",
                    ]:
                        if "outwardIssue" in link:
                            parent_keys.add(link["outwardIssue"]["key"])
                        if "inwardIssue" in link:
                            parent_keys.add(link["inwardIssue"]["key"])

        self.logger.info(f"Found {len(parent_keys)} unique parent/epic references")
        return parent_keys

    async def _fetch_hierarchy_batch(
        self, issue_keys: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Batch fetch parent/epic issues for efficiency."""
        if not issue_keys:
            return {}

        # Check cache first
        cached_data = await self.cache.get_multiple(issue_keys)
        uncached_keys = [key for key in issue_keys if key not in cached_data]

        if not uncached_keys:
            self.logger.info(f"All {len(issue_keys)} parent issues found in cache")
            return cached_data

        self.logger.info(
            f"Fetching {len(uncached_keys)} parent issues (cached: {len(cached_data)})"
        )

        try:
            # Build JQL for batch fetch
            jql = f"key in ({','.join(uncached_keys)})"

            # Fetch with minimal fields for efficiency
            fields = [
                "summary",
                "issuetype",
                "labels",
                "status",
                "parent",
                self.config["epic_link_field"],
                "components",
                "fixVersions",
            ]

            issues = self.jira_client._jira_client.search_issues(
                jql, fields=",".join(fields), maxResults=len(uncached_keys)
            )

            # Process and cache results
            fetched_data = {}
            for issue in issues:
                issue_data = {
                    "key": issue.key,
                    "summary": InputValidator.sanitize_text(issue.fields.summary),
                    "issue_type": issue.fields.issuetype.name,
                    "hierarchy_level": self._determine_hierarchy_level(issue),
                    "status": issue.fields.status.name,
                    "labels": [
                        InputValidator.sanitize_text(label)
                        for label in issue.fields.labels
                    ],
                    "components": [
                        {"name": c.name, "id": c.id}
                        for c in getattr(issue.fields, "components", [])
                    ],
                    "fix_versions": [
                        {"name": v.name, "id": v.id}
                        for v in getattr(issue.fields, "fixVersions", [])
                    ],
                }

                # Check for parent of this parent (grandparent)
                if hasattr(issue.fields, "parent") and issue.fields.parent:
                    issue_data["parent_key"] = issue.fields.parent.key

                fetched_data[issue.key] = issue_data
                await self.cache.set(issue.key, issue_data)

            # Combine cached and fetched data
            return {**cached_data, **fetched_data}

        except Exception as e:
            self.logger.error(f"Failed to fetch hierarchy batch: {e}")
            return cached_data  # Return at least what we have cached

    def _determine_hierarchy_level(self, issue: Any) -> int:
        """Determine the hierarchy level of an issue."""
        issue_type = issue.fields.issuetype.name.lower()

        if "subtask" in issue_type or "sub-task" in issue_type:
            return -1
        elif "epic" in issue_type:
            return 1
        else:
            return 0  # Story, Task, Bug, etc.

    async def _build_hierarchy_context(
        self, activity: Dict[str, Any], parent_data: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build complete hierarchy context for an activity."""
        hierarchy = {
            "level": 0,  # Default to story/task level
            "path": [activity["id"]],
            "parent": None,
            "epic": None,
        }

        # Determine current issue's level
        if "issuetype" in activity:
            issue_type = activity["issuetype"].lower()
            if "subtask" in issue_type:
                hierarchy["level"] = -1
            elif "epic" in issue_type:
                hierarchy["level"] = 1

        # Find parent information
        parent_key = None

        # Check modern parent field
        if "parent" in activity and activity["parent"]:
            parent_key = activity["parent"].get("key")

        # Check legacy epic link
        if not parent_key:
            epic_field = self.config["epic_link_field"]
            if epic_field in activity and activity[epic_field]:
                parent_key = activity[epic_field]

        # Build hierarchy path
        if parent_key and parent_key in parent_data:
            parent_info = parent_data[parent_key]
            hierarchy["parent"] = {
                "key": parent_key,
                "type": parent_info["issue_type"],
                "title": parent_info["summary"],
                "labels": self._extract_strategy_outcome_labels(parent_info["labels"]),
            }

            # Build complete path (up to max depth)
            current_key = parent_key
            depth = 0
            while (
                current_key in parent_data
                and depth < self.config["max_hierarchy_depth"]
            ):
                hierarchy["path"].insert(0, current_key)
                current_parent = parent_data[current_key]
                current_key = current_parent.get("parent_key")
                depth += 1

                # Track epic separately for legacy support
                if current_parent["issue_type"].lower() == "epic":
                    hierarchy["epic"] = {
                        "key": current_parent.get("key", current_key),
                        "name": current_parent["summary"],
                    }

        return hierarchy

    def _extract_organizational_context(
        self, activity: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract organizational context from activity data."""
        context = {
            "project": {
                "key": activity.get("project"),
                "name": activity.get("project_name"),
            },
            "components": [],
            "release": None,
            "strategy_tags": [],
            "outcome_tags": [],
        }

        # Extract components
        if self.config["include_components"] and "components" in activity:
            context["components"] = [c["name"] for c in activity["components"]]

        # Extract fix versions (releases)
        if self.config["include_fix_versions"] and "fixVersions" in activity:
            versions = activity.get("fixVersions", [])
            if versions:
                context["release"] = versions[0].get("name")  # Primary version

        # Extract strategy and outcome tags from labels
        if "labels" in activity:
            labels = self._extract_strategy_outcome_labels(activity["labels"])
            context["strategy_tags"] = labels.get("strategies", [])
            context["outcome_tags"] = labels.get("outcomes", [])

        return context

    def _extract_strategy_outcome_labels(
        self, labels: List[str]
    ) -> Dict[str, List[str]]:
        """Extract strategy and outcome information from labels."""
        result = {"strategies": [], "outcomes": []}

        for label in labels:
            label_lower = label.lower()

            # Check strategy labels
            for prefix in self.config["strategy_labels"]:
                if label_lower.startswith(prefix.lower()):
                    value = label[len(prefix) :].strip()
                    if value:
                        result["strategies"].append(value)

            # Check outcome labels
            for prefix in self.config["outcome_labels"]:
                if label_lower.startswith(prefix.lower()):
                    value = label[len(prefix) :].strip()
                    if value:
                        result["outcomes"].append(value)

        return result

    def _extract_related_issues(self, activity: Dict[str, Any]) -> Dict[str, List[str]]:
        """Extract related issues from issue links."""
        related = {
            "blocks": [],
            "is_blocked_by": [],
            "relates_to": [],
            "subtasks": [],
        }

        if "issuelinks" not in activity:
            return related

        for link in activity["issuelinks"]:
            link_type = link.get("type", {}).get("name", "").lower()

            if "blocks" in link_type:
                if "outwardIssue" in link:
                    related["blocks"].append(link["outwardIssue"]["key"])
                if "inwardIssue" in link:
                    related["is_blocked_by"].append(link["inwardIssue"]["key"])
            elif "relates" in link_type or "related" in link_type:
                if "outwardIssue" in link:
                    related["relates_to"].append(link["outwardIssue"]["key"])
                if "inwardIssue" in link:
                    related["relates_to"].append(link["inwardIssue"]["key"])

        # Add subtasks if present
        if "subtasks" in activity:
            related["subtasks"] = [st["key"] for st in activity.get("subtasks", [])]

        return related

    async def clear_cache(self) -> None:
        """Clear the hierarchy cache."""
        await self.cache.clear()
