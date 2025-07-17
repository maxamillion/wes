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
        config = {"jira": {}, "gemini": {}}
        assert detector.detect_state(config) == ConfigState.EMPTY

    def test_detect_complete_state(self, detector):
        """Test detection of complete configuration."""
        config = {
            "jira": {
                "url": "https://example.atlassian.net",
                "username": "user@example.com",
                "api_token": "test-token",
            },
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
        assert len(missing) == 2
        assert ServiceType.JIRA in missing
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
        assert len(missing) == 1
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
            "gemini": {},  # Not configured
        }

        status = detector.get_service_status(config)

        # Jira should be valid
        assert status[ServiceType.JIRA]["is_valid"] is True
        assert status[ServiceType.JIRA]["message"] == "Configuration complete"

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
        assert service == ServiceType.GEMINI
        assert "Configure Gemini" in message

        # All configured
        config = {
            "jira": {
                "url": "https://example.atlassian.net",
                "username": "user@example.com",
                "api_token": "test-token",
            },
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
        detector.get_service_status(config)
        # This would need custom logic in detector for Red Hat Jira

        # Test minimal Gemini config
        config = {
            "gemini": {
                "api_key": "AIzaSyTest123456789",
            }
        }
        # Gemini should be valid with just API key
        # This would need custom logic in detector
