"""Main application window for the Executive Summary Tool."""

import sys
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QLabel,
    QPushButton,
    QTextEdit,
    QLineEdit,
    QComboBox,
    QSpinBox,
    QDateEdit,
    QCheckBox,
    QProgressBar,
    QStatusBar,
    QMenuBar,
    QMessageBox,
    QGroupBox,
    QListWidget,
    QSplitter,
    QFrame,
    QApplication,
    QGridLayout,
    QFormLayout,
    QListWidgetItem,
)
from PySide6.QtCore import Qt, QThread, Signal, QDate, QTimer
from PySide6.QtGui import QIcon, QFont, QPixmap, QAction

from ..core.config_manager import ConfigManager
from ..core.credential_monitor import CredentialMonitor, MonitoringConfig
from ..utils.logging_config import get_logger
from ..utils.exceptions import WesError
from .config_dialog import ConfigDialog
from .progress_dialog import ProgressDialog
from .setup_wizard import SetupWizard


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()

        self.logger = get_logger(__name__)
        self.config_manager = ConfigManager()

        # Initialize credential monitoring
        monitoring_config = MonitoringConfig(
            check_interval_minutes=60,
            auto_refresh_enabled=True,
            notification_enabled=True,
        )
        self.credential_monitor = CredentialMonitor(
            self.config_manager, monitoring_config
        )

        # Initialize UI
        self.init_ui()

        # Initialize state
        self.current_activity_data = []
        self.current_summary = None
        self.progress_dialog = None

        # Check initial configuration
        self.check_initial_setup()

    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Executive Summary Tool")
        self.setGeometry(100, 100, 1200, 800)

        # Set application icon
        self.setWindowIcon(QIcon(":/icons/app_icon.png"))

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Create main layout
        main_layout = QVBoxLayout(central_widget)

        # Create menu bar
        self.create_menu_bar()

        # Create tab widget
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # Create tabs
        self.create_data_tab()
        self.create_summary_tab()
        self.create_output_tab()

        # Create status bar
        self.create_status_bar()

        # Apply styling
        self.apply_styling()

        # Load saved configuration (after all UI elements are created)
        self.load_ui_configuration()

    def create_menu_bar(self):
        """Create the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")

        new_action = QAction("New Summary", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_summary)
        file_menu.addAction(new_action)

        open_action = QAction("Open Configuration", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_configuration)
        file_menu.addAction(open_action)

        save_action = QAction("Save Configuration", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_configuration)
        file_menu.addAction(save_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Tools menu
        tools_menu = menubar.addMenu("Tools")

        setup_wizard_action = QAction("Setup Wizard", self)
        setup_wizard_action.triggered.connect(self.open_setup_wizard)
        tools_menu.addAction(setup_wizard_action)

        config_action = QAction("Advanced Configuration", self)
        config_action.triggered.connect(self.open_configuration_dialog)
        tools_menu.addAction(config_action)

        test_connections_action = QAction("Test Connections", self)
        test_connections_action.triggered.connect(self.test_connections)
        tools_menu.addAction(test_connections_action)

        # Help menu
        help_menu = menubar.addMenu("Help")

        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def create_data_tab(self):
        """Create the data configuration tab."""
        data_tab = QWidget()
        self.tab_widget.addTab(data_tab, "Data Configuration")

        layout = QVBoxLayout(data_tab)

        # Jira configuration group
        jira_group = QGroupBox("Jira Configuration")
        jira_layout = QFormLayout(jira_group)

        self.jira_url_edit = QLineEdit()
        self.jira_url_edit.setPlaceholderText("https://issues.redhat.com")
        jira_layout.addRow("Jira URL:", self.jira_url_edit)

        self.jira_username_edit = QLineEdit()
        self.jira_username_edit.setPlaceholderText("your.email@company.com")
        jira_layout.addRow("Username:", self.jira_username_edit)

        self.jira_token_edit = QLineEdit()
        self.jira_token_edit.setEchoMode(QLineEdit.Password)
        self.jira_token_edit.setPlaceholderText("Your Jira API token")
        jira_layout.addRow("API Token:", self.jira_token_edit)

        layout.addWidget(jira_group)

        # Date range group
        date_group = QGroupBox("Date Range")
        date_layout = QFormLayout(date_group)

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setDate(QDate.currentDate().addDays(-7))
        self.start_date_edit.setCalendarPopup(True)
        date_layout.addRow("Start Date:", self.start_date_edit)

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setDate(QDate.currentDate())
        self.end_date_edit.setCalendarPopup(True)
        date_layout.addRow("End Date:", self.end_date_edit)

        layout.addWidget(date_group)

        # Users group
        users_group = QGroupBox("Users")
        users_layout = QVBoxLayout(users_group)

        users_input_layout = QHBoxLayout()
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("Enter username or email")
        users_input_layout.addWidget(self.user_input)

        self.add_user_btn = QPushButton("Add User")
        self.add_user_btn.clicked.connect(self.add_user)
        users_input_layout.addWidget(self.add_user_btn)

        users_layout.addLayout(users_input_layout)

        self.users_list = QListWidget()
        users_layout.addWidget(self.users_list)

        users_buttons_layout = QHBoxLayout()
        self.remove_user_btn = QPushButton("Remove Selected")
        self.remove_user_btn.clicked.connect(self.remove_user)
        users_buttons_layout.addWidget(self.remove_user_btn)

        self.load_users_btn = QPushButton("Load from Jira")
        self.load_users_btn.clicked.connect(self.load_users_from_jira)
        users_buttons_layout.addWidget(self.load_users_btn)

        users_layout.addLayout(users_buttons_layout)

        layout.addWidget(users_group)

        # Fetch data button
        fetch_layout = QHBoxLayout()
        fetch_layout.addStretch()

        self.fetch_data_btn = QPushButton("Fetch Jira Data")
        self.fetch_data_btn.setMinimumHeight(40)
        self.fetch_data_btn.clicked.connect(self.fetch_jira_data)
        fetch_layout.addWidget(self.fetch_data_btn)

        fetch_layout.addStretch()
        layout.addLayout(fetch_layout)

    def create_summary_tab(self):
        """Create the summary generation tab."""
        summary_tab = QWidget()
        self.tab_widget.addTab(summary_tab, "Summary Generation")

        layout = QVBoxLayout(summary_tab)

        # AI configuration group
        ai_group = QGroupBox("AI Configuration")
        ai_layout = QFormLayout(ai_group)

        self.ai_model_combo = QComboBox()
        self.ai_model_combo.addItems(["gemini-2.5-flash", "gemini-2.5-pro"])
        ai_layout.addRow("Model:", self.ai_model_combo)

        self.temperature_spin = QSpinBox()
        self.temperature_spin.setRange(0, 100)
        self.temperature_spin.setValue(70)
        self.temperature_spin.setSuffix("%")
        ai_layout.addRow("Temperature:", self.temperature_spin)

        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(100, 8192)
        self.max_tokens_spin.setValue(2048)
        ai_layout.addRow("Max Tokens:", self.max_tokens_spin)

        layout.addWidget(ai_group)

        # Custom prompt group
        prompt_group = QGroupBox("Custom Prompt (Optional)")
        prompt_layout = QVBoxLayout(prompt_group)

        self.custom_prompt_edit = QTextEdit()
        self.custom_prompt_edit.setPlaceholderText(
            "Enter custom prompt for AI summary generation. "
            "Use {activity_data} placeholder for Jira data insertion."
        )
        self.custom_prompt_edit.setMaximumHeight(150)
        prompt_layout.addWidget(self.custom_prompt_edit)

        layout.addWidget(prompt_group)

        # Summary display
        summary_display_group = QGroupBox("Generated Summary")
        summary_display_layout = QVBoxLayout(summary_display_group)

        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        summary_display_layout.addWidget(self.summary_text)

        layout.addWidget(summary_display_group)

        # Generate button
        generate_layout = QHBoxLayout()
        generate_layout.addStretch()

        self.generate_summary_btn = QPushButton("Generate Summary")
        self.generate_summary_btn.setMinimumHeight(40)
        self.generate_summary_btn.clicked.connect(self.generate_summary)
        self.generate_summary_btn.setEnabled(False)
        generate_layout.addWidget(self.generate_summary_btn)

        generate_layout.addStretch()
        layout.addLayout(generate_layout)

    def create_output_tab(self):
        """Create the output and document tab."""
        output_tab = QWidget()
        self.tab_widget.addTab(output_tab, "Document Output")

        layout = QVBoxLayout(output_tab)

        # Google Docs configuration group
        docs_group = QGroupBox("Google Docs Configuration")
        docs_layout = QFormLayout(docs_group)

        self.document_title_edit = QLineEdit()
        self.document_title_edit.setPlaceholderText(
            "Executive Summary - Week of {date}"
        )
        docs_layout.addRow("Document Title:", self.document_title_edit)

        self.folder_id_edit = QLineEdit()
        self.folder_id_edit.setPlaceholderText("Google Drive folder ID (optional)")
        docs_layout.addRow("Folder ID:", self.folder_id_edit)

        self.share_email_edit = QLineEdit()
        self.share_email_edit.setPlaceholderText(
            "Email to share document with (optional)"
        )
        docs_layout.addRow("Share with:", self.share_email_edit)

        layout.addWidget(docs_group)

        # Document preview
        preview_group = QGroupBox("Document Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        preview_layout.addWidget(self.preview_text)

        layout.addWidget(preview_group)

        # Action buttons
        actions_layout = QHBoxLayout()

        self.preview_btn = QPushButton("Preview Document")
        self.preview_btn.clicked.connect(self.preview_document)
        self.preview_btn.setEnabled(False)
        actions_layout.addWidget(self.preview_btn)

        self.create_doc_btn = QPushButton("Create Google Doc")
        self.create_doc_btn.clicked.connect(self.create_google_doc)
        self.create_doc_btn.setEnabled(False)
        actions_layout.addWidget(self.create_doc_btn)

        self.export_btn = QPushButton("Export to File")
        self.export_btn.clicked.connect(self.export_to_file)
        self.export_btn.setEnabled(False)
        actions_layout.addWidget(self.export_btn)

        layout.addLayout(actions_layout)

        # Document URL display
        self.document_url_label = QLabel()
        self.document_url_label.setStyleSheet(
            "color: blue; text-decoration: underline;"
        )
        self.document_url_label.setOpenExternalLinks(True)
        layout.addWidget(self.document_url_label)

    def create_status_bar(self):
        """Create the status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)

    def apply_styling(self):
        """Apply custom styling to the application."""
        style = """
        QMainWindow {
            background-color: #f0f0f0;
        }
        
        QTabWidget::pane {
            border: 1px solid #c0c0c0;
            background-color: white;
        }
        
        QTabWidget::tab-bar {
            alignment: left;
        }
        
        QTabBar::tab {
            background-color: #e0e0e0;
            border: 1px solid #c0c0c0;
            padding: 8px 16px;
            margin-right: 2px;
        }
        
        QTabBar::tab:selected {
            background-color: white;
            border-bottom: 1px solid white;
        }
        
        QGroupBox {
            font-weight: bold;
            border: 2px solid #c0c0c0;
            border-radius: 5px;
            margin-top: 10px;
            padding-top: 10px;
        }
        
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top center;
            padding: 0 5px;
        }
        
        QPushButton {
            background-color: #4CAF50;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: bold;
        }
        
        QPushButton:hover {
            background-color: #45a049;
        }
        
        QPushButton:pressed {
            background-color: #3d8b40;
        }
        
        QPushButton:disabled {
            background-color: #cccccc;
            color: #666666;
        }
        
        QLineEdit, QTextEdit, QComboBox, QSpinBox, QDateEdit {
            border: 1px solid #c0c0c0;
            border-radius: 4px;
            padding: 5px;
        }
        
        QLineEdit:focus, QTextEdit:focus {
            border: 2px solid #4CAF50;
        }
        """

        self.setStyleSheet(style)

    def check_initial_setup(self):
        """Check if initial setup is required."""
        if not self.config_manager.is_configured():
            self.show_setup_wizard()
        else:
            # Start credential monitoring for existing users
            self.credential_monitor.start_monitoring()
            self.setup_credential_notifications()

    def show_setup_wizard(self):
        """Show the setup wizard for new users."""
        wizard = SetupWizard(self.config_manager, self)
        result = wizard.exec()

        if result == SetupWizard.Accepted:
            # Setup completed successfully
            self.credential_monitor.start_monitoring()
            self.setup_credential_notifications()
            self.show_info(
                "Setup Complete",
                "Your Executive Summary Tool has been configured successfully! "
                "You can now start creating executive summaries.",
            )
        else:
            # User cancelled setup
            self.show_warning(
                "Setup Required",
                "The application requires configuration to function properly. "
                "You can access the setup wizard later from File → Setup Wizard.",
            )

    def setup_credential_notifications(self):
        """Setup credential monitoring notifications."""

        def show_credential_notification(message: str, severity: str, data: dict):
            if severity == "error":
                self.show_error("Credential Issue", message)
            elif severity == "warning":
                self.show_warning("Credential Warning", message)
            else:
                self.status_label.setText(message)

        from ..core.credential_monitor import CredentialNotificationManager

        self.notification_manager = CredentialNotificationManager(
            self.credential_monitor
        )
        self.notification_manager.add_notification_callback(
            show_credential_notification
        )

    def load_ui_configuration(self):
        """Load configuration into UI elements."""
        try:
            jira_config = self.config_manager.get_jira_config()

            self.jira_url_edit.setText(jira_config.url)
            self.jira_username_edit.setText(jira_config.username)

            # Load API token from secure storage
            api_token = self.config_manager.retrieve_credential("jira", "api_token")
            if api_token:
                self.jira_token_edit.setText(api_token)

            # Load users
            self.users_list.clear()
            for user in jira_config.default_users:
                self.users_list.addItem(user)

            # Load AI configuration
            ai_config = self.config_manager.get_ai_config()

            model_index = self.ai_model_combo.findText(ai_config.model_name)
            if model_index >= 0:
                self.ai_model_combo.setCurrentIndex(model_index)

            self.temperature_spin.setValue(int(ai_config.temperature * 100))
            self.max_tokens_spin.setValue(ai_config.max_tokens)

            if ai_config.custom_prompt:
                self.custom_prompt_edit.setPlainText(ai_config.custom_prompt)

            self.logger.info("UI configuration loaded")

        except Exception as e:
            self.logger.error(f"Failed to load UI configuration: {e}")
            self.show_error("Failed to load configuration", str(e))

    def save_ui_configuration(self):
        """Save UI configuration."""
        try:
            # Save Jira configuration
            self.config_manager.update_jira_config(
                url=self.jira_url_edit.text(),
                username=self.jira_username_edit.text(),
                default_users=[
                    self.users_list.item(i).text()
                    for i in range(self.users_list.count())
                ],
            )

            # Save AI configuration
            self.config_manager.update_ai_config(
                model_name=self.ai_model_combo.currentText(),
                temperature=self.temperature_spin.value() / 100.0,
                max_tokens=self.max_tokens_spin.value(),
                custom_prompt=self.custom_prompt_edit.toPlainText(),
            )

            # Save credentials if provided
            if self.jira_token_edit.text():
                self.config_manager.store_credential(
                    "jira", "api_token", self.jira_token_edit.text()
                )

            self.logger.info("UI configuration saved")

        except Exception as e:
            self.logger.error(f"Failed to save UI configuration: {e}")
            self.show_error("Failed to save configuration", str(e))

    def add_user(self):
        """Add user to the list."""
        user = self.user_input.text().strip()
        if user:
            self.users_list.addItem(user)
            self.user_input.clear()

    def remove_user(self):
        """Remove selected user from the list."""
        current_row = self.users_list.currentRow()
        if current_row >= 0:
            self.users_list.takeItem(current_row)

    def load_users_from_jira(self):
        """Load users from Jira."""
        # This would be implemented with a worker thread
        self.show_info(
            "Feature not yet implemented", "Load users from Jira is coming soon."
        )

    def fetch_jira_data(self):
        """Fetch data from Jira."""
        try:
            # Save current configuration
            self.save_ui_configuration()

            # Validate inputs
            if not self.jira_url_edit.text():
                self.show_error("Configuration Error", "Please enter Jira URL")
                return

            if not self.jira_username_edit.text():
                self.show_error("Configuration Error", "Please enter Jira username")
                return

            if self.users_list.count() == 0:
                self.show_error("Configuration Error", "Please add at least one user")
                return

            # Show progress
            self.show_progress("Fetching Jira data...")

            # TODO: Implement actual data fetching with worker thread
            # For now, show a placeholder
            self.current_activity_data = [
                {"id": "DEMO-1", "title": "Demo issue", "assignee": "demo.user"}
            ]

            self.hide_progress()
            self.generate_summary_btn.setEnabled(True)
            self.status_label.setText(
                f"Fetched {len(self.current_activity_data)} activities"
            )

        except Exception as e:
            self.hide_progress()
            self.logger.error(f"Failed to fetch Jira data: {e}")
            self.show_error("Data Fetch Error", str(e))

    def generate_summary(self):
        """Generate AI summary."""
        try:
            if not self.current_activity_data:
                self.show_error("No Data", "Please fetch Jira data first")
                return

            # Show progress
            self.show_progress("Generating summary...")

            # TODO: Implement actual summary generation
            # For now, show a placeholder
            self.current_summary = {
                "content": "This is a demo executive summary based on the fetched Jira data.",
                "model": "gemini-2.5-flash",
                "generated_at": datetime.now().isoformat(),
            }

            self.summary_text.setPlainText(self.current_summary["content"])

            self.hide_progress()
            self.preview_btn.setEnabled(True)
            self.create_doc_btn.setEnabled(True)
            self.export_btn.setEnabled(True)
            self.status_label.setText("Summary generated successfully")

        except Exception as e:
            self.hide_progress()
            self.logger.error(f"Failed to generate summary: {e}")
            self.show_error("Summary Generation Error", str(e))

    def preview_document(self):
        """Preview the document."""
        if self.current_summary:
            title = self.document_title_edit.text() or "Executive Summary"
            content = f"# {title}\n\n{self.current_summary['content']}"
            self.preview_text.setPlainText(content)
            self.tab_widget.setCurrentIndex(2)  # Switch to output tab

    def create_google_doc(self):
        """Create Google Doc."""
        try:
            if not self.current_summary:
                self.show_error("No Summary", "Please generate a summary first")
                return

            # Show progress
            self.show_progress("Creating Google Doc...")

            # TODO: Implement actual Google Doc creation
            # For now, show a placeholder
            doc_url = "https://docs.google.com/document/d/demo_document_id/edit"

            self.document_url_label.setText(f'<a href="{doc_url}">Open Document</a>')

            self.hide_progress()
            self.status_label.setText("Google Doc created successfully")

        except Exception as e:
            self.hide_progress()
            self.logger.error(f"Failed to create Google Doc: {e}")
            self.show_error("Document Creation Error", str(e))

    def export_to_file(self):
        """Export summary to file."""
        try:
            if not self.current_summary:
                self.show_error("No Summary", "Please generate a summary first")
                return

            # TODO: Implement file export
            self.show_info("Export", "File export feature coming soon")

        except Exception as e:
            self.logger.error(f"Failed to export to file: {e}")
            self.show_error("Export Error", str(e))

    def open_configuration_dialog(self):
        """Open configuration dialog."""
        dialog = ConfigDialog(self.config_manager, self)
        if dialog.exec() == ConfigDialog.Accepted:
            self.load_ui_configuration()

    def open_setup_wizard(self):
        """Open setup wizard."""
        self.show_setup_wizard()

    def test_connections(self):
        """Test all API connections."""
        # TODO: Implement connection testing
        self.show_info("Connection Test", "Connection testing feature coming soon")

    def new_summary(self):
        """Start a new summary."""
        self.current_activity_data = []
        self.current_summary = None
        self.summary_text.clear()
        self.preview_text.clear()
        self.document_url_label.clear()

        self.generate_summary_btn.setEnabled(False)
        self.preview_btn.setEnabled(False)
        self.create_doc_btn.setEnabled(False)
        self.export_btn.setEnabled(False)

        self.status_label.setText("Ready for new summary")

    def open_configuration(self):
        """Open configuration file."""
        # TODO: Implement configuration file opening
        self.show_info("Open Configuration", "Configuration file opening coming soon")

    def save_configuration(self):
        """Save configuration to file."""
        try:
            self.save_ui_configuration()
            self.show_info("Configuration Saved", "Configuration saved successfully")
        except Exception as e:
            self.show_error("Save Error", str(e))

    def show_about(self):
        """Show about dialog."""
        about_text = """
        <h2>Executive Summary Tool</h2>
        <p>Version 1.0.0</p>
        <p>A cross-platform desktop application for automated executive summary generation.</p>
        <p>Features:</p>
        <ul>
            <li>Jira data integration</li>
            <li>AI-powered summarization</li>
            <li>Google Docs output</li>
            <li>Secure credential management</li>
        </ul>
        <p>Built with PySide6 and Python.</p>
        """

        QMessageBox.about(self, "About", about_text)

    def show_progress(self, message: str):
        """Show progress indication."""
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.status_label.setText(message)

    def hide_progress(self):
        """Hide progress indication."""
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 100)

    def show_error(self, title: str, message: str):
        """Show error message."""
        QMessageBox.critical(self, title, message)

    def show_info(self, title: str, message: str):
        """Show information message."""
        QMessageBox.information(self, title, message)

    def show_warning(self, title: str, message: str):
        """Show warning message."""
        QMessageBox.warning(self, title, message)

    def closeEvent(self, event):
        """Handle application close event."""
        try:
            # Stop credential monitoring
            if hasattr(self, "credential_monitor"):
                self.credential_monitor.stop_monitoring()

            # Save configuration before closing
            self.save_ui_configuration()

            # Accept the close event
            event.accept()

        except Exception as e:
            self.logger.error(f"Error during application close: {e}")
            event.accept()  # Close anyway
