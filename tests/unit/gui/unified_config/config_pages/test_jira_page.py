"""Tests for Jira configuration page."""

from unittest.mock import Mock, patch

import pytest
from PySide6.QtWidgets import QApplication, QLabel

from wes.core.config_manager import ConfigManager
from wes.gui.unified_config.config_pages.jira_page import JiraConfigPage
from wes.gui.unified_config.types import JiraType, ServiceType


class TestJiraConfigPage:
    """Test JiraConfigPage functionality."""

    @pytest.fixture
    def app(self, qtbot):
        """Create QApplication for testing."""
        return QApplication.instance() or QApplication([])

    @pytest.fixture
    def config_manager(self):
        """Create a mock ConfigManager."""
        manager = Mock(spec=ConfigManager)
        manager.config = {}
        manager.retrieve_credential.return_value = None
        return manager

    @pytest.fixture
    def page(self, qtbot, config_manager):
        """Create a JiraConfigPage instance."""
        page = JiraConfigPage(config_manager)
        qtbot.addWidget(page)
        return page

    def test_initial_state(self, page):
        """Test initial state of the page."""
        assert page.service_type == ServiceType.JIRA
        assert page.page_title == "Jira Configuration"
        assert page.url_input.text() == ""
        assert page.username_input.text() == ""
        assert page.api_token_input.text() == ""
        assert page.verify_ssl.isChecked()
        assert page.timeout_input.value() == 30
        assert page.max_results_input.value() == 100

    def test_load_config(self, page):
        """Test loading configuration into UI."""
        config = {
            "jira": {
                "type": "server",
                "url": "https://jira.example.com",
                "username": "testuser",
                "api_token": "test-token-123",
                "verify_ssl": False,
                "timeout": 60,
                "max_results": 200,
                "custom_fields": "field1,field2",
            }
        }

        page.load_config(config)

        assert page.service_selector.get_service_type() == JiraType.SERVER
        assert page.url_input.text() == "https://jira.example.com"
        assert page.username_input.text() == "testuser"
        assert page.api_token_input.text() == "test-token-123"
        assert not page.verify_ssl.isChecked()
        assert page.timeout_input.value() == 60
        assert page.max_results_input.value() == 200
        assert page.custom_fields_input.text() == "field1,field2"

    def test_save_config(self, page):
        """Test saving configuration from UI."""
        # Set values in UI
        page.service_selector.set_service_type(JiraType.CLOUD)
        page.url_input.setText("https://test.atlassian.net")
        page.username_input.setText("user@test.com")
        page.api_token_input.setText("secret-token")
        page.verify_ssl.setChecked(True)
        page.timeout_input.setValue(45)
        page.max_results_input.setValue(150)
        page.custom_fields_input.setText("customfield_10001")

        # Save config
        config = page.save_config()

        assert config == {
            "jira": {
                "type": "cloud",
                "url": "https://test.atlassian.net",
                "username": "user@test.com",
                "api_token": "secret-token",
                "verify_ssl": True,
                "timeout": 45,
                "max_results": 150,
                "custom_fields": "customfield_10001",
            }
        }

    def test_validate_valid_config(self, page):
        """Test validation with valid configuration."""
        page.url_input.setText("https://test.atlassian.net")
        page.username_input.setText("user@test.com")
        page.api_token_input.setText("valid-token-123")

        result = page.validate()

        assert result["is_valid"] is True
        assert result["service"] == ServiceType.JIRA

    def test_validate_missing_url(self, page):
        """Test validation with missing URL."""
        page.username_input.setText("user@test.com")
        page.api_token_input.setText("valid-token")

        result = page.validate()

        assert result["is_valid"] is False
        assert "url" in result["message"].lower()

    def test_validate_invalid_url(self, page):
        """Test validation with invalid URL."""
        page.url_input.setText("not-a-valid-url")
        page.username_input.setText("user@test.com")
        page.api_token_input.setText("valid-token")

        result = page.validate()

        assert result["is_valid"] is False
        assert "url" in result["message"].lower()

    def test_validate_cloud_requires_email(self, page):
        """Test that Cloud Jira requires email as username."""
        page.service_selector.set_service_type(JiraType.CLOUD)
        page.url_input.setText("https://test.atlassian.net")
        page.username_input.setText("notanemail")
        page.api_token_input.setText("valid-token")

        result = page.validate()

        assert result["is_valid"] is False
        assert "email" in result["message"].lower()

    def test_validate_redhat_token_required(self, page):
        """Test that Red Hat Jira requires Personal Access Token."""
        page.service_selector.set_service_type(JiraType.REDHAT)
        page.url_input.setText("https://issues.redhat.com")
        page.username_input.setText("redhatuser")
        # No API token should fail validation

        result = page.validate()

        assert result["is_valid"] is False
        assert "Personal Access Token" in result["message"]

        # Now add the token and it should pass
        page.api_token_input.setText("test-personal-access-token-123456789")
        result = page.validate()
        assert result["is_valid"] is True

    def test_service_type_change_updates_ui(self, page):
        """Test UI updates when service type changes."""
        # Select Red Hat
        page.service_selector.set_service_type(JiraType.REDHAT)
        page._on_service_type_changed(JiraType.REDHAT)

        assert page.api_token_input.isEnabled()
        assert (
            "Personal Access Token" in page.api_token_input.line_edit.placeholderText()
        )

        # Select Cloud
        page.service_selector.set_service_type(JiraType.CLOUD)
        page._on_service_type_changed(JiraType.CLOUD)

        assert page.api_token_input.isEnabled()
        assert "Your API token" in page.api_token_input.line_edit.placeholderText()

    def test_real_time_validation(self, page, qtbot):
        """Test real-time field validation."""
        # URL validation
        page.url_input.setText("invalid-url")
        qtbot.wait(600)  # Wait for validation
        assert (
            page.url_input.indicator.current_state
            == page.url_input.indicator.State.INVALID
        )

        page.url_input.setText("https://test.atlassian.net")
        qtbot.wait(600)
        assert (
            page.url_input.indicator.current_state
            == page.url_input.indicator.State.VALID
        )

        # Username validation for Cloud
        page.service_selector.set_service_type(JiraType.CLOUD)
        page.username_input.setText("notanemail")
        qtbot.wait(600)
        assert (
            page.username_input.indicator.current_state
            == page.username_input.indicator.State.INVALID
        )

        page.username_input.setText("user@test.com")
        qtbot.wait(600)
        assert (
            page.username_input.indicator.current_state
            == page.username_input.indicator.State.VALID
        )

    def test_dirty_state_tracking(self, page, qtbot):
        """Test that changes mark the page as dirty."""
        assert not page.is_dirty()

        # Change URL
        page.url_input.setText("https://test.com")
        assert page.is_dirty()

        # Mark clean
        page.mark_clean()
        assert not page.is_dirty()

        # Change username
        page.username_input.setText("user")
        assert page.is_dirty()

    @patch("wes.gui.unified_config.components.connection_tester.ConnectionTestDialog")
    def test_test_connection(self, mock_dialog_class, page):
        """Test connection testing."""
        # Set valid config
        page.url_input.setText("https://test.atlassian.net")
        page.username_input.setText("user@test.com")
        page.api_token_input.setText("valid-token")

        # Mock dialog
        mock_dialog = Mock()
        mock_dialog_class.return_value = mock_dialog

        # Test connection
        page.test_connection()

        # Dialog should be created and shown
        mock_dialog_class.assert_called_once()
        mock_dialog.exec.assert_called_once()

    @patch("wes.gui.unified_config.utils.dialogs.DialogManager.show_warning")
    def test_test_connection_invalid_config(self, mock_warning, page):
        """Test connection testing with invalid config shows warning."""
        # Leave URL empty
        page.username_input.setText("user@test.com")
        page.api_token_input.setText("token")

        # Test connection
        page.test_connection()

        # Should show warning
        mock_warning.assert_called_once()
        assert "Invalid Configuration" in mock_warning.call_args[0][1]

    def test_advanced_settings_collapsible(self, page):
        """Test advanced settings are collapsible."""
        # Initially collapsed
        assert not page.advanced_group.isChecked()

        # Expand
        page.advanced_group.setChecked(True)
        assert page.advanced_group.isChecked()

        # Title should update
        assert "▼" in page.advanced_group.title()

    def test_help_link(self, page):
        """Test help link is present and configured."""
        # Find help link
        help_link = None
        for child in page.findChildren(QLabel):
            if "How to get an API token" in child.text():
                help_link = child
                break

        assert help_link is not None
        assert help_link.openExternalLinks()
        assert "atlassian.com" in help_link.text()
