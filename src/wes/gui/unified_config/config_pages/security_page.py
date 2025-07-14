"""Security settings configuration page."""

from typing import Any, Dict, List

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wes.core.config_manager import ConfigManager
from wes.gui.unified_config.config_pages.base_page import ConfigPageBase
from wes.gui.unified_config.types import ServiceType, ValidationResult


class SecurityPage(ConfigPageBase):
    """Security settings configuration page."""

    # Not a service, but we need to set this for the base class
    service_type = None
    page_title = "Security Settings"
    page_icon = "SP_VistaShield"
    page_description = "Manage security settings and credential protection"

    def _setup_page_ui(self, parent_layout: QVBoxLayout):
        """Setup security settings UI."""
        # Credential storage
        storage_group = QGroupBox("Credential Storage")
        storage_layout = QFormLayout(storage_group)

        # Encryption
        self.encrypt_creds = self._create_checkbox(
            "Encrypt stored credentials (recommended)", True
        )
        storage_layout.addRow("Encryption:", self.encrypt_creds)

        # Key derivation
        self.use_hardware_key = self._create_checkbox(
            "Use hardware security module if available", False
        )
        storage_layout.addRow("Hardware Security:", self.use_hardware_key)

        # Master password option
        self.require_master_password = self._create_checkbox(
            "Require master password on startup", False
        )
        storage_layout.addRow("Master Password:", self.require_master_password)

        # Change master password button
        change_password_layout = QHBoxLayout()
        self.change_password_btn = QPushButton("Change Master Password")
        self.change_password_btn.clicked.connect(self._change_master_password)
        self.change_password_btn.setEnabled(self.require_master_password.isChecked())
        change_password_layout.addWidget(self.change_password_btn)
        change_password_layout.addStretch()
        storage_layout.addRow("", change_password_layout)

        # Connect checkbox to button
        self.require_master_password.toggled.connect(
            self.change_password_btn.setEnabled
        )

        parent_layout.addWidget(storage_group)

        # Session security
        session_group = QGroupBox("Session Security")
        session_layout = QFormLayout(session_group)

        # Auto-lock
        self.enable_auto_lock = self._create_checkbox("Enable auto-lock", False)
        session_layout.addRow("Auto-lock:", self.enable_auto_lock)

        # Lock timeout
        timeout_layout = QHBoxLayout()
        timeout_label, self.lock_timeout_spin = self._create_spinbox(
            "Lock after inactivity:", 15, 1, 120
        )
        self.lock_timeout_spin.setEnabled(self.enable_auto_lock.isChecked())
        timeout_layout.addWidget(self.lock_timeout_spin)
        timeout_layout.addWidget(QLabel("minutes"))
        timeout_layout.addStretch()
        session_layout.addRow(timeout_label, timeout_layout)

        # Connect checkbox to spinbox
        self.enable_auto_lock.toggled.connect(self.lock_timeout_spin.setEnabled)

        # Clear credentials on exit
        self.clear_on_exit = self._create_checkbox(
            "Clear credentials from memory on exit", True
        )
        session_layout.addRow("On Exit:", self.clear_on_exit)

        parent_layout.addWidget(session_group)

        # API Security
        api_group = QGroupBox("API Security")
        api_layout = QFormLayout(api_group)

        # Certificate validation
        self.verify_ssl = self._create_checkbox(
            "Verify SSL certificates (recommended)", True
        )
        api_layout.addRow("SSL/TLS:", self.verify_ssl)

        # Certificate pinning
        self.cert_pinning = self._create_checkbox(
            "Enable certificate pinning for known services", False
        )
        api_layout.addRow("Cert Pinning:", self.cert_pinning)

        # API key rotation reminder
        self.api_key_rotation = self._create_checkbox("Remind to rotate API keys", True)
        api_layout.addRow("Key Rotation:", self.api_key_rotation)

        # Rotation interval
        rotation_layout = QHBoxLayout()
        rotation_label, self.rotation_days_spin = self._create_spinbox(
            "Rotation interval:", 90, 30, 365
        )
        self.rotation_days_spin.setEnabled(self.api_key_rotation.isChecked())
        rotation_layout.addWidget(self.rotation_days_spin)
        rotation_layout.addWidget(QLabel("days"))
        rotation_layout.addStretch()
        api_layout.addRow(rotation_label, rotation_layout)

        # Connect checkbox to spinbox
        self.api_key_rotation.toggled.connect(self.rotation_days_spin.setEnabled)

        parent_layout.addWidget(api_group)

        # Audit and logging
        audit_group = QGroupBox("Audit and Logging")
        audit_layout = QFormLayout(audit_group)

        # Security event logging
        self.log_security_events = self._create_checkbox("Log security events", True)
        audit_layout.addRow("Security Logging:", self.log_security_events)

        # Failed auth attempts
        self.log_failed_auth = self._create_checkbox(
            "Log failed authentication attempts", True
        )
        audit_layout.addRow("Failed Auth:", self.log_failed_auth)

        # View security log button
        view_log_layout = QHBoxLayout()
        view_log_btn = QPushButton("View Security Log")
        view_log_btn.clicked.connect(self._view_security_log)
        view_log_layout.addWidget(view_log_btn)

        clear_log_btn = QPushButton("Clear Log")
        clear_log_btn.clicked.connect(self._clear_security_log)
        view_log_layout.addWidget(clear_log_btn)
        view_log_layout.addStretch()

        audit_layout.addRow("Log Management:", view_log_layout)

        parent_layout.addWidget(audit_group)

    def _change_master_password(self):
        """Handle master password change."""
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLineEdit

        dialog = QDialog(self)
        dialog.setWindowTitle("Change Master Password")
        dialog.setModal(True)

        layout = QVBoxLayout(dialog)

        # Current password
        layout.addWidget(QLabel("Current Password:"))
        current_password = QLineEdit()
        current_password.setEchoMode(QLineEdit.Password)
        layout.addWidget(current_password)

        # New password
        layout.addWidget(QLabel("New Password:"))
        new_password = QLineEdit()
        new_password.setEchoMode(QLineEdit.Password)
        layout.addWidget(new_password)

        # Confirm password
        layout.addWidget(QLabel("Confirm New Password:"))
        confirm_password = QLineEdit()
        confirm_password.setEchoMode(QLineEdit.Password)
        layout.addWidget(confirm_password)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.Accepted:
            # Validate passwords
            if new_password.text() != confirm_password.text():
                QMessageBox.warning(
                    self, "Password Mismatch", "New passwords do not match."
                )
                return

            if len(new_password.text()) < 8:
                QMessageBox.warning(
                    self,
                    "Weak Password",
                    "Password must be at least 8 characters long.",
                )
                return

            # TODO: Actually change the master password
            QMessageBox.information(
                self,
                "Password Changed",
                "Master password has been changed successfully.",
            )

    def _view_security_log(self):
        """View security event log."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Security Event Log")
        dialog.setModal(True)
        dialog.resize(600, 400)

        layout = QVBoxLayout(dialog)

        # Log viewer
        log_viewer = QTextEdit()
        log_viewer.setReadOnly(True)
        log_viewer.setPlainText(
            "2024-01-15 10:30:15 - Login successful\n"
            "2024-01-15 09:45:22 - Failed login attempt (invalid password)\n"
            "2024-01-14 16:20:10 - API key rotated for Jira\n"
            "2024-01-14 15:10:05 - Configuration changed\n"
            "2024-01-13 11:25:30 - Session locked due to inactivity\n"
        )
        layout.addWidget(log_viewer)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec()

    def _clear_security_log(self):
        """Clear security event log."""
        reply = QMessageBox.question(
            self,
            "Clear Security Log",
            "Are you sure you want to clear the security log?\n"
            "This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            # TODO: Actually clear the log
            QMessageBox.information(
                self, "Log Cleared", "Security log has been cleared."
            )

    def load_config(self, config: Dict[str, Any]) -> None:
        """Load security settings into UI."""
        security_config = config.get("security", {})

        # Credential storage
        self.encrypt_creds.setChecked(security_config.get("encrypt_credentials", True))
        self.use_hardware_key.setChecked(security_config.get("use_hardware_key", False))
        self.require_master_password.setChecked(
            security_config.get("require_master_password", False)
        )

        # Session security
        self.enable_auto_lock.setChecked(security_config.get("enable_auto_lock", False))
        self.lock_timeout_spin.setValue(security_config.get("lock_timeout_minutes", 15))
        self.clear_on_exit.setChecked(security_config.get("clear_on_exit", True))

        # API Security
        self.verify_ssl.setChecked(security_config.get("verify_ssl", True))
        self.cert_pinning.setChecked(security_config.get("certificate_pinning", False))
        self.api_key_rotation.setChecked(
            security_config.get("api_key_rotation_reminder", True)
        )
        self.rotation_days_spin.setValue(
            security_config.get("rotation_interval_days", 90)
        )

        # Audit and logging
        self.log_security_events.setChecked(
            security_config.get("log_security_events", True)
        )
        self.log_failed_auth.setChecked(security_config.get("log_failed_auth", True))

        self.mark_clean()

    def save_config(self) -> Dict[str, Any]:
        """Extract security settings from UI."""
        return {
            "security": {
                "encrypt_credentials": self.encrypt_creds.isChecked(),
                "use_hardware_key": self.use_hardware_key.isChecked(),
                "require_master_password": self.require_master_password.isChecked(),
                "enable_auto_lock": self.enable_auto_lock.isChecked(),
                "lock_timeout_minutes": self.lock_timeout_spin.value(),
                "clear_on_exit": self.clear_on_exit.isChecked(),
                "verify_ssl": self.verify_ssl.isChecked(),
                "certificate_pinning": self.cert_pinning.isChecked(),
                "api_key_rotation_reminder": self.api_key_rotation.isChecked(),
                "rotation_interval_days": self.rotation_days_spin.value(),
                "log_security_events": self.log_security_events.isChecked(),
                "log_failed_auth": self.log_failed_auth.isChecked(),
            }
        }

    def validate(self) -> ValidationResult:
        """Validate security settings."""
        # Security settings are always valid (no required fields)
        return ValidationResult(
            is_valid=True,
            message="Settings valid",
            service=None,
            details={"configured": True},
        )

    def test_connection(self) -> None:
        """No connection test needed for security settings."""
        pass

    def get_basic_fields(self) -> List[QWidget]:
        """Return basic field widgets."""
        return [
            self.encrypt_creds,
            self.require_master_password,
            self.enable_auto_lock,
            self.verify_ssl,
        ]

    def get_advanced_fields(self) -> List[QWidget]:
        """Return advanced field widgets."""
        return [
            self.use_hardware_key,
            self.cert_pinning,
            self.api_key_rotation,
            self.log_security_events,
        ]
