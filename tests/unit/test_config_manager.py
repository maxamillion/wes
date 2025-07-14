"""Unit tests for the configuration manager."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import json
import tempfile
import shutil

from src.wes.core.config_manager import (
    ConfigManager,
    JiraConfig,
    GoogleConfig,
    AIConfig,
    AppConfig,
)
from src.wes.utils.exceptions import ConfigurationError


@pytest.fixture
def temp_config_dir():
    """Create a temporary directory for config files."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_security_manager():
    """Create a mock security manager."""
    security_manager = Mock()
    security_manager.encrypt_credential.side_effect = lambda x: f"encrypted_{x}"
    security_manager.decrypt_credential.side_effect = lambda x: x.replace(
        "encrypted_", ""
    )
    security_manager.store_credential.return_value = None
    security_manager.retrieve_credential.side_effect = (
        lambda service, key: f"test_{service}_{key}"
    )
    security_manager.delete_credential.return_value = None
    return security_manager


@pytest.fixture
def config_manager(temp_config_dir, mock_security_manager):
    """Create a config manager with mocked dependencies."""
    with patch("src.wes.core.config_manager.SecurityManager") as MockSecurityManager:
        MockSecurityManager.return_value = mock_security_manager

        # Override config directory
        manager = ConfigManager()
        manager.config_dir = temp_config_dir
        manager.config_file = temp_config_dir / "config.json"
        manager.security_manager = mock_security_manager

        return manager


class TestConfigManager:
    """Test suite for ConfigManager."""

    def test_initialization(self, config_manager, temp_config_dir):
        """Test config manager initialization."""
        assert config_manager.config_dir == temp_config_dir
        assert config_manager.config_file == temp_config_dir / "config.json"
        assert config_manager.security_manager is not None
        assert isinstance(config_manager.jira_config, JiraConfig)
        assert isinstance(config_manager.google_config, GoogleConfig)
        assert isinstance(config_manager.ai_config, AIConfig)
        assert isinstance(config_manager.app_config, AppConfig)

    def test_save_configuration(self, config_manager):
        """Test saving configuration to file."""
        # Modify configs
        config_manager.jira_config.url = "https://test.atlassian.net"
        config_manager.jira_config.username = "test@example.com"

        # Save
        config_manager.save_configuration()

        # Verify file exists
        assert config_manager.config_file.exists()

        # Load and verify content
        with open(config_manager.config_file, "r") as f:
            saved_config = json.load(f)

        assert saved_config["jira"]["url"] == "https://test.atlassian.net"
        assert saved_config["jira"]["username"] == "test@example.com"

    def test_load_configuration(self, config_manager):
        """Test loading configuration from file."""
        # Create config file
        config_data = {
            "jira": {
                "url": "https://loaded.atlassian.net",
                "username": "loaded@example.com",
                "rate_limit": 50,
                "timeout": 60,
                "default_users": ["user1", "user2"],
            },
            "google": {
                "oauth_client_id": "loaded_client_id",
                "service_account_path": "/path/to/service.json",
                "rate_limit": 200,
                "timeout": 45,
            },
            "ai": {
                "model_name": "gemini-2.5-pro",
                "temperature": 0.8,
                "max_tokens": 4096,
                "custom_prompt": "Custom prompt text",
                "rate_limit": 30,
                "timeout": 120,
            },
            "app": {
                "auto_save": False,
                "check_updates": False,
                "log_level": "DEBUG",
                "theme": "dark",
            },
        }

        with open(config_manager.config_file, "w") as f:
            json.dump(config_data, f)

        # Load configuration
        config_manager.load_configuration()

        # Verify loaded values
        assert config_manager.jira_config.url == "https://loaded.atlassian.net"
        assert config_manager.jira_config.username == "loaded@example.com"
        assert config_manager.jira_config.rate_limit == 50
        assert config_manager.jira_config.timeout == 60
        assert config_manager.jira_config.default_users == ["user1", "user2"]

        assert config_manager.google_config.oauth_client_id == "loaded_client_id"
        assert (
            config_manager.google_config.service_account_path == "/path/to/service.json"
        )

        assert config_manager.ai_config.model_name == "gemini-2.5-pro"
        assert config_manager.ai_config.temperature == 0.8
        assert config_manager.ai_config.custom_prompt == "Custom prompt text"

        assert config_manager.app_config.auto_save is False
        assert config_manager.app_config.theme == "dark"

    def test_update_jira_config(self, config_manager):
        """Test updating Jira configuration."""
        config_manager.update_jira_config(
            url="https://new.atlassian.net",
            username="new@example.com",
            rate_limit=150,
            default_users=["user3", "user4"],
        )

        assert config_manager.jira_config.url == "https://new.atlassian.net"
        assert config_manager.jira_config.username == "new@example.com"
        assert config_manager.jira_config.rate_limit == 150
        assert config_manager.jira_config.default_users == ["user3", "user4"]

        # Verify auto-save if enabled
        config_manager.app_config.auto_save = True
        config_manager.update_jira_config(timeout=90)
        assert config_manager.config_file.exists()

    def test_update_google_config(self, config_manager):
        """Test updating Google configuration."""
        config_manager.update_google_config(
            oauth_client_id="new_client_id",
            service_account_path="/new/path/service.json",
            rate_limit=300,
        )

        assert config_manager.google_config.oauth_client_id == "new_client_id"
        assert (
            config_manager.google_config.service_account_path
            == "/new/path/service.json"
        )
        assert config_manager.google_config.rate_limit == 300

    def test_update_ai_config(self, config_manager):
        """Test updating AI configuration."""
        config_manager.update_ai_config(
            model_name="gemini-2.5-pro",
            temperature=0.9,
            max_tokens=8192,
            custom_prompt="New custom prompt",
        )

        assert config_manager.ai_config.model_name == "gemini-2.5-pro"
        assert config_manager.ai_config.temperature == 0.9
        assert config_manager.ai_config.max_tokens == 8192
        assert config_manager.ai_config.custom_prompt == "New custom prompt"

    def test_update_app_config(self, config_manager):
        """Test updating app configuration."""
        config_manager.update_app_config(
            auto_save=False, check_updates=False, log_level="ERROR", theme="light"
        )

        assert config_manager.app_config.auto_save is False
        assert config_manager.app_config.check_updates is False
        assert config_manager.app_config.log_level == "ERROR"
        assert config_manager.app_config.theme == "light"

    def test_store_credential(self, config_manager, mock_security_manager):
        """Test storing credentials."""
        config_manager.store_credential("jira", "api_token", "secret_token")

        mock_security_manager.store_credential.assert_called_once_with(
            "jira", "api_token", "secret_token"
        )

    def test_retrieve_credential(self, config_manager, mock_security_manager):
        """Test retrieving credentials."""
        result = config_manager.retrieve_credential("jira", "api_token")

        assert result == "test_jira_api_token"
        mock_security_manager.retrieve_credential.assert_called_once_with(
            "jira", "api_token"
        )

    def test_delete_credential(self, config_manager, mock_security_manager):
        """Test deleting credentials."""
        config_manager.delete_credential("jira", "api_token")

        mock_security_manager.delete_credential.assert_called_once_with(
            "jira", "api_token"
        )

    def test_validate_configuration_success(self, config_manager):
        """Test successful configuration validation."""
        # Set up valid configuration
        config_manager.jira_config.url = "https://test.atlassian.net"
        config_manager.jira_config.username = "test@example.com"
        config_manager.google_config.oauth_client_id = "test_client_id"
        config_manager.ai_config.model_name = "gemini-2.5-flash"

        # Mock credential retrieval
        config_manager.security_manager.retrieve_credential.side_effect = (
            lambda s, k: "test_value"
        )

        # Validate
        assert config_manager.validate_configuration() is True

    def test_validate_configuration_missing_jira_url(self, config_manager):
        """Test validation with missing Jira URL."""
        config_manager.jira_config.url = ""

        with pytest.raises(ConfigurationError, match="Jira URL is required"):
            config_manager.validate_configuration()

    def test_validate_configuration_invalid_model(self, config_manager):
        """Test validation with invalid AI model."""
        config_manager.ai_config.model_name = "invalid-model"

        with pytest.raises(ConfigurationError, match="Invalid AI model"):
            config_manager.validate_configuration()

    def test_is_configured(self, config_manager):
        """Test checking if configuration exists."""
        # Initially not configured
        assert config_manager.is_configured() is False

        # Create config file
        config_manager.save_configuration()

        # Now configured
        assert config_manager.is_configured() is True

    def test_get_config_summary(self, config_manager):
        """Test getting configuration summary."""
        # Set up configuration
        config_manager.jira_config.url = "https://test.atlassian.net"
        config_manager.jira_config.username = "test@example.com"
        config_manager.google_config.oauth_client_id = "test_client_id"
        config_manager.ai_config.model_name = "gemini-2.5-flash"

        # Get summary
        summary = config_manager.get_config_summary()

        # Verify summary content
        assert summary["jira"]["configured"] is True
        assert summary["jira"]["url"] == "https://test.atlassian.net"
        assert summary["jira"]["username"] == "test@example.com"

        assert summary["google"]["configured"] is True
        assert summary["google"]["oauth_configured"] is True

        assert summary["ai"]["configured"] is True
        assert summary["ai"]["model"] == "gemini-2.5-flash"

    def test_reset_configuration(self, config_manager):
        """Test resetting configuration."""
        # Set some values
        config_manager.jira_config.url = "https://test.atlassian.net"
        config_manager.save_configuration()

        # Reset
        config_manager.reset_configuration()

        # Verify reset
        assert config_manager.jira_config.url == ""
        assert not config_manager.config_file.exists()

    def test_export_configuration(self, config_manager, temp_config_dir):
        """Test exporting configuration."""
        # Set up configuration
        config_manager.jira_config.url = "https://test.atlassian.net"
        config_manager.jira_config.username = "test@example.com"

        # Export
        export_path = temp_config_dir / "export.json"
        config_manager.export_configuration(str(export_path))

        # Verify export
        assert export_path.exists()
        with open(export_path, "r") as f:
            exported = json.load(f)

        assert exported["jira"]["url"] == "https://test.atlassian.net"
        # Credentials should not be exported
        assert "api_token" not in exported.get("credentials", {})

    def test_import_configuration(self, config_manager, temp_config_dir):
        """Test importing configuration."""
        # Create import file
        import_data = {
            "jira": {
                "url": "https://imported.atlassian.net",
                "username": "imported@example.com",
            },
            "ai": {"model_name": "gemini-2.5-pro", "temperature": 0.5},
        }

        import_path = temp_config_dir / "import.json"
        with open(import_path, "w") as f:
            json.dump(import_data, f)

        # Import
        config_manager.import_configuration(str(import_path))

        # Verify import
        assert config_manager.jira_config.url == "https://imported.atlassian.net"
        assert config_manager.jira_config.username == "imported@example.com"
        assert config_manager.ai_config.model_name == "gemini-2.5-pro"
        assert config_manager.ai_config.temperature == 0.5

    def test_file_permissions(self, config_manager):
        """Test that config files have appropriate permissions."""
        config_manager.save_configuration()

        # Check file permissions (should be readable/writable by owner only)
        stat_info = config_manager.config_file.stat()
        file_mode = stat_info.st_mode & 0o777

        # On Unix systems, should be 0o600 (owner read/write only)
        # This test might need adjustment for Windows
        if not hasattr(stat_info, "st_file_attributes"):  # Unix-like system
            assert file_mode == 0o600
