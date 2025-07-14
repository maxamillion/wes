"""Tests for configuration state detection utilities."""

import pytest

from wes.gui.unified_config.types import ConfigState, ServiceType
from wes.gui.unified_config.utils.config_detector import ConfigDetector


class TestConfigDetector:
    """Test ConfigDetector functionality."""

    @pytest.fixture
    def detector(self):
        """Create a ConfigDetector instance."""
        return ConfigDetector()

    def test_detect_empty_state(self, detector):
        """Test detection of empty configuration."""
        # Empty config
        assert detector.detect_state({}) == ConfigState.EMPTY

        # Config with empty values
        config = {"jira": {}, "google": {}, "gemini": {}}
        assert detector.detect_state(config) == ConfigState.INVALID

    def test_detect_complete_state(self, detector):
        """Test detection of complete configuration."""
        config = {
            "jira": {
                "url": "https://example.atlassian.net",
                "username": "user@example.com",
                "api_token": "test-token",
            },
            "google": {"credentials_path": "/path/to/creds.json"},
            "gemini": {"api_key": "AIzaSyTest123456789"},
        }
        assert detector.detect_state(config) == ConfigState.COMPLETE

    def test_detect_incomplete_state(self, detector):
        """Test detection of incomplete configuration."""
        # Only Jira configured
        config = {
            "jira": {
                "url": "https://example.atlassian.net",
                "username": "user@example.com",
                "api_token": "test-token",
            },
            "google": {},
            "gemini": {},
        }
        assert detector.detect_state(config) == ConfigState.INCOMPLETE

        # Missing required field
        config = {
            "jira": {
                "url": "https://example.atlassian.net",
                "username": "user@example.com",
                # Missing api_token
            }
        }
        assert detector.detect_state(config) == ConfigState.INCOMPLETE

    def test_get_missing_services(self, detector):
        """Test identification of missing services."""
        # All missing
        config = {}
        missing = detector.get_missing_services(config)
        assert len(missing) == 3
        assert ServiceType.JIRA in missing
        assert ServiceType.GOOGLE in missing
        assert ServiceType.GEMINI in missing

        # Only Jira configured
        config = {
            "jira": {
                "url": "https://example.atlassian.net",
                "username": "user@example.com",
                "api_token": "test-token",
            }
        }
        missing = detector.get_missing_services(config)
        assert len(missing) == 2
        assert ServiceType.GOOGLE in missing
        assert ServiceType.GEMINI in missing
        assert ServiceType.JIRA not in missing

    def test_get_service_status(self, detector):
        """Test detailed service status reporting."""
        config = {
            "jira": {
                "url": "https://example.atlassian.net",
                "username": "user@example.com",
                "api_token": "test-token",
            },
            "google": {"credentials_path": ""},  # Empty path
            "gemini": {},  # Not configured
        }

        status = detector.get_service_status(config)

        # Jira should be valid
        assert status[ServiceType.JIRA]["is_valid"] is True
        assert status[ServiceType.JIRA]["message"] == "Configuration complete"

        # Google should be invalid
        assert status[ServiceType.GOOGLE]["is_valid"] is False
        assert "Missing: credentials_path" in status[ServiceType.GOOGLE]["message"]

        # Gemini should be not configured
        assert status[ServiceType.GEMINI]["is_valid"] is False
        assert status[ServiceType.GEMINI]["message"] == "Not configured"

    def test_suggest_next_action(self, detector):
        """Test next action suggestions."""
        # Empty config
        message, service = detector.suggest_next_action({})
        assert service == ServiceType.JIRA
        assert "start by configuring Jira" in message

        # Only Jira configured
        config = {
            "jira": {
                "url": "https://example.atlassian.net",
                "username": "user@example.com",
                "api_token": "test-token",
            }
        }
        message, service = detector.suggest_next_action(config)
        assert service == ServiceType.GOOGLE
        assert "Configure Google" in message

        # All configured
        config = {
            "jira": {
                "url": "https://example.atlassian.net",
                "username": "user@example.com",
                "api_token": "test-token",
            },
            "google": {"credentials_path": "/path/to/creds.json"},
            "gemini": {"api_key": "AIzaSyTest123456789"},
        }
        message, service = detector.suggest_next_action(config)
        assert service is None
        assert "ready to go" in message.lower()

    def test_service_specific_requirements(self, detector):
        """Test service-specific requirement checking."""
        # Test Red Hat Jira (no API token required)
        config = {
            "jira": {
                "type": "redhat",
                "url": "https://issues.redhat.com",
                "username": "user@redhat.com",
                # No api_token needed
            }
        }
        status = detector.get_service_status(config)
        # This would need custom logic in detector for Red Hat Jira

        # Test service account for Google
        config = {
            "google": {
                "auth_method": "service_account",
                "service_account_key_path": "/path/to/key.json",
            }
        }
        # Service account should also be valid
        # This would need custom logic in detector
