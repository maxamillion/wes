"""Service type selector component for Jira configuration."""

from typing import Callable, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from wes.gui.unified_config.types import JiraType


class ServiceSelector(QWidget):
    """
    Smart service selector that helps users choose the correct
    Jira instance type with auto-detection capabilities.
    """

    service_selected = Signal(JiraType)  # type: ignore[misc]

    def __init__(self, parent: Optional[QWidget]=None) -> None:
        super().__init__(parent)
        self.button_group = QButtonGroup()
        self.current_type = JiraType.CLOUD
        self._init_ui()

    def _init_ui(self) -> None:
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Title
        title = QLabel("Select Your Jira Type:")
        title.setStyleSheet("font-weight: bold;")
        layout.addWidget(title)

        # Service options
        self.cloud_radio = self._create_service_option(
            JiraType.CLOUD,
            "Cloud Jira (Atlassian Cloud)",
            "Most common for modern teams\nExample: company.atlassian.net",
            True,  # Default selection
        )

        self.server_radio = self._create_service_option(
            JiraType.SERVER,
            "Server/Data Center",
            "Self-hosted Jira instances\nExample: jira.company.com",
            False,
        )

        self.redhat_radio = self._create_service_option(
            JiraType.REDHAT,
            "Red Hat Jira",
            "For Red Hat employees\nUses Kerberos authentication",
            False,
        )

        # Auto-detect button
        detect_layout = QHBoxLayout()
        detect_layout.addStretch()

        self.detect_button = QPushButton("Auto-Detect from URL")
        self.detect_button.setEnabled(False)  # Enabled when URL is provided
        detect_layout.addWidget(self.detect_button)

        layout.addLayout(detect_layout)

        # Connect signals
        self.button_group.buttonClicked.connect(self._on_selection_changed)

    def _create_service_option(
        self, jira_type: JiraType, title: str, description: str, checked: bool
    ) -> QRadioButton:
        """Create a service option with description."""
        container = QGroupBox()
        container.setStyleSheet(
            """
            QGroupBox {
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 10px;
                margin: 5px 0;
            }
            QGroupBox:hover {
                border-color: #0084ff;
                background-color: #f8f9fa;
            }
        """
        )

        layout = QVBoxLayout(container)

        # Radio button with title
        radio = QRadioButton(title)
        radio.setChecked(checked)
        radio.setStyleSheet("font-weight: bold;")
        # Use ordinal value as ID since QButtonGroup expects integers
        button_id = list(JiraType).index(jira_type)
        self.button_group.addButton(radio, button_id)
        layout.addWidget(radio)

        # Description
        desc_label = QLabel(description)
        desc_label.setStyleSheet("color: #666; margin-left: 20px;")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Make entire container clickable
        container.mousePressEvent = lambda e: radio.setChecked(True)

        if self.layout():
            if self.layout(): self.layout().addWidget(container)

        return radio

    def _on_selection_changed(self, button: QRadioButton) -> None:
        """Handle service type selection change."""
        # Get button ID and convert to JiraType
        button_id = self.button_group.id(button)
        jira_types = list(JiraType)
        if 0 <= button_id < len(jira_types):
            self.current_type = jira_types[button_id]
            self.service_selected.emit(self.current_type)

    def get_service_type(self) -> JiraType:
        """Get currently selected service type."""
        return self.current_type

    def set_service_type(self, jira_type: JiraType) -> None:
        """Set the selected service type."""
        self.current_type = jira_type

        # Update radio buttons
        if jira_type == JiraType.CLOUD:
            self.cloud_radio.setChecked(True)
        elif jira_type == JiraType.SERVER:
            self.server_radio.setChecked(True)
        elif jira_type == JiraType.REDHAT:
            self.redhat_radio.setChecked(True)

    def enable_auto_detect(self, url_callback: Callable[[], str]) -> None:
        """
        Enable auto-detection with a callback to get the current URL.

        Args:
            url_callback: Function that returns the current URL string
        """
        self.detect_button.setEnabled(True)
        self.detect_button.clicked.connect(lambda: self._auto_detect(url_callback()))

    def _auto_detect(self, url: str) -> None:
        """
        Auto-detect Jira type from URL.

        Args:
            url: Jira instance URL
        """
        if not url:
            return

        url_lower = url.lower()

        # Check for cloud instances
        if "atlassian.net" in url_lower:
            self.set_service_type(JiraType.CLOUD)
        # Check for Red Hat instances
        elif any(rh in url_lower for rh in ["redhat.com", "engineering.redhat.com"]):
            self.set_service_type(JiraType.REDHAT)
        # Default to server for other URLs
        elif url_lower.startswith(("http://", "https://")):
            self.set_service_type(JiraType.SERVER)

        # Emit signal for the new selection
        self.service_selected.emit(self.current_type)
