"""OAuth setup dialog for configuring Google OAuth credentials."""

import json
from pathlib import Path
from typing import Optional, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wes.utils.logging_config import get_logger


class OAuthSetupDialog(QDialog):
    """Dialog for setting up Google OAuth credentials."""

    # Signals
    credentials_saved = Signal(dict)  # Emitted when credentials are saved

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_logger(__name__)
        self.setWindowTitle("Google OAuth Setup")
        self.setModal(True)
        self.resize(600, 500)

        self._init_ui()

    def _init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Instructions
        instructions_group = QGroupBox("Setup Instructions")
        instructions_layout = QVBoxLayout(instructions_group)

        instructions = QTextEdit()
        instructions.setReadOnly(True)
        instructions.setMaximumHeight(150)
        instructions.setHtml(
            """
        <h3>How to Create Google OAuth Credentials</h3>
        <ol>
        <li>Click the button below to open Google Cloud Console</li>
        <li>Create a new project or select an existing one</li>
        <li>Enable <b>Google Docs API</b> and <b>Google Drive API</b></li>
        <li>Go to <b>APIs & Services</b> → <b>Credentials</b></li>
        <li>Click <b>Create Credentials</b> → <b>OAuth client ID</b></li>
        <li>Choose <b>Desktop app</b> as the application type</li>
        <li>Name it "WES Desktop App"</li>
        <li>Copy the <b>Client ID</b> and <b>Client Secret</b> below</li>
        </ol>
        """
        )
        instructions_layout.addWidget(instructions)

        # Button to open Google Cloud Console
        console_button = QPushButton("Open Google Cloud Console")
        console_button.clicked.connect(self._open_cloud_console)
        instructions_layout.addWidget(console_button)

        layout.addWidget(instructions_group)

        # Credentials input
        creds_group = QGroupBox("OAuth Credentials")
        creds_layout = QFormLayout(creds_group)

        # Client ID
        self.client_id_input = QLineEdit()
        self.client_id_input.setPlaceholderText(
            "your-client-id.apps.googleusercontent.com"
        )
        self.client_id_input.textChanged.connect(self._validate_inputs)
        creds_layout.addRow("Client ID:", self.client_id_input)

        # Client Secret
        self.client_secret_input = QLineEdit()
        self.client_secret_input.setPlaceholderText("your-client-secret")
        self.client_secret_input.setEchoMode(QLineEdit.Password)
        self.client_secret_input.textChanged.connect(self._validate_inputs)

        secret_layout = QHBoxLayout()
        secret_layout.addWidget(self.client_secret_input)

        # Toggle visibility button
        self.show_secret_button = QPushButton("Show")
        self.show_secret_button.setMaximumWidth(60)
        self.show_secret_button.clicked.connect(self._toggle_secret_visibility)
        secret_layout.addWidget(self.show_secret_button)

        creds_layout.addRow("Client Secret:", secret_layout)

        layout.addWidget(creds_group)

        # Validation message
        self.validation_label = QLabel()
        self.validation_label.setWordWrap(True)
        layout.addWidget(self.validation_label)

        # Alternative option
        alternative_group = QGroupBox("Alternative Option")
        alternative_layout = QVBoxLayout(alternative_group)

        alternative_text = QLabel(
            "If you prefer not to use OAuth, you can use "
            "<b>Service Account</b> authentication instead. "
            "It's simpler and doesn't require this setup."
        )
        alternative_text.setWordWrap(True)
        alternative_layout.addWidget(alternative_text)

        layout.addWidget(alternative_group)

        # Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self._save_credentials)
        self.button_box.rejected.connect(self.reject)

        # Initially disable Save button
        self.button_box.button(QDialogButtonBox.Save).setEnabled(False)

        layout.addWidget(self.button_box)

        # Add stretch
        layout.addStretch()

    def _open_cloud_console(self):
        """Open Google Cloud Console in browser."""
        url = "https://console.cloud.google.com/apis/credentials"
        QDesktopServices.openUrl(url)

    def _toggle_secret_visibility(self):
        """Toggle client secret visibility."""
        if self.client_secret_input.echoMode() == QLineEdit.Password:
            self.client_secret_input.setEchoMode(QLineEdit.Normal)
            self.show_secret_button.setText("Hide")
        else:
            self.client_secret_input.setEchoMode(QLineEdit.Password)
            self.show_secret_button.setText("Show")

    def _validate_inputs(self):
        """Validate the input credentials."""
        client_id = self.client_id_input.text().strip()
        client_secret = self.client_secret_input.text().strip()

        # Check if both fields have content
        if not client_id or not client_secret:
            self.validation_label.setText("")
            self.button_box.button(QDialogButtonBox.Save).setEnabled(False)
            return

        # Validate client ID format
        if not client_id.endswith(".apps.googleusercontent.com"):
            self.validation_label.setText(
                "⚠️ Client ID should end with '.apps.googleusercontent.com'"
            )
            self.validation_label.setStyleSheet("color: orange;")
        else:
            self.validation_label.setText("✓ Credentials look valid")
            self.validation_label.setStyleSheet("color: green;")

        # Enable save button
        self.button_box.button(QDialogButtonBox.Save).setEnabled(True)

    def _save_credentials(self):
        """Save the credentials and close dialog."""
        client_id = self.client_id_input.text().strip()
        client_secret = self.client_secret_input.text().strip()

        if not client_id or not client_secret:
            QMessageBox.warning(
                self,
                "Missing Credentials",
                "Please enter both Client ID and Client Secret.",
            )
            return

        # Warn if client ID doesn't look right
        if not client_id.endswith(".apps.googleusercontent.com"):
            reply = QMessageBox.question(
                self,
                "Unusual Client ID",
                "The Client ID doesn't have the expected format.\n"
                "It should end with '.apps.googleusercontent.com'.\n\n"
                "Continue anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        # Save credentials to file
        try:
            wes_dir = Path.home() / ".wes"
            wes_dir.mkdir(exist_ok=True)

            cred_file = wes_dir / "google_oauth_credentials.json"

            credentials = {"client_id": client_id, "client_secret": client_secret}

            with open(cred_file, "w") as f:
                json.dump(credentials, f, indent=2)

            # Set permissions to be readable only by user
            import os

            os.chmod(cred_file, 0o600)

            self.logger.info(f"OAuth credentials saved to {cred_file}")

            # Emit signal with credentials
            self.credentials_saved.emit(credentials)

            # Show success message
            QMessageBox.information(
                self,
                "Credentials Saved",
                "OAuth credentials have been saved successfully.\n\n"
                "You can now click 'Authenticate with Google' to log in.",
            )

            self.accept()

        except Exception as e:
            self.logger.error(f"Failed to save credentials: {e}")
            QMessageBox.critical(
                self, "Save Failed", f"Failed to save credentials:\n{str(e)}"
            )

    def get_credentials(self) -> Tuple[str, str]:
        """Get the entered credentials."""
        return (
            self.client_id_input.text().strip(),
            self.client_secret_input.text().strip(),
        )
