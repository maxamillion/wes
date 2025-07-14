"""
Unified Configuration Dialog - Implementation Example

This example demonstrates the key architectural patterns for the unified
configuration component that adapts based on user context.
"""

from enum import Enum, auto
from typing import Optional, Dict, Any, List
from PySide6.QtCore import Qt, Signal, QThread, QTimer
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QPushButton, QLabel, QTabWidget, QScrollArea, QGroupBox,
    QDialogButtonBox, QMessageBox
)
from PySide6.QtGui import QIcon, QPixmap

from wes.core.config_manager import ConfigManager
from wes.core.credentials_validator import CredentialValidator


class UIMode(Enum):
    """Configuration UI presentation modes"""
    WIZARD = auto()      # First-time setup with guided flow
    GUIDED = auto()      # Incomplete config with highlighted missing items  
    DIRECT = auto()      # Full access to all settings in tabbed interface


class ConfigState(Enum):
    """Configuration validation states"""
    EMPTY = auto()       # No configuration exists
    INCOMPLETE = auto()  # Partial configuration
    COMPLETE = auto()    # All required fields present
    INVALID = auto()     # Configuration exists but validation failed


class UnifiedConfigDialog(QDialog):
    """
    Adaptive configuration dialog that intelligently switches between
    wizard mode for first-time users and direct mode for returning users.
    """
    
    # Signals
    configuration_complete = Signal(dict)
    mode_changed = Signal(UIMode)
    
    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.validator = CredentialValidator()
        self.current_mode = None
        self.dirty = False
        
        # Initialize UI components
        self._init_ui()
        
        # Detect and set appropriate mode
        self._detect_and_set_mode()
        
    def _init_ui(self):
        """Initialize the UI components"""
        self.setWindowTitle("WES Configuration")
        self.setMinimumSize(800, 600)
        
        # Main layout
        layout = QVBoxLayout(self)
        
        # Mode indicator (shows current mode to user)
        self.mode_label = QLabel()
        self.mode_label.setObjectName("modeLabel")
        layout.addWidget(self.mode_label)
        
        # Stacked widget for different modes
        self.stack = QStackedWidget()
        
        # Create mode-specific widgets
        self.wizard_widget = self._create_wizard_widget()
        self.guided_widget = self._create_guided_widget()
        self.direct_widget = self._create_direct_widget()
        
        self.stack.addWidget(self.wizard_widget)
        self.stack.addWidget(self.guided_widget)
        self.stack.addWidget(self.direct_widget)
        
        layout.addWidget(self.stack)
        
        # Dialog buttons
        self.button_box = QDialogButtonBox()
        self._update_buttons_for_mode()
        layout.addWidget(self.button_box)
        
    def _detect_and_set_mode(self) -> None:
        """Detect configuration state and set appropriate UI mode"""
        config_state = self._analyze_config_state()
        
        if config_state == ConfigState.EMPTY:
            self.set_mode(UIMode.WIZARD)
        elif config_state == ConfigState.INCOMPLETE:
            self.set_mode(UIMode.GUIDED)
        else:
            self.set_mode(UIMode.DIRECT)
            
    def _analyze_config_state(self) -> ConfigState:
        """Analyze current configuration completeness"""
        config = self.config_manager.config
        
        # Check if any configuration exists
        if not config or all(not v for v in config.values()):
            return ConfigState.EMPTY
            
        # Check required fields for each service
        required_complete = {
            'jira': self._check_jira_config(config.get('jira', {})),
            'google': self._check_google_config(config.get('google', {})),
            'gemini': self._check_gemini_config(config.get('gemini', {}))
        }
        
        if all(required_complete.values()):
            return ConfigState.COMPLETE
        elif any(required_complete.values()):
            return ConfigState.INCOMPLETE
        else:
            return ConfigState.INVALID
            
    def set_mode(self, mode: UIMode) -> None:
        """Switch to specified UI mode"""
        if mode == self.current_mode:
            return
            
        self.current_mode = mode
        self.mode_changed.emit(mode)
        
        # Update UI for new mode
        if mode == UIMode.WIZARD:
            self.stack.setCurrentWidget(self.wizard_widget)
            self.mode_label.setText("🚀 Welcome! Let's set up WES together.")
        elif mode == UIMode.GUIDED:
            self.stack.setCurrentWidget(self.guided_widget)
            self.mode_label.setText("⚠️ Some services need configuration.")
            self._update_guided_view()
        else:
            self.stack.setCurrentWidget(self.direct_widget)
            self.mode_label.setText("⚙️ Settings")
            
        self._update_buttons_for_mode()
        
    def _create_wizard_widget(self) -> QWidget:
        """Create wizard mode widget with step-by-step flow"""
        from wes.gui.unified_config.wizard_flow import WizardFlow
        return WizardFlow(self.config_manager, self)
        
    def _create_guided_widget(self) -> QWidget:
        """Create guided mode widget highlighting incomplete items"""
        from wes.gui.unified_config.guided_view import GuidedView
        return GuidedView(self.config_manager, self)
        
    def _create_direct_widget(self) -> QWidget:
        """Create direct mode widget with tabbed interface"""
        from wes.gui.unified_config.direct_view import DirectView
        return DirectView(self.config_manager, self)
        
    def _update_buttons_for_mode(self) -> None:
        """Update dialog buttons based on current mode"""
        self.button_box.clear()
        
        if self.current_mode == UIMode.WIZARD:
            # Wizard mode: Skip, Back, Next, Cancel
            skip_btn = QPushButton("Skip Wizard")
            skip_btn.clicked.connect(lambda: self.set_mode(UIMode.DIRECT))
            self.button_box.addButton(skip_btn, QDialogButtonBox.ActionRole)
            
            self.button_box.addButton(QDialogButtonBox.Cancel)
            # Back/Next buttons managed by WizardFlow
            
        elif self.current_mode == UIMode.GUIDED:
            # Guided mode: Complete Later, Continue Setup
            later_btn = QPushButton("Complete Later")
            later_btn.clicked.connect(self.accept)
            self.button_box.addButton(later_btn, QDialogButtonBox.ActionRole)
            
            continue_btn = QPushButton("Continue Setup")
            continue_btn.setDefault(True)
            continue_btn.clicked.connect(self._continue_guided_setup)
            self.button_box.addButton(continue_btn, QDialogButtonBox.ActionRole)
            
        else:
            # Direct mode: Apply, Save, Cancel
            self.button_box.addButton(QDialogButtonBox.Apply)
            self.button_box.addButton(QDialogButtonBox.Save)
            self.button_box.addButton(QDialogButtonBox.Cancel)
            
            self.button_box.button(QDialogButtonBox.Apply).clicked.connect(
                self._apply_changes
            )
            self.button_box.button(QDialogButtonBox.Save).clicked.connect(
                self._save_and_close
            )
            
    def _apply_changes(self) -> None:
        """Apply configuration changes without closing dialog"""
        if self._validate_and_save():
            QMessageBox.information(self, "Success", "Configuration saved successfully!")
            self.dirty = False
            
    def _save_and_close(self) -> None:
        """Save configuration and close dialog"""
        if self._validate_and_save():
            self.accept()
            
    def _validate_and_save(self) -> bool:
        """Validate and save current configuration"""
        # Collect config from current view
        current_widget = self.stack.currentWidget()
        config = current_widget.get_configuration()
        
        # Validate configuration
        validation_results = self._validate_configuration(config)
        
        if all(result[0] for result in validation_results.values()):
            # Save configuration
            self.config_manager.update_config(config)
            self.configuration_complete.emit(config)
            return True
        else:
            # Show validation errors
            self._show_validation_errors(validation_results)
            return False
            
    def _validate_configuration(self, config: Dict[str, Any]) -> Dict[str, tuple]:
        """Validate configuration for all services"""
        results = {}
        
        # Use existing CredentialValidator for consistency
        if 'jira' in config:
            results['jira'] = self.validator.validate_jira_credentials(
                config['jira']
            )
            
        if 'google' in config:
            results['google'] = self.validator.validate_google_credentials(
                config['google']
            )
            
        if 'gemini' in config:
            results['gemini'] = self.validator.validate_gemini_credentials(
                config['gemini']
            )
            
        return results
        
    def _show_validation_errors(self, results: Dict[str, tuple]) -> None:
        """Display validation errors to user"""
        errors = []
        for service, (is_valid, message) in results.items():
            if not is_valid:
                errors.append(f"{service.title()}: {message}")
                
        if errors:
            QMessageBox.warning(
                self,
                "Configuration Invalid", 
                "Please fix the following issues:\n\n" + "\n".join(errors)
            )
            
    def closeEvent(self, event):
        """Handle dialog close event"""
        if self.dirty:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Do you want to save before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )
            
            if reply == QMessageBox.Save:
                if self._validate_and_save():
                    event.accept()
                else:
                    event.ignore()
            elif reply == QMessageBox.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


class ConfigPageBase(QWidget):
    """Base class for configuration pages with common functionality"""
    
    # Signals
    config_changed = Signal(dict)
    validation_complete = Signal(bool, str)  # is_valid, message
    test_connection_requested = Signal()
    
    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.validator = CredentialValidator()
        self._init_ui()
        self._load_current_config()
        
    def _init_ui(self):
        """Initialize UI - to be implemented by subclasses"""
        raise NotImplementedError
        
    def _load_current_config(self):
        """Load current configuration into UI"""
        self.load_config(self.config_manager.config)
        
    def load_config(self, config: dict) -> None:
        """Load configuration into UI fields"""
        raise NotImplementedError
        
    def save_config(self) -> dict:
        """Extract configuration from UI fields"""
        raise NotImplementedError
        
    def validate(self) -> tuple[bool, str]:
        """Validate current configuration"""
        raise NotImplementedError
        
    def test_connection(self) -> None:
        """Test connection with current settings"""
        raise NotImplementedError
        
    def get_basic_fields(self) -> List[QWidget]:
        """Return list of basic/required field widgets"""
        raise NotImplementedError
        
    def get_advanced_fields(self) -> List[QWidget]:
        """Return list of advanced/optional field widgets"""
        raise NotImplementedError
        
    def show_connection_test_dialog(self):
        """Show unified connection test dialog"""
        from wes.gui.unified_config.components.connection_tester import ConnectionTestDialog
        
        config = self.save_config()
        dialog = ConnectionTestDialog(self.service_type, config, self)
        dialog.test_complete.connect(self._handle_test_result)
        dialog.exec()
        
    def _handle_test_result(self, success: bool, message: str):
        """Handle connection test result"""
        self.validation_complete.emit(success, message)
        
        # Update UI to show connection status
        if hasattr(self, 'connection_status_label'):
            if success:
                self.connection_status_label.setText("✓ Connected")
                self.connection_status_label.setStyleSheet("color: green;")
            else:
                self.connection_status_label.setText("✗ Connection Failed")
                self.connection_status_label.setStyleSheet("color: red;")


# Example of how existing pages would be refactored
class JiraConfigPage(ConfigPageBase):
    """Jira configuration page with adaptive UI"""
    
    service_type = "jira"
    
    def _init_ui(self):
        """Initialize Jira configuration UI"""
        layout = QVBoxLayout(self)
        
        # Basic settings group
        basic_group = QGroupBox("Connection Details")
        basic_layout = QVBoxLayout(basic_group)
        
        # Service type selector
        from wes.gui.unified_config.components.service_selector import ServiceSelector
        self.service_selector = ServiceSelector()
        self.service_selector.service_selected.connect(self._on_service_selected)
        basic_layout.addWidget(self.service_selector)
        
        # URL input
        self.url_input = self._create_validated_input("Jira URL:", "url")
        basic_layout.addWidget(self.url_input)
        
        # Credentials
        self.username_input = self._create_validated_input("Username:", "username")
        self.api_token_input = self._create_validated_input("API Token:", "password")
        basic_layout.addWidget(self.username_input)
        basic_layout.addWidget(self.api_token_input)
        
        # Connection test button and status
        test_layout = QHBoxLayout()
        self.test_button = QPushButton("Test Connection")
        self.test_button.clicked.connect(self.test_connection)
        test_layout.addWidget(self.test_button)
        
        self.connection_status_label = QLabel("")
        test_layout.addWidget(self.connection_status_label)
        test_layout.addStretch()
        
        basic_layout.addLayout(test_layout)
        layout.addWidget(basic_group)
        
        # Advanced settings (collapsible)
        self.advanced_group = self._create_advanced_group()
        layout.addWidget(self.advanced_group)
        
        layout.addStretch()
        
    def _create_advanced_group(self) -> QGroupBox:
        """Create collapsible advanced settings group"""
        group = QGroupBox("▶ Advanced Settings")
        group.setCheckable(True)
        group.setChecked(False)  # Collapsed by default
        
        layout = QVBoxLayout(group)
        
        # SSL verification
        self.verify_ssl = self._create_checkbox("Verify SSL Certificates", True)
        layout.addWidget(self.verify_ssl)
        
        # Timeout setting
        self.timeout_input = self._create_spinbox("Connection Timeout (seconds):", 30)
        layout.addWidget(self.timeout_input)
        
        # Max results
        self.max_results_input = self._create_spinbox("Max Results:", 100)
        layout.addWidget(self.max_results_input)
        
        return group
        
    def load_config(self, config: dict) -> None:
        """Load Jira configuration into UI"""
        jira_config = config.get('jira', {})
        
        # Set service type
        service_type = jira_config.get('type', 'cloud')
        self.service_selector.set_service_type(service_type)
        
        # Set basic fields
        self.url_input.setText(jira_config.get('url', ''))
        self.username_input.setText(jira_config.get('username', ''))
        self.api_token_input.setText(jira_config.get('api_token', ''))
        
        # Set advanced fields
        self.verify_ssl.setChecked(jira_config.get('verify_ssl', True))
        self.timeout_input.setValue(jira_config.get('timeout', 30))
        self.max_results_input.setValue(jira_config.get('max_results', 100))
        
    def save_config(self) -> dict:
        """Extract Jira configuration from UI"""
        return {
            'jira': {
                'type': self.service_selector.get_service_type(),
                'url': self.url_input.text().strip(),
                'username': self.username_input.text().strip(),
                'api_token': self.api_token_input.text().strip(),
                'verify_ssl': self.verify_ssl.isChecked(),
                'timeout': self.timeout_input.value(),
                'max_results': self.max_results_input.value()
            }
        }
        
    def validate(self) -> tuple[bool, str]:
        """Validate Jira configuration"""
        config = self.save_config()['jira']
        
        # Check required fields
        if not config['url']:
            return False, "Jira URL is required"
        if not config['username']:
            return False, "Username is required"
        if not config['api_token']:
            return False, "API Token is required"
            
        # Validate URL format
        if not config['url'].startswith(('http://', 'https://')):
            return False, "Jira URL must start with http:// or https://"
            
        return True, "Configuration valid"
        
    def test_connection(self) -> None:
        """Test Jira connection"""
        # First validate
        is_valid, message = self.validate()
        if not is_valid:
            QMessageBox.warning(self, "Invalid Configuration", message)
            return
            
        # Show connection test dialog
        self.show_connection_test_dialog()
        
    def get_basic_fields(self) -> List[QWidget]:
        """Return basic field widgets"""
        return [
            self.service_selector,
            self.url_input,
            self.username_input,
            self.api_token_input,
            self.test_button
        ]
        
    def get_advanced_fields(self) -> List[QWidget]:
        """Return advanced field widgets"""
        return [
            self.verify_ssl,
            self.timeout_input,
            self.max_results_input
        ]