"""Pytest configuration and fixtures for the Executive Summary Tool tests."""

import os
import tempfile
import asyncio
from pathlib import Path
from typing import Dict, Any
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication

from src.executive_summary_tool.core.config_manager import ConfigManager
from src.executive_summary_tool.core.security_manager import SecurityManager


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def qapp():
    """QApplication fixture for GUI tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    # Don't quit the app here as it may be used by other tests


@pytest.fixture
def temp_config_dir():
    """Create a temporary directory for configuration files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def mock_config_manager(temp_config_dir):
    """Create a mock configuration manager with temporary directory."""
    config_manager = ConfigManager(config_dir=temp_config_dir)
    return config_manager


@pytest.fixture
def sample_jira_config():
    """Sample Jira configuration data."""
    return {
        "url": "https://test-company.atlassian.net",
        "username": "test.user@company.com",
        "api_token": "test_api_token_12345",
        "default_project": "TEST",
        "default_users": ["test.user1", "test.user2"],
        "default_query": "project = TEST AND updated >= -1w",
        "rate_limit": 100,
        "timeout": 30
    }


@pytest.fixture
def sample_ai_config():
    """Sample AI configuration data."""
    return {
        "gemini_api_key": "AIza_test_key_12345",
        "model_name": "gemini-pro",
        "temperature": 0.7,
        "max_tokens": 2048,
        "rate_limit": 60,
        "timeout": 60,
        "custom_prompt": "Generate an executive summary based on: {activity_data}"
    }


@pytest.fixture
def sample_google_config():
    """Sample Google configuration data."""
    return {
        "service_account_path": "/path/to/service-account.json",
        "oauth_client_id": "test_client_id",
        "oauth_client_secret": "test_client_secret",
        "oauth_refresh_token": "test_refresh_token",
        "docs_folder_id": "test_folder_id_12345",
        "rate_limit": 100,
        "timeout": 30
    }


@pytest.fixture
def sample_jira_activity_data():
    """Sample Jira activity data for testing."""
    return [
        {
            "id": "TEST-123",
            "type": "issue",
            "title": "Fix authentication bug",
            "description": "Users unable to login with SSO",
            "status": "In Progress",
            "assignee": "john.doe",
            "priority": "High",
            "created": "2024-01-15T10:00:00Z",
            "updated": "2024-01-16T14:30:00Z",
            "url": "https://test-company.atlassian.net/browse/TEST-123",
            "project": "TEST",
            "project_name": "Test Project",
            "changes": [
                {
                    "field": "status",
                    "from": "To Do",
                    "to": "In Progress",
                    "author": "john.doe",
                    "created": "2024-01-16T09:00:00Z"
                }
            ],
            "comments": [
                {
                    "id": "comment_1",
                    "author": "jane.smith",
                    "body": "This looks related to the recent SSO changes",
                    "created": "2024-01-16T11:00:00Z",
                    "updated": "2024-01-16T11:00:00Z"
                }
            ]
        },
        {
            "id": "TEST-124",
            "type": "issue",
            "title": "Update user documentation",
            "description": "Documentation needs to reflect new features",
            "status": "Done",
            "assignee": "jane.smith",
            "priority": "Medium",
            "created": "2024-01-14T08:00:00Z",
            "updated": "2024-01-16T16:00:00Z",
            "url": "https://test-company.atlassian.net/browse/TEST-124",
            "project": "TEST",
            "project_name": "Test Project",
            "changes": [
                {
                    "field": "status",
                    "from": "In Progress",
                    "to": "Done",
                    "author": "jane.smith",
                    "created": "2024-01-16T16:00:00Z"
                }
            ],
            "comments": []
        }
    ]


@pytest.fixture
def sample_ai_summary():
    """Sample AI-generated summary for testing."""
    return {
        "content": """# Executive Summary

## Key Highlights
- 2 issues processed during the reporting period
- 1 high-priority authentication issue currently in progress
- 1 documentation update completed

## Team Performance
The team has been actively working on critical infrastructure issues and documentation updates.

## Progress Updates
- Authentication bug (TEST-123) is being actively investigated
- User documentation (TEST-124) has been successfully updated

## Risks and Blockers
- Authentication issue may impact user access if not resolved quickly

## Recommendations
- Prioritize resolution of authentication bug
- Continue maintaining up-to-date documentation""",
        "model": "gemini-pro",
        "usage": {
            "prompt_token_count": 150,
            "candidates_token_count": 200,
            "total_token_count": 350
        },
        "generated_at": 1705507200.0,
        "safety_ratings": []
    }


@pytest.fixture
def mock_jira_client():
    """Mock Jira client for testing."""
    mock_client = Mock()
    mock_client.get_user_activities.return_value = []
    mock_client.get_projects.return_value = []
    mock_client.get_users.return_value = []
    mock_client.validate_jql.return_value = True
    mock_client.get_connection_info.return_value = {"connected": True}
    mock_client.close.return_value = None
    return mock_client


@pytest.fixture
def mock_gemini_client():
    """Mock Gemini client for testing."""
    mock_client = Mock()
    mock_client.generate_summary.return_value = {
        "content": "Test executive summary",
        "model": "gemini-pro"
    }
    mock_client.validate_api_key.return_value = True
    mock_client.close.return_value = None
    return mock_client


@pytest.fixture
def mock_google_docs_client():
    """Mock Google Docs client for testing."""
    mock_client = Mock()
    mock_client.create_document.return_value = "test_document_id"
    mock_client.create_formatted_summary.return_value = "test_document_id"
    mock_client.get_document_url.return_value = "https://docs.google.com/document/d/test_document_id/edit"
    mock_client.share_document.return_value = None
    mock_client.close.return_value = None
    return mock_client


@pytest.fixture
def mock_security_manager():
    """Mock security manager for testing."""
    mock_manager = Mock(spec=SecurityManager)
    mock_manager.encrypt_credential.return_value = "encrypted_credential"
    mock_manager.decrypt_credential.return_value = "decrypted_credential"
    mock_manager.store_credential.return_value = None
    mock_manager.retrieve_credential.return_value = "test_credential"
    mock_manager.delete_credential.return_value = None
    mock_manager.validate_integrity.return_value = True
    return mock_manager


@pytest.fixture
def environment_variables():
    """Set up test environment variables."""
    old_values = {}
    test_vars = {
        "EXECUTIVE_SUMMARY_TEST_MODE": "true",
        "EXECUTIVE_SUMMARY_LOG_LEVEL": "DEBUG"
    }
    
    # Set test environment variables
    for key, value in test_vars.items():
        old_values[key] = os.environ.get(key)
        os.environ[key] = value
    
    yield test_vars
    
    # Restore original environment variables
    for key, old_value in old_values.items():
        if old_value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = old_value


# Pytest markers for test categorization
pytest_markers = [
    "unit: Unit tests",
    "integration: Integration tests", 
    "security: Security tests",
    "e2e: End-to-end tests",
    "gui: GUI tests",
    "slow: Slow-running tests",
    "api: API integration tests"
]


def pytest_configure(config):
    """Configure pytest with custom markers."""
    for marker in pytest_markers:
        config.addinivalue_line("markers", marker)


@pytest.fixture(autouse=True)
def setup_test_logging():
    """Setup logging for tests."""
    import logging
    
    # Set up test logging
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Suppress some noisy loggers during tests
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)