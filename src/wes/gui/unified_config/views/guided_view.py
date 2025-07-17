"""Guided view mode for unified configuration - highlights incomplete items."""

from typing import Any, Dict

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from wes.core.config_manager import ConfigManager
from wes.gui.unified_config.config_pages import (
    GeminiConfigPage,
    JiraConfigPage,
)
from wes.gui.unified_config.types import ServiceType, ValidationResult
from wes.gui.unified_config.utils.config_detector import ConfigDetector


class ServiceCard(QFrame):
    """Card widget for displaying service configuration status."""

    configure_clicked = Signal()

    def __init__(self, service_type: ServiceType, parent=None):
        super().__init__(parent)
        self.service_type = service_type
        self.is_configured = False
        self._init_ui()

    def _init_ui(self):
        """Initialize the UI."""
        self.setFrameStyle(QFrame.Box)
        self.setStyleSheet(
            """
            ServiceCard {
                border: 2px solid #ddd;
                border-radius: 8px;
                background-color: white;
                padding: 15px;
            }
            ServiceCard:hover {
                border-color: #0084ff;
                background-color: #f8f9fa;
            }
        """
        )

        layout = QVBoxLayout(self)

        # Header with icon and title
        header_layout = QHBoxLayout()

        # Status icon
        self.status_icon = QLabel("⚠️")
        self.status_icon.setFont(QFont("", 24))
        header_layout.addWidget(self.status_icon)

        # Title
        titles = {
            ServiceType.JIRA: "Jira Connection",
            ServiceType.GEMINI: "Gemini AI",
        }

        title_label = QLabel(f"<h3>{titles[self.service_type]}</h3>")
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        # Description
        descriptions = {
            ServiceType.JIRA: "Connect to your Jira instance to fetch activity data",
            ServiceType.GEMINI: "Configure Gemini AI for intelligent summarization",
        }

        desc_label = QLabel(descriptions[self.service_type])
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; margin: 10px 0;")
        layout.addWidget(desc_label)

        # Status message
        self.status_message = QLabel("Not configured")
        self.status_message.setStyleSheet("color: #d73502; font-weight: bold;")
        layout.addWidget(self.status_message)

        # Configure button
        self.configure_button = QPushButton("Configure Now")
        self.configure_button.clicked.connect(self.configure_clicked)
        self.configure_button.setStyleSheet(
            """
            QPushButton {
                background-color: #0084ff;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0066cc;
            }
        """
        )
        layout.addWidget(self.configure_button)

    def update_status(self, validation_result: ValidationResult):
        """Update the card based on validation result."""
        self.is_configured = validation_result["is_valid"]

        if self.is_configured:
            self.status_icon.setText("✅")
            self.status_message.setText("Configured")
            self.status_message.setStyleSheet("color: #1e7e34; font-weight: bold;")
            self.configure_button.setText("Modify")
            self.configure_button.setStyleSheet(
                """
                QPushButton {
                    background-color: #6c757d;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #5a6268;
                }
            """
            )
        else:
            self.status_icon.setText("⚠️")
            self.status_message.setText(validation_result["message"])
            self.status_message.setStyleSheet("color: #d73502; font-weight: bold;")
            self.configure_button.setText("Configure Now")
            self.configure_button.setStyleSheet(
                """
                QPushButton {
                    background-color: #0084ff;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #0066cc;
                }
            """
            )


class GuidedView(QWidget):
    """
    Guided view for incomplete configurations.
    Shows which services need setup with clear calls to action.
    """

    # Signals
    configuration_updated = Signal(str, dict)  # service, config
    setup_complete = Signal()

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.config_detector = ConfigDetector()
        self.service_cards = {}
        self.config_dialogs = {}
        self._init_ui()
        self.refresh_status()

    def _init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)

        # Header
        header_label = QLabel(
            "<h2>Complete Your Setup</h2>"
            "<p>Some services need to be configured before you can start creating summaries. "
            "Click on any service below to set it up.</p>"
        )
        header_label.setWordWrap(True)
        layout.addWidget(header_label)

        # Scroll area for service cards
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll_widget = QWidget()
        self.cards_layout = QVBoxLayout(scroll_widget)
        self.cards_layout.setSpacing(15)

        # Create service cards
        for service_type in ServiceType:
            card = ServiceCard(service_type)
            card.configure_clicked.connect(
                lambda s=service_type: self._configure_service(s)
            )
            self.service_cards[service_type] = card
            self.cards_layout.addWidget(card)

        self.cards_layout.addStretch()
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)

        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.refresh_button = QPushButton("Refresh Status")
        self.refresh_button.clicked.connect(self.refresh_status)
        button_layout.addWidget(self.refresh_button)

        self.continue_button = QPushButton("Continue to Settings")
        self.continue_button.clicked.connect(self._check_and_continue)
        self.continue_button.setEnabled(False)
        button_layout.addWidget(self.continue_button)

        layout.addLayout(button_layout)

    def refresh_status(self):
        """Refresh the configuration status for all services."""
        # Get current configuration status
        service_status = self.config_detector.get_service_status(
            self.config_manager.config
        )

        # Update each card
        all_configured = True
        for service_type, status in service_status.items():
            self.service_cards[service_type].update_status(status)
            if not status["is_valid"]:
                all_configured = False

        # Enable continue button if all configured
        self.continue_button.setEnabled(all_configured)

        if all_configured:
            self.continue_button.setText("All Configured! Continue →")
            self.continue_button.setStyleSheet(
                """
                QPushButton {
                    background-color: #28a745;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #218838;
                }
            """
            )

    def _configure_service(self, service_type: ServiceType):
        """Open configuration dialog for a specific service."""
        # Create dialog if not exists
        if service_type not in self.config_dialogs:
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Configure {service_type.value.title()}")
            dialog.setMinimumSize(600, 500)

            layout = QVBoxLayout(dialog)

            # Create appropriate config page
            if service_type == ServiceType.JIRA:
                page = JiraConfigPage(self.config_manager)
            elif service_type == ServiceType.GEMINI:
                page = GeminiConfigPage(self.config_manager)

            layout.addWidget(page)

            # Buttons
            button_layout = QHBoxLayout()
            button_layout.addStretch()

            cancel_button = QPushButton("Cancel")
            cancel_button.clicked.connect(dialog.reject)
            button_layout.addWidget(cancel_button)

            save_button = QPushButton("Save")
            save_button.clicked.connect(
                lambda: self._save_service_config(service_type, page, dialog)
            )
            save_button.setDefault(True)
            button_layout.addWidget(save_button)

            layout.addLayout(button_layout)

            self.config_dialogs[service_type] = (dialog, page)

        # Show dialog
        dialog, page = self.config_dialogs[service_type]
        dialog.exec()

    def _save_service_config(self, service_type: ServiceType, page, dialog):
        """Save configuration for a service."""
        # Validate first
        validation_result = page.validate()
        if not validation_result["is_valid"]:
            QMessageBox.warning(
                dialog, "Invalid Configuration", validation_result["message"]
            )
            return

        # Save configuration
        config = page.save_config()
        service_config = config.get(service_type.value, {})

        # Update config manager using specific service methods
        # Each update method automatically saves the configuration
        if service_type.value == "jira":
            self.config_manager.update_jira_config(**service_config)
        elif service_type.value == "google":
            self.config_manager.update_google_config(**service_config)
        elif service_type.value == "gemini":
            self.config_manager.update_ai_config(**service_config)

        # Emit update signal
        self.configuration_updated.emit(service_type.value, service_config)

        # Close dialog
        dialog.accept()

        # Refresh status
        self.refresh_status()

    def _check_and_continue(self):
        """Check if all services are configured and continue."""
        # Double-check configuration
        service_status = self.config_detector.get_service_status(
            self.config_manager.config
        )

        all_configured = all(status["is_valid"] for status in service_status.values())

        if all_configured:
            self.setup_complete.emit()
        else:
            # Show what's missing
            missing = [
                service.value.title()
                for service, status in service_status.items()
                if not status["is_valid"]
            ]

            QMessageBox.information(
                self,
                "Configuration Incomplete",
                f"Please configure the following services first:\n\n"
                f"• {chr(10).join(missing)}",
            )

    def get_configuration(self) -> Dict[str, Any]:
        """Get the current configuration."""
        return self.config_manager.config
