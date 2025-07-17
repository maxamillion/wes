"""Direct view mode for unified configuration - tabbed interface."""

from typing import Any, Dict, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QScrollArea,
    QStyle,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from wes.core.config_manager import ConfigManager
from wes.gui.unified_config.config_pages import (
    GeminiConfigPage,
    JiraConfigPage,
)
from wes.gui.unified_config.types import ServiceType


class DirectView(QWidget):
    """
    Direct configuration view with tabbed interface for all settings.
    Shows validation status on each tab.
    """

    # Signals
    configuration_changed = Signal()  # type: ignore[misc]
    validation_state_changed = Signal(bool)  # all_valid

    def __init__(self, config_manager: ConfigManager, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.config_manager = config_manager
        self.pages = {}
        self.validation_states = {}
        self._init_ui()
        self._connect_signals()

    def _init_ui(self) -> None:
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)

        # Create tabs for each service
        self._create_service_tabs()

        # Add application settings tab
        self._create_app_settings_tab()

        # Add security settings tab
        self._create_security_tab()

        layout.addWidget(self.tab_widget)

        # Update tab icons based on validation
        self._update_tab_icons()

    def _wrap_in_scroll_area(self, widget) -> None:
        """Wrap a widget in a scroll area for better small screen support."""
        scroll_area = QScrollArea()
        scroll_area.setWidget(widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Style the scroll area
        scroll_area.setStyleSheet(
            """
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                width: 12px;
                background: #f0f0f0;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #c0c0c0;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #a0a0a0;
            }
            QScrollBar:horizontal {
                height: 12px;
                background: #f0f0f0;
                border-radius: 6px;
            }
            QScrollBar::handle:horizontal {
                background: #c0c0c0;
                border-radius: 6px;
                min-width: 20px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #a0a0a0;
            }
        """
        )

        return scroll_area

    def _create_service_tabs(self) -> None:
        """Create tabs for each service configuration."""
        # Jira tab
        self.jira_page = JiraConfigPage(self.config_manager)
        self.pages[ServiceType.JIRA] = self.jira_page
        jira_scroll = self._wrap_in_scroll_area(self.jira_page)
        jira_index = self.tab_widget.addTab(jira_scroll, "Jira")

        # Gemini tab
        self.gemini_page = GeminiConfigPage(self.config_manager)
        self.pages[ServiceType.GEMINI] = self.gemini_page
        gemini_scroll = self._wrap_in_scroll_area(self.gemini_page)
        gemini_index = self.tab_widget.addTab(gemini_scroll, "Gemini AI")

    def _create_app_settings_tab(self) -> None:
        """Create application settings tab."""
        from wes.gui.unified_config.config_pages.app_settings_page import (
            AppSettingsPage,
        )

        self.app_page = AppSettingsPage(self.config_manager)
        app_scroll = self._wrap_in_scroll_area(self.app_page)
        app_index = self.tab_widget.addTab(app_scroll, "Application")

    def _create_security_tab(self) -> None:
        """Create security settings tab."""
        from wes.gui.unified_config.config_pages.security_page import SecurityPage

        self.security_page = SecurityPage(self.config_manager)
        security_scroll = self._wrap_in_scroll_area(self.security_page)
        security_index = self.tab_widget.addTab(security_scroll, "Security")

    def _connect_signals(self) -> None:
        """Connect signals from all pages."""
        # Connect configuration changes
        for page in self.pages.values():
            page.config_changed.connect(self._on_config_changed)
            page.page_complete.connect(
                lambda valid, p=page: self._on_page_validated(p, valid)
            )
            page.validation_complete.connect(self._on_validation_complete)

        # Connect app and security pages if they exist
        if hasattr(self, "app_page"):
            self.app_page.config_changed.connect(self._on_config_changed)

        if hasattr(self, "security_page"):
            self.security_page.config_changed.connect(self._on_config_changed)

    def _on_config_changed(self, config: Dict[str, Any]) -> None:
        """Handle configuration change from any page."""
        self.configuration_changed.emit()

    def _on_page_validated(self, page, is_valid: bool) -> None:
        """Handle page validation state change."""
        # Find which service this page belongs to
        for service, p in self.pages.items():
            if p == page:
                self.validation_states[service] = is_valid
                break

        # Update tab icon
        self._update_tab_icons()

        # Check if all required services are valid
        all_valid = all(
            self.validation_states.get(service, False)
            for service in [ServiceType.JIRA, ServiceType.GEMINI]
        )
        self.validation_state_changed.emit(all_valid)

    def _on_validation_complete(self, result: Dict[str, Any]) -> None:
        """Handle validation completion with detailed result."""
        # Update connection status on the specific tab
        service = result.get("service")
        if service in self.pages:
            page = self.pages[service]
            # Page will handle updating its own UI

    def _update_tab_icons(self) -> None:
        """Update tab icons based on validation state."""
        style = self.style()

        # Icons for different states
        valid_icon = style.standardIcon(QStyle.SP_DialogYesButton)
        invalid_icon = style.standardIcon(QStyle.SP_DialogCancelButton)
        warning_icon = style.standardIcon(QStyle.SP_MessageBoxWarning)

        # Update service tabs
        for i, (service, page) in enumerate(self.pages.items()):
            # Get validation state
            validation_result = page.validate()

            if validation_result["is_valid"]:
                self.tab_widget.setTabIcon(i, valid_icon)
                self.tab_widget.setTabToolTip(i, "Configuration complete")
            elif validation_result["details"].get("configured", False):
                # Configured but invalid
                self.tab_widget.setTabIcon(i, invalid_icon)
                self.tab_widget.setTabToolTip(i, validation_result["message"])
            else:
                # Not configured
                self.tab_widget.setTabIcon(i, warning_icon)
                self.tab_widget.setTabToolTip(i, "Configuration required")

    def get_configuration(self) -> Dict[str, Any]:
        """
        Get the complete configuration from all pages.

        Returns:
            Dictionary with all service configurations
        """
        config = {}

        # Get config from each service page
        for service, page in self.pages.items():
            service_config = page.save_config()
            config.update(service_config)

        # Get app settings
        if hasattr(self, "app_page"):
            app_config = self.app_page.save_config()
            config.update(app_config)

        # Get security settings
        if hasattr(self, "security_page"):
            security_config = self.security_page.save_config()
            config.update(security_config)

        return config

    def validate_all(self) -> Dict[ServiceType, Dict[str, Any]]:
        """
        Validate all service configurations.

        Returns:
            Dictionary mapping services to their validation results
        """
        results = {}

        for service, page in self.pages.items():
            results[service] = page.validate()

        return results

    def show_service(self, service: ServiceType) -> None:
        """
        Show a specific service tab.

        Args:
            service: The service to display
        """
        if service in self.pages:
            index = list(self.pages.keys()).index(service)
            self.tab_widget.setCurrentIndex(index)

    def refresh(self) -> None:
        """Refresh all pages with current configuration."""
        # Each page will reload from config manager
        for page in self.pages.values():
            page._load_current_config()

        if hasattr(self, "app_page"):
            self.app_page._load_current_config()

        if hasattr(self, "security_page"):
            self.security_page._load_current_config()

        # Update validation states
        self._update_tab_icons()
