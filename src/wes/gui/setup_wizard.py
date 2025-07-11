"""Unified credential setup wizard for simplified onboarding."""

import asyncio
import json
import threading
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QStackedWidget,
    QWidget,
    QLabel,
    QPushButton,
    QLineEdit,
    QTextEdit,
    QProgressBar,
    QFrame,
    QGroupBox,
    QFormLayout,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QMessageBox,
    QScrollArea,
    QSpacerItem,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QThread, QTimer, Signal, QObject
from PySide6.QtGui import QFont, QPixmap, QIcon

from ..core.config_manager import ConfigManager
from ..utils.logging_config import get_logger
from ..utils.exceptions import ConfigurationError
from .credential_validators import CredentialValidator
from .oauth_handler import GoogleOAuthHandler
from ..integrations.redhat_jira_client import is_redhat_jira


class ValidationWorker(QObject):
    """Worker for background credential validation."""

    validation_complete = Signal(str, bool, str)  # service, success, message

    def __init__(self, service: str, credentials: Dict[str, str]):
        super().__init__()
        self.service = service
        self.credentials = credentials
        self.validator = CredentialValidator()

    def validate(self):
        """Validate credentials in background thread."""
        try:
            if self.service == "jira":
                success, message = self.validator.validate_jira_credentials(
                    self.credentials.get("url", ""),
                    self.credentials.get("username", ""),
                    self.credentials.get("api_token", ""),
                )
            elif self.service == "google":
                success, message = self.validator.validate_google_credentials(
                    self.credentials
                )
            elif self.service == "gemini":
                success, message = self.validator.validate_gemini_credentials(
                    self.credentials.get("api_key", "")
                )
            else:
                success, message = False, "Unknown service"

            self.validation_complete.emit(self.service, success, message)

        except Exception as e:
            self.validation_complete.emit(self.service, False, str(e))


class WizardPage(QWidget):
    """Base class for wizard pages."""

    def __init__(self, title: str, subtitle: str = ""):
        super().__init__()
        self.title = title
        self.subtitle = subtitle
        self.setup_ui()

    def setup_ui(self):
        """Setup the page UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)

        # Header
        header_layout = QVBoxLayout()

        title_label = QLabel(self.title)
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)

        if self.subtitle:
            subtitle_label = QLabel(self.subtitle)
            subtitle_label.setWordWrap(True)
            subtitle_label.setStyleSheet("color: #666666;")
            header_layout.addWidget(subtitle_label)

        layout.addLayout(header_layout)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)

        # Content area
        self.content_layout = QVBoxLayout()
        layout.addLayout(self.content_layout)

        layout.addStretch()

    def validate_page(self) -> tuple[bool, str]:
        """Validate the page data."""
        return True, ""

    def get_data(self) -> Dict[str, Any]:
        """Get the page data."""
        return {}

    def set_data(self, data: Dict[str, Any]):
        """Set the page data."""
        pass


class WelcomePage(WizardPage):
    """Welcome page explaining the setup process."""

    def __init__(self):
        super().__init__(
            "Welcome to Executive Summary Tool",
            "Let's get you set up with the integrations you need.",
        )

        # Services overview
        services_group = QGroupBox("What we'll set up:")
        services_layout = QVBoxLayout(services_group)

        services = [
            ("Jira", "Connect to your Jira instance to fetch work item data"),
            ("Google Drive", "Create and store executive summary documents"),
            ("Google Gemini", "Generate AI-powered summaries from your data"),
        ]

        for service, description in services:
            service_layout = QHBoxLayout()

            service_label = QLabel(f"• {service}")
            service_font = QFont()
            service_font.setBold(True)
            service_label.setFont(service_font)
            service_layout.addWidget(service_label)

            desc_label = QLabel(description)
            desc_label.setWordWrap(True)
            service_layout.addWidget(desc_label, 1)

            services_layout.addLayout(service_layout)

        self.content_layout.addWidget(services_group)

        # Estimated time
        time_label = QLabel("⏱️ Estimated setup time: 5-10 minutes")
        time_label.setStyleSheet(
            "background-color: #e8f4fd; padding: 10px; border-radius: 4px;"
        )
        self.content_layout.addWidget(time_label)


class ServiceSelectionPage(WizardPage):
    """Page for selecting which services to configure."""

    def __init__(self):
        super().__init__(
            "Select Services",
            "Choose which integrations you'd like to set up. You can always add more later.",
        )

        self.service_checkboxes = {}

        services = [
            ("jira", "Jira", "Required for fetching work item data", True),
            (
                "google_drive",
                "Google Drive",
                "For creating and storing documents",
                False,
            ),
            ("gemini", "Google Gemini", "Required for AI-powered summaries", True),
        ]

        for service_id, name, description, required in services:
            checkbox = QCheckBox(name)
            checkbox.setChecked(True)
            checkbox.setEnabled(not required)

            if required:
                checkbox.setToolTip("This service is required")
                name += " (Required)"

            service_layout = QVBoxLayout()
            service_layout.addWidget(checkbox)

            desc_label = QLabel(description)
            desc_label.setStyleSheet("margin-left: 20px; color: #666666;")
            desc_label.setWordWrap(True)
            service_layout.addWidget(desc_label)

            self.content_layout.addLayout(service_layout)
            self.service_checkboxes[service_id] = checkbox

    def get_data(self) -> Dict[str, Any]:
        """Get selected services."""
        return {
            service_id: checkbox.isChecked()
            for service_id, checkbox in self.service_checkboxes.items()
        }


class JiraSetupPage(WizardPage):
    """Jira configuration page with guided setup."""

    def __init__(self):
        super().__init__(
            "Connect to Jira",
            "We'll help you connect to your Jira instance and generate an API token.",
        )

        # URL detection
        url_group = QGroupBox("Jira Instance")
        url_layout = QFormLayout(url_group)

        self.url_edit = QLineEdit()
        self.url_edit.setText("https://issues.redhat.com")  # Set as default value
        self.url_edit.setPlaceholderText("https://issues.redhat.com")
        self.url_edit.textChanged.connect(self.on_url_changed)
        url_layout.addRow("Jira URL:", self.url_edit)

        self.url_status = QLabel()
        url_layout.addRow("Status:", self.url_status)

        self.content_layout.addWidget(url_group)

        # Credentials
        creds_group = QGroupBox("Authentication")
        creds_layout = QFormLayout(creds_group)

        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("your.email@company.com")
        self.username_label = QLabel("Email/Username:")
        creds_layout.addRow(self.username_label, self.username_edit)

        # API Token with help
        token_layout = QHBoxLayout()
        self.token_edit = QLineEdit()
        self.token_edit.setEchoMode(QLineEdit.Password)
        self.token_edit.setPlaceholderText("Your Jira API token")
        token_layout.addWidget(self.token_edit)

        self.help_token_btn = QPushButton("Get API Token")
        self.help_token_btn.clicked.connect(self.open_api_token_help)
        token_layout.addWidget(self.help_token_btn)

        creds_layout.addRow("API Token:", token_layout)

        self.content_layout.addWidget(creds_group)

        # Test connection
        test_layout = QHBoxLayout()
        self.test_btn = QPushButton("Test Connection")
        self.test_btn.clicked.connect(self.test_connection)
        test_layout.addWidget(self.test_btn)

        self.test_result = QLabel()
        test_layout.addWidget(self.test_result, 1)

        self.content_layout.addLayout(test_layout)

        # Trigger URL validation for default value
        self.on_url_changed(self.url_edit.text())

    def on_url_changed(self, text: str):
        """Handle URL change to validate format and update username guidance."""
        if not text:
            self.url_status.setText("")
            self._reset_username_guidance()
            return

        try:
            parsed = urlparse(text)
            if parsed.scheme and parsed.netloc:
                if "atlassian.net" in parsed.netloc:
                    self.url_status.setText("✅ Valid Jira Cloud URL")
                    self.url_status.setStyleSheet("color: green;")
                    self._set_cloud_username_guidance()
                elif is_redhat_jira(text):
                    self.url_status.setText("🔴 Red Hat Jira instance detected")
                    self.url_status.setStyleSheet("color: #cc0000;")  # Red Hat red
                    self._set_redhat_username_guidance()
                else:
                    self.url_status.setText("ℹ️ Server/Data Center instance detected")
                    self.url_status.setStyleSheet("color: blue;")
                    self._set_onpremise_username_guidance()
            else:
                self.url_status.setText("⚠️ Invalid URL format")
                self.url_status.setStyleSheet("color: orange;")
                self._reset_username_guidance()
        except Exception:
            self.url_status.setText("❌ Invalid URL")
            self.url_status.setStyleSheet("color: red;")
            self._reset_username_guidance()

    def _set_cloud_username_guidance(self):
        """Set username guidance for Jira Cloud."""
        self.username_label.setText("Email Address:")
        self.username_edit.setPlaceholderText("your.email@company.com")
        self.username_edit.setToolTip(
            "Jira Cloud requires your email address as the username"
        )

    def _set_onpremise_username_guidance(self):
        """Set username guidance for on-premise Jira."""
        self.username_label.setText("Username:")
        self.username_edit.setPlaceholderText("username or email@company.com")
        self.username_edit.setToolTip(
            "Enter your Jira username (may be email or username depending on your configuration)"
        )

    def _set_redhat_username_guidance(self):
        """Set username guidance for Red Hat Jira."""
        self.username_label.setText("Red Hat Username:")
        self.username_edit.setPlaceholderText("your-redhat-username")
        self.username_edit.setToolTip(
            "Enter your Red Hat Jira username (typically your Red Hat employee ID or LDAP username)"
        )

    def _reset_username_guidance(self):
        """Reset username guidance to default."""
        self.username_label.setText("Email/Username:")
        self.username_edit.setPlaceholderText("your.email@company.com")
        self.username_edit.setToolTip("")

    def open_api_token_help(self):
        """Open help for API token generation."""
        url = self.url_edit.text().strip()
        if url:
            token_url = f"{url.rstrip('/')}/secure/ViewProfile.jspa?selectedTab=com.atlassian.pats.pats-plugin:jira-user-personal-access-tokens"
        else:
            token_url = "https://id.atlassian.com/manage-profile/security/api-tokens"

        msg = QMessageBox()
        msg.setWindowTitle("Generate API Token")
        msg.setText("To generate a Jira API token:")
        msg.setInformativeText(
            "1. Click 'Open Token Page' below\n"
            "2. Log in to your Jira account\n"
            "3. Click 'Create API token'\n"
            "4. Give it a label (e.g., 'Executive Summary Tool')\n"
            "5. Copy the generated token\n"
            "6. Paste it in the API Token field"
        )

        open_btn = msg.addButton("Open Token Page", QMessageBox.ActionRole)
        msg.addButton(QMessageBox.Ok)

        result = msg.exec()
        if msg.clickedButton() == open_btn:
            import webbrowser

            webbrowser.open(token_url)

    def test_connection(self):
        """Test Jira connection."""
        self.test_btn.setEnabled(False)
        self.test_result.setText("Testing connection...")
        self.test_result.setStyleSheet("color: blue;")

        # Create validator worker
        credentials = {
            "url": self.url_edit.text(),
            "username": self.username_edit.text(),
            "api_token": self.token_edit.text(),
        }

        self.worker = ValidationWorker("jira", credentials)
        self.worker.validation_complete.connect(self.on_validation_complete)

        # Run in thread
        self.thread = QThread()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.validate)
        self.thread.start()

        # Ensure the dialog stays visible
        if self.window():
            self.window().show()
            self.window().raise_()
            self.window().activateWindow()

    def on_validation_complete(self, service: str, success: bool, message: str):
        """Handle validation completion."""
        self.test_btn.setEnabled(True)
        self.thread.quit()
        self.thread.wait()  # Wait for thread to finish

        if success:
            self.test_result.setText("✅ Connection successful!")
            self.test_result.setStyleSheet("color: green;")
        else:
            self.test_result.setText(f"❌ {message}")
            self.test_result.setStyleSheet("color: red;")

        # Ensure dialog remains visible and focused
        wizard = self.window()
        if wizard and isinstance(wizard, SetupWizard):
            wizard.show()
            wizard.raise_()
            wizard.activateWindow()

    def validate_page(self) -> tuple[bool, str]:
        """Validate the Jira configuration."""
        if not self.url_edit.text().strip():
            return False, "Jira URL is required"

        if not self.username_edit.text().strip():
            return False, "Username is required"

        # Additional validation based on instance type
        url = self.url_edit.text().strip()
        username = self.username_edit.text().strip()

        try:
            from urllib.parse import urlparse

            parsed = urlparse(url.lower())

            if "atlassian.net" in parsed.netloc:
                # Jira Cloud requires email format
                import re

                email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
                if not re.match(email_pattern, username):
                    return (
                        False,
                        "Jira Cloud requires a valid email address as username",
                    )
            elif is_redhat_jira(url):
                # Red Hat Jira has specific username requirements
                if len(username.strip()) < 3:
                    return False, "Red Hat Jira username must be at least 3 characters"
                # Red Hat usernames are typically alphanumeric with hyphens
                import re

                username_pattern = r"^[a-zA-Z0-9._-]+$"
                if not re.match(username_pattern, username.strip()):
                    return (
                        False,
                        "Red Hat Jira username should contain only letters, numbers, dots, underscores, and hyphens",
                    )
        except Exception:
            pass  # Continue with basic validation

        if not self.token_edit.text().strip():
            return False, "API token is required"

        return True, ""

    def get_data(self) -> Dict[str, Any]:
        """Get Jira configuration data."""
        return {
            "url": self.url_edit.text().strip(),
            "username": self.username_edit.text().strip(),
            "api_token": self.token_edit.text().strip(),
        }


class GoogleSetupPage(WizardPage):
    """Google services setup page with OAuth flow."""

    def __init__(self):
        super().__init__(
            "Connect to Google Services",
            "We'll set up Google Drive access for document creation and storage.",
        )

        # OAuth setup
        oauth_group = QGroupBox("Google Account Connection")
        oauth_layout = QVBoxLayout(oauth_group)

        oauth_info = QLabel(
            "We'll use Google OAuth to securely connect to your Google account. "
            "This will give the application permission to create and manage documents in Google Drive."
        )
        oauth_info.setWordWrap(True)
        oauth_layout.addWidget(oauth_info)

        # OAuth button
        oauth_btn_layout = QHBoxLayout()
        self.oauth_btn = QPushButton("🔗 Connect to Google Account")
        self.oauth_btn.clicked.connect(self.start_oauth_flow)
        oauth_btn_layout.addWidget(self.oauth_btn)
        oauth_btn_layout.addStretch()

        oauth_layout.addLayout(oauth_btn_layout)

        # Status
        self.oauth_status = QLabel()
        oauth_layout.addWidget(self.oauth_status)

        self.content_layout.addWidget(oauth_group)

        # Optional folder configuration
        folder_group = QGroupBox("Document Storage (Optional)")
        folder_layout = QFormLayout(folder_group)

        self.folder_id_edit = QLineEdit()
        self.folder_id_edit.setPlaceholderText("Leave empty to use root folder")
        folder_layout.addRow("Google Drive Folder ID:", self.folder_id_edit)

        folder_help = QLabel(
            "If you want to store documents in a specific folder, "
            "copy the folder ID from the URL when viewing the folder in Google Drive."
        )
        folder_help.setWordWrap(True)
        folder_help.setStyleSheet("color: #666666; font-size: 10px;")
        folder_layout.addRow("", folder_help)

        self.content_layout.addWidget(folder_group)

        # OAuth handler will be initialized when needed
        self.oauth_handler = None
        self.credentials = None
        self.config_manager = None

    def start_oauth_flow(self):
        """Start Google OAuth flow."""
        # Initialize OAuth handler if not already done
        if not self.oauth_handler:
            # Get config manager from parent wizard
            wizard = self.window()
            if hasattr(wizard, "config_manager"):
                self.oauth_handler = GoogleOAuthHandler(wizard.config_manager)
            else:
                self.oauth_handler = GoogleOAuthHandler()

            self.oauth_handler.auth_complete.connect(self.on_oauth_complete)
            self.oauth_handler.auth_error.connect(self.on_oauth_error)

        # Check if OAuth client is configured
        if (
            self.oauth_handler.CLIENT_CONFIG["web"]["client_id"]
            == "your-client-id.apps.googleusercontent.com"
            or self.oauth_handler.CLIENT_CONFIG["web"]["client_secret"]
            == "your-client-secret"
        ):
            # Show configuration dialog
            self.show_oauth_config_dialog()
            return

        self.oauth_btn.setEnabled(False)
        self.oauth_status.setText("🔄 Opening browser for Google authentication...")
        self.oauth_status.setStyleSheet("color: blue;")

        self.oauth_handler.start_flow()

        # Ensure the dialog stays visible during OAuth flow
        if self.window():
            self.window().show()
            self.window().raise_()
            self.window().activateWindow()

    def on_oauth_complete(self, credentials: Dict[str, str]):
        """Handle OAuth completion."""
        self.credentials = credentials
        self.oauth_btn.setEnabled(True)
        self.oauth_btn.setText("✅ Connected to Google")
        self.oauth_status.setText("✅ Successfully connected to Google account!")
        self.oauth_status.setStyleSheet("color: green;")

        # Ensure dialog remains visible and focused after OAuth
        wizard = self.window()
        if wizard and isinstance(wizard, SetupWizard):
            wizard.show()
            wizard.raise_()
            wizard.activateWindow()

    def on_oauth_error(self, error: str):
        """Handle OAuth error."""
        self.oauth_btn.setEnabled(True)
        self.oauth_status.setText(f"❌ Authentication failed: {error}")
        self.oauth_status.setStyleSheet("color: red;")

        # Ensure dialog remains visible and focused after OAuth error
        wizard = self.window()
        if wizard and isinstance(wizard, SetupWizard):
            wizard.show()
            wizard.raise_()
            wizard.activateWindow()

    def show_oauth_config_dialog(self):
        """Show dialog to configure OAuth client credentials."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Configure Google OAuth")
        dialog.setModal(True)
        dialog.resize(700, 600)  # Set a reasonable default size

        main_layout = QVBoxLayout(dialog)

        # Create a scroll area for the content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        # Title
        title = QLabel("Google OAuth Setup Required")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        scroll_layout.addWidget(title)

        # Main instructions
        intro = QLabel(
            "Google OAuth client credentials are required to authenticate with Google services. "
            "Follow the steps below to obtain these credentials."
        )
        intro.setWordWrap(True)
        scroll_layout.addWidget(intro)

        # Add some spacing
        scroll_layout.addSpacing(20)

        # Step-by-step instructions with clickable links
        steps_group = QGroupBox("Setup Instructions")
        steps_layout = QVBoxLayout(steps_group)

        # Step 1
        step1_layout = QVBoxLayout()
        step1_label = QLabel("<b>Step 1: Go to Google Cloud Console</b>")
        step1_layout.addWidget(step1_label)

        console_link = QLabel(
            '<a href="https://console.cloud.google.com">https://console.cloud.google.com</a>'
        )
        console_link.setOpenExternalLinks(True)
        console_link.setTextInteractionFlags(Qt.TextBrowserInteraction)
        step1_layout.addWidget(console_link)

        # Quick link to credentials page
        quick_link = QLabel(
            'Or go directly to: <a href="https://console.cloud.google.com/apis/credentials">Credentials Page</a>'
        )
        quick_link.setOpenExternalLinks(True)
        quick_link.setTextInteractionFlags(Qt.TextBrowserInteraction)
        quick_link.setStyleSheet("margin-left: 20px;")
        step1_layout.addWidget(quick_link)

        steps_layout.addLayout(step1_layout)
        steps_layout.addSpacing(10)

        # Step 2
        step2 = QLabel(
            "<b>Step 2: Create a Project</b><br>"
            "• Click 'Select a project' → 'New Project'<br>"
            "• Enter a project name (e.g., 'Executive Summary Tool')<br>"
            "• Click 'Create'"
        )
        step2.setWordWrap(True)
        steps_layout.addWidget(step2)
        steps_layout.addSpacing(10)

        # Step 3
        step3 = QLabel(
            "<b>Step 3: Enable Required APIs</b><br>"
            "• In your project, go to 'APIs & Services' → 'Library'<br>"
            "• Search for and enable:<br>"
            "  - Google Drive API<br>"
            "  - Google Docs API"
        )
        step3.setWordWrap(True)
        steps_layout.addWidget(step3)
        steps_layout.addSpacing(10)

        # Step 4
        step4 = QLabel(
            "<b>Step 4: Create OAuth Credentials</b><br>"
            "• Go to 'APIs & Services' → 'Credentials'<br>"
            "• Click 'Create Credentials' → 'OAuth client ID'<br>"
            "• If prompted to configure consent screen:<br>"
            "  - Choose 'Internal' (for Google Workspace) or 'External' (personal)<br>"
            "  - Fill in required fields<br>"
            "  - Add your email to test users if 'External'<br>"
            "• For Application type, select <b>'Desktop app'</b><br>"
            "• Name it (e.g., 'Executive Summary Tool Desktop')<br>"
            "• Click 'Create'"
        )
        step4.setWordWrap(True)
        steps_layout.addWidget(step4)
        steps_layout.addSpacing(10)

        # Step 5
        step5 = QLabel(
            "<b>Step 5: Copy Your Credentials</b><br>"
            "• Copy the Client ID and Client Secret<br>"
            "• Paste them in the fields below"
        )
        step5.setWordWrap(True)
        steps_layout.addWidget(step5)

        scroll_layout.addWidget(steps_group)
        scroll_layout.addSpacing(20)

        # Credentials form
        cred_group = QGroupBox("Enter Your OAuth Credentials")
        form_layout = QFormLayout(cred_group)

        self.client_id_edit = QLineEdit()
        self.client_id_edit.setPlaceholderText(
            "e.g., 123456789-abcdef.apps.googleusercontent.com"
        )
        form_layout.addRow("Client ID:", self.client_id_edit)

        self.client_secret_edit = QLineEdit()
        self.client_secret_edit.setEchoMode(QLineEdit.Password)
        self.client_secret_edit.setPlaceholderText("Your OAuth Client Secret")
        form_layout.addRow("Client Secret:", self.client_secret_edit)

        scroll_layout.addWidget(cred_group)

        # Important note
        note_label = QLabel(
            "<b>Note:</b> The application will use <code>http://localhost:8080/callback</code> "
            "as the redirect URI. This is automatically configured for Desktop applications."
        )
        note_label.setWordWrap(True)
        note_label.setStyleSheet(
            "background-color: #f0f0f0; padding: 10px; border-radius: 5px;"
        )
        scroll_layout.addWidget(note_label)

        # Add stretch to push content up
        scroll_layout.addStretch()

        # Set the scroll widget
        scroll_area.setWidget(scroll_widget)
        main_layout.addWidget(scroll_area)

        # Buttons (outside scroll area)
        button_layout = QHBoxLayout()

        help_btn = QPushButton("🌐 Open Google Console")
        help_btn.clicked.connect(lambda: self._open_google_console())
        button_layout.addWidget(help_btn)

        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save and Continue")
        save_btn.clicked.connect(
            lambda: self._save_oauth_config(
                dialog, self.client_id_edit.text(), self.client_secret_edit.text()
            )
        )
        save_btn.setDefault(True)
        button_layout.addWidget(save_btn)

        main_layout.addLayout(button_layout)

        dialog.exec()

    def _open_google_console(self):
        """Open Google Cloud Console in browser."""
        import webbrowser

        webbrowser.open("https://console.cloud.google.com/apis/credentials")

    def _save_oauth_config(self, dialog, client_id, client_secret):
        """Save OAuth configuration."""
        if not client_id or not client_secret:
            QMessageBox.warning(
                dialog,
                "Missing Credentials",
                "Please enter both Client ID and Client Secret",
            )
            return

        try:
            # Update OAuth handler configuration
            self.oauth_handler.CLIENT_CONFIG["web"]["client_id"] = client_id
            self.oauth_handler.CLIENT_CONFIG["web"]["client_secret"] = client_secret

            # Save to config manager if available
            wizard = self.window()
            if hasattr(wizard, "config_manager"):
                wizard.config_manager.update_google_config(oauth_client_id=client_id)
                wizard.config_manager.store_credential(
                    "google", "oauth_client_secret", client_secret
                )

            # Also save to credentials file for persistence
            from pathlib import Path

            cred_dir = Path.home() / ".wes"
            cred_dir.mkdir(exist_ok=True)
            cred_file = cred_dir / "google_oauth_credentials.json"

            with open(cred_file, "w") as f:
                json.dump({"client_id": client_id, "client_secret": client_secret}, f)

            dialog.accept()

            # Restart OAuth flow
            self.start_oauth_flow()

        except Exception as e:
            QMessageBox.critical(dialog, "Error", f"Failed to save credentials: {e}")

    def validate_page(self) -> tuple[bool, str]:
        """Validate Google setup."""
        if not self.credentials:
            return False, "Google authentication is required"
        return True, ""

    def get_data(self) -> Dict[str, Any]:
        """Get Google configuration data."""
        data = self.credentials or {}
        data["docs_folder_id"] = self.folder_id_edit.text().strip()
        return data


class GeminiSetupPage(WizardPage):
    """Google Gemini API setup page."""

    def __init__(self):
        super().__init__(
            "Connect to Google Gemini",
            "Set up AI-powered summary generation with Google Gemini.",
        )

        # API Key setup
        api_group = QGroupBox("Gemini API Key")
        api_layout = QFormLayout(api_group)

        # API Key with help
        key_layout = QHBoxLayout()
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setPlaceholderText("Your Google Gemini API key")
        key_layout.addWidget(self.api_key_edit)

        self.help_key_btn = QPushButton("Get API Key")
        self.help_key_btn.clicked.connect(self.open_api_key_help)
        key_layout.addWidget(self.help_key_btn)

        api_layout.addRow("API Key:", key_layout)

        self.content_layout.addWidget(api_group)

        # Model selection
        model_group = QGroupBox("Model Configuration")
        model_layout = QFormLayout(model_group)

        self.model_combo = QComboBox()
        self.model_combo.addItems(["gemini-2.5-flash", "gemini-2.5-pro"])
        self.model_combo.setCurrentText("gemini-2.5-flash")
        model_layout.addRow("Model:", self.model_combo)

        self.content_layout.addWidget(model_group)

        # Test API key
        test_layout = QHBoxLayout()
        self.test_btn = QPushButton("Test API Key")
        self.test_btn.clicked.connect(self.test_api_key)
        test_layout.addWidget(self.test_btn)

        self.test_result = QLabel()
        test_layout.addWidget(self.test_result, 1)

        self.content_layout.addLayout(test_layout)

    def open_api_key_help(self):
        """Open help for API key generation."""
        msg = QMessageBox()
        msg.setWindowTitle("Get Gemini API Key")
        msg.setText("To get a Google Gemini API key:")
        msg.setInformativeText(
            "1. Click 'Open AI Studio' below\n"
            "2. Sign in with your Google account\n"
            "3. Click 'Get API key' in the top navigation\n"
            "4. Click 'Create API key in new project' or select existing project\n"
            "5. Copy the generated API key\n"
            "6. Paste it in the API Key field above"
        )

        open_btn = msg.addButton("Open AI Studio", QMessageBox.ActionRole)
        msg.addButton(QMessageBox.Ok)

        result = msg.exec()
        if msg.clickedButton() == open_btn:
            import webbrowser

            webbrowser.open("https://aistudio.google.com/app/apikey")

    def test_api_key(self):
        """Test Gemini API key."""
        self.test_btn.setEnabled(False)
        self.test_result.setText("Testing API key...")
        self.test_result.setStyleSheet("color: blue;")

        credentials = {"api_key": self.api_key_edit.text()}

        self.worker = ValidationWorker("gemini", credentials)
        self.worker.validation_complete.connect(self.on_validation_complete)

        self.thread = QThread()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.validate)
        self.thread.start()

        # Ensure the dialog stays visible
        if self.window():
            self.window().show()
            self.window().raise_()
            self.window().activateWindow()

    def on_validation_complete(self, service: str, success: bool, message: str):
        """Handle validation completion."""
        self.test_btn.setEnabled(True)
        self.thread.quit()
        self.thread.wait()  # Wait for thread to finish

        if success:
            self.test_result.setText("✅ API key is valid!")
            self.test_result.setStyleSheet("color: green;")
        else:
            self.test_result.setText(f"❌ {message}")
            self.test_result.setStyleSheet("color: red;")

        # Ensure dialog remains visible and focused
        wizard = self.window()
        if wizard and isinstance(wizard, SetupWizard):
            wizard.show()
            wizard.raise_()
            wizard.activateWindow()

    def validate_page(self) -> tuple[bool, str]:
        """Validate Gemini setup."""
        if not self.api_key_edit.text().strip():
            return False, "Gemini API key is required"
        return True, ""

    def get_data(self) -> Dict[str, Any]:
        """Get Gemini configuration data."""
        return {
            "api_key": self.api_key_edit.text().strip(),
            "model_name": self.model_combo.currentText(),
        }


class SummaryPage(WizardPage):
    """Summary page showing configuration status."""

    def __init__(self):
        super().__init__(
            "Setup Complete!",
            "Your Executive Summary Tool is now configured and ready to use.",
        )

        self.services_status = {}

        # Status display
        self.status_layout = QVBoxLayout()
        self.content_layout.addLayout(self.status_layout)

        # Next steps
        next_steps_group = QGroupBox("Next Steps")
        next_steps_layout = QVBoxLayout(next_steps_group)

        steps = [
            "🎯 Create your first executive summary",
            "⚙️ Customize default settings if needed",
            "📊 Explore data filtering options",
            "🔄 Set up scheduled report generation",
        ]

        for step in steps:
            step_label = QLabel(step)
            next_steps_layout.addWidget(step_label)

        self.content_layout.addWidget(next_steps_group)

    def update_status(
        self, configured_services: Dict[str, bool], service_data: Dict[str, Dict]
    ):
        """Update the configuration status display."""
        # Clear existing status
        for i in reversed(range(self.status_layout.count())):
            self.status_layout.itemAt(i).widget().setParent(None)

        service_names = {
            "jira": "Jira",
            "google_drive": "Google Drive",
            "gemini": "Google Gemini",
        }

        for service_id, configured in configured_services.items():
            if not configured:
                continue

            status_widget = QFrame()
            status_widget.setFrameStyle(QFrame.Box)
            status_layout = QHBoxLayout(status_widget)

            # Service name and status
            name_label = QLabel(f"✅ {service_names.get(service_id, service_id)}")
            name_font = QFont()
            name_font.setBold(True)
            name_label.setFont(name_font)
            status_layout.addWidget(name_label)

            # Service details
            if service_id == "jira" and service_id in service_data:
                url = service_data[service_id].get("url", "")
                detail_label = QLabel(f"Connected to: {url}")
            elif service_id == "google_drive":
                detail_label = QLabel("OAuth authentication configured")
            elif service_id == "gemini" and service_id in service_data:
                model = service_data[service_id].get("model_name", "gemini-2.5-pro")
                detail_label = QLabel(f"Using model: {model}")
            else:
                detail_label = QLabel("Configured successfully")

            detail_label.setStyleSheet("color: #666666;")
            status_layout.addWidget(detail_label, 1)

            self.status_layout.addWidget(status_widget)


class SetupWizard(QDialog):
    """Main setup wizard dialog."""

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)

        self.config_manager = config_manager
        self.logger = get_logger(__name__)

        self.pages = []
        self.current_page = 0

        self.setup_ui()
        self.create_pages()

        # Window settings
        self.setWindowTitle("Executive Summary Tool - Setup Wizard")
        self.setGeometry(200, 200, 800, 600)
        self.setModal(True)

        # Prevent dialog from closing unintentionally
        self.setAttribute(Qt.WA_DeleteOnClose, False)

    def setup_ui(self):
        """Setup the wizard UI."""
        layout = QVBoxLayout(self)

        # Page container
        self.stacked_widget = QStackedWidget()
        layout.addWidget(self.stacked_widget)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Navigation buttons
        nav_layout = QHBoxLayout()

        self.back_btn = QPushButton("◀ Back")
        self.back_btn.clicked.connect(self.go_back)
        self.back_btn.setEnabled(False)
        nav_layout.addWidget(self.back_btn)

        nav_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        nav_layout.addWidget(self.cancel_btn)

        self.next_btn = QPushButton("Next ▶")
        self.next_btn.clicked.connect(self.go_next)
        nav_layout.addWidget(self.next_btn)

        layout.addLayout(nav_layout)

    def create_pages(self):
        """Create wizard pages."""
        # Welcome page
        self.pages.append(WelcomePage())

        # Service selection
        self.pages.append(ServiceSelectionPage())

        # Service setup pages
        self.jira_page = JiraSetupPage()
        self.pages.append(self.jira_page)

        self.google_page = GoogleSetupPage()
        self.pages.append(self.google_page)

        self.gemini_page = GeminiSetupPage()
        self.pages.append(self.gemini_page)

        # Summary page
        self.summary_page = SummaryPage()
        self.pages.append(self.summary_page)

        # Add pages to stacked widget
        for page in self.pages:
            self.stacked_widget.addWidget(page)

        self.update_navigation()

    def go_next(self):
        """Go to next page."""
        current_page = self.pages[self.current_page]

        # Validate current page
        valid, message = current_page.validate_page()
        if not valid:
            QMessageBox.warning(self, "Validation Error", message)
            return

        # Handle final page
        if self.current_page == len(self.pages) - 1:
            self.finish_setup()
            return

        # Go to next page
        self.current_page += 1
        self.stacked_widget.setCurrentIndex(self.current_page)

        # Update summary page if we reached it
        if self.current_page == len(self.pages) - 1:
            self.update_summary()

        self.update_navigation()

    def go_back(self):
        """Go to previous page."""
        if self.current_page > 0:
            self.current_page -= 1
            self.stacked_widget.setCurrentIndex(self.current_page)
            self.update_navigation()

    def update_navigation(self):
        """Update navigation button states."""
        self.back_btn.setEnabled(self.current_page > 0)

        if self.current_page == len(self.pages) - 1:
            self.next_btn.setText("Finish")
        else:
            self.next_btn.setText("Next ▶")

    def update_summary(self):
        """Update the summary page with configuration status."""
        # Get service selection
        service_selection = self.pages[1].get_data()

        # Collect all service data
        service_data = {}
        if service_selection.get("jira", False):
            service_data["jira"] = self.jira_page.get_data()
        if service_selection.get("google_drive", False):
            service_data["google_drive"] = self.google_page.get_data()
        if service_selection.get("gemini", False):
            service_data["gemini"] = self.gemini_page.get_data()

        self.summary_page.update_status(service_selection, service_data)

    def finish_setup(self):
        """Complete the setup process."""
        try:
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)  # Indeterminate

            # Get service selection
            service_selection = self.pages[1].get_data()

            # Save configurations
            if service_selection.get("jira", False):
                jira_data = self.jira_page.get_data()
                self.config_manager.update_jira_config(
                    url=jira_data["url"], username=jira_data["username"]
                )
                self.config_manager.store_credential(
                    "jira", "api_token", jira_data["api_token"]
                )

            if service_selection.get("google_drive", False):
                google_data = self.google_page.get_data()
                self.config_manager.update_google_config(
                    oauth_client_id=google_data.get("client_id", ""),
                    docs_folder_id=google_data.get("docs_folder_id", ""),
                )
                if "client_secret" in google_data:
                    self.config_manager.store_credential(
                        "google", "oauth_client_secret", google_data["client_secret"]
                    )
                if "refresh_token" in google_data:
                    self.config_manager.store_credential(
                        "google", "oauth_refresh_token", google_data["refresh_token"]
                    )

            if service_selection.get("gemini", False):
                gemini_data = self.gemini_page.get_data()
                self.config_manager.update_ai_config(
                    model_name=gemini_data["model_name"]
                )
                self.config_manager.store_credential(
                    "ai", "gemini_api_key", gemini_data["api_key"]
                )

            self.progress_bar.setVisible(False)

            QMessageBox.information(
                self,
                "Setup Complete",
                "Your Executive Summary Tool has been configured successfully!",
            )

            self.accept()

        except Exception as e:
            self.progress_bar.setVisible(False)
            self.logger.error(f"Setup failed: {e}")
            QMessageBox.critical(self, "Setup Error", f"Failed to complete setup: {e}")

    def closeEvent(self, event):
        """Handle close event to prevent accidental closing."""
        # If we're in the middle of validation, don't close
        if hasattr(self, "thread") and self.thread and self.thread.isRunning():
            event.ignore()
            return

        # Otherwise, let the default close behavior happen
        super().closeEvent(event)
