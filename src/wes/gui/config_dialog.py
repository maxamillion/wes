"""Configuration dialog for the Executive Summary Tool."""

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core.config_manager import ConfigManager
from ..integrations.redhat_jira_client import is_redhat_jira
from ..utils.exceptions import ConfigurationError
from ..utils.logging_config import get_logger


class ConfigDialog(QDialog):
    """Configuration dialog for application settings."""

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)

        self.config_manager = config_manager
        self.logger = get_logger(__name__)

        self.init_ui()
        self.load_configuration()

    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Configuration")
        self.setGeometry(200, 200, 600, 500)
        self.setModal(True)

        # Main layout
        layout = QVBoxLayout(self)

        # Tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # Create tabs
        self.create_jira_tab()
        self.create_ai_tab()
        self.create_app_tab()
        self.create_security_tab()

        # Button box
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Apply
        )
        button_box.accepted.connect(self.accept_configuration)
        button_box.rejected.connect(self.reject)
        button_box.button(QDialogButtonBox.Apply).clicked.connect(
            self.apply_configuration
        )

        layout.addWidget(button_box)

        # Test connections button
        test_layout = QHBoxLayout()
        self.test_connections_btn = QPushButton("Test All Connections")
        self.test_connections_btn.clicked.connect(self.test_connections)
        test_layout.addWidget(self.test_connections_btn)
        test_layout.addStretch()

        layout.insertLayout(-1, test_layout)

    def create_jira_tab(self):
        """Create Jira configuration tab."""
        jira_tab = QWidget()
        self.tab_widget.addTab(jira_tab, "Jira")

        layout = QVBoxLayout(jira_tab)

        # Connection settings
        connection_group = QGroupBox("Connection Settings")
        connection_layout = QFormLayout(connection_group)

        self.jira_url_edit = QLineEdit()
        self.jira_url_edit.setPlaceholderText("https://issues.redhat.com")
        self.jira_url_edit.textChanged.connect(self._on_jira_url_changed)
        connection_layout.addRow("Jira URL:", self.jira_url_edit)

        self.jira_username_edit = QLineEdit()
        self.jira_username_edit.setPlaceholderText("your.email@company.com")
        self.jira_username_label = QLabel("Username:")
        connection_layout.addRow(self.jira_username_label, self.jira_username_edit)

        self.jira_token_edit = QLineEdit()
        self.jira_token_edit.setEchoMode(QLineEdit.Password)
        self.jira_token_edit.setPlaceholderText("Your Jira API token")
        connection_layout.addRow("API Token:", self.jira_token_edit)

        layout.addWidget(connection_group)

        # Default settings
        defaults_group = QGroupBox("Default Settings")
        defaults_layout = QFormLayout(defaults_group)

        self.default_project_edit = QLineEdit()
        self.default_project_edit.setPlaceholderText("PROJECT")
        defaults_layout.addRow("Default Project:", self.default_project_edit)

        self.default_query_edit = QTextEdit()
        self.default_query_edit.setPlaceholderText(
            "project = PROJECT AND updated >= -1w"
        )
        self.default_query_edit.setMaximumHeight(100)
        defaults_layout.addRow("Default JQL Query:", self.default_query_edit)

        layout.addWidget(defaults_group)

        # Performance settings
        performance_group = QGroupBox("Performance Settings")
        performance_layout = QFormLayout(performance_group)

        self.jira_rate_limit_spin = QSpinBox()
        self.jira_rate_limit_spin.setRange(1, 1000)
        self.jira_rate_limit_spin.setValue(100)
        self.jira_rate_limit_spin.setSuffix(" requests/min")
        performance_layout.addRow("Rate Limit:", self.jira_rate_limit_spin)

        self.jira_timeout_spin = QSpinBox()
        self.jira_timeout_spin.setRange(5, 120)
        self.jira_timeout_spin.setValue(30)
        self.jira_timeout_spin.setSuffix(" seconds")
        performance_layout.addRow("Timeout:", self.jira_timeout_spin)

        layout.addWidget(performance_group)

        layout.addStretch()

    def create_ai_tab(self):
        """Create AI configuration tab."""
        ai_tab = QWidget()
        self.tab_widget.addTab(ai_tab, "AI")

        layout = QVBoxLayout(ai_tab)

        # API settings
        api_group = QGroupBox("API Settings")
        api_layout = QFormLayout(api_group)

        self.gemini_api_key_edit = QLineEdit()
        self.gemini_api_key_edit.setEchoMode(QLineEdit.Password)
        self.gemini_api_key_edit.setPlaceholderText("Your Google Gemini API key")
        api_layout.addRow("Gemini API Key:", self.gemini_api_key_edit)

        self.ai_model_combo = QComboBox()
        self.ai_model_combo.addItems(["gemini-2.5-flash", "gemini-2.5-pro"])
        api_layout.addRow("Model:", self.ai_model_combo)

        layout.addWidget(api_group)

        # Generation settings
        generation_group = QGroupBox("Generation Settings")
        generation_layout = QFormLayout(generation_group)

        self.temperature_spin = QSpinBox()
        self.temperature_spin.setRange(0, 100)
        self.temperature_spin.setValue(70)
        self.temperature_spin.setSuffix("%")
        generation_layout.addRow("Temperature:", self.temperature_spin)

        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(100, 8192)
        self.max_tokens_spin.setValue(2048)
        generation_layout.addRow("Max Tokens:", self.max_tokens_spin)

        self.ai_rate_limit_spin = QSpinBox()
        self.ai_rate_limit_spin.setRange(1, 1000)
        self.ai_rate_limit_spin.setValue(60)
        self.ai_rate_limit_spin.setSuffix(" requests/min")
        generation_layout.addRow("Rate Limit:", self.ai_rate_limit_spin)

        layout.addWidget(generation_group)

        # Custom prompt
        prompt_group = QGroupBox("Custom Prompt Template")
        prompt_layout = QVBoxLayout(prompt_group)

        self.custom_prompt_edit = QTextEdit()
        self.custom_prompt_edit.setPlaceholderText(
            "Enter custom prompt template. Use {activity_data} placeholder for data insertion."
        )
        prompt_layout.addWidget(self.custom_prompt_edit)

        layout.addWidget(prompt_group)

        layout.addStretch()

    def create_app_tab(self):
        """Create application configuration tab."""
        app_tab = QWidget()
        self.tab_widget.addTab(app_tab, "Application")

        layout = QVBoxLayout(app_tab)

        # UI settings
        ui_group = QGroupBox("User Interface")
        ui_layout = QFormLayout(ui_group)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["System", "Light", "Dark"])
        ui_layout.addRow("Theme:", self.theme_combo)

        self.language_combo = QComboBox()
        self.language_combo.addItems(["English", "Spanish", "French", "German"])
        ui_layout.addRow("Language:", self.language_combo)

        layout.addWidget(ui_group)

        # Behavior settings
        behavior_group = QGroupBox("Behavior")
        behavior_layout = QVBoxLayout(behavior_group)

        self.auto_save_check = QCheckBox("Auto-save configuration")
        self.auto_save_check.setChecked(True)
        behavior_layout.addWidget(self.auto_save_check)

        self.check_updates_check = QCheckBox("Check for updates automatically")
        self.check_updates_check.setChecked(True)
        behavior_layout.addWidget(self.check_updates_check)

        layout.addWidget(behavior_group)

        # Logging settings
        logging_group = QGroupBox("Logging")
        logging_layout = QFormLayout(logging_group)

        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.log_level_combo.setCurrentText("INFO")
        logging_layout.addRow("Log Level:", self.log_level_combo)

        layout.addWidget(logging_group)

        # Privacy settings
        privacy_group = QGroupBox("Privacy")
        privacy_layout = QVBoxLayout(privacy_group)

        self.telemetry_check = QCheckBox(
            "Enable telemetry (helps improve the application)"
        )
        privacy_layout.addWidget(self.telemetry_check)

        layout.addWidget(privacy_group)

        layout.addStretch()

    def create_security_tab(self):
        """Create security configuration tab."""
        security_tab = QWidget()
        self.tab_widget.addTab(security_tab, "Security")

        layout = QVBoxLayout(security_tab)

        # Encryption settings
        encryption_group = QGroupBox("Encryption")
        encryption_layout = QVBoxLayout(encryption_group)

        self.encryption_enabled_check = QCheckBox("Enable credential encryption")
        self.encryption_enabled_check.setChecked(True)
        encryption_layout.addWidget(self.encryption_enabled_check)

        key_rotation_layout = QFormLayout()
        self.key_rotation_spin = QSpinBox()
        self.key_rotation_spin.setRange(30, 365)
        self.key_rotation_spin.setValue(90)
        self.key_rotation_spin.setSuffix(" days")
        key_rotation_layout.addRow("Key Rotation Period:", self.key_rotation_spin)

        encryption_layout.addLayout(key_rotation_layout)

        layout.addWidget(encryption_group)

        # Session settings
        session_group = QGroupBox("Session Management")
        session_layout = QFormLayout(session_group)

        self.session_timeout_spin = QSpinBox()
        self.session_timeout_spin.setRange(5, 480)
        self.session_timeout_spin.setValue(60)
        self.session_timeout_spin.setSuffix(" minutes")
        session_layout.addRow("Session Timeout:", self.session_timeout_spin)

        self.max_login_attempts_spin = QSpinBox()
        self.max_login_attempts_spin.setRange(1, 10)
        self.max_login_attempts_spin.setValue(5)
        session_layout.addRow("Max Login Attempts:", self.max_login_attempts_spin)

        layout.addWidget(session_group)

        # Audit settings
        audit_group = QGroupBox("Audit Logging")
        audit_layout = QVBoxLayout(audit_group)

        self.audit_logging_check = QCheckBox("Enable audit logging")
        self.audit_logging_check.setChecked(True)
        audit_layout.addWidget(self.audit_logging_check)

        layout.addWidget(audit_group)

        layout.addStretch()

    def _on_jira_url_changed(self, text: str):
        """Handle Jira URL change to update username guidance."""
        if not text:
            self._reset_jira_username_guidance()
            return

        try:
            from urllib.parse import urlparse

            parsed = urlparse(text.lower())

            if "atlassian.net" in parsed.netloc:
                # Jira Cloud - requires email
                self.jira_username_label.setText("Email Address:")
                self.jira_username_edit.setPlaceholderText("your.email@company.com")
                self.jira_username_edit.setToolTip(
                    "Jira Cloud requires your email address as the username"
                )
            elif is_redhat_jira(text):
                # Red Hat Jira - specific username format
                self.jira_username_label.setText("Red Hat Username:")
                self.jira_username_edit.setPlaceholderText("your-redhat-username")
                self.jira_username_edit.setToolTip(
                    "Enter your Red Hat Jira username (typically your Red Hat employee ID or LDAP username)"
                )
            else:
                # On-premise - flexible username
                self.jira_username_label.setText("Username:")
                self.jira_username_edit.setPlaceholderText(
                    "username or email@company.com"
                )
                self.jira_username_edit.setToolTip(
                    "Enter your Jira username (may be email or username depending on your configuration)"
                )
        except Exception:
            self._reset_jira_username_guidance()

    def _reset_jira_username_guidance(self):
        """Reset Jira username guidance to default."""
        self.jira_username_label.setText("Username:")
        self.jira_username_edit.setPlaceholderText("your.email@company.com")
        self.jira_username_edit.setToolTip("")

    def load_configuration(self):
        """Load current configuration into UI."""
        try:
            config = self.config_manager.get_config()

            # Jira configuration
            jira_config = config.jira
            self.jira_url_edit.setText(jira_config.url)
            self.jira_username_edit.setText(jira_config.username)
            self.default_project_edit.setText(jira_config.default_project)
            self.default_query_edit.setPlainText(jira_config.default_query)
            self.jira_rate_limit_spin.setValue(jira_config.rate_limit)
            self.jira_timeout_spin.setValue(jira_config.timeout)

            # AI configuration
            ai_config = config.ai
            model_index = self.ai_model_combo.findText(ai_config.model_name)
            if model_index >= 0:
                self.ai_model_combo.setCurrentIndex(model_index)

            self.temperature_spin.setValue(int(ai_config.temperature * 100))
            self.max_tokens_spin.setValue(ai_config.max_tokens)
            self.ai_rate_limit_spin.setValue(ai_config.rate_limit)
            self.custom_prompt_edit.setPlainText(ai_config.custom_prompt)

            # App configuration
            app_config = config.app
            theme_index = self.theme_combo.findText(app_config.theme.title())
            if theme_index >= 0:
                self.theme_combo.setCurrentIndex(theme_index)

            self.auto_save_check.setChecked(app_config.auto_save)
            self.check_updates_check.setChecked(app_config.check_updates)

            log_level_index = self.log_level_combo.findText(app_config.log_level)
            if log_level_index >= 0:
                self.log_level_combo.setCurrentIndex(log_level_index)

            self.telemetry_check.setChecked(app_config.telemetry_enabled)

            # Security configuration
            security_config = config.security
            self.encryption_enabled_check.setChecked(security_config.encryption_enabled)
            self.key_rotation_spin.setValue(security_config.key_rotation_days)
            self.session_timeout_spin.setValue(security_config.session_timeout_minutes)
            self.max_login_attempts_spin.setValue(security_config.max_login_attempts)
            self.audit_logging_check.setChecked(security_config.audit_logging)

            # Load stored credentials
            jira_token = self.config_manager.retrieve_credential("jira", "api_token")
            if jira_token:
                self.jira_token_edit.setText(jira_token)

            gemini_key = self.config_manager.retrieve_credential("ai", "gemini_api_key")
            if gemini_key:
                self.gemini_api_key_edit.setText(gemini_key)

            # Update Jira username guidance based on URL
            self._on_jira_url_changed(self.jira_url_edit.text())

            self.logger.info("Configuration loaded into dialog")

        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            QMessageBox.warning(
                self, "Configuration Error", f"Failed to load configuration: {e}"
            )

    def save_configuration(self):
        """Save configuration from UI."""
        try:
            # Update Jira configuration
            self.config_manager.update_jira_config(
                url=self.jira_url_edit.text(),
                username=self.jira_username_edit.text(),
                default_project=self.default_project_edit.text(),
                default_query=self.default_query_edit.toPlainText(),
                rate_limit=self.jira_rate_limit_spin.value(),
                timeout=self.jira_timeout_spin.value(),
            )

            # Update AI configuration
            self.config_manager.update_ai_config(
                model_name=self.ai_model_combo.currentText(),
                temperature=self.temperature_spin.value() / 100.0,
                max_tokens=self.max_tokens_spin.value(),
                rate_limit=self.ai_rate_limit_spin.value(),
                custom_prompt=self.custom_prompt_edit.toPlainText(),
            )

            # Store credentials
            if self.jira_token_edit.text():
                self.config_manager.store_credential(
                    "jira", "api_token", self.jira_token_edit.text()
                )

            if self.gemini_api_key_edit.text():
                self.config_manager.store_credential(
                    "ai", "gemini_api_key", self.gemini_api_key_edit.text()
                )

            self.logger.info("Configuration saved from dialog")

        except Exception as e:
            self.logger.error(f"Failed to save configuration: {e}")
            raise ConfigurationError(f"Failed to save configuration: {e}")

    def test_connections(self):
        """Test all API connections."""
        # This would implement actual connection testing
        QMessageBox.information(
            self, "Connection Test", "Connection testing feature coming soon."
        )

    def apply_configuration(self):
        """Apply configuration without closing dialog."""
        try:
            self.save_configuration()
            QMessageBox.information(
                self, "Configuration Applied", "Configuration saved successfully."
            )
        except Exception as e:
            QMessageBox.critical(self, "Configuration Error", str(e))

    def accept_configuration(self):
        """Accept and save configuration."""
        try:
            self.save_configuration()
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Configuration Error", str(e))

    def validate_configuration(self) -> bool:
        """Validate current configuration."""
        try:
            # Basic validation
            if not self.jira_url_edit.text():
                QMessageBox.warning(self, "Validation Error", "Jira URL is required.")
                return False

            if not self.jira_username_edit.text():
                QMessageBox.warning(
                    self, "Validation Error", "Jira username is required."
                )
                return False

            # Additional validation for Jira Cloud
            jira_url = self.jira_url_edit.text().strip()
            jira_username = self.jira_username_edit.text().strip()

            if jira_url and jira_username:
                try:
                    import re
                    from urllib.parse import urlparse

                    parsed = urlparse(jira_url.lower())
                    if "atlassian.net" in parsed.netloc:
                        email_pattern = (
                            r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
                        )
                        if not re.match(email_pattern, jira_username):
                            QMessageBox.warning(
                                self,
                                "Validation Error",
                                "Jira Cloud requires a valid email address as username.",
                            )
                            return False
                    elif is_redhat_jira(jira_url):
                        # Red Hat Jira username validation
                        if len(jira_username.strip()) < 3:
                            QMessageBox.warning(
                                self,
                                "Validation Error",
                                "Red Hat Jira username must be at least 3 characters.",
                            )
                            return False
                        username_pattern = r"^[a-zA-Z0-9._-]+$"
                        if not re.match(username_pattern, jira_username.strip()):
                            QMessageBox.warning(
                                self,
                                "Validation Error",
                                "Red Hat Jira username should contain only letters, "
                                "numbers, dots, underscores, and hyphens.",
                            )
                            return False
                except Exception as e:
                    self.logger.debug(f"Exception during validation: {e}")
                    # Continue with basic validation

            if (
                not self.jira_token_edit.text()
                and not self.config_manager.retrieve_credential("jira", "api_token")
            ):
                QMessageBox.warning(
                    self, "Validation Error", "Jira API token is required."
                )
                return False

            if (
                not self.gemini_api_key_edit.text()
                and not self.config_manager.retrieve_credential("ai", "gemini_api_key")
            ):
                QMessageBox.warning(
                    self, "Validation Error", "Gemini API key is required."
                )
                return False

            return True

        except Exception as e:
            self.logger.error(f"Configuration validation failed: {e}")
            QMessageBox.critical(self, "Validation Error", str(e))
            return False
