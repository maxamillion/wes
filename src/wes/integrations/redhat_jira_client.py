"""Red Hat Jira integration client with enhanced authentication and Red Hat-specific features."""

import asyncio
import time
import warnings
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Try to import rhjira if available, fallback to standard jira
# To install rhjira: pip install git+https://gitlab.com/prarit/rhjira-python.git
# Note: rhjira is an optional dependency for Red Hat Jira optimization
try:
    import rhjira

    RHJIRA_AVAILABLE = True
except ImportError:
    RHJIRA_AVAILABLE = False
    # Fallback to standard jira library
    from jira import JIRA
    import jira as rhjira

from ..utils.exceptions import AuthenticationError, JiraIntegrationError, RateLimitError
from ..utils.logging_config import get_logger, get_security_logger
from ..utils.validators import InputValidator


class RedHatJiraClient:
    """Enhanced Jira client specifically designed for Red Hat Jira instances."""

    def __init__(
        self,
        url: str,
        username: str,
        api_token: str,
        rate_limit: int = 100,
        timeout: int = 30,
        verify_ssl: bool = True,
        use_rhjira: bool = True,
        oauth_config: Optional[Dict[str, str]] = None,
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
        self.verify_ssl = verify_ssl
        self.use_rhjira = use_rhjira and RHJIRA_AVAILABLE
        self.oauth_config = oauth_config

        # Initialize rate limiter
        self.rate_limiter = self._create_rate_limiter(rate_limit)

        # Initialize client
        self._client: Optional[Any] = None
        self._initialize_client()

    def _create_rate_limiter(self, max_requests: int):
        """Create rate limiter for Red Hat Jira."""

        class RateLimiter:
            def __init__(self, max_requests: int, time_window: int = 60):
                self.max_requests = max_requests
                self.time_window = time_window
                self.requests = []
                self._lock = asyncio.Lock()

            async def acquire(self) -> None:
                async with self._lock:
                    now = time.time()
                    self.requests = [
                        req_time
                        for req_time in self.requests
                        if now - req_time < self.time_window
                    ]

                    if len(self.requests) >= self.max_requests:
                        wait_time = self.time_window - (now - self.requests[0])
                        if wait_time > 0:
                            await asyncio.sleep(wait_time)
                            return await self.acquire()

                    self.requests.append(now)

        return RateLimiter(max_requests=max_requests, time_window=60)

    def _initialize_client(self) -> None:
        """Initialize Red Hat Jira client with appropriate library."""
        try:
            if self.use_rhjira and RHJIRA_AVAILABLE:
                self._initialize_rhjira_client()
            else:
                self._initialize_standard_jira_client()

            # Test connection
            self._test_connection()

            self.security_logger.log_authentication_attempt(
                service="redhat_jira",
                username=self.username,
                success=True,
                client_type="rhjira" if self.use_rhjira else "jira",
            )

            self.logger.info(
                f"Red Hat Jira client initialized successfully using {
                    'rhjira' if self.use_rhjira else 'jira'}"
            )

        except Exception as e:
            self.security_logger.log_authentication_attempt(
                service="redhat_jira",
                username=self.username,
                success=False,
                error=str(e),
            )
            raise AuthenticationError(f"Red Hat Jira authentication failed: {e}")

    def _initialize_rhjira_client(self) -> None:
        """Initialize using rhjira library for Red Hat specific features."""
        try:
            # Configure rhjira with Red Hat-specific settings
            options = {
                "verify": self.verify_ssl,
                "check_update": False,
                "agile_rest_path": "agile",
                "timeout": self.timeout,
            }

            # Add Red Hat specific configurations
            if hasattr(rhjira, "RHJIRA"):
                # Use Red Hat specific client if available with Bearer token
                self._client = rhjira.RHJIRA(
                    server=self.url,
                    token_auth=self.api_token,  # Use Bearer token instead of basic auth
                    options=options,
                )
            else:
                # Fallback to standard JIRA with Red Hat Bearer token
                self._client = rhjira.JIRA(
                    server=self.url,
                    token_auth=self.api_token,  # Use Bearer token instead of basic auth
                    options=options,
                )

            self.logger.info("Initialized Red Hat Jira client with rhjira library")

        except Exception as e:
            self.logger.error(f"Failed to initialize rhjira client: {e}")
            raise

    def _initialize_standard_jira_client(self) -> None:
        """Initialize using standard jira library with Red Hat optimizations."""
        try:
            # Configure with Red Hat enterprise settings
            options = {
                "verify": self.verify_ssl,
                "check_update": False,
                "agile_rest_path": "agile",
                "timeout": self.timeout,
            }

            # Create session with retry strategy for enterprise environments
            session = requests.Session()

            # Configure retries for enterprise stability
            retry_strategy = Retry(
                total=3,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["HEAD", "GET", "OPTIONS"],
                backoff_factor=1,
            )

            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount("http://", adapter)
            session.mount("https://", adapter)

            # Handle SSL verification for Red Hat environments
            if not self.verify_ssl:
                session.verify = False
                warnings.filterwarnings("ignore", message="Unverified HTTPS request")

            # Red Hat Jira uses Personal Access Tokens with Bearer authentication
            # Set up Bearer token authentication for Red Hat Jira
            session.headers.update(
                {
                    "Authorization": f"Bearer {self.api_token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                }
            )

            self._client = JIRA(
                server=self.url,
                token_auth=self.api_token,  # Use token_auth instead of basic_auth
                options=options,
                get_server_info=False,  # Skip server info for faster init
            )

            # Override session for Red Hat Bearer token authentication
            self._client._session = session

            self.logger.info(
                "Initialized Red Hat Jira client with standard jira library"
            )

        except Exception as e:
            self.logger.error(f"Failed to initialize standard Jira client: {e}")
            raise

    def _test_connection(self) -> None:
        """Test Red Hat Jira connection with enhanced validation."""
        try:
            # Test basic connectivity
            user = self._client.current_user()
            self.logger.info(f"Connected to Red Hat Jira as user: {user}")

            # Test Red Hat specific capabilities if using rhjira
            if self.use_rhjira and hasattr(self._client, "get_redhat_info"):
                try:
                    rh_info = self._client.get_redhat_info()
                    self.logger.info(f"Red Hat Jira info: {rh_info}")
                except Exception as e:
                    self.logger.warning(
                        f"Could not retrieve Red Hat specific info: {e}"
                    )

        except Exception as e:
            # Check if this is an authentication error with helpful guidance
            error_str = str(e).lower()
            if "401" in str(e) or "unauthorized" in error_str:
                raise AuthenticationError(
                    "Red Hat Jira authentication failed. Please ensure you're using a valid "
                    "Personal Access Token (PAT). Go to your Red Hat Jira profile → "
                    "Personal Access Tokens → Create token. Use the token (not your password) "
                    "in the API Token field."
                )
            else:
                raise AuthenticationError(f"Red Hat Jira connection test failed: {e}")

    async def validate_connection(self) -> bool:
        """Validate the connection to Red Hat Jira.

        Returns:
            True if connection is valid

        Raises:
            AuthenticationError: If authentication fails
        """
        # The connection is already validated during initialization
        # Just do a simple test to ensure it's still valid
        try:
            # Try to get current user info as a validation test
            if hasattr(self, "_client") and self._client:
                myself = self._client.myself()
                self.logger.debug(f"Connection validated for user: {myself['name']}")
                return True
            else:
                raise AuthenticationError("Jira client not initialized")
        except Exception as e:
            self.logger.error(f"Connection validation failed: {e}")
            raise AuthenticationError(f"Failed to validate connection: {e}")

    async def get_user_activities(
        self,
        users: List[str],
        start_date: datetime,
        end_date: datetime,
        projects: Optional[List[str]] = None,
        include_comments: bool = True,
        max_results: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Get user activities with Red Hat specific optimizations."""
        try:
            # Validate inputs
            InputValidator.validate_user_list(users)

            if end_date <= start_date:
                raise JiraIntegrationError("End date must be after start date")

            # Rate limiting
            await self.rate_limiter.acquire()

            # Build Red Hat optimized JQL query
            jql = self._build_redhat_activity_query(
                users, start_date, end_date, projects
            )

            # Execute query with Red Hat specific handling
            activities = await self._execute_redhat_query(
                jql, max_results, include_comments
            )

            self.security_logger.log_api_request(
                service="redhat_jira",
                endpoint="search",
                method="GET",
                status_code=200,
                results_count=len(activities),
            )

            return activities

        except Exception as e:
            self.logger.error(f"Failed to get user activities from Red Hat Jira: {e}")
            raise JiraIntegrationError(f"Failed to get user activities: {e}")

    def _build_redhat_activity_query(
        self,
        users: List[str],
        start_date: datetime,
        end_date: datetime,
        projects: Optional[List[str]] = None,
    ) -> str:
        """Build JQL query optimized for Red Hat Jira instances."""
        try:
            # Format dates for JQL
            start_str = start_date.strftime("%Y-%m-%d")
            end_str = end_date.strftime("%Y-%m-%d")

            # Build user clause with Red Hat username handling
            user_clause = f"assignee in ({','.join([f'\"{user}\"' for user in users])})"

            # Build date clause
            date_clause = f"updated >= '{start_str}' AND updated <= '{end_str}'"

            # Build project clause
            project_clause = ""
            if projects:
                project_clause = f" AND project in ({
                    ','.join(
                        [
                            f'\"{proj}\"' for proj in projects])})"

            # Add Red Hat specific filters if available
            redhat_filters = self._get_redhat_specific_filters()

            # Combine clauses
            jql = f"{user_clause} AND {date_clause}{project_clause}{redhat_filters}"

            # Validate JQL
            InputValidator.validate_jira_query(jql)

            self.logger.debug(f"Built Red Hat JQL query: {jql}")
            return jql

        except Exception as e:
            raise JiraIntegrationError(f"Failed to build Red Hat JQL query: {e}")

    def _get_redhat_specific_filters(self) -> str:
        """Get Red Hat specific JQL filters."""
        filters = []

        # Add Red Hat specific issue type filters
        # Exclude internal-only issue types from general queries
        filters.append("issuetype not in ('Red Hat Internal')")

        # Join filters with AND
        return " AND " + " AND ".join(filters) if filters else ""

    async def _execute_redhat_query(
        self, jql: str, max_results: int, include_comments: bool
    ) -> List[Dict[str, Any]]:
        """Execute JQL query with Red Hat specific optimizations."""
        try:
            # Configure fields for Red Hat specific data
            fields = [
                "summary",
                "description",
                "status",
                "assignee",
                "created",
                "updated",
                "priority",
                "project",  # Add project field to prevent AttributeError
                "issuelinks",
                "components",
                "fixVersions",
                "labels",
            ]

            # Add Red Hat specific fields if using rhjira
            if self.use_rhjira and hasattr(self._client, "get_redhat_fields"):
                try:
                    redhat_fields = self._client.get_redhat_fields()
                    fields.extend(redhat_fields)
                except Exception as e:
                    self.logger.warning(f"Could not get Red Hat specific fields: {e}")

            # Search for issues
            issues = self._client.search_issues(
                jql,
                maxResults=max_results,
                expand="changelog" if include_comments else None,
                fields=",".join(fields),
            )

            activities = []

            for issue in issues:
                activity = await self._process_redhat_issue(issue, include_comments)
                activities.append(activity)

            return activities

        except Exception as e:
            if hasattr(e, "status_code") and e.status_code == 429:
                raise RateLimitError(f"Red Hat Jira rate limit exceeded: {e}")
            else:
                raise JiraIntegrationError(f"Red Hat Jira query failed: {e}")

    async def _process_redhat_issue(
        self, issue: Any, include_comments: bool
    ) -> Dict[str, Any]:
        """Process Red Hat Jira issue with enhanced data extraction."""
        try:
            # Log the issue being processed for debugging
            self.logger.debug(f"Processing issue {issue.key}")

            # Build basic activity data with safe field access
            activity = {
                "id": issue.key,
                "type": "issue",
                "title": InputValidator.sanitize_text(
                    getattr(issue.fields, "summary", "No summary")
                ),
                "description": InputValidator.sanitize_text(
                    getattr(issue.fields, "description", "") or ""
                ),
                "status": (
                    getattr(issue.fields.status, "name", "Unknown")
                    if hasattr(issue.fields, "status")
                    else "Unknown"
                ),
                "assignee": None,
                "priority": None,
                "created": getattr(issue.fields, "created", None),
                "updated": getattr(issue.fields, "updated", None),
                "url": f"{self.url}/browse/{issue.key}",
                "project": "Unknown",
                "project_name": "Unknown Project",
                "changes": [],
            }

            # Safely extract assignee
            if hasattr(issue.fields, "assignee") and issue.fields.assignee:
                activity["assignee"] = getattr(
                    issue.fields.assignee, "displayName", None
                )

            # Safely extract priority
            if hasattr(issue.fields, "priority") and issue.fields.priority:
                activity["priority"] = getattr(issue.fields.priority, "name", None)

            # Safely extract project information
            if hasattr(issue.fields, "project") and issue.fields.project:
                activity["project"] = getattr(issue.fields.project, "key", "Unknown")
                activity["project_name"] = getattr(
                    issue.fields.project, "name", "Unknown Project"
                )
            else:
                self.logger.warning(f"Issue {issue.key} has no project field")

            # Add Red Hat specific fields
            if hasattr(issue.fields, "components") and issue.fields.components:
                activity["components"] = [comp.name for comp in issue.fields.components]

            if hasattr(issue.fields, "fixVersions") and issue.fields.fixVersions:
                activity["fix_versions"] = [
                    ver.name for ver in issue.fields.fixVersions
                ]

            if hasattr(issue.fields, "labels") and issue.fields.labels:
                activity["labels"] = issue.fields.labels

            # Process Red Hat specific custom fields if using rhjira
            if self.use_rhjira:
                redhat_data = self._extract_redhat_fields(issue)
                activity.update(redhat_data)

            # Add changelog if requested
            if include_comments and hasattr(issue, "changelog"):
                activity["changes"] = await self._process_changelog(issue.changelog)

            # Add comments if requested
            if include_comments:
                activity["comments"] = await self._process_comments(issue)

            return activity

        except Exception as e:
            self.logger.error(
                f"Failed to process Red Hat issue {issue.key}: {e}", exc_info=True
            )
            # Return a minimal valid activity instead of an error object
            # This prevents error messages from being sent to Gemini as data
            return {
                "id": getattr(issue, "key", "UNKNOWN"),
                "type": "issue",
                "title": f"Issue {getattr(issue, 'key', 'UNKNOWN')} (processing error)",
                "description": "Unable to retrieve issue details due to a processing error.",
                "status": "Error",
                "assignee": None,
                "priority": None,
                "created": None,
                "updated": None,
                "url": f"{self.url}/browse/{getattr(issue, 'key', 'UNKNOWN')}",
                "project": "Unknown",
                "project_name": "Unknown Project",
                "changes": [],
                "_processing_error": str(
                    e
                ),  # Store error for debugging but prefix with _ so it's clear it's metadata
            }

    def _extract_redhat_fields(self, issue: Any) -> Dict[str, Any]:
        """Extract Red Hat specific fields from issue."""
        redhat_data = {}

        # Extract Red Hat specific custom fields
        # This would be customized based on Red Hat's Jira configuration
        try:
            # Example Red Hat specific fields
            if hasattr(issue.fields, "customfield_10000"):  # Example custom field
                redhat_data["redhat_team"] = issue.fields.customfield_10000

            if hasattr(issue.fields, "customfield_10001"):  # Example custom field
                redhat_data["redhat_product"] = issue.fields.customfield_10001

            # Add more Red Hat specific field extractions as needed

        except Exception as e:
            self.logger.warning(f"Could not extract Red Hat fields: {e}")

        return redhat_data

    async def _process_changelog(self, changelog: Any) -> List[Dict[str, Any]]:
        """Process issue changelog with Red Hat specific handling."""
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
            self.logger.error(f"Failed to process Red Hat changelog: {e}")

        return changes

    async def _process_comments(self, issue: Any) -> List[Dict[str, Any]]:
        """Process issue comments with Red Hat specific handling."""
        comments = []

        try:
            issue_comments = self._client.comments(issue)

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
            self.logger.error(f"Failed to process Red Hat comments: {e}")

        return comments

    async def get_projects(self) -> List[Dict[str, Any]]:
        """Get list of projects with Red Hat specific handling."""
        try:
            await self.rate_limiter.acquire()

            projects = self._client.projects()

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

                # Add Red Hat specific project information
                if hasattr(project, "category") and project.category:
                    project_data["category"] = project.category.name

                project_list.append(project_data)

            self.security_logger.log_api_request(
                service="redhat_jira",
                endpoint="projects",
                method="GET",
                status_code=200,
                results_count=len(project_list),
            )

            return project_list

        except Exception as e:
            self.logger.error(f"Failed to get Red Hat projects: {e}")
            raise JiraIntegrationError(f"Failed to get projects: {e}")

    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information for Red Hat Jira."""
        info = {
            "url": self.url,
            "username": self.username,
            "connected": self._client is not None,
            "client_type": "rhjira" if self.use_rhjira else "jira",
            "rhjira_available": RHJIRA_AVAILABLE,
            "ssl_verification": self.verify_ssl,
        }

        if self._client:
            try:
                server_info = self._client.server_info()
                info["server_info"] = server_info

                # Add Red Hat specific server information
                if self.use_rhjira and hasattr(self._client, "get_redhat_server_info"):
                    try:
                        rh_server_info = self._client.get_redhat_server_info()
                        info["redhat_server_info"] = rh_server_info
                    except Exception as e:
                        self.logger.warning(f"Could not get Red Hat server info: {e}")

            except Exception as e:
                self.logger.warning(f"Could not get server info: {e}")

        return info

    async def close(self) -> None:
        """Close Red Hat Jira client connections."""
        try:
            if self._client:
                # Clean up any Red Hat specific resources
                if self.use_rhjira and hasattr(self._client, "close"):
                    self._client.close()

                self._client = None

            self.logger.info("Red Hat Jira client closed")

        except Exception as e:
            self.logger.error(f"Error closing Red Hat Jira client: {e}")


def is_redhat_jira(url: str) -> bool:
    """Check if the URL is a Red Hat Jira instance."""
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url.lower())

        # Only accept HTTP/HTTPS URLs
        if parsed.scheme not in ["http", "https"]:
            return False

        # Check for Red Hat domains
        redhat_domains = [
            "redhat.com",
            "jira.redhat.com",
            "issues.redhat.com",
            "bugzilla.redhat.com",
        ]

        return any(domain in parsed.netloc for domain in redhat_domains)
    except Exception:
        return False


def get_redhat_jira_client(
    url: str, username: str, api_token: str, **kwargs
) -> RedHatJiraClient:
    """Factory function to create Red Hat Jira client."""
    return RedHatJiraClient(url=url, username=username, api_token=api_token, **kwargs)
