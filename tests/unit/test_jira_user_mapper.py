"""Unit tests for Jira user mapper functionality."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from wes.integrations.jira_user_mapper import JiraUserMapper, UserMappingCache


class TestUserMappingCache:
    """Test user mapping cache functionality."""

    def test_cache_operations(self):
        """Test basic cache get/set operations."""
        cache = UserMappingCache()

        # Test empty cache
        assert cache.get("test@example.com") is None

        # Test set and get
        cache.set("test@example.com", "testuser")
        assert cache.get("test@example.com") == "testuser"


class TestJiraUserMapper:
    """Test Jira user mapper functionality."""

    @pytest.fixture
    def mock_jira_client(self):
        """Create a mock Jira client."""
        client = Mock()
        client._make_request = AsyncMock()
        client.is_redhat = True
        return client

    @pytest.fixture
    def mapper(self, mock_jira_client):
        """Create a JiraUserMapper instance."""
        return JiraUserMapper(mock_jira_client)

    @pytest.mark.asyncio
    async def test_search_redhat_user_with_correct_endpoint(
        self, mapper, mock_jira_client
    ):
        """Test that Red Hat user search uses the correct endpoint."""
        # Mock response for user/search endpoint
        mock_jira_client._make_request.return_value = [
            {
                "name": "testuser",
                "key": "testuser",
                "emailAddress": "testuser@redhat.com",
                "displayName": "Test User",
            }
        ]

        # Test searching for a Red Hat email
        result = await mapper._search_redhat_user("testuser@redhat.com")

        # Verify the correct endpoint was called
        mock_jira_client._make_request.assert_called_with(
            "GET", "/rest/api/2/user/search?username=testuser@redhat.com"
        )

        assert result == "testuser"

    @pytest.mark.asyncio
    async def test_search_redhat_user_fallback_to_prefix(
        self, mapper, mock_jira_client
    ):
        """Test fallback to username prefix when full email search fails."""
        # First call (full email) returns empty
        # Second call (username prefix) returns user
        mock_jira_client._make_request.side_effect = [
            [],  # Empty response for full email
            [  # Response for username prefix
                {
                    "name": "testuser",
                    "key": "testuser",
                    "emailAddress": "testuser@redhat.com",
                    "displayName": "Test User",
                }
            ],
        ]

        result = await mapper._search_redhat_user("testuser@redhat.com")

        # Verify both endpoints were called
        assert mock_jira_client._make_request.call_count == 2

        # First call with full email
        mock_jira_client._make_request.assert_any_call(
            "GET", "/rest/api/2/user/search?username=testuser@redhat.com"
        )

        # Second call with username prefix
        mock_jira_client._make_request.assert_any_call(
            "GET", "/rest/api/2/user/search?username=testuser"
        )

        assert result == "testuser"

    @pytest.mark.asyncio
    async def test_search_redhat_user_non_redhat_email(self, mapper, mock_jira_client):
        """Test that non-Red Hat emails return None immediately."""
        result = await mapper._search_redhat_user("user@example.com")

        # Should not make any API calls
        mock_jira_client._make_request.assert_not_called()

        assert result is None

    @pytest.mark.asyncio
    async def test_search_redhat_user_handles_non_json_response(
        self, mapper, mock_jira_client
    ):
        """Test handling of non-JSON responses."""
        # Simulate an exception when API returns non-JSON
        mock_jira_client._make_request.side_effect = Exception("Invalid JSON response")

        result = await mapper._search_redhat_user("testuser@redhat.com")

        # Should handle the error gracefully
        assert result is None

    @pytest.mark.asyncio
    async def test_search_redhat_user_multiple_results(self, mapper, mock_jira_client):
        """Test handling multiple search results."""
        mock_jira_client._make_request.return_value = [
            {
                "name": "testuser1",
                "key": "testuser1",
                "emailAddress": "otheruser@redhat.com",
                "displayName": "Other User",
            },
            {
                "name": "testuser",
                "key": "testuser",
                "emailAddress": "testuser@redhat.com",
                "displayName": "Test User",
            },
        ]

        result = await mapper._search_redhat_user("testuser@redhat.com")

        # Should return the user with matching email
        assert result == "testuser"

    @pytest.mark.asyncio
    async def test_map_emails_to_usernames_with_cache(self, mapper, mock_jira_client):
        """Test email to username mapping with caching."""
        # First, populate cache
        mapper.cache.set("cached@redhat.com", "cacheduser")

        # Mock response for non-cached email
        mock_jira_client._make_request.return_value = [
            {
                "name": "newuser",
                "key": "newuser",
                "emailAddress": "new@redhat.com",
                "displayName": "New User",
            }
        ]

        # Map multiple emails
        result = await mapper.map_emails_to_usernames(
            ["cached@redhat.com", "new@redhat.com"]
        )

        # Cached email should not trigger API call
        assert result["cached@redhat.com"] == "cacheduser"
        assert result["new@redhat.com"] == "newuser"

        # Only one API call for the non-cached email
        assert mock_jira_client._make_request.call_count > 0
