"""Unit tests for Jira hierarchy resolver functionality."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from wes.integrations.jira_hierarchy_resolver import (
    HierarchyCache,
    HierarchyNode,
    JiraHierarchyResolver,
)


class TestHierarchyCache:
    """Test hierarchy cache functionality."""

    @pytest.mark.asyncio
    async def test_cache_operations(self):
        """Test basic cache get/set operations."""
        cache = HierarchyCache(ttl=1, max_size=3)

        # Test empty cache
        assert await cache.get("test-key") is None

        # Test set and get
        await cache.set("test-key", {"data": "test"})
        result = await cache.get("test-key")
        assert result == {"data": "test"}

        # Test expiration
        await asyncio.sleep(1.1)
        assert await cache.get("test-key") is None

    @pytest.mark.asyncio
    async def test_cache_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        cache = HierarchyCache(ttl=60, max_size=2)

        # Fill cache
        await cache.set("key1", {"data": "1"})
        await cache.set("key2", {"data": "2"})

        # Add third item should evict first
        await cache.set("key3", {"data": "3"})

        # First item should be evicted
        assert await cache.get("key1") is None
        assert await cache.get("key2") == {"data": "2"}
        assert await cache.get("key3") == {"data": "3"}

    @pytest.mark.asyncio
    async def test_get_multiple(self):
        """Test getting multiple items from cache."""
        cache = HierarchyCache(ttl=60, max_size=10)

        await cache.set("key1", {"data": "1"})
        await cache.set("key2", {"data": "2"})

        results = await cache.get_multiple(["key1", "key2", "key3"])
        assert results == {"key1": {"data": "1"}, "key2": {"data": "2"}}


class TestJiraHierarchyResolver:
    """Test Jira hierarchy resolver functionality."""

    @pytest.fixture
    def mock_jira_client(self):
        """Create a mock Jira client."""
        client = Mock()
        client._jira_client = Mock()
        return client

    @pytest.fixture
    def resolver(self, mock_jira_client):
        """Create a JiraHierarchyResolver instance."""
        config = {
            "epic_link_field": "customfield_10007",
            "fetch_parents": True,
            "max_hierarchy_depth": 3,
            "cache_ttl": 3600,
            "strategy_labels": ["strategy:", "initiative:"],
            "outcome_labels": ["outcome:", "goal:"],
            "include_components": True,
            "include_fix_versions": True,
        }
        return JiraHierarchyResolver(mock_jira_client, config)

    @pytest.mark.asyncio
    async def test_collect_parent_references(self, resolver):
        """Test collecting parent references from activities."""
        activities = [
            {
                "id": "PROJ-123",
                "parent": {"key": "PROJ-100"},
                "customfield_10007": "PROJ-101",
                "issuelinks": [
                    {
                        "type": {"name": "Epic-Story Link"},
                        "outwardIssue": {"key": "PROJ-102"},
                    }
                ],
            },
            {"id": "PROJ-124", "parent": {"key": "PROJ-100"}},
        ]

        parent_refs = await resolver._collect_parent_references(activities)
        assert parent_refs == {"PROJ-100", "PROJ-101", "PROJ-102"}

    @pytest.mark.asyncio
    async def test_enrich_activities_with_hierarchy(self, resolver, mock_jira_client):
        """Test enriching activities with hierarchy data."""
        # Mock activities
        activities = [
            {
                "id": "PROJ-123",
                "title": "Implement feature",
                "status": "In Progress",
                "project": "PROJ",
                "project_name": "Project Name",
                "parent": {"key": "PROJ-100"},
                "labels": ["feature", "backend"],
                "components": [{"name": "API", "id": "comp1"}],
            }
        ]

        # Mock parent data fetch
        mock_issue = Mock()
        mock_issue.key = "PROJ-100"
        mock_issue.fields.summary = "Q4 Platform Epic"
        mock_issue.fields.issuetype.name = "Epic"
        mock_issue.fields.status.name = "Open"
        mock_issue.fields.labels = ["strategy:platform", "outcome:scalability"]
        mock_issue.fields.components = []
        mock_issue.fields.fixVersions = []
        mock_issue.fields.parent = None

        mock_jira_client._jira_client.search_issues.return_value = [mock_issue]

        # Enrich activities
        enriched = await resolver.enrich_activities_with_hierarchy(activities)

        # Verify hierarchy was added
        assert len(enriched) == 1
        activity = enriched[0]
        assert "hierarchy" in activity
        assert activity["hierarchy"]["parent"]["key"] == "PROJ-100"
        assert activity["hierarchy"]["parent"]["type"] == "Epic"
        assert activity["hierarchy"]["parent"]["title"] == "Q4 Platform Epic"

        # Verify organizational context
        assert "organizational_context" in activity
        assert activity["organizational_context"]["components"] == ["API"]
        assert activity["organizational_context"]["project"]["key"] == "PROJ"

    @pytest.mark.asyncio
    async def test_build_hierarchy_context(self, resolver):
        """Test building hierarchy context for an activity."""
        activity = {
            "id": "PROJ-123",
            "issuetype": "Story",
            "parent": {"key": "PROJ-100"},
        }

        parent_data = {
            "PROJ-100": {
                "key": "PROJ-100",
                "summary": "Epic Title",
                "issue_type": "Epic",
                "hierarchy_level": 1,
                "status": "Open",
                "labels": ["strategy:growth"],
                "parent_key": None,
            }
        }

        hierarchy = await resolver._build_hierarchy_context(activity, parent_data)

        assert hierarchy["level"] == 0  # Story level
        assert hierarchy["parent"]["key"] == "PROJ-100"
        assert hierarchy["parent"]["type"] == "Epic"
        assert hierarchy["parent"]["title"] == "Epic Title"
        assert hierarchy["path"] == ["PROJ-100", "PROJ-123"]
        assert hierarchy["epic"]["key"] == "PROJ-100"

    def test_extract_strategy_outcome_labels(self, resolver):
        """Test extracting strategy and outcome labels."""
        labels = [
            "backend",
            "strategy:platform",
            "outcome:performance",
            "goal:scale-10x",
            "feature",
        ]

        result = resolver._extract_strategy_outcome_labels(labels)

        assert result["strategies"] == ["platform"]
        assert set(result["outcomes"]) == {"performance", "scale-10x"}

    def test_extract_related_issues(self, resolver):
        """Test extracting related issues from issue links."""
        activity = {
            "issuelinks": [
                {
                    "type": {"name": "Blocks"},
                    "outwardIssue": {"key": "PROJ-124"},
                },
                {
                    "type": {"name": "Blocks"},
                    "inwardIssue": {"key": "PROJ-125"},
                },
                {
                    "type": {"name": "Relates"},
                    "outwardIssue": {"key": "PROJ-126"},
                },
            ],
            "subtasks": [{"key": "PROJ-123-1"}, {"key": "PROJ-123-2"}],
        }

        related = resolver._extract_related_issues(activity)

        assert related["blocks"] == ["PROJ-124"]
        assert related["is_blocked_by"] == ["PROJ-125"]
        assert related["relates_to"] == ["PROJ-126"]
        assert related["subtasks"] == ["PROJ-123-1", "PROJ-123-2"]

    def test_determine_hierarchy_level(self, resolver):
        """Test determining hierarchy level from issue type."""
        # Epic
        epic_issue = Mock()
        epic_issue.fields.issuetype.name = "Epic"
        assert resolver._determine_hierarchy_level(epic_issue) == 1

        # Subtask
        subtask_issue = Mock()
        subtask_issue.fields.issuetype.name = "Sub-task"
        assert resolver._determine_hierarchy_level(subtask_issue) == -1

        # Story
        story_issue = Mock()
        story_issue.fields.issuetype.name = "Story"
        assert resolver._determine_hierarchy_level(story_issue) == 0
