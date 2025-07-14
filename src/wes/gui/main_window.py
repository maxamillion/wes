"""Main application window with unified configuration integration."""

import asyncio
import json
import sys
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QDate, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QStatusBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core.config_manager import ConfigManager
from ..core.credential_monitor import CredentialMonitor, MonitoringConfig
from ..utils.exceptions import WesError
from ..utils.logging_config import get_logger
from .unified_config import ConfigState as UnifiedConfigState
from .unified_config import UnifiedConfigDialog
from .unified_config.utils.config_detector import ConfigDetector


class ViewState(Enum):
    """Enumeration of possible view states."""

    WELCOME = "welcome"
    MAIN = "main"
    PROGRESS = "progress"
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

        # Initialize UI
        self.init_ui()

        # Check initial configuration state
        self.check_initial_setup()

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

        main_layout.addWidget(self.main_stack)

        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Start credential monitoring
        self.credential_monitor.start()
        self.credential_monitor.validation_complete.connect(
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

        # Project filter
        self.project_filter = QLineEdit()
        self.project_filter.setPlaceholderText("e.g., PROJ-123, PROJ-456")
        options_layout.addRow("Projects (optional):", self.project_filter)

        # Assignee filter
        self.assignee_filter = QLineEdit()
        self.assignee_filter.setPlaceholderText("e.g., john.doe@company.com")
        options_layout.addRow("Assignee (optional):", self.assignee_filter)

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
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.cancel_summary)
        layout.addWidget(cancel_button)

        self.main_stack.addWidget(self.progress_widget)

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

        if result == QDialog.Accepted:
            # Configuration was saved
            self.update_config_status()
            self.status_bar.showMessage("Configuration updated", 3000)

    def on_configuration_updated(self, config: Dict[str, Any]):
        """Handle configuration updates from the unified dialog."""
        # Update UI elements that depend on configuration
        self.update_config_status()

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

        # Switch to progress view
        self.switch_view(ViewState.PROGRESS)

        # Start summary generation
        # ... (implementation of summary generation)

    def cancel_summary(self):
        """Cancel summary generation."""
        if self.summary_worker and self.summary_worker.isRunning():
            self.summary_worker.quit()
            self.summary_worker.wait()

        self.switch_view(ViewState.MAIN)

    def show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About WES",
            "WES - Executive Summary Tool\n\n"
            "Version 1.0.0\n\n"
            "Automated executive summary generation from Jira data.",
        )

    def on_credential_validation_complete(self, results: Dict[str, Any]):
        """Handle credential validation results."""
        # Update UI based on validation results
        if hasattr(self, "config_status_label"):
            self.update_config_status()

    def closeEvent(self, event):
        """Handle application close."""
        # Stop credential monitor
        self.credential_monitor.stop()

        # Cancel any running operations
        if self.summary_worker and self.summary_worker.isRunning():
            self.summary_worker.quit()
            self.summary_worker.wait()

        event.accept()
