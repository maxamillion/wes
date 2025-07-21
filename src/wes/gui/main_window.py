"""Main application window with unified configuration integration."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict

from PySide6.QtCore import QDate, Qt, QTimer
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QStatusBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core.config_manager import ConfigManager
from ..core.credential_monitor import CredentialMonitor, MonitoringConfig
from ..core.orchestrator import WorkflowOrchestrator, WorkflowResult
from ..utils.logging_config import get_logger
from .export_dialog import ExportDialog
from .summary_worker import SummaryWorker
from .unified_config import ConfigState as UnifiedConfigState
from .unified_config import UnifiedConfigDialog
from .unified_config.utils.config_detector import ConfigDetector


class ViewState(Enum):
    """Enumeration of possible view states."""

    WELCOME = "welcome"
    MAIN = "main"
    PROGRESS = "progress"
    RESULT = "result"
    # Removed SETUP and CONFIG - now handled by unified dialog


class MainWindow(QMainWindow):
    """Main application window with unified configuration."""

    def __init__(self):
        super().__init__()

        self.logger = get_logger(__name__)
        self.config_manager = ConfigManager()
        self.config_detector = ConfigDetector()

        # Initialize credential monitoring
        monitoring_config = MonitoringConfig(
            check_interval_minutes=60,
            auto_refresh_enabled=True,
            notification_enabled=True,
        )
        self.credential_monitor = CredentialMonitor(
            self.config_manager, monitoring_config
        )

        # Current state
        self.current_view = ViewState.WELCOME
        self.summary_worker = None
        self.current_result = None
        self.orchestrator = WorkflowOrchestrator(self.config_manager)

        # Initialize UI
        self.init_ui()

        # Check initial configuration state
        self.check_initial_setup()

    @property
    def is_redhat_jira(self) -> bool:
        """Check if Red Hat Jira is configured."""
        try:
            jira_config = self.config_manager.get_jira_config()
            ldap_config = self.config_manager.get_ldap_config()
            return "redhat.com" in jira_config.url.lower() and ldap_config.enabled
        except Exception:
            return False

    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("WES - Executive Summary Tool")
        self.setMinimumSize(1200, 800)

        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create menu bar
        self.create_menu_bar()

        # Create main stack for different views
        self.main_stack = QStackedWidget()

        # Create views
        self.create_welcome_view()
        self.create_main_view()
        self.create_progress_view()
        self.create_result_view()

        main_layout.addWidget(self.main_stack)

        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Start credential monitoring
        self.credential_monitor.start_monitoring()
        self.credential_monitor.credential_status_changed.connect(
            self.on_credential_validation_complete
        )

    def create_menu_bar(self):
        """Create the application menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")

        new_summary_action = QAction("New Summary", self)
        new_summary_action.setShortcut("Ctrl+N")
        new_summary_action.triggered.connect(self.new_summary)
        file_menu.addAction(new_summary_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit menu
        edit_menu = menubar.addMenu("Edit")

        settings_action = QAction("Settings...", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self.show_settings)
        edit_menu.addAction(settings_action)

        # View menu
        view_menu = menubar.addMenu("View")

        home_action = QAction("Home", self)
        home_action.triggered.connect(lambda: self.switch_view(ViewState.MAIN))
        view_menu.addAction(home_action)

        # Help menu
        help_menu = menubar.addMenu("Help")

        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def create_welcome_view(self):
        """Create the welcome view."""
        self.welcome_widget = QWidget()
        layout = QVBoxLayout(self.welcome_widget)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(20)

        # Logo placeholder
        logo_label = QLabel("WES")
        logo_font = QFont()
        logo_font.setPointSize(48)
        logo_font.setBold(True)
        logo_label.setFont(logo_font)
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setStyleSheet("color: #0084ff;")
        layout.addWidget(logo_label)

        # Title
        title_label = QLabel("Welcome to WES")
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # Subtitle
        subtitle_label = QLabel("Executive Summary Automation Tool")
        subtitle_font = QFont()
        subtitle_font.setPointSize(14)
        subtitle_label.setFont(subtitle_font)
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setStyleSheet("color: #666;")
        layout.addWidget(subtitle_label)

        # Get started button
        self.get_started_button = QPushButton("Get Started")
        self.get_started_button.setFixedSize(200, 50)
        self.get_started_button.setStyleSheet(
            """
            QPushButton {
                background-color: #0084ff;
                color: white;
                font-size: 16px;
                font-weight: bold;
                border-radius: 25px;
            }
            QPushButton:hover {
                background-color: #0066cc;
            }
        """
        )
        self.get_started_button.clicked.connect(self.show_settings)
        layout.addWidget(self.get_started_button, alignment=Qt.AlignCenter)

        self.main_stack.addWidget(self.welcome_widget)

    def create_main_view(self):
        """Create the main summary generation view."""
        self.main_widget = QWidget()
        layout = QVBoxLayout(self.main_widget)

        # Header
        header = QLabel("Create Executive Summary")
        header_font = QFont()
        header_font.setPointSize(18)
        header_font.setBold(True)
        header.setFont(header_font)
        layout.addWidget(header)

        # Configuration status
        self.config_status_widget = self.create_config_status_widget()
        layout.addWidget(self.config_status_widget)

        # Summary options
        options_group = QGroupBox("Summary Options")
        options_layout = QFormLayout(options_group)

        # Date range
        date_layout = QHBoxLayout()
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate().addDays(-7))
        date_layout.addWidget(QLabel("From:"))
        date_layout.addWidget(self.start_date)

        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())
        date_layout.addWidget(QLabel("To:"))
        date_layout.addWidget(self.end_date)
        date_layout.addStretch()

        options_layout.addRow("Date Range:", date_layout)

        # Manager scope for Red Hat Jira
        if self.is_redhat_jira:
            self.manager_scope_widget = self.create_manager_scope_widget()
            options_layout.addRow("Scope:", self.manager_scope_widget)

        # Project filter
        self.project_filter = QLineEdit()
        self.project_filter.setPlaceholderText("e.g., PROJ-123, PROJ-456")
        options_layout.addRow("Projects (optional):", self.project_filter)

        # Assignee filter (hide when using manager scope)
        self.assignee_filter = QLineEdit()
        self.assignee_filter.setPlaceholderText("e.g., john.doe@company.com")
        self.assignee_row_label = QLabel("Assignee (optional):")
        options_layout.addRow(self.assignee_row_label, self.assignee_filter)

        layout.addWidget(options_group)

        # Generate button
        self.generate_button = QPushButton("Generate Summary")
        self.generate_button.setFixedHeight(50)
        self.generate_button.setStyleSheet(
            """
            QPushButton {
                background-color: #28a745;
                color: white;
                font-size: 16px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """
        )
        self.generate_button.clicked.connect(self.generate_summary)
        layout.addWidget(self.generate_button)

        layout.addStretch()

        self.main_stack.addWidget(self.main_widget)

    def create_config_status_widget(self):
        """Create configuration status widget."""
        widget = QFrame()
        widget.setFrameStyle(QFrame.Box)
        widget.setStyleSheet(
            """
            QFrame {
                border: 1px solid #ddd;
                border-radius: 5px;
                background-color: #f8f9fa;
                padding: 10px;
            }
        """
        )

        layout = QHBoxLayout(widget)

        # Status label
        self.config_status_label = QLabel("Checking configuration...")
        layout.addWidget(self.config_status_label)

        layout.addStretch()

        # Configure button
        configure_button = QPushButton("Configure")
        configure_button.clicked.connect(self.show_settings)
        layout.addWidget(configure_button)

        # Update status
        self.update_config_status()

        return widget

    def create_manager_scope_widget(self):
        """Create widget for manager scope selection (Red Hat Jira only)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Radio buttons for scope selection
        self.use_configured_users = QRadioButton("Use configured users")
        self.use_configured_users.setChecked(True)
        self.use_manager_org = QRadioButton("Use manager's organization")

        # Radio button layout
        radio_layout = QHBoxLayout()
        radio_layout.addWidget(self.use_configured_users)
        radio_layout.addWidget(self.use_manager_org)
        radio_layout.addStretch()
        layout.addLayout(radio_layout)

        # Manager email input container
        self.manager_input_container = QWidget()
        manager_layout = QVBoxLayout(self.manager_input_container)
        manager_layout.setContentsMargins(20, 5, 0, 0)

        # Manager email input
        email_layout = QHBoxLayout()
        email_layout.addWidget(QLabel("Manager Email:"))
        self.manager_email = QLineEdit()
        self.manager_email.setPlaceholderText("manager@redhat.com")
        self.manager_email.setMinimumWidth(250)
        email_layout.addWidget(self.manager_email)
        email_layout.addStretch()
        manager_layout.addLayout(email_layout)

        # Help text
        help_text = QLabel(
            "ℹ Enter manager's email to include their entire organizational team"
        )
        help_text.setStyleSheet("color: #666; font-size: 12px; padding-left: 100px;")
        help_text.setWordWrap(True)
        manager_layout.addWidget(help_text)

        layout.addWidget(self.manager_input_container)

        # Initially hide manager input
        self.manager_input_container.setVisible(False)

        # Connect signals
        self.use_manager_org.toggled.connect(self.on_manager_mode_toggled)

        return widget

    def on_manager_mode_toggled(self, checked: bool):
        """Handle manager mode toggle."""
        self.manager_input_container.setVisible(checked)

        # Hide/show assignee filter
        if hasattr(self, "assignee_filter"):
            self.assignee_filter.setVisible(not checked)
            self.assignee_row_label.setVisible(not checked)

            # Clear assignee filter when using manager mode
            if checked:
                self.assignee_filter.clear()

    def create_progress_view(self):
        """Create the progress view for summary generation."""
        self.progress_widget = QWidget()
        layout = QVBoxLayout(self.progress_widget)
        layout.setAlignment(Qt.AlignCenter)

        # Title
        title = QLabel("Generating Summary")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimumWidth(400)
        layout.addWidget(self.progress_bar)

        # Status label
        self.progress_status = QLabel("Initializing...")
        layout.addWidget(self.progress_status)

        # Cancel button
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_summary)
        layout.addWidget(self.cancel_button)

        self.main_stack.addWidget(self.progress_widget)

    def create_result_view(self):
        """Create the result view for displaying generated summary."""
        self.result_widget = QWidget()
        layout = QVBoxLayout(self.result_widget)

        # Header
        header_layout = QHBoxLayout()

        title = QLabel("Executive Summary")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        header_layout.addWidget(title)

        header_layout.addStretch()

        # Action buttons
        new_button = QPushButton("New Summary")
        new_button.clicked.connect(self.new_summary)
        header_layout.addWidget(new_button)

        export_button = QPushButton("Export...")
        export_button.setStyleSheet(
            """
            QPushButton {
                background-color: #28a745;
                color: white;
                font-weight: bold;
                padding: 6px 15px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """
        )
        export_button.clicked.connect(self.show_export_dialog)
        header_layout.addWidget(export_button)

        layout.addLayout(header_layout)

        # Summary content
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        layout.addWidget(self.result_text)

        # Quick actions bar
        actions_layout = QHBoxLayout()

        copy_button = QPushButton("Copy to Clipboard")
        copy_button.clicked.connect(self.copy_summary_to_clipboard)
        actions_layout.addWidget(copy_button)

        save_markdown_button = QPushButton("Save as Markdown")
        save_markdown_button.clicked.connect(lambda: self.quick_export("markdown"))
        actions_layout.addWidget(save_markdown_button)

        save_pdf_button = QPushButton("Save as PDF")
        save_pdf_button.clicked.connect(lambda: self.quick_export("pdf"))
        actions_layout.addWidget(save_pdf_button)

        actions_layout.addStretch()

        layout.addLayout(actions_layout)

        self.main_stack.addWidget(self.result_widget)

    def check_initial_setup(self):
        """Check if initial setup is needed."""
        config_state = self.config_detector.detect_state(self.config_manager.config)

        if config_state == UnifiedConfigState.EMPTY:
            # First time user
            QTimer.singleShot(500, self.show_initial_setup)
        elif config_state == UnifiedConfigState.INCOMPLETE:
            # Incomplete setup
            QTimer.singleShot(500, self.show_incomplete_setup_warning)
        else:
            # Configuration complete
            self.switch_view(ViewState.MAIN)

    def show_initial_setup(self):
        """Show initial setup dialog."""
        reply = QMessageBox.information(
            self,
            "Welcome to WES",
            "Welcome! Let's set up WES to create executive summaries.\n\n"
            "Click OK to begin the setup wizard.",
            QMessageBox.Ok | QMessageBox.Cancel,
            QMessageBox.Ok,
        )

        if reply == QMessageBox.Ok:
            self.show_settings()

    def show_incomplete_setup_warning(self):
        """Show warning about incomplete setup."""
        missing_services = self.config_detector.get_missing_services(
            self.config_manager.config
        )

        service_names = [s.value.title() for s in missing_services]

        reply = QMessageBox.question(
            self,
            "Incomplete Configuration",
            f"The following services need to be configured:\n"
            f"• {chr(10).join(service_names)}\n\n"
            f"Would you like to complete the setup now?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )

        if reply == QMessageBox.Yes:
            self.show_settings()
        else:
            # Allow user to continue with incomplete config
            self.switch_view(ViewState.MAIN)

    def show_settings(self):
        """Show the unified settings dialog."""
        dialog = UnifiedConfigDialog(self.config_manager, self)

        # Connect to handle configuration updates
        dialog.configuration_complete.connect(self.on_configuration_updated)

        # Show dialog
        result = dialog.exec()

        if result == QDialog.DialogCode.Accepted:
            # Configuration was saved
            self.update_config_status()
            self.status_bar.showMessage("Configuration updated", 3000)

    def on_configuration_updated(self, config: Dict[str, Any]):
        """Handle configuration updates from the unified dialog."""
        # Update UI elements that depend on configuration
        self.update_config_status()

        # Check if Red Hat Jira status changed - if so, recreate main view
        if hasattr(self, "main_widget"):
            old_is_redhat = hasattr(self, "manager_scope_widget")
            new_is_redhat = self.is_redhat_jira

            if old_is_redhat != new_is_redhat:
                # Recreate main view to show/hide manager field
                self.main_stack.removeWidget(self.main_widget)
                self.main_widget.deleteLater()
                self.create_main_view()

        # If we're on welcome screen and config is now complete,
        # switch to main view
        if self.current_view == ViewState.WELCOME:
            config_state = self.config_detector.detect_state(self.config_manager.config)
            if config_state == UnifiedConfigState.COMPLETE:
                self.switch_view(ViewState.MAIN)

    def update_config_status(self):
        """Update configuration status display."""
        if not hasattr(self, "config_status_label"):
            return

        service_status = self.config_detector.get_service_status(
            self.config_manager.config
        )

        all_configured = all(s["is_valid"] for s in service_status.values())

        if all_configured:
            self.config_status_label.setText("✓ All services configured")
            self.config_status_label.setStyleSheet("color: green;")
            if hasattr(self, "generate_button"):
                self.generate_button.setEnabled(True)
        else:
            # List what's missing
            missing = [
                service.value.title()
                for service, status in service_status.items()
                if not status["is_valid"]
            ]
            self.config_status_label.setText(
                f"⚠️ Configuration incomplete: {', '.join(missing)}"
            )
            self.config_status_label.setStyleSheet("color: orange;")
            if hasattr(self, "generate_button"):
                self.generate_button.setEnabled(False)

    def switch_view(self, view_state: ViewState):
        """Switch between different views."""
        self.current_view = view_state

        if view_state == ViewState.WELCOME:
            self.main_stack.setCurrentWidget(self.welcome_widget)
        elif view_state == ViewState.MAIN:
            self.main_stack.setCurrentWidget(self.main_widget)
            self.update_config_status()
        elif view_state == ViewState.PROGRESS:
            self.main_stack.setCurrentWidget(self.progress_widget)
        elif view_state == ViewState.RESULT:
            self.main_stack.setCurrentWidget(self.result_widget)

    def new_summary(self):
        """Start a new summary."""
        self.switch_view(ViewState.MAIN)

    def generate_summary(self):
        """Generate executive summary."""
        # Validate configuration first
        config_state = self.config_detector.detect_state(self.config_manager.config)
        if config_state != UnifiedConfigState.COMPLETE:
            QMessageBox.warning(
                self,
                "Configuration Incomplete",
                "Please complete the configuration before generating a summary.",
            )
            return

        # Get parameters
        start_date = self.start_date.date().toPython()
        end_date = self.end_date.date().toPython()

        # Convert to datetime
        from datetime import datetime

        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())

        # Determine if using manager mode or user list
        manager_identifier = None
        use_ldap_hierarchy = False
        users = []

        if (
            self.is_redhat_jira
            and hasattr(self, "use_manager_org")
            and self.use_manager_org.isChecked()
        ):
            # Manager mode - validate email
            manager_email = self.manager_email.text().strip()
            if not manager_email:
                QMessageBox.warning(
                    self,
                    "Manager Email Required",
                    "Please enter the manager's email address.",
                )
                return

            # Basic email validation
            if "@" not in manager_email:
                QMessageBox.warning(
                    self,
                    "Invalid Email",
                    "Please enter a valid email address.",
                )
                return

            manager_identifier = manager_email
            use_ldap_hierarchy = True
        else:
            # Standard mode - use configured username
            jira_config = self.config_manager.get_jira_config()
            users = [jira_config.username] if jira_config.username else []

            if not users:
                QMessageBox.warning(
                    self,
                    "No User Specified",
                    "Please configure a Jira username in settings.",
                )
                return

        # Switch to progress view
        self.switch_view(ViewState.PROGRESS)
        self.progress_bar.setValue(0)
        self.progress_bar.setEnabled(True)
        self.progress_status.setText("Initializing...")
        self.cancel_button.setEnabled(True)

        # Create and start worker
        self.summary_worker = SummaryWorker(
            orchestrator=self.orchestrator,
            users=users,
            start_date=start_datetime,
            end_date=end_datetime,
            custom_prompt=None,
            manager_identifier=manager_identifier,
            use_ldap_hierarchy=use_ldap_hierarchy,
        )

        # Connect signals
        self.summary_worker.progress_update.connect(self.on_progress_update)
        self.summary_worker.generation_complete.connect(self.on_generation_complete)
        self.summary_worker.generation_failed.connect(self.on_generation_failed)

        # Start generation
        self.summary_worker.start()

    def cancel_summary(self):
        """Cancel summary generation."""
        if self.summary_worker and self.summary_worker.isRunning():
            self.logger.info("Cancelling summary generation...")

            # Disable cancel button to prevent multiple clicks
            self.cancel_button.setEnabled(False)

            # Update UI to show cancellation in progress
            self.progress_status.setText("Cancelling...")
            self.progress_bar.setEnabled(False)

            # Cancel the worker
            self.summary_worker.cancel()

            # Request thread termination
            self.summary_worker.quit()

            # Wait for thread to finish (with timeout)
            if not self.summary_worker.wait(5000):  # 5 second timeout
                self.logger.warning(
                    "Worker thread did not terminate gracefully, forcing termination"
                )
                self.summary_worker.terminate()
                self.summary_worker.wait()

            self.logger.info("Summary generation cancelled")

        self.switch_view(ViewState.MAIN)

    def on_progress_update(self, message: str, percentage: int):
        """Handle progress updates from worker.

        Args:
            message: Progress message
            percentage: Progress percentage (0-100)
        """
        self.progress_status.setText(message)
        self.progress_bar.setValue(percentage)

    def on_generation_complete(self, result: WorkflowResult):
        """Handle successful summary generation.

        Args:
            result: Workflow result containing summary data
        """
        self.current_result = result
        self.switch_view(ViewState.RESULT)

        # Update result view with summary
        if result.summary_content:
            self.result_text.setPlainText(result.summary_content)
            self.status_bar.showMessage("Summary generated successfully", 3000)
        else:
            self.result_text.setPlainText("No summary content generated.")

    def on_generation_failed(self, error_message: str):
        """Handle failed summary generation.

        Args:
            error_message: Error message
        """
        self.switch_view(ViewState.MAIN)
        QMessageBox.critical(
            self, "Generation Failed", f"Failed to generate summary:\n\n{error_message}"
        )

    def show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About WES",
            "WES - Executive Summary Tool\n\n"
            "Version 1.0.0\n\n"
            "Automated executive summary generation from Jira data.",
        )

    def on_credential_validation_complete(
        self, service: str, credential_type: str, healthy: bool
    ):
        """Handle credential validation results.

        Args:
            service: Service name
            credential_type: Type of credential
            healthy: Whether the credential is healthy
        """
        # Update UI based on validation results
        if hasattr(self, "config_status_label"):
            self.update_config_status()

    def show_export_dialog(self):
        """Show the export dialog for the current summary."""
        if not self.current_result or not self.current_result.summary_data:
            QMessageBox.warning(self, "No Summary", "No summary available to export.")
            return

        dialog = ExportDialog(self.current_result.summary_data, self)
        dialog.export_complete.connect(self.on_export_complete)
        dialog.exec()

    def copy_summary_to_clipboard(self):
        """Copy the current summary to clipboard."""
        if not self.current_result or not self.current_result.summary_data:
            return

        from ..core.export_manager import ExportManager

        export_manager = ExportManager()

        try:
            success = export_manager.copy_to_clipboard(self.current_result.summary_data)
            if success:
                self.status_bar.showMessage("Summary copied to clipboard", 3000)
        except Exception as e:
            QMessageBox.warning(
                self, "Copy Failed", f"Failed to copy to clipboard: {str(e)}"
            )

    def quick_export(self, format: str):
        """Quick export to a specific format."""
        if not self.current_result or not self.current_result.summary_data:
            return

        from pathlib import Path

        from ..core.export_manager import ExportManager

        export_manager = ExportManager()

        # Get file path
        file_extensions = {
            "markdown": ("Markdown Files (*.md)", ".md"),
            "pdf": ("PDF Files (*.pdf)", ".pdf"),
        }

        filter_text, extension = file_extensions.get(format, ("All Files (*)", ""))

        # Suggest filename
        date_str = datetime.now().strftime("%Y-%m-%d")
        suggested_name = f"executive_summary_{date_str}{extension}"

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            f"Save Executive Summary as {format.upper()}",
            suggested_name,
            filter_text,
        )

        if filepath:
            try:
                filepath = Path(filepath)
                if not filepath.suffix:
                    filepath = filepath.with_suffix(extension)

                success = export_manager.export_summary(
                    self.current_result.summary_data, format, filepath
                )

                if success:
                    self.status_bar.showMessage(
                        f"Summary exported to {filepath.name}", 3000
                    )
            except Exception as e:
                QMessageBox.critical(
                    self, "Export Failed", f"Failed to export summary:\n{str(e)}"
                )

    def on_export_complete(self, format: str, filepath: str):
        """Handle export completion.

        Args:
            format: Export format
            filepath: Path where file was saved (empty for clipboard)
        """
        if format == "clipboard":
            self.status_bar.showMessage("Summary copied to clipboard", 3000)
        else:
            from pathlib import Path

            filename = Path(filepath).name
            self.status_bar.showMessage(f"Summary exported to {filename}", 3000)

    def closeEvent(self, event):
        """Handle application close."""
        # Stop credential monitor
        self.credential_monitor.stop_monitoring()

        # Cancel any running operations
        if self.summary_worker and self.summary_worker.isRunning():
            self.summary_worker.quit()
            self.summary_worker.wait()

        event.accept()
