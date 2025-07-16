"""LDAP configuration dialog for Red Hat integration."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
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
)

from ..core.config_manager import ConfigManager
from ..integrations.redhat_ldap_client import RedHatLDAPClient
from ..utils.logging_config import get_logger


class LDAPConfigDialog(QDialog):
    """Dialog for configuring LDAP settings."""

    config_saved = Signal()

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.logger = get_logger(__name__)
        self.ldap_config = config_manager.get_ldap_config()

        self.setWindowTitle("LDAP Configuration")
        self.setModal(True)
        self.resize(600, 500)

        self._setup_ui()
        self._load_config()

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout()

        # Enable/Disable checkbox
        self.enable_checkbox = QCheckBox("Enable LDAP Integration")
        self.enable_checkbox.stateChanged.connect(self._on_enable_changed)
        layout.addWidget(self.enable_checkbox)

        # Connection settings group
        self.connection_group = QGroupBox("Connection Settings")
        connection_layout = QFormLayout()

        self.server_url_edit = QLineEdit()
        self.server_url_edit.setPlaceholderText("ldaps://ldap.corp.redhat.com")
        connection_layout.addRow("LDAP Server URL:", self.server_url_edit)

        self.base_dn_edit = QLineEdit()
        self.base_dn_edit.setPlaceholderText("ou=users,dc=redhat,dc=com")
        connection_layout.addRow("Base DN:", self.base_dn_edit)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 300)
        self.timeout_spin.setSuffix(" seconds")
        connection_layout.addRow("Timeout:", self.timeout_spin)

        self.ssl_checkbox = QCheckBox("Use SSL/TLS")
        connection_layout.addRow("Security:", self.ssl_checkbox)

        self.validate_certs_checkbox = QCheckBox("Validate Certificates")
        connection_layout.addRow("", self.validate_certs_checkbox)

        self.connection_group.setLayout(connection_layout)
        layout.addWidget(self.connection_group)

        # Query settings group
        self.query_group = QGroupBox("Query Settings")
        query_layout = QFormLayout()

        self.max_depth_spin = QSpinBox()
        self.max_depth_spin.setRange(1, 10)
        self.max_depth_spin.setToolTip(
            "Maximum depth to traverse in organizational hierarchy"
        )
        query_layout.addRow("Max Hierarchy Depth:", self.max_depth_spin)

        self.cache_ttl_spin = QSpinBox()
        self.cache_ttl_spin.setRange(0, 1440)
        self.cache_ttl_spin.setSuffix(" minutes")
        self.cache_ttl_spin.setToolTip("How long to cache LDAP query results")
        query_layout.addRow("Cache TTL:", self.cache_ttl_spin)

        self.query_group.setLayout(query_layout)
        layout.addWidget(self.query_group)

        # Test connection button
        test_layout = QHBoxLayout()
        self.test_button = QPushButton("Test Connection")
        self.test_button.clicked.connect(self._test_connection)
        test_layout.addWidget(self.test_button)

        self.test_result = QLabel()
        test_layout.addWidget(self.test_result)
        test_layout.addStretch()

        layout.addLayout(test_layout)

        # Test results area
        self.test_details = QTextEdit()
        self.test_details.setReadOnly(True)
        self.test_details.setMaximumHeight(150)
        self.test_details.setPlaceholderText("Connection test results will appear here")
        layout.addWidget(self.test_details)

        # Dialog buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self._save_config)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self.setLayout(layout)

    def _load_config(self):
        """Load current configuration into UI."""
        self.enable_checkbox.setChecked(self.ldap_config.enabled)
        self.server_url_edit.setText(self.ldap_config.server_url)
        self.base_dn_edit.setText(self.ldap_config.base_dn)
        self.timeout_spin.setValue(self.ldap_config.timeout)
        self.ssl_checkbox.setChecked(self.ldap_config.use_ssl)
        self.validate_certs_checkbox.setChecked(self.ldap_config.validate_certs)
        self.max_depth_spin.setValue(self.ldap_config.max_hierarchy_depth)
        self.cache_ttl_spin.setValue(self.ldap_config.cache_ttl_minutes)

        self._on_enable_changed()

    def _on_enable_changed(self):
        """Handle enable/disable checkbox state change."""
        enabled = self.enable_checkbox.isChecked()
        self.connection_group.setEnabled(enabled)
        self.query_group.setEnabled(enabled)
        self.test_button.setEnabled(enabled)

    def _test_connection(self):
        """Test LDAP connection with current settings."""
        import asyncio

        self.test_button.setEnabled(False)
        self.test_result.setText("Testing...")
        self.test_details.clear()

        # Get current settings from UI
        server_url = self.server_url_edit.text().strip()
        base_dn = self.base_dn_edit.text().strip()
        timeout = self.timeout_spin.value()
        use_ssl = self.ssl_checkbox.isChecked()
        validate_certs = self.validate_certs_checkbox.isChecked()

        if not server_url:
            self.test_result.setText("❌ Error: Server URL is required")
            self.test_button.setEnabled(True)
            return

        async def test_ldap():
            """Async function to test LDAP connection."""
            client = RedHatLDAPClient(
                server_url=server_url,
                base_dn=base_dn,
                timeout=timeout,
                use_ssl=use_ssl,
                validate_certs=validate_certs,
            )

            details = []
            try:
                # Test connection
                await client.connect()
                details.append("✅ Successfully connected to LDAP server")

                # Get connection info
                info = client.get_connection_info()
                details.append(f"Server: {info['server_url']}")
                details.append(f"Base DN: {info['base_dn']}")
                details.append(f"SSL: {info['use_ssl']}")

                # Try a simple search to validate
                valid = await client.validate_connection()
                if valid:
                    details.append("✅ LDAP queries are working")
                else:
                    details.append("⚠️ Connection established but queries may fail")

                await client.disconnect()
                return True, "\n".join(details)

            except Exception as e:
                details.append(f"❌ Connection failed: {str(e)}")
                return False, "\n".join(details)

        # Run the async test
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            success, details = loop.run_until_complete(test_ldap())

            if success:
                self.test_result.setText("✅ Connection successful")
                self.test_result.setStyleSheet("color: green")
            else:
                self.test_result.setText("❌ Connection failed")
                self.test_result.setStyleSheet("color: red")

            self.test_details.setText(details)

        except Exception as e:
            self.test_result.setText("❌ Test failed")
            self.test_result.setStyleSheet("color: red")
            self.test_details.setText(f"Error running test: {str(e)}")

        finally:
            self.test_button.setEnabled(True)

    def _save_config(self):
        """Save LDAP configuration."""
        try:
            # Validate inputs
            if self.enable_checkbox.isChecked():
                server_url = self.server_url_edit.text().strip()
                if not server_url:
                    QMessageBox.warning(
                        self, "Validation Error", "LDAP server URL is required"
                    )
                    return

                if not server_url.startswith(("ldap://", "ldaps://")):
                    QMessageBox.warning(
                        self,
                        "Validation Error",
                        "LDAP server URL must start with ldap:// or ldaps://",
                    )
                    return

            # Update configuration
            self.config_manager.update_ldap_config(
                enabled=self.enable_checkbox.isChecked(),
                server_url=self.server_url_edit.text().strip(),
                base_dn=self.base_dn_edit.text().strip(),
                timeout=self.timeout_spin.value(),
                use_ssl=self.ssl_checkbox.isChecked(),
                validate_certs=self.validate_certs_checkbox.isChecked(),
                max_hierarchy_depth=self.max_depth_spin.value(),
                cache_ttl_minutes=self.cache_ttl_spin.value(),
            )

            self.logger.info("LDAP configuration saved")
            self.config_saved.emit()

            QMessageBox.information(
                self, "Success", "LDAP configuration saved successfully"
            )

            self.accept()

        except Exception as e:
            self.logger.error(f"Failed to save LDAP configuration: {e}")
            QMessageBox.critical(
                self, "Error", f"Failed to save configuration: {str(e)}"
            )
