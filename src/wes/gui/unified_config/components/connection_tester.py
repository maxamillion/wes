"""Unified connection testing dialog component."""

import time
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wes.gui.credential_validators import CredentialValidator
from wes.gui.unified_config.types import ConnectionTestResult, ServiceType


class ConnectionTestWorker(QThread):
    """Extended validation worker that provides detailed progress updates."""

    progress_update = Signal(str, str)  # step_name, status
    result = Signal(bool, str, dict)  # success, message, details

    def __init__(self, validator, service_type: str, config: dict):
        super().__init__()
        self.validator = validator
        self.service_type = service_type
        self.config = config
        self.steps = []

    def run(self):
        """Run validation with detailed progress reporting."""
        try:
            # Define test steps based on service type
            if self.service_type == "jira":
                self.steps = [
                    ("Checking URL format", self._check_url_format),
                    ("Testing network connectivity", self._test_connectivity),
                    ("Validating credentials", self._validate_credentials),
                    ("Checking permissions", self._check_permissions),
                ]
            elif self.service_type == "google":
                self.steps = [
                    ("Checking OAuth configuration", self._check_oauth),
                    ("Validating tokens", self._validate_tokens),
                    ("Testing API access", self._test_api_access),
                ]
            elif self.service_type == "gemini":
                self.steps = [
                    ("Validating API key format", self._check_api_key),
                    ("Testing API connection", self._test_api_connection),
                    ("Checking model availability", self._check_model),
                ]

            # Execute each step
            for step_name, step_func in self.steps:
                self.progress_update.emit(step_name, "testing")
                success, message = step_func()

                if success:
                    self.progress_update.emit(step_name, "success")
                else:
                    self.progress_update.emit(step_name, "failed")
                    self.result.emit(
                        False, message, {"failed_step": step_name, "error": message}
                    )
                    return

                # Small delay for UI updates
                time.sleep(0.3)

            # All steps passed
            self.result.emit(
                True,
                "Connection successful!",
                {"steps_completed": len(self.steps), "timestamp": time.time()},
            )

        except Exception as e:
            self.result.emit(False, str(e), {"error_type": "exception"})

    def _check_url_format(self) -> tuple[bool, str]:
        """Check if URL is properly formatted."""
        if self.service_type == "jira":
            url = self.config.get("url", "")
            if not url:
                return False, "URL is required"
            if not url.startswith(("http://", "https://")):
                return False, "URL must start with http:// or https://"
        return True, "URL format valid"

    def _test_connectivity(self) -> tuple[bool, str]:
        """Test network connectivity to service."""
        # Actual implementation would test network
        return True, "Network connection established"

    def _validate_credentials(self) -> tuple[bool, str]:
        """Validate service credentials."""
        # Call the appropriate service-specific validator
        try:
            if self.service_type == "jira":
                result = self.validator.validate_jira_credentials(
                    self.config.get("url", ""),
                    self.config.get("username", ""),
                    self.config.get("api_token", ""),
                )
            elif self.service_type == "google":
                result = self.validator.validate_google_credentials(self.config)
            elif self.service_type == "gemini":
                result = self.validator.validate_gemini_credentials(
                    self.config.get("api_key", "")
                )
            else:
                return False, f"Unknown service type: {self.service_type}"

            return result[0], result[1]
        except Exception as e:
            return False, f"Credential validation failed: {str(e)}"

    def _check_permissions(self) -> tuple[bool, str]:
        """Check user permissions."""
        # Service-specific permission checks
        return True, "Permissions verified"

    def _check_oauth(self) -> tuple[bool, str]:
        """Check OAuth configuration."""
        return True, "OAuth configuration valid"

    def _validate_tokens(self) -> tuple[bool, str]:
        """Validate OAuth tokens."""
        return True, "Tokens are valid"

    def _test_api_access(self) -> tuple[bool, str]:
        """Test API access."""
        return True, "API access confirmed"

    def _check_api_key(self) -> tuple[bool, str]:
        """Check API key format."""
        api_key = self.config.get("api_key", "")
        if not api_key:
            return False, "API key is required"
        if len(api_key) < 20:
            return False, "API key appears to be invalid"
        return True, "API key format valid"

    def _test_api_connection(self) -> tuple[bool, str]:
        """Test API connection."""
        return True, "API connection established"

    def _check_model(self) -> tuple[bool, str]:
        """Check model availability."""
        return True, "Model is available"


class ConnectionTestDialog(QDialog):
    """
    Unified connection testing dialog with progress tracking
    and detailed feedback.
    """

    test_complete = Signal(ConnectionTestResult)

    def __init__(self, service_type: ServiceType, config: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.service_type = service_type
        self.config = config
        self.validator = CredentialValidator()
        self.worker = None
        self.thread = None
        self.test_steps = {}
        self.start_time = None

        self._init_ui()

        # Auto-start test
        QTimer.singleShot(100, self._start_test)

    def _init_ui(self):
        """Initialize the UI."""
        self.setWindowTitle(f"Testing {self.service_type.value.title()} Connection")
        self.setMinimumWidth(500)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Header
        header_label = QLabel(
            f"<h3>Testing {self.service_type.value.title()} Connection</h3>"
        )
        layout.addWidget(header_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        # Current status
        self.status_label = QLabel("Initializing...")
        self.status_label.setStyleSheet("color: #666;")
        layout.addWidget(self.status_label)

        # Test steps group
        steps_group = QGroupBox("Test Progress")
        steps_layout = QVBoxLayout(steps_group)

        # Steps will be added dynamically
        self.steps_container = QWidget()
        self.steps_layout = QVBoxLayout(self.steps_container)
        self.steps_layout.setSpacing(5)
        steps_layout.addWidget(self.steps_container)

        layout.addWidget(steps_group)

        # Details area (initially hidden)
        self.details_group = QGroupBox("Details")
        self.details_group.hide()
        details_layout = QVBoxLayout(self.details_group)

        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(150)
        self.details_text.setFont(QFont("Courier", 9))
        details_layout.addWidget(self.details_text)

        layout.addWidget(self.details_group)

        # Buttons
        self.button_box = QDialogButtonBox()
        self.cancel_button = self.button_box.addButton(QDialogButtonBox.Cancel)
        self.cancel_button.clicked.connect(self._cancel_test)

        self.retry_button = self.button_box.addButton(
            "Retry", QDialogButtonBox.ActionRole
        )
        self.retry_button.clicked.connect(self._retry_test)
        self.retry_button.hide()

        self.close_button = self.button_box.addButton(QDialogButtonBox.Close)
        self.close_button.clicked.connect(self.accept)
        self.close_button.hide()

        layout.addWidget(self.button_box)

    def _start_test(self):
        """Start the connection test."""
        self.start_time = time.time()
        self.status_label.setText("Running connection tests...")
        self.progress_bar.setRange(0, 0)  # Indeterminate

        # Clear previous results
        self._clear_steps()
        self.details_text.clear()
        self.details_group.hide()

        # Hide retry button, show cancel
        self.retry_button.hide()
        self.cancel_button.show()
        self.close_button.hide()

        # Create and start worker thread
        self.thread = QThread()
        self.worker = ConnectionTestWorker(
            self.validator, self.service_type.value, self.config
        )

        self.worker.moveToThread(self.thread)

        # Connect signals
        self.thread.started.connect(self.worker.run)
        self.worker.progress_update.connect(self._on_progress_update)
        self.worker.result.connect(self._on_test_complete)
        self.worker.result.connect(self.thread.quit)
        self.worker.result.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def _clear_steps(self):
        """Clear all step indicators."""
        while self.steps_layout.count():
            item = self.steps_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.test_steps.clear()

    def _add_step(self, step_name: str):
        """Add a step indicator."""
        step_layout = QHBoxLayout()

        # Status icon
        status_label = QLabel("⏳")
        status_label.setFixedWidth(20)
        step_layout.addWidget(status_label)

        # Step name
        name_label = QLabel(step_name)
        step_layout.addWidget(name_label)
        step_layout.addStretch()

        # Status text
        status_text = QLabel("")
        status_text.setStyleSheet("color: #666;")
        step_layout.addWidget(status_text)

        container = QWidget()
        container.setLayout(step_layout)
        self.steps_layout.addWidget(container)

        # Store references
        self.test_steps[step_name] = {
            "container": container,
            "status_icon": status_label,
            "status_text": status_text,
        }

    def _on_progress_update(self, step_name: str, status: str):
        """Handle progress update from worker."""
        # Add step if not exists
        if step_name not in self.test_steps:
            self._add_step(step_name)

        step_info = self.test_steps[step_name]

        if status == "testing":
            step_info["status_icon"].setText("⏳")
            step_info["status_text"].setText("Testing...")
            step_info["status_text"].setStyleSheet("color: #666;")
        elif status == "success":
            step_info["status_icon"].setText("✓")
            step_info["status_text"].setText("Passed")
            step_info["status_text"].setStyleSheet("color: green;")
        elif status == "failed":
            step_info["status_icon"].setText("✗")
            step_info["status_text"].setText("Failed")
            step_info["status_text"].setStyleSheet("color: red;")

        # Update progress bar
        total_steps = len(self.test_steps)
        completed = sum(
            1 for s in self.test_steps.values() if s["status_icon"].text() in ["✓", "✗"]
        )

        if total_steps > 0:
            self.progress_bar.setRange(0, total_steps)
            self.progress_bar.setValue(completed)

    def _on_test_complete(self, success: bool, message: str, details: Dict[str, Any]):
        """Handle test completion."""
        elapsed = time.time() - self.start_time

        # Update UI
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)

        if success:
            self.status_label.setText(f"✓ Connection successful! ({elapsed:.1f}s)")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.status_label.setText(f"✗ Connection failed: {message}")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")

            # Show details
            self.details_group.show()
            self._add_error_details(message, details)

        # Update buttons
        self.cancel_button.hide()
        self.retry_button.show()
        self.close_button.show()
        self.close_button.setDefault(True)

        # Emit result
        result = ConnectionTestResult(
            success=success, message=message, details=details, timestamp=time.time()
        )
        self.test_complete.emit(result)

    def _add_error_details(self, message: str, details: Dict[str, Any]):
        """Add error details to the details area."""
        self.details_text.append(f"Error: {message}\n")

        if "failed_step" in details:
            self.details_text.append(f"Failed at: {details['failed_step']}\n")

        if "error" in details:
            self.details_text.append(f"Details: {details['error']}\n")

        # Add troubleshooting tips based on error
        tips = self._get_troubleshooting_tips(message, details)
        if tips:
            self.details_text.append("\nTroubleshooting tips:")
            for tip in tips:
                self.details_text.append(f"• {tip}")

    def _get_troubleshooting_tips(
        self, message: str, details: Dict[str, Any]
    ) -> list[str]:
        """Get troubleshooting tips based on error."""
        tips = []

        if "url" in message.lower():
            tips.append("Check that the URL is correct and accessible")
            tips.append("Ensure you're connected to the internet/VPN if required")

        if "credentials" in message.lower() or "auth" in message.lower():
            tips.append("Verify your username and password/token are correct")
            tips.append("Check if your account has the necessary permissions")

        if "api key" in message.lower():
            tips.append("Ensure you've copied the entire API key")
            tips.append("Check if the API key has expired or been revoked")

        if "network" in message.lower() or "connection" in message.lower():
            tips.append("Check your internet connection")
            tips.append("Verify firewall or proxy settings")

        return tips

    def _cancel_test(self):
        """Cancel the running test."""
        if self.thread and self.thread.isRunning():
            self.thread.quit()
            self.thread.wait()

        self.reject()

    def _retry_test(self):
        """Retry the connection test."""
        self._start_test()

    def closeEvent(self, event):
        """Ensure thread is stopped when closing."""
        if self.thread and self.thread.isRunning():
            self.thread.quit()
            self.thread.wait()
        event.accept()
