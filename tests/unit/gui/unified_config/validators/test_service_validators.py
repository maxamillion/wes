"""Tests for service-specific validators."""

import json
import os
import tempfile
from unittest.mock import Mock, patch

import pytest

from wes.gui.unified_config.types import JiraType, ServiceType
from wes.gui.unified_config.validators.service_validators import (
    GeminiValidator,
    GoogleValidator,
    JiraValidator,
    get_validator,
)


class TestJiraValidator:
    """Test JiraValidator functionality."""

    @pytest.fixture
    def validator(self):
        """Create a JiraValidator instance."""
        return JiraValidator()

    def test_validate_config_cloud_jira_valid(self, validator):
        """Test validation of valid Cloud Jira configuration."""
        config = {
            "type": "cloud",
            "url": "https://example.atlassian.net",
            "username": "user@example.com",
            "api_token": "test-api-token-12345",
        }

        result = validator.validate_config(config)
        assert result["is_valid"] is True
        assert result["service"] == ServiceType.JIRA

    def test_validate_config_missing_required_fields(self, validator):
        """Test validation with missing required fields."""
        # Missing URL
        config = {
            "type": "cloud",
            "username": "user@example.com",
            "api_token": "test-token",
        }
        result = validator.validate_config(config)
        assert result["is_valid"] is False
        assert "url" in result["message"].lower()

        # Missing API token for cloud
        config = {
            "type": "cloud",
            "url": "https://example.atlassian.net",
            "username": "user@example.com",
        }
        result = validator.validate_config(config)
        assert result["is_valid"] is False
        assert "api_token" in result["message"].lower()

    def test_validate_config_redhat_jira(self, validator):
        """Test validation of Red Hat Jira (no API token required)."""
        config = {
            "type": "redhat",
            "url": "https://issues.redhat.com",
            "username": "user@redhat.com",
            # No api_token needed
        }

        result = validator.validate_config(config)
        assert result["is_valid"] is True

    def test_validate_config_invalid_url(self, validator):
        """Test validation with invalid URL."""
        config = {
            "type": "cloud",
            "url": "not-a-valid-url",
            "username": "user@example.com",
            "api_token": "test-token",
        }

        result = validator.validate_config(config)
        assert result["is_valid"] is False
        assert "url" in result["message"].lower()

    def test_validate_config_cloud_requires_email(self, validator):
        """Test that cloud Jira requires email as username."""
        config = {
            "type": "cloud",
            "url": "https://example.atlassian.net",
            "username": "justausername",  # Not an email
            "api_token": "test-token",
        }

        result = validator.validate_config(config)
        assert result["is_valid"] is False
        assert "email" in result["message"].lower()

    def test_validate_field_url(self, validator):
        """Test URL field validation."""
        # Valid URLs
        valid, msg = validator.validate_field("url", "https://example.atlassian.net")
        assert valid is True

        valid, msg = validator.validate_field("url", "http://jira.company.com")
        assert valid is True

        # Invalid URLs
        valid, msg = validator.validate_field("url", "")
        assert valid is False

        valid, msg = validator.validate_field("url", "not-a-url")
        assert valid is False

    def test_validate_field_api_token(self, validator):
        """Test API token field validation."""
        # Valid token
        valid, msg = validator.validate_field("api_token", "a" * 30)
        assert valid is True

        # Too short
        valid, msg = validator.validate_field("api_token", "short")
        assert valid is False
        assert "too short" in msg.lower()

    @patch("wes.integrations.jira_client.JiraClient")
    def test_validate_connection_success(self, mock_client_class, validator):
        """Test successful connection validation."""
        # Mock successful connection
        mock_client = Mock()
        mock_client.test_connection.return_value = None
        mock_client_class.return_value = mock_client

        config = {
            "type": "cloud",
            "url": "https://example.atlassian.net",
            "username": "user@example.com",
            "api_token": "test-token",
        }

        success, message = validator.validate_connection(config)
        assert success is True
        assert "connected" in message.lower()


class TestGoogleValidator:
    """Test GoogleValidator functionality."""

    @pytest.fixture
    def validator(self):
        """Create a GoogleValidator instance."""
        return GoogleValidator()

    def test_validate_config_oauth_valid(self, validator):
        """Test validation of valid OAuth configuration."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            creds_path = f.name

        try:
            config = {"auth_method": "oauth", "credentials_path": creds_path}

            result = validator.validate_config(config)
            assert result["is_valid"] is True
            assert result["service"] == ServiceType.GOOGLE
        finally:
            os.unlink(creds_path)

    def test_validate_config_oauth_missing_creds(self, validator):
        """Test validation with missing OAuth credentials."""
        config = {
            "auth_method": "oauth"
            # Missing credentials_path
        }

        result = validator.validate_config(config)
        assert result["is_valid"] is False
        assert "authentication required" in result["message"].lower()

    def test_validate_config_oauth_creds_not_found(self, validator):
        """Test validation with non-existent credentials file."""
        config = {"auth_method": "oauth", "credentials_path": "/non/existent/path.json"}

        result = validator.validate_config(config)
        assert result["is_valid"] is False
        assert "not found" in result["message"].lower()

    def test_validate_config_service_account_valid(self, validator):
        """Test validation of valid service account configuration."""
        # Create a temporary service account key file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                {
                    "type": "service_account",
                    "client_email": "test@project.iam.gserviceaccount.com",
                    "private_key": "test-key",
                },
                f,
            )
            key_path = f.name

        try:
            config = {
                "auth_method": "service_account",
                "service_account_key_path": key_path,
            }

            result = validator.validate_config(config)
            assert result["is_valid"] is True
        finally:
            os.unlink(key_path)

    def test_validate_config_service_account_invalid_format(self, validator):
        """Test validation with invalid service account key format."""
        # Create a key file without required fields
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"type": "service_account"}, f)  # Missing client_email
            key_path = f.name

        try:
            config = {
                "auth_method": "service_account",
                "service_account_key_path": key_path,
            }

            result = validator.validate_config(config)
            assert result["is_valid"] is False
            assert "invalid" in result["message"].lower()
        finally:
            os.unlink(key_path)


class TestGeminiValidator:
    """Test GeminiValidator functionality."""

    @pytest.fixture
    def validator(self):
        """Create a GeminiValidator instance."""
        return GeminiValidator()

    def test_validate_config_valid(self, validator):
        """Test validation of valid Gemini configuration."""
        config = {
            "api_key": "AIzaSyTest1234567890123456789012345",
            "model": "gemini-1.5-pro",
            "temperature": 0.7,
        }

        result = validator.validate_config(config)
        assert result["is_valid"] is True
        assert result["service"] == ServiceType.GEMINI

    def test_validate_config_missing_api_key(self, validator):
        """Test validation with missing API key."""
        config = {"model": "gemini-1.5-pro", "temperature": 0.7}

        result = validator.validate_config(config)
        assert result["is_valid"] is False
        assert "api_key" in result["message"].lower()

    def test_validate_config_invalid_api_key_format(self, validator):
        """Test validation with invalid API key format."""
        # Wrong prefix
        config = {"api_key": "SKtest1234567890", "model": "gemini-1.5-pro"}

        result = validator.validate_config(config)
        assert result["is_valid"] is False
        assert "format" in result["message"].lower()

        # Too short
        config = {"api_key": "AIzaShort", "model": "gemini-1.5-pro"}

        result = validator.validate_config(config)
        assert result["is_valid"] is False
        assert "too short" in result["message"].lower()

    def test_validate_config_invalid_model(self, validator):
        """Test validation with invalid model."""
        config = {
            "api_key": "AIzaSyTest1234567890123456789012345",
            "model": "invalid-model-name",
        }

        result = validator.validate_config(config)
        assert result["is_valid"] is False
        assert "model" in result["message"].lower()

    def test_validate_config_invalid_temperature(self, validator):
        """Test validation with invalid temperature."""
        config = {
            "api_key": "AIzaSyTest1234567890123456789012345",
            "model": "gemini-1.5-pro",
            "temperature": 1.5,  # Out of range
        }

        result = validator.validate_config(config)
        assert result["is_valid"] is False
        assert "temperature" in result["message"].lower()

    def test_validate_api_key_field(self, validator):
        """Test API key field validation."""
        # Valid key
        valid, msg = validator._validate_api_key("AIzaSyTest1234567890123456789012345")
        assert valid is True

        # Invalid characters
        valid, msg = validator._validate_api_key("AIzaSy@Test#123")
        assert valid is False
        assert "invalid characters" in msg.lower()


class TestValidatorRegistry:
    """Test validator registry functionality."""

    def test_get_validator(self):
        """Test getting validators by service type."""
        jira_validator = get_validator(ServiceType.JIRA)
        assert isinstance(jira_validator, JiraValidator)

        google_validator = get_validator(ServiceType.GOOGLE)
        assert isinstance(google_validator, GoogleValidator)

        gemini_validator = get_validator(ServiceType.GEMINI)
        assert isinstance(gemini_validator, GeminiValidator)
