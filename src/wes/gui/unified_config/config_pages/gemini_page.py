"""Gemini AI configuration page for unified config dialog."""

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wes.core.config_manager import ConfigManager
from wes.gui.unified_config.components.validation_indicator import ValidatedLineEdit
from wes.gui.unified_config.config_pages.base_page import ConfigPageBase
from wes.gui.unified_config.types import ServiceType, ValidationResult


class GeminiConfigPage(ConfigPageBase):
    """Gemini AI configuration page with model selection and parameters."""

    service_type = ServiceType.GEMINI
    page_title = "Gemini AI Configuration"
    page_icon = "SP_FileDialogInfoView"
    page_description = "Configure Google's Gemini AI for intelligent summarization"

    def _setup_page_ui(self, parent_layout: QVBoxLayout) -> None:
        """Setup Gemini-specific UI."""
        # API Key configuration
        api_group = QGroupBox("API Configuration")
        api_layout = QFormLayout(api_group)

        # API Key input
        self.api_key_input = ValidatedLineEdit("Your Gemini API key", password=True)
        self.api_key_input.set_validator(self._validate_api_key)
        api_layout.addRow("API Key:", self.api_key_input)

        # Help link for API key
        help_layout = QHBoxLayout()
        help_layout.addStretch()
        help_link = QLabel(
            '<a href="https://makersuite.google.com/app/apikey">Get your Gemini API key</a>'
        )
        help_link.setOpenExternalLinks(True)
        help_link.setStyleSheet("color: #0084ff;")
        help_layout.addWidget(help_link)
        api_layout.addRow("", help_layout)

        parent_layout.addWidget(api_group)

        # Model configuration
        model_group = QGroupBox("Model Settings")
        model_layout = QFormLayout(model_group)

        # Model selection
        self.model_combo = QComboBox()
        self.model_combo.addItems(["gemini-2.5-pro", "gemini-2.5-flash"])
        self.model_combo.currentTextChanged.connect(self._on_model_changed)
        model_layout.addRow("Model:", self.model_combo)

        # Model description
        self.model_desc = QLabel()
        self.model_desc.setWordWrap(True)
        self.model_desc.setStyleSheet("color: #666; font-size: 12px;")
        model_layout.addRow("", self.model_desc)

        # Temperature slider
        temp_layout = QVBoxLayout()
        temp_header = QHBoxLayout()
        temp_header.addWidget(QLabel("Temperature:"))
        self.temp_value_label = QLabel("0.7")
        temp_header.addStretch()
        temp_header.addWidget(self.temp_value_label)
        temp_layout.addLayout(temp_header)

        self.temperature_slider = QSlider(Qt.Horizontal)
        self.temperature_slider.setRange(0, 100)  # 0.0 to 1.0
        self.temperature_slider.setValue(70)  # 0.7
        self.temperature_slider.setTickPosition(QSlider.TicksBelow)
        self.temperature_slider.setTickInterval(10)
        self.temperature_slider.valueChanged.connect(self._on_temperature_changed)
        temp_layout.addWidget(self.temperature_slider)

        # Temperature labels
        temp_labels = QHBoxLayout()
        temp_labels.addWidget(QLabel("Focused"))
        temp_labels.addStretch()
        temp_labels.addWidget(QLabel("Balanced"))
        temp_labels.addStretch()
        temp_labels.addWidget(QLabel("Creative"))
        temp_layout.addLayout(temp_labels)

        model_layout.addRow(temp_layout)

        # Max tokens
        max_tokens_label, self.max_tokens_input = self._create_spinbox(
            "Max Output Tokens:", 2048, 100, 8192
        )
        model_layout.addRow(max_tokens_label, self.max_tokens_input)

        parent_layout.addWidget(model_group)

        # Prompt customization (advanced)
        self.prompt_group = self._create_prompt_group()
        parent_layout.addWidget(self.prompt_group)

        # Connection test area
        test_layout = QHBoxLayout()
        self.test_button = self._create_test_button()
        test_layout.addWidget(self.test_button)

        self.connection_status_label = QLabel("")
        test_layout.addWidget(self.connection_status_label)
        test_layout.addStretch()

        parent_layout.addLayout(test_layout)

        # Initialize model description
        self._on_model_changed(self.model_combo.currentText())

        # Connect change tracking
        self._connect_change_tracking()

    def _create_prompt_group(self) -> QGroupBox:
        """Create prompt customization group."""
        group = self._create_group_box("Prompt Customization", collapsible=True)
        layout = QVBoxLayout(group)

        # Prompt template description
        desc = QLabel(
            "Customize the AI prompt template. Use {jira_data} as a placeholder "
            "for the Jira activity data that will be inserted."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666; margin-bottom: 10px;")
        layout.addWidget(desc)

        # Prompt template editor
        self.prompt_template = QTextEdit()
        self.prompt_template.setPlaceholderText(
            "Enter custom prompt template...\n\n"
            "Example:\n"
            "Based on the following Jira activity data:\n"
            "{jira_data}\n\n"
            "Please create an executive summary that highlights key accomplishments."
        )
        self.prompt_template.setMaximumHeight(150)
        self.prompt_template.textChanged.connect(self.mark_dirty)
        layout.addWidget(self.prompt_template)

        # Reset button
        reset_layout = QHBoxLayout()
        reset_layout.addStretch()
        reset_button = QPushButton("Reset to Default")
        reset_button.clicked.connect(self._reset_prompt_template)
        reset_layout.addWidget(reset_button)
        layout.addLayout(reset_layout)

        return group

    def _on_model_changed(self, model: str) -> None:
        """Update model description when selection changes."""
        descriptions = {
            "gemini-2.5-pro": "Most capable model with 2M token context window. "
            "Best for complex summarization tasks.",
            "gemini-2.5-flash": "Faster, lightweight model with 1M token context. "
            "Good balance of speed and quality.",
        }

        self.model_desc.setText(descriptions.get(model, ""))
        self.mark_dirty()

    def _on_temperature_changed(self, value: int) -> None:
        """Update temperature display when slider changes."""
        temp = value / 100.0
        self.temp_value_label.setText(f"{temp:.1f}")
        self.mark_dirty()

    def _reset_prompt_template(self) -> None:
        """Reset prompt template to default."""
        default_prompt = (
            "Based on the following Jira activity data:\n"
            "{jira_data}\n\n"
            "Please create a comprehensive executive summary that:\n"
            "1. Highlights key accomplishments and deliverables\n"
            "2. Identifies any blockers or challenges\n"
            "3. Summarizes progress on major initiatives\n"
            "4. Lists upcoming priorities\n\n"
            "Format the summary in a clear, professional manner suitable "
            "for executive review."
        )
        self.prompt_template.setPlainText(default_prompt)
        self.mark_dirty()

    def _validate_api_key(self, api_key: str) -> tuple[bool, str]:
        """Validate Gemini API key format."""
        if not api_key:
            return False, "API key is required"

        # Gemini API keys typically start with 'AIza'
        if not api_key.startswith("AIza"):
            return False, "Invalid API key format"

        if len(api_key) < 30:
            return False, "API key appears too short"

        return True, "API key format valid"

    def load_config(self, config: Dict[str, Any]) -> None:
        """Load Gemini configuration into UI."""
        gemini_config = config.get("gemini", {})

        # Set API key
        self.api_key_input.setText(gemini_config.get("api_key", ""))

        # Set model
        model = gemini_config.get("model", "gemini-2.5-pro")
        index = self.model_combo.findText(model)
        if index >= 0:
            self.model_combo.setCurrentIndex(index)

        # Set temperature
        temp = gemini_config.get("temperature", 0.7)
        self.temperature_slider.setValue(int(temp * 100))

        # Set max tokens
        self.max_tokens_input.setValue(gemini_config.get("max_tokens", 2048))

        # Set custom prompt if available
        custom_prompt = gemini_config.get("custom_prompt", "")
        if custom_prompt:
            self.prompt_template.setPlainText(custom_prompt)

        self.mark_clean()

    def save_config(self) -> Dict[str, Any]:
        """Extract Gemini configuration from UI."""
        config = {
            "gemini": {
                "api_key": self.api_key_input.text().strip(),
                "model": self.model_combo.currentText(),
                "temperature": self.temperature_slider.value() / 100.0,
                "max_tokens": self.max_tokens_input.value(),
            }
        }

        # Add custom prompt if provided
        custom_prompt = self.prompt_template.toPlainText().strip()
        if custom_prompt:
            config["gemini"]["custom_prompt"] = custom_prompt

        return config

    def validate(self) -> ValidationResult:
        """Validate Gemini configuration."""
        config = self.save_config()["gemini"]

        # Check API key
        if not config["api_key"]:
            return ValidationResult(
                is_valid=False,
                message="API key is required",
                service=ServiceType.GEMINI,
                details={"field": "api_key", "validation_type": "required"}
            )

        # Validate API key format
        is_valid, message = self._validate_api_key(config["api_key"])
        if not is_valid:
            return ValidationResult(
                is_valid=False,
                message=message,
                service=ServiceType.GEMINI,
                details={"field": "api_key", "validation_type": "format"}
            )

        # Check model selection
        if not config["model"]:
            return ValidationResult(
                is_valid=False,
                message="Model selection is required",
                service=ServiceType.GEMINI,
                details={"field": "model", "validation_type": "required"}
            )

        return ValidationResult(
            is_valid=True,
            message="Gemini configuration is valid",
            service=ServiceType.GEMINI,
            details={"validated_fields": ["api_key", "model"]}
        )

    def get_basic_fields(self) -> List[QWidget]:
        """Return basic field widgets."""
        return [
            self.api_key_input,
            self.model_combo,
            self.temperature_slider,
            self.max_tokens_input,
        ]

    def get_advanced_fields(self) -> List[QWidget]:
        """Return advanced field widgets."""
        return [self.prompt_template]

    def _connect_change_tracking(self) -> None:
        """Connect change tracking to form fields."""
        # Most connections already made during widget creation
        self.api_key_input.text_changed.connect(lambda: self.mark_dirty())
        self.model_combo.currentTextChanged.connect(lambda: self.mark_dirty())
