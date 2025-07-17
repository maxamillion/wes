"""Jira configuration page for unified config dialog."""

from typing import Any, Dict, List

from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from wes.gui.unified_config.components.service_selector import ServiceSelector
from wes.gui.unified_config.components.validation_indicator import ValidatedLineEdit
from wes.gui.unified_config.config_pages.base_page import ConfigPageBase
from wes.gui.unified_config.types import JiraType, ServiceType, ValidationResult


class JiraConfigPage(ConfigPageBase):
    """Jira configuration page with adaptive UI."""

    service_type = ServiceType.JIRA
    page_title = "Jira Configuration"
    page_icon = "SP_DialogYesButton"
    page_description = "Connect to your Jira instance to fetch activity data"

    def _setup_page_ui(self, parent_layout: QVBoxLayout):
        """Setup Jira-specific UI."""
        # Service type selector
        self.service_selector = ServiceSelector()
        self.service_selector.service_selected.connect(self._on_service_type_changed)
        parent_layout.addWidget(self.service_selector)

        # Basic settings group
        basic_group = QGroupBox("Connection Details")
        basic_layout = QFormLayout(basic_group)

        # URL input with validation
        self.url_input = ValidatedLineEdit("https://company.atlassian.net")
        self.url_input.set_validator(self._validate_url)
        basic_layout.addRow("Jira URL:", self.url_input)

        # Enable auto-detect after URL is created
        self.service_selector.enable_auto_detect(lambda: self.url_input.text())

        # Username input
        self.username_input = ValidatedLineEdit("user@company.com")
        self.username_input.set_validator(self._validate_username)
        basic_layout.addRow("Username:", self.username_input)

        # API Token input (password field)
        self.api_token_input = ValidatedLineEdit("Your API token", password=True)
        self.api_token_input.set_validator(self._validate_api_token)
        basic_layout.addRow("API Token:", self.api_token_input)

        # Help link for API token
        help_layout = QHBoxLayout()
        help_layout.addStretch()
        self.help_link = QLabel(
            '<a href="https://id.atlassian.com/manage-profile/security/api-tokens">How to get an API token?</a>'
        )
        self.help_link.setOpenExternalLinks(True)
        self.help_link.setStyleSheet("color: #0084ff;")
        help_layout.addWidget(self.help_link)
        basic_layout.addRow("", help_layout)

        # Connection test area
        test_layout = QHBoxLayout()
        self.test_button = self._create_test_button()
        test_layout.addWidget(self.test_button)

        self.connection_status_label = QLabel("")
        test_layout.addWidget(self.connection_status_label)
        test_layout.addStretch()

        basic_layout.addRow("", test_layout)

        parent_layout.addWidget(basic_group)

        # Advanced settings (collapsible)
        self.advanced_group = self._create_advanced_group()
        parent_layout.addWidget(self.advanced_group)

        # Connect change tracking
        self._connect_change_tracking()

    def _create_advanced_group(self) -> QGroupBox:
        """Create collapsible advanced settings group."""
        group = self._create_group_box("Advanced Settings", collapsible=True)
        layout = QFormLayout(group)

        # SSL verification
        self.verify_ssl = self._create_checkbox("Verify SSL Certificates", True)
        layout.addRow("Security:", self.verify_ssl)

        # Timeout setting
        timeout_label, self.timeout_input = self._create_spinbox(
            "Connection Timeout (seconds):", 30, 5, 300
        )
        layout.addRow(timeout_label, self.timeout_input)

        # Max results
        max_results_label, self.max_results_input = self._create_spinbox(
            "Max Results per Query:", 100, 10, 1000
        )
        layout.addRow(max_results_label, self.max_results_input)

        # Custom fields (for advanced users)
        self.custom_fields_input = QLineEdit()
        self.custom_fields_input.setPlaceholderText(
            "e.g., customfield_10001,customfield_10002"
        )
        self.custom_fields_input.textChanged.connect(self.mark_dirty)
        layout.addRow("Custom Fields:", self.custom_fields_input)

        return group

    def _on_service_type_changed(self, jira_type: JiraType):
        """Handle Jira type change."""
        # Update UI based on type
        if jira_type == JiraType.REDHAT:
            self.api_token_input.setEnabled(True)
            self.api_token_input.line_edit.setPlaceholderText(
                "Your Red Hat Personal Access Token"
            )
            self.username_input.line_edit.setPlaceholderText("Your Red Hat username")
            # Update help link for Red Hat Jira
            self.help_link.setText(
                '<a href="https://issues.redhat.com">Log in to Red Hat Jira → Profile → Personal Access Tokens</a>'
            )
        else:
            self.api_token_input.setEnabled(True)
            self.api_token_input.line_edit.setPlaceholderText("Your API token")
            self.username_input.line_edit.setPlaceholderText("user@company.com")
            # Update help link for standard Jira
            self.help_link.setText(
                '<a href="https://id.atlassian.com/manage-profile/security/api-tokens">How to get an API token?</a>'
            )

        # Clear connection status
        self.connection_status_label.clear()
        self.mark_dirty()

    def load_config(self, config: Dict[str, Any]) -> None:
        """Load Jira configuration into UI."""
        jira_config = config.get("jira", {})

        # Set service type
        jira_type_str = jira_config.get("type", "cloud")
        jira_type = JiraType(jira_type_str)
        self.service_selector.set_service_type(jira_type)

        # Set basic fields
        self.url_input.setText(jira_config.get("url", ""))
        self.username_input.setText(jira_config.get("username", ""))

        # Try to load API token from config manager (might be stored securely)
        if self.config_manager:
            api_token = self.config_manager.retrieve_credential("jira", "api_token")
            if api_token:
                self.api_token_input.setText(api_token)
            else:
                self.api_token_input.setText(jira_config.get("api_token", ""))

        # Set advanced fields
        self.verify_ssl.setChecked(jira_config.get("verify_ssl", True))
        self.timeout_input.setValue(jira_config.get("timeout", 30))
        self.max_results_input.setValue(jira_config.get("max_results", 100))
        self.custom_fields_input.setText(jira_config.get("custom_fields", ""))

        # Mark as clean after loading
        self.mark_clean()

    def save_config(self) -> Dict[str, Any]:
        """Extract Jira configuration from UI."""
        return {
            "jira": {
                "type": self.service_selector.get_service_type().value,
                "url": self.url_input.text().strip(),
                "username": self.username_input.text().strip(),
                "api_token": self.api_token_input.text().strip(),
                "verify_ssl": self.verify_ssl.isChecked(),
                "timeout": self.timeout_input.value(),
                "max_results": self.max_results_input.value(),
                "custom_fields": self.custom_fields_input.text().strip(),
            }
        }

    def validate(self) -> ValidationResult:
        """Validate Jira configuration."""
        config = self.save_config()["jira"]
        jira_type = JiraType(config["type"])

        # Check required fields
        if not config["url"]:
            return ValidationResult(
                is_valid=False,
                message="Jira URL is required",
                service=self.service_type,
                details={"field": "url"},
            )

        if not config["username"]:
            return ValidationResult(
                is_valid=False,
                message="Username is required",
                service=self.service_type,
                details={"field": "username"},
            )

        # API token required for all Jira instances
        if not config["api_token"]:
            token_name = (
                "Personal Access Token" if jira_type == JiraType.REDHAT else "API Token"
            )
            return ValidationResult(
                is_valid=False,
                message=f"{token_name} is required",
                service=self.service_type,
                details={"field": "api_token"},
            )

        # Validate URL format
        url = config["url"]
        if not url.startswith(("http://", "https://")):
            return ValidationResult(
                is_valid=False,
                message="URL must start with http:// or https://",
                service=self.service_type,
                details={"field": "url", "current_value": url},
            )

        # Cloud Jira requires email as username
        if jira_type == JiraType.CLOUD and "@" not in config["username"]:
            return ValidationResult(
                is_valid=False,
                message="Cloud Jira requires email address as username",
                service=self.service_type,
                details={"field": "username"},
            )

        # All validations passed
        return ValidationResult(
            is_valid=True,
            message="Configuration valid",
            service=self.service_type,
            details={"configured": True},
        )

    def get_basic_fields(self) -> List[QWidget]:
        """Return basic field widgets."""
        return [
            self.service_selector,
            self.url_input,
            self.username_input,
            self.api_token_input,
            self.test_button,
        ]

    def get_advanced_fields(self) -> List[QWidget]:
        """Return advanced field widgets."""
        return [
            self.verify_ssl,
            self.timeout_input,
            self.max_results_input,
            self.custom_fields_input,
        ]

    def _connect_change_tracking(self):
        """Connect change tracking to form fields."""
        # Already connected in widget creation
        # Additional connections for complex widgets
        self.url_input.text_changed.connect(lambda: self.mark_dirty())
        self.username_input.text_changed.connect(lambda: self.mark_dirty())
        self.api_token_input.text_changed.connect(lambda: self.mark_dirty())

    # Validation functions
    def _validate_url(self, url: str) -> tuple[bool, str]:
        """Validate Jira URL."""
        if not url:
            return False, "URL is required"

        if not url.startswith(("http://", "https://")):
            return False, "Must start with http:// or https://"

        # Check for common patterns
        if "atlassian.net" in url:
            return True, "Atlassian Cloud URL detected"
        elif "jira" in url.lower():
            return True, "Valid Jira URL"
        else:
            return True, "URL format valid"

    def _validate_username(self, username: str) -> tuple[bool, str]:
        """Validate username."""
        if not username:
            return False, "Username is required"

        # Get current Jira type
        jira_type = self.service_selector.get_service_type()

        # Cloud Jira requires email address format
        if jira_type == JiraType.CLOUD:
            if "@" in username and "." in username:
                return True, "Valid email address"
            else:
                return False, "Cloud Jira requires email address"

        # Red Hat Jira and Server allow various username formats
        elif jira_type in [JiraType.REDHAT, JiraType.SERVER]:
            # Allow alphanumeric, hyphens, underscores, dots, and @ symbols
            # This supports formats like: rhn-support-admiller, john.doe, user@domain
            import re

            if re.match(r"^[a-zA-Z0-9._@-]+$", username):
                if len(username) >= 3:
                    return True, "Valid username"
                else:
                    return False, "Username too short (minimum 3 characters)"
            else:
                return False, "Username contains invalid characters"

        return True, "Username valid"

    def _validate_api_token(self, token: str) -> tuple[bool, str]:
        """Validate API token."""
        jira_type = self.service_selector.get_service_type()

        if not token:
            if jira_type == JiraType.REDHAT:
                return False, "Personal Access Token is required"
            else:
                return False, "API token is required"

        if len(token) < 20:
            token_name = (
                "Personal Access Token" if jira_type == JiraType.REDHAT else "API token"
            )
            return False, f"{token_name} appears too short"

        if jira_type == JiraType.REDHAT:
            return True, "Personal Access Token format valid"
        else:
            return True, "API token format valid"
