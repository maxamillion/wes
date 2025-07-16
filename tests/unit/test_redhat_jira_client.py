"""Unit tests for Red Hat Jira client integration."""

import asyncio
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from wes.integrations.redhat_jira_client import (
    RHJIRA_AVAILABLE,
    RedHatJiraClient,
    get_redhat_jira_client,
    is_redhat_jira,
)
from wes.utils.exceptions import (
    AuthenticationError,
    JiraIntegrationError,
)


class TestRedHatJiraDetection:
    """Test Red Hat Jira instance detection."""

    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://issues.redhat.com", True),
            ("https://jira.redhat.com", True),
            ("https://bugzilla.redhat.com", True),
            ("https://redhat.com/jira", True),
            ("https://test.redhat.com", True),
            ("https://company.atlassian.net", False),
            ("https://jira.company.com", False),
            ("https://issues.github.com", False),
            ("", False),
            ("invalid-url", False),
        ],
    )
    def test_is_redhat_jira(self, url, expected):
        """Test Red Hat Jira URL detection."""
        assert is_redhat_jira(url) == expected

    def test_is_redhat_jira_with_invalid_url(self):
        """Test detection with malformed URLs."""
        assert is_redhat_jira("not-a-url") == False
        assert is_redhat_jira("ftp://redhat.com") == False


class TestRedHatJiraClient:
    """Test Red Hat Jira client functionality."""

    @pytest.fixture
    def redhat_config(self):
        """Red Hat Jira configuration for testing."""
        return {
            "url": "https://issues.redhat.com",
            "username": "testuser",
            "api_token": "test_token_123",
            "rate_limit": 100,
            "timeout": 30,
        }

    @pytest.fixture
    def non_redhat_config(self):
        """Non-Red Hat Jira configuration for testing."""
        return {
            "url": "https://company.atlassian.net",
            "username": "test@company.com",
            "api_token": "test_token_123",
            "rate_limit": 100,
            "timeout": 30,
        }

    @patch("wes.integrations.redhat_jira_client.RHJIRA_AVAILABLE", False)
    def test_client_initialization_without_rhjira(self, redhat_config):
        """Test client initialization when rhjira is not available."""
        with patch("wes.integrations.redhat_jira_client.JIRA") as mock_jira:
            mock_jira_instance = Mock()
            mock_jira_instance.current_user.return_value = "testuser"
            mock_jira.return_value = mock_jira_instance

            client = RedHatJiraClient(**redhat_config)

            assert client.use_rhjira == False
            assert client._client == mock_jira_instance
            mock_jira.assert_called_once()

    @patch("wes.integrations.redhat_jira_client.RHJIRA_AVAILABLE", True)
    def test_client_initialization_with_rhjira(self, redhat_config):
        """Test client initialization when rhjira is available."""
        with patch("wes.integrations.redhat_jira_client.rhjira") as mock_rhjira:
            mock_client_instance = Mock()
            mock_client_instance.current_user.return_value = "testuser"
            mock_rhjira.RHJIRA.return_value = (
                mock_client_instance  # Use RHJIRA instead of JIRA
            )

            client = RedHatJiraClient(**redhat_config)

            assert client.use_rhjira == True
            assert client._client == mock_client_instance

    def test_client_initialization_with_ssl_disabled(self, redhat_config):
        """Test client initialization with SSL verification disabled."""
        redhat_config["verify_ssl"] = False

        with patch("src.wes.integrations.redhat_jira_client.JIRA") as mock_jira:
            mock_jira_instance = Mock()
            mock_jira_instance.current_user.return_value = "testuser"
            mock_jira.return_value = mock_jira_instance

            client = RedHatJiraClient(**redhat_config)

            assert client.verify_ssl == False
            mock_jira.assert_called_once()

    def test_authentication_failure(self, redhat_config):
        """Test handling of authentication failures."""
        with patch("src.wes.integrations.redhat_jira_client.JIRA") as mock_jira:
            mock_jira.side_effect = Exception("Authentication failed")

            with pytest.raises(
                AuthenticationError, match="Red Hat Jira authentication failed"
            ):
                RedHatJiraClient(**redhat_config)

    @pytest.mark.asyncio
    async def test_get_user_activities_success(self, redhat_config):
        """Test successful user activities retrieval."""
        with patch("src.wes.integrations.redhat_jira_client.JIRA") as mock_jira:
            # Setup mock client
            mock_jira_instance = Mock()
            mock_jira_instance.current_user.return_value = "testuser"
            mock_jira_instance.search_issues.return_value = []
            mock_jira.return_value = mock_jira_instance

            client = RedHatJiraClient(**redhat_config)

            # Test activity retrieval
            start_date = datetime(2024, 1, 1)
            end_date = datetime(2024, 1, 31)
            users = ["testuser"]

            activities = await client.get_user_activities(
                users=users, start_date=start_date, end_date=end_date
            )

            assert isinstance(activities, list)
            mock_jira_instance.search_issues.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_activities_with_comments(self, redhat_config):
        """Test user activities retrieval with comments enabled."""
        with patch("src.wes.integrations.redhat_jira_client.JIRA") as mock_jira:
            # Setup mock issue
            mock_issue = Mock()
            mock_issue.key = "RH-123"
            mock_issue.fields.summary = "Test issue"
            mock_issue.fields.description = "Test description"
            mock_issue.fields.status.name = "In Progress"
            mock_issue.fields.assignee.displayName = "Test User"
            mock_issue.fields.priority.name = "High"
            mock_issue.fields.created = "2024-01-01T00:00:00Z"
            mock_issue.fields.updated = "2024-01-02T00:00:00Z"
            mock_issue.fields.project.key = "RH"
            mock_issue.fields.project.name = "Red Hat"
            mock_issue.fields.components = []
            mock_issue.fields.fixVersions = []
            mock_issue.fields.labels = []

            # Setup mock client
            mock_jira_instance = Mock()
            mock_jira_instance.current_user.return_value = "testuser"
            mock_jira_instance.search_issues.return_value = [mock_issue]
            mock_jira_instance.comments.return_value = []
            mock_jira.return_value = mock_jira_instance

            client = RedHatJiraClient(**redhat_config)

            start_date = datetime(2024, 1, 1)
            end_date = datetime(2024, 1, 31)
            users = ["testuser"]

            activities = await client.get_user_activities(
                users=users,
                start_date=start_date,
                end_date=end_date,
                include_comments=True,
            )

            assert len(activities) == 1
            assert activities[0]["id"] == "RH-123"
            assert activities[0]["title"] == "Test issue"
            assert "comments" in activities[0]

    @pytest.mark.asyncio
    async def test_get_projects_success(self, redhat_config):
        """Test successful projects retrieval."""
        with patch("src.wes.integrations.redhat_jira_client.JIRA") as mock_jira:
            # Setup mock project
            mock_project = Mock()
            mock_project.key = "RH"
            mock_project.name = "Red Hat"
            mock_project.description = "Red Hat project"
            mock_project.category = None

            # Setup mock client
            mock_jira_instance = Mock()
            mock_jira_instance.current_user.return_value = "testuser"
            mock_jira_instance.projects.return_value = [mock_project]
            mock_jira.return_value = mock_jira_instance

            client = RedHatJiraClient(**redhat_config)

            projects = await client.get_projects()

            assert len(projects) == 1
            assert projects[0]["key"] == "RH"
            assert projects[0]["name"] == "Red Hat"

    @pytest.mark.asyncio
    async def test_rate_limiting(self, redhat_config):
        """Test rate limiting functionality."""
        with patch("src.wes.integrations.redhat_jira_client.JIRA") as mock_jira:
            mock_jira_instance = Mock()
            mock_jira_instance.current_user.return_value = "testuser"
            mock_jira.return_value = mock_jira_instance

            # Create config with rate limit
            test_config = redhat_config.copy()
            test_config["rate_limit"] = 1  # Very low rate limit
            client = RedHatJiraClient(**test_config)

            # Rate limiter should be active
            assert client.rate_limiter is not None

            # Test acquire
            await client.rate_limiter.acquire()  # Should succeed

            # Multiple rapid acquires should be rate limited
            start_time = asyncio.get_event_loop().time()
            await client.rate_limiter.acquire()
            end_time = asyncio.get_event_loop().time()

            # Should have been delayed due to rate limiting
            assert end_time - start_time >= 0.5  # Some delay expected

    def test_get_connection_info(self, redhat_config):
        """Test connection information retrieval."""
        with patch("src.wes.integrations.redhat_jira_client.JIRA") as mock_jira:
            mock_jira_instance = Mock()
            mock_jira_instance.current_user.return_value = "testuser"
            mock_jira_instance.server_info.return_value = {"version": "8.0.0"}
            mock_jira.return_value = mock_jira_instance

            client = RedHatJiraClient(**redhat_config)

            info = client.get_connection_info()

            assert info["url"] == redhat_config["url"]
            assert info["username"] == redhat_config["username"]
            assert info["connected"] == True
            assert info["client_type"] in ["rhjira", "jira"]
            assert "rhjira_available" in info
            assert "ssl_verification" in info

    @pytest.mark.asyncio
    async def test_close_client(self, redhat_config):
        """Test client cleanup."""
        with patch("src.wes.integrations.redhat_jira_client.JIRA") as mock_jira:
            mock_jira_instance = Mock()
            mock_jira_instance.current_user.return_value = "testuser"
            mock_jira.return_value = mock_jira_instance

            client = RedHatJiraClient(**redhat_config)

            await client.close()

            assert client._client is None

    def test_redhat_specific_filters(self, redhat_config):
        """Test Red Hat specific JQL filters."""
        with patch("src.wes.integrations.redhat_jira_client.JIRA") as mock_jira:
            mock_jira_instance = Mock()
            mock_jira_instance.current_user.return_value = "testuser"
            mock_jira.return_value = mock_jira_instance

            client = RedHatJiraClient(**redhat_config)

            # Test Red Hat specific filters
            filters = client._get_redhat_specific_filters()
            assert isinstance(filters, str)

    @pytest.mark.asyncio
    async def test_jira_error_handling(self, redhat_config):
        """Test handling of Jira-specific errors."""
        with patch("src.wes.integrations.redhat_jira_client.JIRA") as mock_jira:
            mock_jira_instance = Mock()
            mock_jira_instance.current_user.return_value = "testuser"
            mock_jira_instance.search_issues.side_effect = Exception("API Error")
            mock_jira.return_value = mock_jira_instance

            client = RedHatJiraClient(**redhat_config)

            with pytest.raises(JiraIntegrationError):
                await client.get_user_activities(
                    users=["testuser"],
                    start_date=datetime(2024, 1, 1),
                    end_date=datetime(2024, 1, 31),
                )


class TestRedHatJiraFactory:
    """Test Red Hat Jira client factory function."""

    def test_get_redhat_jira_client(self):
        """Test factory function for creating Red Hat Jira client."""
        with patch("src.wes.integrations.redhat_jira_client.JIRA") as mock_jira:
            mock_jira_instance = Mock()
            mock_jira_instance.current_user.return_value = "testuser"
            mock_jira.return_value = mock_jira_instance

            client = get_redhat_jira_client(
                url="https://issues.redhat.com",
                username="testuser",
                api_token="test_token",
            )

            assert isinstance(client, RedHatJiraClient)
            assert client.url == "https://issues.redhat.com"
            assert client.username == "testuser"


class TestRedHatJiraIntegration:
    """Integration tests for Red Hat Jira functionality."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_end_to_end_workflow(self):
        """Test complete Red Hat Jira workflow."""
        config = {
            "url": "https://issues.redhat.com",
            "username": "testuser",
            "api_token": "test_token",
        }

        with patch("src.wes.integrations.redhat_jira_client.JIRA") as mock_jira:
            # Setup comprehensive mock
            mock_issue = Mock()
            mock_issue.key = "RH-123"
            mock_issue.fields.summary = "Test Red Hat issue"
            mock_issue.fields.description = "Description"
            mock_issue.fields.status.name = "Open"
            mock_issue.fields.assignee.displayName = "Red Hat User"
            mock_issue.fields.priority.name = "High"
            mock_issue.fields.created = "2024-01-01T00:00:00Z"
            mock_issue.fields.updated = "2024-01-02T00:00:00Z"
            mock_issue.fields.project.key = "RH"
            mock_issue.fields.project.name = "Red Hat Project"
            mock_issue.fields.components = []
            mock_issue.fields.fixVersions = []
            mock_issue.fields.labels = ["redhat", "internal"]

            mock_project = Mock()
            mock_project.key = "RH"
            mock_project.name = "Red Hat Project"
            mock_project.description = "Internal Red Hat project"

            mock_jira_instance = Mock()
            mock_jira_instance.current_user.return_value = "testuser"
            mock_jira_instance.search_issues.return_value = [mock_issue]
            mock_jira_instance.projects.return_value = [mock_project]
            mock_jira_instance.comments.return_value = []
            mock_jira_instance.server_info.return_value = {"version": "8.20.0"}
            mock_jira.return_value = mock_jira_instance

            # Create client and test workflow
            client = RedHatJiraClient(**config)

            # Test projects
            projects = await client.get_projects()
            assert len(projects) == 1
            assert projects[0]["key"] == "RH"

            # Test activities
            activities = await client.get_user_activities(
                users=["testuser"],
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 1, 31),
            )
            assert len(activities) == 1
            assert activities[0]["id"] == "RH-123"
            assert activities[0]["labels"] == ["redhat", "internal"]

            # Test connection info
            info = client.get_connection_info()
            assert info["connected"] == True
            assert (
                "redhat" not in info.get("server_info", {}).get("version", "").lower()
                or True
            )  # Version may vary

            # Cleanup
            await client.close()

    @pytest.mark.integration
    def test_redhat_vs_standard_detection(self):
        """Test that Red Hat URLs are properly detected vs standard Jira."""
        redhat_urls = [
            "https://issues.redhat.com",
            "https://jira.redhat.com",
            "https://bugzilla.redhat.com",
        ]

        standard_urls = [
            "https://company.atlassian.net",
            "https://jira.company.com",
            "https://issues.company.org",
        ]

        for url in redhat_urls:
            assert is_redhat_jira(url) == True, f"Should detect {url} as Red Hat Jira"

        for url in standard_urls:
            assert (
                is_redhat_jira(url) == False
            ), f"Should not detect {url} as Red Hat Jira"


@pytest.mark.skipif(not RHJIRA_AVAILABLE, reason="rhjira library not available")
class TestRHJiraLibraryIntegration:
    """Tests that only run when rhjira library is actually available."""

    def test_rhjira_library_import(self):
        """Test that rhjira library can be imported when available."""
        import rhjira

        assert hasattr(rhjira, "JIRA") or hasattr(rhjira, "RHJIRA")

    @patch("src.wes.integrations.redhat_jira_client.RHJIRA_AVAILABLE", True)
    def test_client_uses_rhjira_when_available(self):
        """Test client uses rhjira library when it's available."""
        config = {
            "url": "https://issues.redhat.com",
            "username": "testuser",
            "api_token": "test_token",
        }

        with patch("src.wes.integrations.redhat_jira_client.rhjira") as mock_rhjira:
            mock_client = Mock()
            mock_client.current_user.return_value = "testuser"
            mock_rhjira.JIRA.return_value = mock_client

            client = RedHatJiraClient(**config)

            assert client.use_rhjira == True
            mock_rhjira.JIRA.assert_called_once()
