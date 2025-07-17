"""Unified configuration dialog that adapts based on user context."""

from typing import Any, Dict, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QStyle,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QCloseEvent

from wes.core.config_manager import ConfigManager
from wes.gui.unified_config.types import ConfigState, ServiceType, UIMode
from wes.gui.unified_config.utils.config_detector import ConfigDetector


class UnifiedConfigDialog(QDialog):
    """
    Adaptive configuration dialog that intelligently switches between
    wizard mode for first-time users and direct mode for returning users.
    """

    # Signals
    configuration_complete = Signal(dict)  # type: ignore[misc]
    mode_changed = Signal(UIMode)  # type: ignore[misc]

    def __init__(self, config_manager: ConfigManager, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.config_manager = config_manager
        self.config_detector = ConfigDetector()
        self.current_mode: Optional[UIMode] = None
        self.dirty = False

        # Track which pages have been validated
        self.page_validation_state = {}

        # Initialize UI components
        self._init_ui()

        # Detect and set appropriate mode
        self._detect_and_set_mode()

    def _init_ui(self) -> None:
        """Initialize the UI components."""
        self.setWindowTitle("WES Configuration")

        # Get available screen geometry for responsive sizing
        screen = self.screen()
        if screen:
            available_rect = screen.availableGeometry()

            # Set responsive size (80% of available space, with min/max constraints)
            default_width = min(900, int(available_rect.width() * 0.8))
            default_height = min(700, int(available_rect.height() * 0.8))

            self.resize(default_width, default_height)

            # Center on screen
            self.move(
                available_rect.center().x() - default_width // 2,
                available_rect.center().y() - default_height // 2,
            )
        else:
            # Fallback if screen detection fails
            self.resize(900, 700)

        # Set more reasonable minimum size for small screens
        self.setMinimumSize(600, 400)

        # Apply dialog styling
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowMaximizeButtonHint
            | Qt.WindowMinimizeButtonHint
        )

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header area with mode indicator
        header_widget = QWidget()
        header_widget.setObjectName("configHeader")
        header_widget.setStyleSheet(
            """
            #configHeader {
                background-color: #f0f0f0;
                border-bottom: 1px solid #d0d0d0;
            }
        """
        )

        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(20, 10, 20, 10)

        self.mode_icon = QLabel()
        header_layout.addWidget(self.mode_icon)

        self.mode_label = QLabel()
        self.mode_label.setObjectName("modeLabel")
        self.mode_label.setStyleSheet(
            """
            #modeLabel {
                font-size: 16px;
                font-weight: bold;
            }
        """
        )
        header_layout.addWidget(self.mode_label)
        header_layout.addStretch()

        # Mode switch button (only shown in certain modes)
        self.mode_switch_button = QPushButton()
        self.mode_switch_button.hide()
        header_layout.addWidget(self.mode_switch_button)

        layout.addWidget(header_widget)

        # Content area - Stacked widget for different modes
        self.stack = QStackedWidget()
        self.stack.setContentsMargins(0, 0, 0, 0)

        # Create mode-specific widgets (lazy loading)
        self.wizard_widget: Optional[QWidget] = None
        self.guided_widget: Optional[QWidget] = None
        self.direct_widget: Optional[QWidget] = None

        # Add placeholder widgets - actual widgets created on demand
        self.stack.addWidget(QWidget())  # Index 0: Wizard
        self.stack.addWidget(QWidget())  # Index 1: Guided
        self.stack.addWidget(QWidget())  # Index 2: Direct

        layout.addWidget(self.stack)

        # Button area
        button_widget = QWidget()
        button_widget.setObjectName("buttonArea")
        button_widget.setStyleSheet(
            """
            #buttonArea {
                background-color: #f0f0f0;
                border-top: 1px solid #d0d0d0;
            }
        """
        )

        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(20, 10, 20, 10)

        self.button_box = QDialogButtonBox()
        button_layout.addWidget(self.button_box)

        layout.addWidget(button_widget)

        # Connect dialog button box standard buttons
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def _detect_and_set_mode(self) -> None:
        """Detect configuration state and set appropriate UI mode."""
        config_state = self.config_detector.detect_state(self.config_manager.config)

        if config_state == ConfigState.EMPTY:
            self.set_mode(UIMode.WIZARD)
        elif config_state == ConfigState.INCOMPLETE:
            self.set_mode(UIMode.GUIDED)
        else:
            self.set_mode(UIMode.DIRECT)

    def set_mode(self, mode: UIMode) -> None:
        """Switch to specified UI mode."""
        if mode == self.current_mode:
            return

        self.current_mode = mode
        self.mode_changed.emit(mode)

        # Update UI for new mode
        if mode == UIMode.WIZARD:
            self._setup_wizard_mode()
        elif mode == UIMode.GUIDED:
            self._setup_guided_mode()
        else:
            self._setup_direct_mode()

        self._update_buttons_for_mode()

    def _setup_wizard_mode(self) -> None:
        """Setup wizard mode UI."""
        # Set header
        icon = self.style().standardIcon(QStyle.SP_DialogYesButton)
        self.mode_icon.setPixmap(icon.pixmap(24, 24))
        self.mode_label.setText("Welcome! Let's set up WES together.")

        # Show skip button
        self.mode_switch_button.setText("Skip to Advanced Mode")
        self.mode_switch_button.clicked.connect(lambda: self.set_mode(UIMode.DIRECT))
        self.mode_switch_button.show()

        # Create wizard widget if needed
        if self.wizard_widget is None:
            from wes.gui.unified_config.views.wizard_view import WizardView

            self.wizard_widget = WizardView(self.config_manager, self)
            self.wizard_widget.wizard_complete.connect(self._on_wizard_complete)
            self.wizard_widget.page_changed.connect(self._on_wizard_page_changed)
            widget_to_remove = self.stack.widget(0)
            if widget_to_remove:
                widget_to_remove.deleteLater()
                self.stack.removeWidget(widget_to_remove)
            self.stack.insertWidget(0, self.wizard_widget)

        self.stack.setCurrentIndex(0)

    def _setup_guided_mode(self) -> None:
        """Setup guided mode UI."""
        # Set header
        icon = self.style().standardIcon(QStyle.SP_MessageBoxWarning)
        self.mode_icon.setPixmap(icon.pixmap(24, 24))
        self.mode_label.setText("Some services need configuration to continue.")

        # Show mode switch
        self.mode_switch_button.setText("Switch to Advanced Mode")
        self.mode_switch_button.clicked.connect(lambda: self.set_mode(UIMode.DIRECT))
        self.mode_switch_button.show()

        # Create guided widget if needed
        if self.guided_widget is None:
            from wes.gui.unified_config.views.guided_view import GuidedView

            self.guided_widget = GuidedView(self.config_manager, self)
            self.guided_widget.configuration_updated.connect(self._on_config_updated)
            self.guided_widget.setup_complete.connect(self._on_guided_complete)
            widget_to_remove = self.stack.widget(1)
            if widget_to_remove:
                widget_to_remove.deleteLater()
                self.stack.removeWidget(widget_to_remove)
            self.stack.insertWidget(1, self.guided_widget)

        # Update guided view with current state
        if self.guided_widget is not None:
            self.guided_widget.refresh_status()
        self.stack.setCurrentIndex(1)

    def _setup_direct_mode(self) -> None:
        """Setup direct mode UI."""
        # Set header
        icon = self.style().standardIcon(QStyle.SP_ComputerIcon)
        self.mode_icon.setPixmap(icon.pixmap(24, 24))
        self.mode_label.setText("Settings")

        # Hide mode switch in direct mode
        self.mode_switch_button.hide()

        # Create direct widget if needed
        if self.direct_widget is None:
            from wes.gui.unified_config.views.direct_view import DirectView

            self.direct_widget = DirectView(self.config_manager, self)
            self.direct_widget.configuration_changed.connect(self._on_config_changed)
            self.direct_widget.validation_state_changed.connect(
                self._on_validation_changed
            )
            widget_to_remove = self.stack.widget(2)
            if widget_to_remove:
                widget_to_remove.deleteLater()
                self.stack.removeWidget(widget_to_remove)
            self.stack.insertWidget(2, self.direct_widget)

        self.stack.setCurrentIndex(2)

    def _update_buttons_for_mode(self) -> None:
        """Update dialog buttons based on current mode."""
        self.button_box.clear()

        if self.current_mode == UIMode.WIZARD:
            # Wizard mode: Cancel only (wizard manages its own navigation)
            self.button_box.addButton(QDialogButtonBox.Cancel)

        elif self.current_mode == UIMode.GUIDED:
            # Guided mode: Complete Later, Continue Setup
            later_btn = QPushButton("Complete Later")
            later_btn.clicked.connect(self._complete_later)
            self.button_box.addButton(later_btn, QDialogButtonBox.ActionRole)

            self.button_box.addButton(QDialogButtonBox.Cancel)

        else:
            # Direct mode: Apply, Save, Cancel
            self.button_box.addButton(QDialogButtonBox.Apply)
            self.button_box.addButton(QDialogButtonBox.Save)
            self.button_box.addButton(QDialogButtonBox.Cancel)

            # Connect apply button
            apply_btn = self.button_box.button(QDialogButtonBox.Apply)
            apply_btn.clicked.connect(self._apply_changes)

            # Connect save button
            save_btn = self.button_box.button(QDialogButtonBox.Save)
            save_btn.clicked.connect(self._save_and_close)

    def _apply_changes(self) -> None:
        """Apply configuration changes without closing dialog."""
        if self._save_configuration():
            QMessageBox.information(
                self, "Success", "Configuration saved successfully!"
            )
            self.dirty = False

            # Check if we should switch modes
            new_state = self.config_detector.detect_state(self.config_manager.config)
            if new_state == ConfigState.COMPLETE and self.current_mode == UIMode.GUIDED:
                self.set_mode(UIMode.DIRECT)

    def _save_and_close(self) -> None:
        """Save configuration and close dialog."""
        if self._save_configuration():
            self.accept()

    def _save_configuration(self) -> bool:
        """Save current configuration."""
        # Get configuration from current view
        current_widget = self.stack.currentWidget()
        if hasattr(current_widget, "get_configuration"):
            config = current_widget.get_configuration()

            # Validate configuration
            if self._validate_configuration(config):
                # Update config manager using specific service methods
                # Each update method automatically saves the configuration
                for service, service_config in config.items():
                    if service == "jira":
                        self.config_manager.update_jira_config(**service_config)
                    elif service == "google":
                        self.config_manager.update_google_config(**service_config)
                    elif service == "gemini":
                        self.config_manager.update_ai_config(**service_config)

                # Emit signal
                self.configuration_complete.emit(config)
                return True

        return False

    def _validate_configuration(self, config: Dict[str, Any]) -> bool:
        """Validate configuration before saving."""
        # In direct mode, we allow partial configs
        if self.current_mode == UIMode.DIRECT:
            return True

        # In wizard/guided mode, check completeness
        errors = []
        service_status = self.config_detector.get_service_status(config)

        for service, status in service_status.items():
            if not status["is_valid"] and status["details"]["configured"]:
                errors.append(f"{service.value.title()}: {status['message']}")

        if errors:
            QMessageBox.warning(
                self,
                "Configuration Incomplete",
                "Please complete the following:\n\n" + "\n".join(errors),
            )
            return False

        return True

    def _complete_later(self) -> None:
        """Handle 'Complete Later' action in guided mode."""
        reply = QMessageBox.question(
            self,
            "Incomplete Configuration",
            "Some services are not configured. You can complete the setup later from the Settings menu.\n\n"
            "Continue without completing setup?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.accept()

    def _on_wizard_complete(self) -> None:
        """Handle wizard completion."""
        self._save_configuration()
        self.accept()

    def _on_wizard_page_changed(self, page_index: int) -> None:
        """Handle wizard page change."""
        # Update header based on wizard progress
        if self.wizard_widget is not None and hasattr(self.wizard_widget, "get_page_info"):
            info = self.wizard_widget.get_page_info(page_index)
            if info:
                self.mode_label.setText(info.get("description", "Configuration"))

    def _on_guided_complete(self) -> None:
        """Handle guided setup completion."""
        # Switch to direct mode
        self.set_mode(UIMode.DIRECT)

    def _on_config_updated(self, service: str, config: Dict[str, Any]) -> None:
        """Handle configuration update from guided view."""
        self.dirty = True

        # Call the appropriate service-specific update method
        if service == "jira":
            self.config_manager.update_jira_config(**config)
        elif service == "google":
            self.config_manager.update_google_config(**config)
        elif service == "gemini" or service == "ai":
            self.config_manager.update_ai_config(**config)
        else:
            raise ValueError(f"Unknown service type: {service}")

    def _on_config_changed(self) -> None:
        """Handle configuration change in direct mode."""
        self.dirty = True

    def _on_validation_changed(self, all_valid: bool) -> None:
        """Handle validation state change."""
        # Enable/disable save button based on validation
        if self.current_mode == UIMode.DIRECT:
            save_btn = self.button_box.button(QDialogButtonBox.Save)
            if save_btn:
                save_btn.setEnabled(all_valid)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Handle dialog close event."""
        if self.dirty:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Do you want to save before closing?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )

            if reply == QMessageBox.StandardButton.Save:
                if self._save_configuration():
                    event.accept()
                else:
                    event.ignore()
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
