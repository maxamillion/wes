"""Google services configuration page for unified config dialog."""

import os
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from wes.core.config_manager import ConfigManager
from wes.gui.unified_config.components.validation_indicator import ValidationIndicator
from wes.gui.unified_config.config_pages.base_page import ConfigPageBase
from wes.gui.unified_config.types import ServiceType, ValidationResult


class GoogleConfigPage(ConfigPageBase):
    """Google services configuration page with OAuth and service account support."""

    service_type = ServiceType.GOOGLE
    page_title = "Google Services Configuration"
    page_icon = "SP_DriveNetIcon"
    page_description = "Configure Google Docs access for document creation"

    # Custom signal for OAuth flow
    oauth_requested = Signal()

    def _setup_page_ui(self, parent_layout: QVBoxLayout):
        """Setup Google-specific UI."""
        # Authentication method selection
        auth_group = QGroupBox("Authentication Method")
        auth_layout = QVBoxLayout(auth_group)

        # Create radio buttons for auth methods
        self.auth_button_group = QButtonGroup()

        self.oauth_radio = QRadioButton("OAuth 2.0 (Recommended)")
        self.oauth_radio.setChecked(True)
        self.auth_button_group.addButton(self.oauth_radio, 0)
        auth_layout.addWidget(self.oauth_radio)

        oauth_desc = QLabel(
            "Authenticate with your Google account. Best for personal use."
        )
        oauth_desc.setStyleSheet("color: #666; margin-left: 20px; margin-bottom: 10px;")
        oauth_desc.setWordWrap(True)
        auth_layout.addWidget(oauth_desc)

        self.service_account_radio = QRadioButton("Service Account")
        self.auth_button_group.addButton(self.service_account_radio, 1)
        auth_layout.addWidget(self.service_account_radio)

        sa_desc = QLabel(
            "Use a service account key file. Best for automation and shared use."
        )
        sa_desc.setStyleSheet("color: #666; margin-left: 20px;")
        sa_desc.setWordWrap(True)
        auth_layout.addWidget(sa_desc)

        parent_layout.addWidget(auth_group)

        # OAuth configuration
        self.oauth_group = QGroupBox("OAuth Configuration")
        oauth_layout = QVBoxLayout(self.oauth_group)

        # OAuth status and button
        oauth_status_layout = QHBoxLayout()

        self.oauth_button = QPushButton("Authenticate with Google")
        self.oauth_button.clicked.connect(self._handle_oauth_click)
        oauth_status_layout.addWidget(self.oauth_button)

        self.oauth_status = QLabel("Not authenticated")
        self.oauth_status.setStyleSheet("color: #666;")
        oauth_status_layout.addWidget(self.oauth_status)

        self.oauth_indicator = ValidationIndicator()
        oauth_status_layout.addWidget(self.oauth_indicator)
        oauth_status_layout.addStretch()

        oauth_layout.addLayout(oauth_status_layout)

        # OAuth email display
        self.oauth_email_label = QLabel("")
        self.oauth_email_label.setStyleSheet("color: green; margin-left: 20px;")
        self.oauth_email_label.hide()
        oauth_layout.addWidget(self.oauth_email_label)

        parent_layout.addWidget(self.oauth_group)

        # Service Account configuration
        self.service_account_group = QGroupBox("Service Account Configuration")
        sa_layout = QFormLayout(self.service_account_group)

        # Key file path
        key_file_layout = QHBoxLayout()
        self.key_file_input = QLineEdit()
        self.key_file_input.setPlaceholderText("/path/to/service-account-key.json")
        self.key_file_input.textChanged.connect(self._validate_key_file)
        key_file_layout.addWidget(self.key_file_input)

        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self._browse_key_file)
        key_file_layout.addWidget(self.browse_button)

        self.key_file_indicator = ValidationIndicator()
        key_file_layout.addWidget(self.key_file_indicator)

        sa_layout.addRow("Key File:", key_file_layout)

        # Service account email (read-only, populated from key file)
        self.sa_email_input = QLineEdit()
        self.sa_email_input.setReadOnly(True)
        self.sa_email_input.setStyleSheet("background-color: #f0f0f0;")
        sa_layout.addRow("Service Account:", self.sa_email_input)

        parent_layout.addWidget(self.service_account_group)

        # Initially hide service account group
        self.service_account_group.hide()

        # Advanced settings
        self.advanced_group = self._create_advanced_group()
        parent_layout.addWidget(self.advanced_group)

        # Connection test area
        test_layout = QHBoxLayout()
        self.test_button = self._create_test_button()
        test_layout.addWidget(self.test_button)

        self.connection_status_label = QLabel("")
        test_layout.addWidget(self.connection_status_label)
        test_layout.addStretch()

        parent_layout.addLayout(test_layout)

        # Connect auth method change
        self.auth_button_group.buttonClicked.connect(self._on_auth_method_changed)

        # Connect change tracking
        self._connect_change_tracking()

    def _create_advanced_group(self) -> QGroupBox:
        """Create advanced settings group."""
        group = self._create_group_box("Advanced Settings", collapsible=True)
        layout = QFormLayout(group)

        # OAuth scopes
        scopes_group = QGroupBox("OAuth Scopes")
        scopes_layout = QVBoxLayout(scopes_group)

        self.scope_docs = self._create_checkbox("Google Docs (read/write)", True)
        self.scope_docs.setEnabled(False)  # Always required
        scopes_layout.addWidget(self.scope_docs)

        self.scope_drive = self._create_checkbox("Google Drive (create files)", True)
        self.scope_drive.setEnabled(False)  # Always required
        scopes_layout.addWidget(self.scope_drive)

        self.scope_sheets = self._create_checkbox("Google Sheets (optional)", False)
        scopes_layout.addWidget(self.scope_sheets)

        layout.addRow(scopes_group)

        # Retry settings
        retry_label, self.retry_attempts = self._create_spinbox(
            "Retry Attempts:", 3, 0, 10
        )
        layout.addRow(retry_label, self.retry_attempts)

        timeout_label, self.request_timeout = self._create_spinbox(
            "Request Timeout (seconds):", 30, 10, 300
        )
        layout.addRow(timeout_label, self.request_timeout)

        return group

    def _on_auth_method_changed(self, button: QRadioButton):
        """Handle authentication method change."""
        if button == self.oauth_radio:
            self.oauth_group.show()
            self.service_account_group.hide()
        else:
            self.oauth_group.hide()
            self.service_account_group.show()

        self.mark_dirty()

    def _handle_oauth_click(self):
        """Handle OAuth authentication button click."""
        # Check if we have the OAuth handler available
        try:
            # Try simplified OAuth first
            from wes.gui.simplified_oauth_handler import SimplifiedGoogleOAuthHandler

            # Create simplified OAuth handler
            oauth_handler = SimplifiedGoogleOAuthHandler(self.config_manager)
            oauth_handler.auth_complete.connect(self._on_oauth_complete)
            oauth_handler.auth_error.connect(self._on_oauth_failed)

            # Update button to show loading state
            self.oauth_button.setText("Connecting...")
            self.oauth_button.setEnabled(False)
            self.oauth_status.setText("Opening browser...")
            self.oauth_status.setStyleSheet("color: #666;")

            # Start OAuth flow
            oauth_handler.start_flow()

        except ImportError:
            # Fallback to manual OAuth if simplified not available
            try:
                from wes.gui.oauth_handler import GoogleOAuthHandler

                # Create OAuth handler
                oauth_handler = GoogleOAuthHandler(self.config_manager)
                oauth_handler.auth_complete.connect(self._on_oauth_complete)
                oauth_handler.auth_error.connect(self._on_oauth_failed)

                # Start OAuth flow
                oauth_handler.start_flow()

            except ImportError:
                QMessageBox.warning(
                    self,
                    "OAuth Not Available",
                    "OAuth authentication requires additional setup. "
                    "Please use Service Account authentication instead.",
                )

    def _on_oauth_complete(self, cred_data: dict):
        """Handle successful OAuth authentication."""
        # Store the credentials in config manager
        if self.config_manager:
            # Store tokens securely
            self.config_manager.store_credential(
                "google", "oauth_access_token", cred_data.get("access_token", "")
            )
            self.config_manager.store_credential(
                "google", "oauth_refresh_token", cred_data.get("refresh_token", "")
            )

            # Store non-sensitive OAuth info
            google_config = self.config_manager.get_google_config()
            self.config_manager.update_google_config(
                oauth_client_id=cred_data.get("client_id", "proxy-managed"),
                oauth_token_uri=cred_data.get(
                    "token_uri", "https://oauth2.googleapis.com/token"
                ),
            )

        # Test credentials to get user email
        user_email = "Google Account"
        try:
            from wes.gui.simplified_oauth_handler import SimplifiedGoogleOAuthHandler

            handler = SimplifiedGoogleOAuthHandler()
            success, message = handler.test_credentials(cred_data)
            if success and "connected as" in message:
                user_email = message.split("connected as ")[-1]
        except:
            pass

        # Update UI
        self.oauth_status.setText("✓ Authenticated")
        self.oauth_status.setStyleSheet("color: green;")
        self.oauth_indicator.set_valid(f"Connected successfully")

        self.oauth_email_label.setText(f"Logged in as: {user_email}")
        self.oauth_email_label.show()

        self.oauth_button.setText("Re-authenticate")
        self.oauth_button.setEnabled(True)

        # Mark that we have OAuth configured
        self.oauth_configured = True

        self.mark_dirty()

    def _on_oauth_failed(self, error: str):
        """Handle failed OAuth authentication."""
        self.oauth_status.setText("Not authenticated")
        self.oauth_status.setStyleSheet("color: #666;")
        self.oauth_indicator.set_invalid(error)

        # Re-enable button
        self.oauth_button.setText("Authenticate with Google")
        self.oauth_button.setEnabled(True)

        QMessageBox.warning(
            self,
            "Authentication Failed",
            f"Failed to authenticate with Google:\n{error}",
        )

    def _browse_key_file(self):
        """Browse for service account key file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Service Account Key File",
            "",
            "JSON Files (*.json);;All Files (*)",
        )

        if file_path:
            self.key_file_input.setText(file_path)
            self._validate_key_file()

    def _validate_key_file(self):
        """Validate service account key file."""
        file_path = self.key_file_input.text().strip()

        if not file_path:
            self.key_file_indicator.clear()
            self.sa_email_input.clear()
            return

        if not os.path.exists(file_path):
            self.key_file_indicator.set_invalid("File not found")
            self.sa_email_input.clear()
            return

        # Try to read the key file and extract service account email
        try:
            import json

            with open(file_path, "r") as f:
                key_data = json.load(f)

            if "client_email" in key_data:
                self.sa_email_input.setText(key_data["client_email"])
                self.key_file_indicator.set_valid("Valid service account key")
            else:
                self.key_file_indicator.set_invalid("Invalid key file format")
                self.sa_email_input.clear()

        except Exception as e:
            self.key_file_indicator.set_invalid(f"Error reading file: {str(e)}")
            self.sa_email_input.clear()

        self.mark_dirty()

    def load_config(self, config: Dict[str, Any]) -> None:
        """Load Google configuration into UI."""
        google_config = config.get("google", {})

        # Set authentication method
        auth_method = google_config.get("auth_method", "oauth")
        if auth_method == "service_account":
            self.service_account_radio.setChecked(True)
            self.oauth_group.hide()
            self.service_account_group.show()
        else:
            self.oauth_radio.setChecked(True)
            self.oauth_group.show()
            self.service_account_group.hide()

        # Load OAuth config
        # Check if we have OAuth tokens stored
        if self.config_manager:
            access_token = self.config_manager.retrieve_credential(
                "google", "oauth_access_token"
            )
            refresh_token = self.config_manager.retrieve_credential(
                "google", "oauth_refresh_token"
            )

            if access_token and refresh_token:
                self.oauth_configured = True
                self.oauth_status.setText("✓ Authenticated")
                self.oauth_status.setStyleSheet("color: green;")
                self.oauth_indicator.set_valid("Previously authenticated")
                self.oauth_button.setText("Re-authenticate")

                # Try to get user email from config
                if "user_email" in google_config:
                    self.oauth_email_label.setText(
                        f"Logged in as: {google_config['user_email']}"
                    )
                    self.oauth_email_label.show()

        # Load service account config
        if "service_account_key_path" in google_config:
            self.key_file_input.setText(google_config["service_account_key_path"])
            self._validate_key_file()

        # Load advanced settings
        self.scope_sheets.setChecked(google_config.get("scope_sheets", False))
        self.retry_attempts.setValue(google_config.get("retry_attempts", 3))
        self.request_timeout.setValue(google_config.get("request_timeout", 30))

        self.mark_clean()

    def save_config(self) -> Dict[str, Any]:
        """Extract Google configuration from UI."""
        config = {
            "google": {
                "auth_method": (
                    "oauth" if self.oauth_radio.isChecked() else "service_account"
                ),
                "scope_sheets": self.scope_sheets.isChecked(),
                "retry_attempts": self.retry_attempts.value(),
                "request_timeout": self.request_timeout.value(),
            }
        }

        # Add auth-specific config
        if self.oauth_radio.isChecked():
            if hasattr(self, "oauth_configured") and self.oauth_configured:
                config["google"]["oauth_configured"] = True

            # Extract email from label if available
            email_text = self.oauth_email_label.text()
            if email_text.startswith("Logged in as: "):
                config["google"]["user_email"] = email_text.replace(
                    "Logged in as: ", ""
                )
        else:
            config["google"][
                "service_account_key_path"
            ] = self.key_file_input.text().strip()
            config["google"][
                "service_account_email"
            ] = self.sa_email_input.text().strip()

        return config

    def validate(self) -> ValidationResult:
        """Validate Google configuration."""
        config = self.save_config()["google"]

        if config["auth_method"] == "oauth":
            # Check if authenticated
            if not config.get("oauth_configured") and not (
                hasattr(self, "oauth_configured") and self.oauth_configured
            ):
                return ValidationResult(
                    is_valid=False,
                    message="Google OAuth authentication required",
                    service=self.service_type,
                    details={"auth_method": "oauth", "authenticated": False},
                )
        else:
            # Check service account key
            key_path = config.get("service_account_key_path", "")
            if not key_path:
                return ValidationResult(
                    is_valid=False,
                    message="Service account key file required",
                    service=self.service_type,
                    details={"auth_method": "service_account", "field": "key_file"},
                )

            if not os.path.exists(key_path):
                return ValidationResult(
                    is_valid=False,
                    message="Service account key file not found",
                    service=self.service_type,
                    details={"auth_method": "service_account", "key_path": key_path},
                )

        return ValidationResult(
            is_valid=True,
            message="Configuration valid",
            service=self.service_type,
            details={"configured": True},
        )

    def get_basic_fields(self) -> List[QWidget]:
        """Return basic field widgets."""
        return [
            self.oauth_radio,
            self.service_account_radio,
            self.oauth_button,
            self.key_file_input,
            self.browse_button,
        ]

    def get_advanced_fields(self) -> List[QWidget]:
        """Return advanced field widgets."""
        return [self.scope_sheets, self.retry_attempts, self.request_timeout]

    def _connect_change_tracking(self):
        """Connect change tracking to form fields."""
        # Auth method changes
        self.auth_button_group.buttonClicked.connect(lambda: self.mark_dirty())

        # Service account changes
        self.key_file_input.textChanged.connect(lambda: self.mark_dirty())
