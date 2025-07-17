"""Wizard view mode for unified configuration - step-by-step setup."""

from typing import Any, Dict, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from wes.core.config_manager import ConfigManager
from wes.gui.unified_config.config_pages import (
    GeminiConfigPage,
    JiraConfigPage,
)


class WizardPage(QWidget):
    """Base class for wizard pages."""

    def __init__(self, title: str, description: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.description = description
        self._init_ui()

    def _init_ui(self):
        """Initialize base UI for wizard pages."""
        layout = QVBoxLayout(self)

        # Title
        title_label = QLabel(f"<h2>{self.title}</h2>")
        layout.addWidget(title_label)

        # Description
        desc_label = QLabel(self.description)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; margin-bottom: 20px;")
        layout.addWidget(desc_label)

        # Separator
        separator = QFrame()
        separator.setFrameStyle(QFrame.HLine | QFrame.Sunken)
        layout.addWidget(separator)

        # Page-specific content
        self._add_content(layout)

        layout.addStretch()

    def _add_content(self, layout: QVBoxLayout):
        """Add page-specific content. Override in subclasses."""

    def validate(self) -> bool:
        """Validate page content. Override in subclasses."""
        return True


class WelcomePage(WizardPage):
    """Welcome page for the wizard."""

    def __init__(self, parent=None):
        super().__init__(
            "Welcome to WES Setup",
            "Let's configure WES to create executive summaries from your Jira data. "
            "This wizard will guide you through connecting to Jira, Google Docs, "
            "and Gemini AI.",
            parent,
        )

    def _add_content(self, layout: QVBoxLayout):
        """Add welcome page content."""
        # Feature list
        features = QLabel(
            "<h3>What you'll set up:</h3>"
            "<ul>"
            "<li><b>Jira Connection</b> - Access your project data</li>"
            "<li><b>Google Docs</b> - Create and share summaries</li>"
            "<li><b>Gemini AI</b> - Generate intelligent insights</li>"
            "</ul>"
            "<p>This process takes about 5 minutes.</p>"
        )
        features.setWordWrap(True)
        layout.addWidget(features)


class SummaryPage(WizardPage):
    """Summary page showing configuration status."""

    def __init__(self, parent=None):
        super().__init__(
            "Setup Complete!",
            "Your configuration is ready. Here's what we've set up:",
            parent,
        )
        self.status_labels = {}

    def _add_content(self, layout: QVBoxLayout):
        """Add summary content."""
        # Status for each service
        services = [
            ("Jira", "jira_status"),
            ("Gemini AI", "gemini_status"),
        ]

        for service_name, key in services:
            service_layout = QHBoxLayout()

            service_label = QLabel(f"<b>{service_name}:</b>")
            service_label.setFixedWidth(120)
            service_layout.addWidget(service_label)

            status_label = QLabel("Not configured")
            status_label.setStyleSheet("color: #666;")
            self.status_labels[key] = status_label
            service_layout.addWidget(status_label)

            service_layout.addStretch()
            layout.addLayout(service_layout)

        # Next steps
        next_steps = QLabel(
            "<h3>Next Steps:</h3>"
            "<ul>"
            "<li>Click 'Finish' to save your configuration</li>"
            "<li>You can modify settings anytime from the Settings menu</li>"
            "<li>Start creating summaries from the main window</li>"
            "</ul>"
        )
        next_steps.setWordWrap(True)
        next_steps.setStyleSheet("margin-top: 20px;")
        layout.addWidget(next_steps)

    def update_status(self, jira: bool, gemini: bool):
        """Update service status display."""

        def format_status(configured: bool):
            if configured:
                return '<span style="color: green;">✓ Configured</span>'
            else:
                return '<span style="color: red;">✗ Not configured</span>'

        self.status_labels["jira_status"].setText(format_status(jira))
        self.status_labels["gemini_status"].setText(format_status(gemini))


class WizardView(QWidget):
    """
    Wizard view for step-by-step configuration.
    """

    # Signals
    wizard_complete = Signal()
    page_changed = Signal(int)  # page index

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.pages = []
        self.current_page = 0
        self._init_ui()

    def _init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximumHeight(10)
        layout.addWidget(self.progress_bar)

        # Page stack
        self.page_stack = QStackedWidget()

        # Create pages
        self._create_pages()

        layout.addWidget(self.page_stack)

        # Navigation buttons
        nav_layout = QHBoxLayout()

        self.back_button = QPushButton("← Back")
        self.back_button.clicked.connect(self._go_back)
        nav_layout.addWidget(self.back_button)

        nav_layout.addStretch()

        # Step indicator
        self.step_label = QLabel()
        nav_layout.addWidget(self.step_label)

        nav_layout.addStretch()

        self.next_button = QPushButton("Next →")
        self.next_button.clicked.connect(self._go_next)
        self.next_button.setDefault(True)
        nav_layout.addWidget(self.next_button)

        layout.addLayout(nav_layout)

        # Initialize first page
        self._update_navigation()

    def _create_pages(self):
        """Create wizard pages."""
        # Welcome page
        welcome = WelcomePage()
        self.pages.append(welcome)
        self.page_stack.addWidget(welcome)

        # Jira configuration
        self.jira_page = JiraConfigPage(self.config_manager)
        self.pages.append(self.jira_page)
        self.page_stack.addWidget(self.jira_page)

        # Gemini configuration
        self.gemini_page = GeminiConfigPage(self.config_manager)
        self.pages.append(self.gemini_page)
        self.page_stack.addWidget(self.gemini_page)

        # Summary page
        self.summary_page = SummaryPage()
        self.pages.append(self.summary_page)
        self.page_stack.addWidget(self.summary_page)

        # Set progress bar range
        self.progress_bar.setRange(0, len(self.pages) - 1)

    def _update_navigation(self):
        """Update navigation buttons and progress."""
        # Update progress bar
        self.progress_bar.setValue(self.current_page)

        # Update step label
        self.step_label.setText(f"Step {self.current_page + 1} of {len(self.pages)}")

        # Update buttons
        self.back_button.setEnabled(self.current_page > 0)

        # Last page shows "Finish" instead of "Next"
        if self.current_page == len(self.pages) - 1:
            self.next_button.setText("Finish")
            # Update summary
            self._update_summary()
        else:
            self.next_button.setText("Next →")

        # Show current page
        self.page_stack.setCurrentIndex(self.current_page)

        # Emit page changed signal
        self.page_changed.emit(self.current_page)

    def _go_back(self):
        """Go to previous page."""
        if self.current_page > 0:
            self.current_page -= 1
            self._update_navigation()

    def _go_next(self):
        """Go to next page or finish."""
        # Validate current page
        current_widget = self.pages[self.current_page]

        # Skip validation for welcome and summary pages
        if hasattr(current_widget, "validate") and not isinstance(
            current_widget, (WelcomePage, SummaryPage)
        ):
            validation_result = current_widget.validate()
            if not validation_result["is_valid"]:
                # Let the page handle showing the error
                return

        # Check if we're on the last page
        if self.current_page == len(self.pages) - 1:
            # Finish wizard
            self.wizard_complete.emit()
        else:
            # Go to next page
            self.current_page += 1
            self._update_navigation()

    def _update_summary(self):
        """Update the summary page with configuration status."""
        # Check each service configuration
        jira_valid = self.jira_page.validate()["is_valid"]
        gemini_valid = self.gemini_page.validate()["is_valid"]

        self.summary_page.update_status(jira_valid, gemini_valid)

    def get_configuration(self) -> Dict[str, Any]:
        """Get the complete configuration from all pages."""
        config = {}

        # Get Jira config
        config.update(self.jira_page.save_config())

        # Get Gemini config
        config.update(self.gemini_page.save_config())

        return config

    def get_page_info(self, page_index: int) -> Optional[Dict[str, str]]:
        """Get information about a specific page."""
        if 0 <= page_index < len(self.pages):
            page = self.pages[page_index]
            return {
                "title": getattr(page, "title", "Configuration"),
                "description": getattr(page, "description", ""),
            }
        return None
