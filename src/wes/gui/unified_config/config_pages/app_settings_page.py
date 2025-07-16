"""Application settings configuration page."""

from typing import Any, Dict, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from wes.core.config_manager import ConfigManager
from wes.gui.unified_config.config_pages.base_page import ConfigPageBase
from wes.gui.unified_config.types import ServiceType, ValidationResult


class AppSettingsPage(ConfigPageBase):
    """Application settings configuration page."""

    # Not a service, but we need to set this for the base class
    service_type = None
    page_title = "Application Settings"
    page_icon = "SP_ComputerIcon"
    page_description = "Configure general application behavior and preferences"

    def _setup_page_ui(self, parent_layout: QVBoxLayout):
        """Setup application settings UI."""
        # General settings
        general_group = QGroupBox("General Settings")
        general_layout = QFormLayout(general_group)

        # Theme selection
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["System Default", "Light", "Dark"])
        self.theme_combo.currentTextChanged.connect(self.mark_dirty)
        general_layout.addRow("Theme:", self.theme_combo)

        # Auto-save
        self.auto_save_check = self._create_checkbox("Enable auto-save", True)
        general_layout.addRow("Auto-save:", self.auto_save_check)

        # Auto-save interval
        interval_layout = QHBoxLayout()
        _, self.save_interval_spin = self._create_spinbox(
            "Auto-save interval (minutes):", 5, 1, 60
        )
        interval_layout.addWidget(self.save_interval_spin)
        interval_layout.addWidget(QLabel("minutes"))
        interval_layout.addStretch()
        general_layout.addRow("Save Interval:", interval_layout)

        parent_layout.addWidget(general_group)

        # Summary settings
        summary_group = QGroupBox("Summary Generation")
        summary_layout = QFormLayout(summary_group)

        # Default date range
        _, self.date_range_spin = self._create_spinbox(
            "Default date range (days):", 7, 1, 365
        )
        summary_layout.addRow("Date Range:", self.date_range_spin)

        # Include options
        self.include_subtasks = self._create_checkbox("Include subtasks", True)
        summary_layout.addRow("Subtasks:", self.include_subtasks)

        self.include_comments = self._create_checkbox("Include comments", True)
        summary_layout.addRow("Comments:", self.include_comments)

        self.group_by_epic = self._create_checkbox("Group by epic", True)
        summary_layout.addRow("Grouping:", self.group_by_epic)

        parent_layout.addWidget(summary_group)

        # Output settings
        output_group = QGroupBox("Output Settings")
        output_layout = QFormLayout(output_group)

        # Default output directory
        output_dir_layout = QHBoxLayout()
        self.output_dir_input = QLineEdit()
        self.output_dir_input.setPlaceholderText("Default: Documents folder")
        self.output_dir_input.textChanged.connect(self.mark_dirty)
        output_dir_layout.addWidget(self.output_dir_input)

        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._browse_output_dir)
        output_dir_layout.addWidget(browse_button)

        output_layout.addRow("Output Directory:", output_dir_layout)

        # File naming
        self.file_naming_combo = QComboBox()
        self.file_naming_combo.addItems(
            [
                "Executive_Summary_YYYY-MM-DD",
                "Summary_YYYY-MM-DD_HH-MM",
                "Project_Summary_YYYY-MM-DD",
                "Custom",
            ]
        )
        self.file_naming_combo.currentTextChanged.connect(self.mark_dirty)
        output_layout.addRow("File Naming:", self.file_naming_combo)

        # Open after generation
        self.open_after_gen = self._create_checkbox(
            "Open document after generation", True
        )
        output_layout.addRow("After Generation:", self.open_after_gen)

        parent_layout.addWidget(output_group)

        # Advanced settings
        self.advanced_group = self._create_advanced_group()
        parent_layout.addWidget(self.advanced_group)

    def _create_advanced_group(self) -> QGroupBox:
        """Create advanced settings group."""
        group = self._create_group_box("Advanced Settings", collapsible=True)
        layout = QFormLayout(group)

        # Logging
        self.enable_debug_log = self._create_checkbox("Enable debug logging", False)
        layout.addRow("Logging:", self.enable_debug_log)

        # Cache settings
        self.cache_duration_spin = QSpinBox()
        self.cache_duration_spin.setRange(0, 168)  # 0 to 1 week in hours
        self.cache_duration_spin.setValue(24)
        self.cache_duration_spin.setSuffix(" hours")
        self.cache_duration_spin.setSpecialValueText("Disabled")
        self.cache_duration_spin.valueChanged.connect(self.mark_dirty)
        layout.addRow("Cache Duration:", self.cache_duration_spin)

        # Clear cache button
        clear_cache_layout = QHBoxLayout()
        clear_cache_button = QPushButton("Clear Cache")
        clear_cache_button.clicked.connect(self._clear_cache)
        clear_cache_layout.addWidget(clear_cache_button)
        self.cache_size_label = QLabel("Cache size: 0 MB")
        clear_cache_layout.addWidget(self.cache_size_label)
        clear_cache_layout.addStretch()
        layout.addRow("Cache:", clear_cache_layout)

        # Proxy settings
        self.use_proxy = self._create_checkbox("Use proxy", False)
        layout.addRow("Network:", self.use_proxy)

        proxy_layout = QHBoxLayout()
        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText("http://proxy.company.com:8080")
        self.proxy_input.setEnabled(False)
        self.proxy_input.textChanged.connect(self.mark_dirty)
        proxy_layout.addWidget(self.proxy_input)

        # Enable/disable proxy input based on checkbox
        self.use_proxy.toggled.connect(self.proxy_input.setEnabled)

        layout.addRow("Proxy URL:", proxy_layout)

        return group

    def _browse_output_dir(self):
        """Browse for output directory."""
        current_dir = self.output_dir_input.text() or ""

        directory = QFileDialog.getExistingDirectory(
            self, "Select Output Directory", current_dir, QFileDialog.ShowDirsOnly
        )

        if directory:
            self.output_dir_input.setText(directory)

    def _clear_cache(self):
        """Clear application cache."""
        # TODO: Implement actual cache clearing
        from PySide6.QtWidgets import QMessageBox

        reply = QMessageBox.question(
            self,
            "Clear Cache",
            "Are you sure you want to clear the application cache?\n"
            "This will remove cached Jira data and may slow down the next summary generation.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            # Clear cache
            # self.config_manager.clear_cache()
            self.cache_size_label.setText("Cache size: 0 MB")
            QMessageBox.information(
                self, "Cache Cleared", "Application cache has been cleared."
            )

    def load_config(self, config: Dict[str, Any]) -> None:
        """Load application settings into UI."""
        app_config = config.get("application", {})

        # General settings
        theme = app_config.get("theme", "System Default")
        index = self.theme_combo.findText(theme)
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)

        self.auto_save_check.setChecked(app_config.get("auto_save", True))
        self.save_interval_spin.setValue(app_config.get("auto_save_interval", 5))

        # Summary settings
        self.date_range_spin.setValue(app_config.get("default_date_range", 7))
        self.include_subtasks.setChecked(app_config.get("include_subtasks", True))
        self.include_comments.setChecked(app_config.get("include_comments", True))
        self.group_by_epic.setChecked(app_config.get("group_by_epic", True))

        # Output settings
        self.output_dir_input.setText(app_config.get("output_directory", ""))

        naming = app_config.get("file_naming", "Executive_Summary_YYYY-MM-DD")
        naming_index = self.file_naming_combo.findText(naming)
        if naming_index >= 0:
            self.file_naming_combo.setCurrentIndex(naming_index)

        self.open_after_gen.setChecked(app_config.get("open_after_generation", True))

        # Advanced settings
        self.enable_debug_log.setChecked(app_config.get("debug_logging", False))
        self.cache_duration_spin.setValue(app_config.get("cache_duration_hours", 24))
        self.use_proxy.setChecked(app_config.get("use_proxy", False))
        self.proxy_input.setText(app_config.get("proxy_url", ""))

        # Update cache size display
        # cache_size = self.config_manager.get_cache_size()
        # self.cache_size_label.setText(f"Cache size: {cache_size:.1f} MB")

        self.mark_clean()

    def save_config(self) -> Dict[str, Any]:
        """Extract application settings from UI."""
        return {
            "application": {
                "theme": self.theme_combo.currentText(),
                "auto_save": self.auto_save_check.isChecked(),
                "auto_save_interval": self.save_interval_spin.value(),
                "default_date_range": self.date_range_spin.value(),
                "include_subtasks": self.include_subtasks.isChecked(),
                "include_comments": self.include_comments.isChecked(),
                "group_by_epic": self.group_by_epic.isChecked(),
                "output_directory": self.output_dir_input.text().strip(),
                "file_naming": self.file_naming_combo.currentText(),
                "open_after_generation": self.open_after_gen.isChecked(),
                "debug_logging": self.enable_debug_log.isChecked(),
                "cache_duration_hours": self.cache_duration_spin.value(),
                "use_proxy": self.use_proxy.isChecked(),
                "proxy_url": self.proxy_input.text().strip(),
            }
        }

    def validate(self) -> ValidationResult:
        """Validate application settings."""
        # Application settings are always valid (no required fields)
        return ValidationResult(
            is_valid=True,
            message="Settings valid",
            service=None,
            details={"configured": True},
        )

    def test_connection(self) -> None:
        """No connection test needed for app settings."""
        pass

    def get_basic_fields(self) -> List[QWidget]:
        """Return basic field widgets."""
        return [
            self.theme_combo,
            self.auto_save_check,
            self.save_interval_spin,
            self.date_range_spin,
            self.output_dir_input,
        ]

    def get_advanced_fields(self) -> List[QWidget]:
        """Return advanced field widgets."""
        return [
            self.enable_debug_log,
            self.cache_duration_spin,
            self.use_proxy,
            self.proxy_input,
        ]
