
import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock, patch

from src.wes.integrations.jira_client import JiraClient


class TestJiraClientHierarchy(unittest.TestCase):
    @patch("src.wes.integrations.jira_client.JiraClient._initialize_client")
    def test_get_issue_hierarchy(self, mock_initialize_client):
        # Create a mock for the JiraClient
        jira_client = JiraClient(
            url="https://jira.example.com",
            username="user",
            api_token="long_enough_api_token_for_validation",
        )

        # Mock the _jira_client and its issue method
        jira_client._jira_client = MagicMock()

        # Define the mock issues
        mock_issue_story = MagicMock()
        mock_issue_story.key = "STORY-123"
        mock_issue_story.fields.summary = "Story Summary"
        mock_issue_story.fields.issuetype.name = "Story"
        mock_issue_story.fields.parent = MagicMock()
        mock_issue_story.fields.parent.key = "EPIC-456"

        mock_issue_epic = MagicMock()
        mock_issue_epic.key = "EPIC-456"
        mock_issue_epic.fields.summary = "Epic Summary"
        mock_issue_epic.fields.issuetype.name = "Epic"
        mock_issue_epic.fields.parent = None

        # Set up the mock to return the appropriate issue
        def get_issue(issue_id, fields):
            if issue_id == "STORY-123":
                return mock_issue_story
            elif issue_id == "EPIC-456":
                return mock_issue_epic
            return None

        jira_client._jira_client.issue = MagicMock(side_effect=get_issue)

        # Mock the rate limiter
        jira_client.rate_limiter = AsyncMock()
        jira_client.rate_limiter.acquire = AsyncMock()

        # Run the test
        hierarchy = asyncio.run(jira_client._get_issue_hierarchy("STORY-123"))

        # Assert the results
        self.assertIn("issue", hierarchy)
        self.assertEqual(hierarchy["issue"]["key"], "STORY-123")
        self.assertIn("parent", hierarchy["issue"])
        self.assertEqual(hierarchy["issue"]["parent"]["key"], "EPIC-456")

        # Verify that the hierarchy is cached correctly
        self.assertIn("STORY-123", jira_client.issue_cache)
        self.assertEqual(jira_client.issue_cache["STORY-123"], hierarchy)


if __name__ == "__main__":
    unittest.main()
