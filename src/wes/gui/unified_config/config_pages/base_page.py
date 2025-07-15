"""Base class for configuration pages."""

from abc import abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from wes.core.config_manager import ConfigManager
from wes.gui.unified_config.types import ServiceType, ValidationResult
from wes.gui.unified_config.utils.responsive_layout import ResponsiveConfigLayout
from wes.gui.unified_config.utils.dialogs import DialogManager
from wes.gui.unified_config.utils.styles import StyleManager
from wes.gui.unified_config.utils.constants import ConfigConstants


class ConfigPageBase(QWidget):
    """Base class for configuration pages with common functionality."""

    # Signals
    config_changed = Signal(dict)
    validation_complete = Signal(ValidationResult)
    test_connection_requested = Signal()
    page_complete = Signal(bool)  # Emitted when page validation state changes

    # Class attributes to be defined by subclasses
    service_type: ServiceType = None
    page_title: str = ""
    page_icon: str = ""
    page_description: str = ""

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self._is_dirty = False
        self._validation_timer = QTimer()
        self._validation_timer.setSingleShot(True)
        self._validation_timer.timeout.connect(self._perform_validation)

        # Initialize responsive layout manager
        self.responsive_layout = ResponsiveConfigLayout(self)

        # Initialize UI
        self._init_ui()

        # Load current configuration
        self._load_current_config()

        # Connect change tracking
        self._connect_change_tracking()

        # Make the page responsive
        self.responsive_layout.make_responsive()

    def _init_ui(self):
        """Initialize the base UI structure."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Page header
        header_layout = QHBoxLayout()

        # Icon
        if self.page_icon:
            icon_label = QLabel()
            icon = self.style().standardIcon(
                getattr(QStyle, self.page_icon, QStyle.SP_ComputerIcon)
            )
            icon_label.setPixmap(icon.pixmap(32, 32))
            header_layout.addWidget(icon_label)

        # Title and description
        text_layout = QVBoxLayout()
        title_label = QLabel(f"<h2>{self.page_title}</h2>")
        text_layout.addWidget(title_label)

        if self.page_description:
            desc_label = QLabel(self.page_description)
            desc_label.setObjectName("description_label")  # Mark for responsive hiding
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet(StyleManager.get_label_style("secondary"))
            text_layout.addWidget(desc_label)

        header_layout.addLayout(text_layout)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        # Separator
        separator = QLabel()
        separator.setFrameStyle(QLabel.HLine | QLabel.Sunken)
        layout.addWidget(separator)

        # Page-specific content (implemented by subclasses)
        self._setup_page_ui(layout)

        # Don't add stretch - let content determine height for better scrolling
        # layout.addStretch()  # Removed to allow proper scrolling

    @abstractmethod
    def _setup_page_ui(self, parent_layout: QVBoxLayout):
        """Setup page-specific UI. Must be implemented by subclasses."""
        pass

    def _load_current_config(self):
        """Load current configuration into UI."""
        config = self.config_manager.config
        self.load_config(config)

    @abstractmethod
    def load_config(self, config: Dict[str, Any]) -> None:
        """Load configuration into UI fields."""
        pass

    @abstractmethod
    def save_config(self) -> Dict[str, Any]:
        """Extract configuration from UI fields."""
        pass

    @abstractmethod
    def validate(self) -> ValidationResult:
        """Validate current configuration."""
        pass

    def test_connection(self) -> None:
        """Test connection with current settings."""
        # First validate
        validation_result = self.validate()
        if not validation_result["is_valid"]:
            DialogManager.show_warning(
                self, "Invalid Configuration", validation_result["message"]
            )
            return

        # Show connection test dialog
        self._show_connection_test_dialog()

    def _show_connection_test_dialog(self):
        """Show unified connection test dialog."""
        from wes.gui.unified_config.components.connection_tester import (
            ConnectionTestDialog,
        )

        config = self.save_config()
        dialog = ConnectionTestDialog(
            self.service_type, config.get(self.service_type.value, {}), self
        )
        dialog.test_complete.connect(self._handle_test_result)
        dialog.exec()

    def _handle_test_result(self, result: Dict[str, Any]):
        """Handle connection test result."""
        validation_result = ValidationResult(
            is_valid=result["success"],
            message=result["message"],
            service=self.service_type,
            details=result.get("details", {}),
        )
        self.validation_complete.emit(validation_result)

        # Update connection status if we have a label for it
        if hasattr(self, "connection_status_label"):
            self._update_connection_status(result["success"], result["message"])

    def _update_connection_status(self, success: bool, message: str):
        """Update connection status display."""
        if success:
            self.connection_status_label.setText("✓ Connected")
            self.connection_status_label.setStyleSheet(
                StyleManager.get_label_style("success")
            )
        else:
            self.connection_status_label.setText("✗ Not Connected")
            self.connection_status_label.setStyleSheet(
                StyleManager.get_label_style("danger")
            )
            self.connection_status_label.setToolTip(message)

    @abstractmethod
    def get_basic_fields(self) -> List[QWidget]:
        """Return list of basic/required field widgets."""
        pass

    @abstractmethod
    def get_advanced_fields(self) -> List[QWidget]:
        """Return list of advanced/optional field widgets."""
        pass

    def is_dirty(self) -> bool:
        """Check if configuration has unsaved changes."""
        return self._is_dirty

    def mark_dirty(self):
        """Mark configuration as having unsaved changes."""
        if not self._is_dirty:
            self._is_dirty = True
            current_config = self.save_config()
            self.config_changed.emit(current_config)

            # Schedule validation
            self._validation_timer.stop()
            self._validation_timer.start(
                ConfigConstants.VALIDATION_DELAY_MS
            )  # Validate after delay

    def mark_clean(self):
        """Mark configuration as saved."""
        self._is_dirty = False

    def _connect_change_tracking(self):
        """Connect change tracking to form fields."""
        # This should be called by subclasses after creating their widgets
        pass

    def _perform_validation(self):
        """Perform validation and emit result."""
        result = self.validate()
        self.page_complete.emit(result["is_valid"])

    # Utility methods for creating common UI elements

    def _create_labeled_input(
        self, label: str, password: bool = False
    ) -> Tuple[QLabel, QLineEdit]:
        """Create a labeled input field."""
        label_widget = QLabel(label)
        input_widget = QLineEdit()

        if password:
            input_widget.setEchoMode(QLineEdit.Password)

        # Connect change tracking
        input_widget.textChanged.connect(self.mark_dirty)

        return label_widget, input_widget

    def _create_checkbox(self, text: str, checked: bool = False) -> QCheckBox:
        """Create a checkbox."""
        checkbox = QCheckBox(text)
        checkbox.setChecked(checked)
        checkbox.stateChanged.connect(self.mark_dirty)
        return checkbox

    def _create_spinbox(
        self, label: str, value: int = 0, min_val: int = 0, max_val: int = 9999
    ) -> Tuple[QLabel, QSpinBox]:
        """Create a labeled spinbox."""
        label_widget = QLabel(label)
        spinbox = QSpinBox()
        spinbox.setRange(min_val, max_val)
        spinbox.setValue(value)
        spinbox.valueChanged.connect(self.mark_dirty)
        return label_widget, spinbox

    def _create_group_box(self, title: str, collapsible: bool = False) -> QGroupBox:
        """Create a group box, optionally collapsible."""
        if collapsible:
            # Use responsive layout utility for collapsible sections
            # Note: caller must add content widget separately
            return self.responsive_layout.create_collapsible_section(
                title, QWidget(), start_collapsed=True
            )
        else:
            group = QGroupBox(title)
            return group

    def _create_test_button(self) -> QPushButton:
        """Create a test connection button."""
        button = QPushButton("Test Connection")
        button.clicked.connect(self.test_connection)
        return button
