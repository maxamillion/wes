"""Jira integration client for fetching work item data."""

import asyncio
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from jira import JIRA, JIRAError

from ..utils.exceptions import AuthenticationError, JiraIntegrationError, RateLimitError
from ..utils.logging_config import get_logger, get_security_logger
from ..utils.validators import InputValidator
from .redhat_jira_client import RedHatJiraClient, is_redhat_jira


class RateLimiter:
    """Rate limiter for API requests."""

    def __init__(self, max_requests: int = 100, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire rate limit permit."""
        async with self._lock:
            now = time.time()

            # Remove old requests
            self.requests = [
                req_time
                for req_time in self.requests
                if now - req_time < self.time_window
            ]

            # Check if we're at the limit
            if len(self.requests) >= self.max_requests:
                wait_time = self.time_window - (now - self.requests[0])
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    return await self.acquire()

            # Add current request
            self.requests.append(now)


class JiraClient:
    """Secure Jira API client."""

    def __init__(
        self,
        url: str,
        username: str,
        api_token: str,
        rate_limit: int = 100,
        timeout: int = 30,
    ):
        self.logger = get_logger(__name__)
        self.security_logger = get_security_logger()

        # Validate inputs
        InputValidator.validate_jira_url(url)
        InputValidator.validate_user_identifier(username)
        InputValidator.validate_api_key(api_token)

        self.url = url.rstrip("/")
        self.username = username
        self.api_token = api_token
        self.timeout = timeout

        # Check if this is a Red Hat Jira instance
        self.is_redhat = is_redhat_jira(url)

        if self.is_redhat:
            # Use Red Hat Jira client for Red Hat instances
            self._redhat_client = RedHatJiraClient(
                url=url,
                username=username,
                api_token=api_token,
                rate_limit=rate_limit,
                timeout=timeout,
            )
            self._jira_client = self._redhat_client._client
            self.rate_limiter = self._redhat_client.rate_limiter
        else:
            # Initialize rate limiter for standard Jira
            self.rate_limiter = RateLimiter(max_requests=rate_limit, time_window=60)

            # Initialize standard JIRA client
            self._jira_client: Optional[JIRA] = None
            self._redhat_client = None
            self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize JIRA client with authentication."""
        try:
            self._jira_client = JIRA(
                server=self.url,
                basic_auth=(self.username, self.api_token),
                timeout=self.timeout,
                options={
                    "verify": True,
                    "check_update": False,
                    "agile_rest_path": "agile",
                },
            )

            # Test connection
            self._test_connection()

            self.security_logger.log_authentication_attempt(
                service="jira", username=self.username, success=True
            )

            self.logger.info("Jira client initialized successfully")

        except JIRAError as e:
            self.security_logger.log_authentication_attempt(
                service="jira", username=self.username, success=False, error=str(e)
            )
            raise AuthenticationError(f"Jira authentication failed: {e}")
        except Exception as e:
            self.logger.error(f"Failed to initialize Jira client: {e}")
            raise JiraIntegrationError(f"Failed to initialize Jira client: {e}")

    def _test_connection(self) -> None:
        """Test Jira connection."""
        try:
            # Get current user to test authentication
            user = self._jira_client.current_user()
            self.logger.info(f"Connected to Jira as user: {user}")

        except Exception as e:
            raise AuthenticationError(f"Jira connection test failed: {e}")

    async def get_user_activities(
        self,
        users: List[str],
        start_date: datetime,
        end_date: datetime,
        projects: Optional[List[str]] = None,
        include_comments: bool = True,
        max_results: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Get user activities from Jira within date range."""
        try:
            # Delegate to Red Hat client if this is a Red Hat instance
            if self.is_redhat and self._redhat_client:
                return await self._redhat_client.get_user_activities(
                    users, start_date, end_date, projects, include_comments, max_results
                )

            # Standard Jira processing
            # Validate inputs
            InputValidator.validate_user_list(users)

            if end_date <= start_date:
                raise JiraIntegrationError("End date must be after start date")

            # Rate limiting
            await self.rate_limiter.acquire()

            # Build JQL query
            jql = self._build_activity_query(users, start_date, end_date, projects)

            # Execute query
            activities = await self._execute_query(jql, max_results, include_comments)

            self.security_logger.log_api_request(
                service="jira",
                endpoint="search",
                method="GET",
                status_code=200,
                results_count=len(activities),
            )

            return activities

        except Exception as e:
            self.logger.error(f"Failed to get user activities: {e}")
            raise JiraIntegrationError(f"Failed to get user activities: {e}")

    def _build_activity_query(
        self,
        users: List[str],
        start_date: datetime,
        end_date: datetime,
        projects: Optional[List[str]] = None,
    ) -> str:
        """Build JQL query for user activities."""
        try:
            # Format dates for JQL
            start_str = start_date.strftime("%Y-%m-%d")
            end_str = end_date.strftime("%Y-%m-%d")

            # Build user clause with proper escaping
            escaped_users = []
            for user in users:
                # JQL requires escaping these special characters with backslashes
                escaped_user = user
                # Escape backslashes first (must be done before other escapes)
                escaped_user = escaped_user.replace("\\", "\\\\")
                # Escape quotes
                escaped_user = escaped_user.replace('"', '\\"')
                # Escape other special JQL characters
                escaped_user = escaped_user.replace("*", "\\*")
                escaped_user = escaped_user.replace("?", "\\?")
                escaped_user = escaped_user.replace("+", "\\+")
                escaped_user = escaped_user.replace("-", "\\-")
                escaped_user = escaped_user.replace("&", "\\&")
                escaped_user = escaped_user.replace("|", "\\|")
                escaped_user = escaped_user.replace("!", "\\!")
                escaped_user = escaped_user.replace("(", "\\(")
                escaped_user = escaped_user.replace(")", "\\)")
                escaped_user = escaped_user.replace("{", "\\{")
                escaped_user = escaped_user.replace("}", "\\}")
                escaped_user = escaped_user.replace("[", "\\[")
                escaped_user = escaped_user.replace("]", "\\]")
                escaped_user = escaped_user.replace("^", "\\^")
                escaped_user = escaped_user.replace("~", "\\~")
                escaped_user = escaped_user.replace(":", "\\:")
                escaped_users.append(f'"{escaped_user}"')

            user_clause = f"assignee in ({','.join(escaped_users)})"

            # Build date clause
            date_clause = f"updated >= '{start_str}' AND updated <= '{end_str}'"

            # Build project clause with proper escaping
            project_clause = ""
            if projects:
                escaped_projects = []
                for proj in projects:
                    # JQL requires escaping these special characters with backslashes
                    escaped_proj = proj
                    # Escape backslashes first (must be done before other escapes)
                    escaped_proj = escaped_proj.replace("\\", "\\\\")
                    # Escape quotes
                    escaped_proj = escaped_proj.replace('"', '\\"')
                    # Escape other special JQL characters
                    escaped_proj = escaped_proj.replace("*", "\\*")
                    escaped_proj = escaped_proj.replace("?", "\\?")
                    escaped_proj = escaped_proj.replace("+", "\\+")
                    escaped_proj = escaped_proj.replace("-", "\\-")
                    escaped_proj = escaped_proj.replace("&", "\\&")
                    escaped_proj = escaped_proj.replace("|", "\\|")
                    escaped_proj = escaped_proj.replace("!", "\\!")
                    escaped_proj = escaped_proj.replace("(", "\\(")
                    escaped_proj = escaped_proj.replace(")", "\\)")
                    escaped_proj = escaped_proj.replace("{", "\\{")
                    escaped_proj = escaped_proj.replace("}", "\\}")
                    escaped_proj = escaped_proj.replace("[", "\\[")
                    escaped_proj = escaped_proj.replace("]", "\\]")
                    escaped_proj = escaped_proj.replace("^", "\\^")
                    escaped_proj = escaped_proj.replace("~", "\\~")
                    escaped_proj = escaped_proj.replace(":", "\\:")
                    escaped_projects.append(f'"{escaped_proj}"')
                project_clause = f" AND project in ({','.join(escaped_projects)})"

            # Combine clauses
            jql = f"{user_clause} AND {date_clause}{project_clause}"

            # Validate JQL
            InputValidator.validate_jira_query(jql)

            self.logger.debug(f"Built JQL query: {jql}")
            return jql

        except Exception as e:
            raise JiraIntegrationError(f"Failed to build JQL query: {e}")

    async def _execute_query(
        self, jql: str, max_results: int, include_comments: bool
    ) -> List[Dict[str, Any]]:
        """Execute JQL query and return results."""
        try:
            # Search for issues
            issues = self._jira_client.search_issues(
                jql,
                maxResults=max_results,
                expand="changelog" if include_comments else None,
                fields="summary,description,status,assignee,created,updated,priority,issuelinks",
            )

            activities = []

            for issue in issues:
                activity = await self._process_issue(issue, include_comments)
                activities.append(activity)

            return activities

        except JIRAError as e:
            if e.status_code == 429:
                raise RateLimitError(f"Jira rate limit exceeded: {e}")
            else:
                raise JiraIntegrationError(f"Jira query failed: {e}")
        except Exception as e:
            raise JiraIntegrationError(f"Failed to execute query: {e}")

    async def _process_issue(
        self, issue: Any, include_comments: bool
    ) -> Dict[str, Any]:
        """Process individual issue into activity data."""
        try:
            activity = {
                "id": issue.key,
                "type": "issue",
                "title": InputValidator.sanitize_text(issue.fields.summary),
                "description": InputValidator.sanitize_text(
                    issue.fields.description or ""
                ),
                "status": issue.fields.status.name,
                "assignee": (
                    issue.fields.assignee.displayName if issue.fields.assignee else None
                ),
                "priority": (
                    issue.fields.priority.name if issue.fields.priority else None
                ),
                "created": issue.fields.created,
                "updated": issue.fields.updated,
                "url": f"{self.url}/browse/{issue.key}",
                "project": issue.fields.project.key,
                "project_name": issue.fields.project.name,
                "changes": [],
            }

            # Add changelog if requested
            if include_comments and hasattr(issue, "changelog"):
                activity["changes"] = await self._process_changelog(issue.changelog)

            # Add comments if requested
            if include_comments:
                activity["comments"] = await self._process_comments(issue)

            return activity

        except Exception as e:
            self.logger.error(f"Failed to process issue {issue.key}: {e}")
            return {
                "id": issue.key,
                "type": "issue",
                "title": "Error processing issue",
                "error": str(e),
            }

    async def _process_changelog(self, changelog: Any) -> List[Dict[str, Any]]:
        """Process issue changelog."""
        changes = []

        try:
            for history in changelog.histories:
                for item in history.items:
                    change = {
                        "field": item.field,
                        "from": InputValidator.sanitize_text(item.fromString or ""),
                        "to": InputValidator.sanitize_text(item.toString or ""),
                        "author": history.author.displayName,
                        "created": history.created,
                    }
                    changes.append(change)

        except Exception as e:
            self.logger.error(f"Failed to process changelog: {e}")

        return changes

    async def _process_comments(self, issue: Any) -> List[Dict[str, Any]]:
        """Process issue comments."""
        comments = []

        try:
            issue_comments = self._jira_client.comments(issue)

            for comment in issue_comments:
                comment_data = {
                    "id": comment.id,
                    "author": comment.author.displayName,
                    "body": InputValidator.sanitize_text(comment.body),
                    "created": comment.created,
                    "updated": (
                        comment.updated
                        if hasattr(comment, "updated")
                        else comment.created
                    ),
                }
                comments.append(comment_data)

        except Exception as e:
            self.logger.error(f"Failed to process comments: {e}")

        return comments

    async def get_projects(self) -> List[Dict[str, Any]]:
        """Get list of available projects."""
        try:
            # Delegate to Red Hat client if this is a Red Hat instance
            if self.is_redhat and self._redhat_client:
                return await self._redhat_client.get_projects()

            # Standard Jira processing
            await self.rate_limiter.acquire()

            projects = self._jira_client.projects()

            project_list = []
            for project in projects:
                project_data = {
                    "key": project.key,
                    "name": InputValidator.sanitize_text(project.name),
                    "description": InputValidator.sanitize_text(
                        project.description or ""
                    ),
                    "url": f"{self.url}/projects/{project.key}",
                }
                project_list.append(project_data)

            self.security_logger.log_api_request(
                service="jira",
                endpoint="projects",
                method="GET",
                status_code=200,
                results_count=len(project_list),
            )

            return project_list

        except Exception as e:
            self.logger.error(f"Failed to get projects: {e}")
            raise JiraIntegrationError(f"Failed to get projects: {e}")

    async def get_users(
        self, project_key: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get list of users (optionally filtered by project)."""
        try:
            await self.rate_limiter.acquire()

            if project_key:
                # Get users for specific project
                users = self._jira_client.search_assignable_users_for_projects(
                    "", projectKeys=project_key, maxResults=100
                )
            else:
                # Get all users (limited search)
                users = self._jira_client.search_users("", maxResults=100)

            user_list = []
            for user in users:
                user_data = {
                    "key": user.key,
                    "name": user.name,
                    "displayName": InputValidator.sanitize_text(user.displayName),
                    "email": (
                        user.emailAddress if hasattr(user, "emailAddress") else None
                    ),
                    "active": user.active,
                }
                user_list.append(user_data)

            self.security_logger.log_api_request(
                service="jira",
                endpoint="users",
                method="GET",
                status_code=200,
                results_count=len(user_list),
            )

            return user_list

        except Exception as e:
            self.logger.error(f"Failed to get users: {e}")
            raise JiraIntegrationError(f"Failed to get users: {e}")

    async def validate_jql(self, jql: str) -> bool:
        """Validate JQL query."""
        try:
            await self.rate_limiter.acquire()

            # Validate syntax first
            InputValidator.validate_jira_query(jql)

            # Test query with limit
            self._jira_client.search_issues(jql, maxResults=1)

            return True

        except Exception as e:
            self.logger.error(f"JQL validation failed: {e}")
            return False

    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information."""
        # Delegate to Red Hat client if this is a Red Hat instance
        if self.is_redhat and self._redhat_client:
            return self._redhat_client.get_connection_info()

        # Standard Jira connection info
        return {
            "url": self.url,
            "username": self.username,
            "connected": self._jira_client is not None,
            "server_info": (
                self._jira_client.server_info() if self._jira_client else None
            ),
            "client_type": "jira",
        }

    async def close(self) -> None:
        """Close client connections."""
        try:
            # Close Red Hat client if it's being used
            if self.is_redhat and self._redhat_client:
                await self._redhat_client.close()
                self._redhat_client = None

            if self._jira_client:
                # JIRA client doesn't have explicit close method
                self._jira_client = None

            self.logger.info("Jira client closed")

        except Exception as e:
            self.logger.error(f"Error closing Jira client: {e}")


class JiraActivitySummary:
    """Summarize Jira activity data."""

    @staticmethod
    def summarize_activities(activities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate summary of activities."""
        if not activities:
            return {
                "total_issues": 0,
                "total_comments": 0,
                "total_changes": 0,
                "users": [],
                "projects": [],
                "status_distribution": {},
                "priority_distribution": {},
            }

        users = set()
        projects = set()
        statuses = {}
        priorities = {}
        total_comments = 0
        total_changes = 0

        for activity in activities:
            if activity.get("assignee"):
                users.add(activity["assignee"])

            if activity.get("project"):
                projects.add(activity["project"])

            status = activity.get("status", "Unknown")
            statuses[status] = statuses.get(status, 0) + 1

            priority = activity.get("priority", "Unknown")
            priorities[priority] = priorities.get(priority, 0) + 1

            total_comments += len(activity.get("comments", []))
            total_changes += len(activity.get("changes", []))

        return {
            "total_issues": len(activities),
            "total_comments": total_comments,
            "total_changes": total_changes,
            "users": list(users),
            "projects": list(projects),
            "status_distribution": statuses,
            "priority_distribution": priorities,
        }
