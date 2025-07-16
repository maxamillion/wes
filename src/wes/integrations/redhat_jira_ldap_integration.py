"""Integration module that combines Red Hat Jira and LDAP functionality."""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..core.config_manager import ConfigManager
from ..utils.exceptions import JiraIntegrationError, WesError
from ..utils.logging_config import get_logger
from .redhat_jira_client import RedHatJiraClient
from .redhat_ldap_client import LDAPIntegrationError, RedHatLDAPClient


class RedHatJiraLDAPIntegration:
    """Integrates Red Hat Jira with LDAP for organizational queries."""

    def __init__(self, config_manager: ConfigManager):
        """Initialize integration with configuration.

        Args:
            config_manager: Configuration manager instance
        """
        self.logger = get_logger(__name__)
        self.config_manager = config_manager

        # Get configurations
        self.jira_config = config_manager.get_jira_config()
        self.ldap_config = config_manager.get_ldap_config()

        # Initialize clients
        self.jira_client: Optional[RedHatJiraClient] = None
        self.ldap_client: Optional[RedHatLDAPClient] = None

        # Cache for LDAP queries
        self._ldap_cache: Dict[str, Tuple[List[str], Dict[str, Any], float]] = {}

    async def initialize(self) -> None:
        """Initialize Jira and LDAP clients."""
        try:
            # Initialize Red Hat Jira client
            self.jira_client = RedHatJiraClient(
                url=self.jira_config.url,
                username=self.jira_config.username,
                api_token=self.jira_config.api_token,
                rate_limit=self.jira_config.rate_limit,
                timeout=self.jira_config.timeout,
            )

            # Validate Jira connection
            await self.jira_client.validate_connection()

            # Initialize LDAP client if enabled
            if self.ldap_config.enabled:
                self.ldap_client = RedHatLDAPClient(
                    server_url=self.ldap_config.server_url,
                    base_dn=self.ldap_config.base_dn,
                    timeout=self.ldap_config.timeout,
                    use_ssl=self.ldap_config.use_ssl,
                    validate_certs=self.ldap_config.validate_certs,
                )

                # Validate LDAP connection
                await self.ldap_client.validate_connection()

            self.logger.info("Red Hat Jira-LDAP integration initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize integration: {e}")
            raise WesError(f"Integration initialization failed: {e}")

    async def get_manager_team_activities(
        self,
        manager_identifier: str,
        start_date: datetime,
        end_date: datetime,
        projects: Optional[List[str]] = None,
        include_comments: bool = True,
        max_results: int = 1000,
        max_hierarchy_depth: Optional[int] = None,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Get Jira activities for a manager's entire team using LDAP.

        Args:
            manager_identifier: Manager's email or username
            start_date: Start date for activities
            end_date: End date for activities
            projects: Optional list of projects to filter
            include_comments: Whether to include comments
            max_results: Maximum number of results
            max_hierarchy_depth: Maximum depth to traverse in org hierarchy

        Returns:
            Tuple of (list of activities, organizational hierarchy)
        """
        try:
            if not self.ldap_config.enabled or not self.ldap_client:
                raise LDAPIntegrationError("LDAP is not enabled or initialized")

            # Use configured max depth if not specified
            if max_hierarchy_depth is None:
                max_hierarchy_depth = self.ldap_config.max_hierarchy_depth

            # Check cache first
            cache_key = f"{manager_identifier}:{max_hierarchy_depth}"
            if cache_key in self._ldap_cache:
                cached_users, cached_hierarchy, cache_time = self._ldap_cache[cache_key]
                cache_age_minutes = (asyncio.get_event_loop().time() - cache_time) / 60

                if cache_age_minutes < self.ldap_config.cache_ttl_minutes:
                    self.logger.info(
                        f"Using cached LDAP data for {manager_identifier} "
                        f"(age: {cache_age_minutes:.1f} minutes)"
                    )
                    users = cached_users
                    hierarchy = cached_hierarchy
                else:
                    # Cache expired
                    users, hierarchy = await self._fetch_team_members(
                        manager_identifier, max_hierarchy_depth
                    )
                    self._update_cache(cache_key, users, hierarchy)
            else:
                # Not in cache
                users, hierarchy = await self._fetch_team_members(
                    manager_identifier, max_hierarchy_depth
                )
                self._update_cache(cache_key, users, hierarchy)

            # Log team composition
            self.logger.info(
                f"Found {len(users)} team members for {manager_identifier}: {users}"
            )

            # Get activities for all team members
            if users:
                activities = await self.jira_client.get_user_activities(
                    users=users,
                    start_date=start_date,
                    end_date=end_date,
                    projects=projects,
                    include_comments=include_comments,
                    max_results=max_results,
                )
            else:
                activities = []

            # Add organizational context to activities
            activities = self._enrich_activities_with_org_data(activities, hierarchy)

            return activities, hierarchy

        except Exception as e:
            self.logger.error(
                f"Failed to get manager team activities for {manager_identifier}: {e}"
            )
            raise JiraIntegrationError(f"Team activities query failed: {e}")

    async def _fetch_team_members(
        self, manager_identifier: str, max_depth: int
    ) -> Tuple[List[str], Dict[str, Any]]:
        """Fetch team members from LDAP.

        Args:
            manager_identifier: Manager's email or username
            max_depth: Maximum hierarchy depth

        Returns:
            Tuple of (list of Jira usernames, organizational hierarchy)
        """
        try:
            # Get team members and hierarchy from LDAP
            users, hierarchy = await self.ldap_client.get_team_members_for_manager(
                manager_identifier, max_depth
            )

            return users, hierarchy

        except Exception as e:
            self.logger.error(f"LDAP query failed for {manager_identifier}: {e}")
            raise LDAPIntegrationError(f"LDAP query failed: {e}")

    def _update_cache(
        self, cache_key: str, users: List[str], hierarchy: Dict[str, Any]
    ) -> None:
        """Update LDAP cache.

        Args:
            cache_key: Cache key
            users: List of usernames
            hierarchy: Organizational hierarchy
        """
        current_time = asyncio.get_event_loop().time()
        self._ldap_cache[cache_key] = (users, hierarchy, current_time)

        # Clean old cache entries
        max_cache_age = self.ldap_config.cache_ttl_minutes * 60
        keys_to_remove = []
        for key, (_, _, cache_time) in self._ldap_cache.items():
            if current_time - cache_time > max_cache_age * 2:  # 2x TTL for cleanup
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self._ldap_cache[key]

    def _enrich_activities_with_org_data(
        self, activities: List[Dict[str, Any]], hierarchy: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Enrich activities with organizational data.

        Args:
            activities: List of Jira activities
            hierarchy: Organizational hierarchy

        Returns:
            Enriched activities
        """
        # Build a mapping of username to org data
        org_map = self._build_org_map(hierarchy)

        # Enrich each activity
        for activity in activities:
            assignee = activity.get("assignee")
            if assignee and assignee in org_map:
                org_data = org_map[assignee]
                activity["org_data"] = {
                    "manager": org_data.get("manager"),
                    "title": org_data.get("title"),
                    "department": org_data.get("department"),
                    "hierarchy_level": org_data.get("level"),
                }

        return activities

    def _build_org_map(self, hierarchy: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Build a mapping of usernames to organizational data.

        Args:
            hierarchy: Organizational hierarchy

        Returns:
            Dictionary mapping usernames to org data
        """
        org_map = {}

        def _process_node(
            node: Dict[str, Any], manager: Optional[str] = None, level: int = 0
        ) -> None:
            uid = node.get("uid")
            if uid:
                org_map[uid] = {
                    "email": node.get("email"),
                    "display_name": node.get("display_name"),
                    "title": node.get("title"),
                    "department": node.get("department"),
                    "manager": manager,
                    "level": level,
                }

                # Process direct reports
                for report in node.get("direct_reports", []):
                    _process_node(report, uid, level + 1)

        _process_node(hierarchy)
        return org_map

    async def get_user_activities_with_fallback(
        self,
        users: List[str],
        start_date: datetime,
        end_date: datetime,
        projects: Optional[List[str]] = None,
        include_comments: bool = True,
        max_results: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Get user activities with LDAP enrichment if available.

        This method provides a fallback mechanism that works with or without LDAP.

        Args:
            users: List of usernames (can be emails if LDAP is enabled)
            start_date: Start date for activities
            end_date: End date for activities
            projects: Optional list of projects to filter
            include_comments: Whether to include comments
            max_results: Maximum number of results

        Returns:
            List of activities
        """
        try:
            # If LDAP is enabled and we have email addresses, map them
            if self.ldap_config.enabled and self.ldap_client:
                mapped_users = []
                for user in users:
                    if "@" in user:
                        # This is an email, try to map it
                        ldap_user = await self.ldap_client.search_user_by_email(user)
                        if ldap_user and ldap_user.uid:
                            mapped_users.append(ldap_user.uid)
                        else:
                            # Fallback to extracting username from email
                            mapped_users.append(user.split("@")[0])
                    else:
                        # Already a username
                        mapped_users.append(user)

                users = mapped_users

            # Get activities from Jira
            activities = await self.jira_client.get_user_activities(
                users=users,
                start_date=start_date,
                end_date=end_date,
                projects=projects,
                include_comments=include_comments,
                max_results=max_results,
            )

            return activities

        except Exception as e:
            self.logger.error(f"Failed to get user activities with fallback: {e}")
            raise JiraIntegrationError(f"Activities query failed: {e}")

    async def validate_manager_access(self, manager_identifier: str) -> bool:
        """Validate that a manager exists in LDAP and has direct reports.

        Args:
            manager_identifier: Manager's email or username

        Returns:
            True if manager is valid and has reports
        """
        try:
            if not self.ldap_config.enabled or not self.ldap_client:
                self.logger.warning("LDAP not enabled, cannot validate manager")
                return True  # Allow operation to continue

            # Search for manager
            if "@" in manager_identifier:
                manager = await self.ldap_client.search_user_by_email(
                    manager_identifier
                )
            else:
                manager = await self.ldap_client.search_user_by_uid(manager_identifier)

            if not manager:
                self.logger.warning(f"Manager not found in LDAP: {manager_identifier}")
                return False

            # Check if manager has direct reports
            manager_dn = f"uid={manager.uid},{self.ldap_client.base_dn}"
            direct_reports = await self.ldap_client.get_direct_reports(manager_dn)

            if not direct_reports:
                self.logger.warning(
                    f"Manager {manager_identifier} has no direct reports"
                )
                return False

            self.logger.info(
                f"Manager {manager_identifier} validated with "
                f"{len(direct_reports)} direct reports"
            )
            return True

        except Exception as e:
            self.logger.error(f"Failed to validate manager {manager_identifier}: {e}")
            return False

    def get_integration_info(self) -> Dict[str, Any]:
        """Get integration status information."""
        info = {
            "jira_connected": bool(self.jira_client),
            "ldap_enabled": self.ldap_config.enabled,
            "ldap_connected": bool(self.ldap_client),
            "cache_entries": len(self._ldap_cache),
        }

        if self.jira_client:
            info["jira_info"] = self.jira_client.get_connection_info()

        if self.ldap_client:
            info["ldap_info"] = self.ldap_client.get_connection_info()

        return info

    async def close(self) -> None:
        """Close all connections."""
        try:
            if self.jira_client:
                await self.jira_client.close()

            if self.ldap_client:
                await self.ldap_client.disconnect()

            self.logger.info("Red Hat Jira-LDAP integration closed")

        except Exception as e:
            self.logger.error(f"Error closing integration: {e}")
