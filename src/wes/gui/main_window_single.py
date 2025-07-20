"""Single-window main application for the Executive Summary Tool."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict

from PySide6.QtCore import (
    QDate,
    Qt,
    QThread,
    QTimer,
    Signal,
)
from PySide6.QtGui import QAction, QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
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
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core.config_manager import ConfigManager
from ..core.credential_monitor import CredentialMonitor, MonitoringConfig
from ..utils.logging_config import get_logger
from .credential_validators import CredentialValidator
from .unified_config import UnifiedConfigDialog
from .unified_config.types import ConfigState as UnifiedConfigState
from .unified_config.utils.config_detector import ConfigDetector


class ValidationWorker(QThread):
    """Worker for background credential validation."""

    validation_complete = Signal(str, bool, str)  # service, success, message

    def __init__(self, service: str, credentials: Dict[str, str], parent=None):
        super().__init__(parent)
        self.service = service
        self.credentials = credentials
        self.validator = CredentialValidator()

    def run(self):
        """Validate credentials in background thread."""
        try:
            if self.service == "jira":
                success, message = self.validator.validate_jira_credentials(
                    self.credentials.get("url", ""),
                    self.credentials.get("username", ""),
                    self.credentials.get("api_token", ""),
                )
            elif self.service == "gemini":
                success, message = self.validator.validate_gemini_credentials(
                    self.credentials.get("api_key", "")
                )
            else:
                success, message = False, "Unknown service"

            self.validation_complete.emit(self.service, success, message)

        except Exception as e:
            self.validation_complete.emit(self.service, False, str(e))


class ViewState(Enum):
    """Enumeration of possible view states."""

    WELCOME = "welcome"
    MAIN = "main"
    PROGRESS = "progress"


class SingleWindowMainWindow(QMainWindow):
    """Main application window with integrated views."""

    def __init__(self):
        super().__init__()

        self.logger = get_logger(__name__)
        self.config_manager = ConfigManager()
        self.config_detector = ConfigDetector()
        self.credential_validator = CredentialValidator()

        # Initialize credential monitoring
        monitoring_config = MonitoringConfig(
            check_interval_minutes=60,
            auto_refresh_enabled=True,
            notification_enabled=True,
        )
        self.credential_monitor = CredentialMonitor(
            self.config_manager, monitoring_config
        )

        # Initialize state
        self.current_view = ViewState.WELCOME
        self.previous_view = ViewState.WELCOME  # Track previous view for navigation
        self.setup_completed = False
        self.current_activity_data = []
        self.current_summary = None
        self.validation_threads = []

        # Initialize UI
        self.init_ui()

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
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Create menu bar
        self.create_menu_bar()

        # Create navigation bar
        self.create_navigation_bar()
        main_layout.addWidget(self.nav_bar)

        # Create stacked widget for different views
        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget)

        # Create views
        self.create_welcome_view()
        self.create_main_view()
        self.create_progress_view()

        # Create status bar
        self.create_status_bar()

        # Apply styling
        self.apply_styling()

    def create_menu_bar(self):
        """Create the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")

        new_action = QAction("New Summary", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_summary)
        file_menu.addAction(new_action)

        save_action = QAction("Save Configuration", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_configuration)
        file_menu.addAction(save_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit menu
        edit_menu = menubar.addMenu("Edit")

        settings_action = QAction("Settings...", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self.show_unified_settings)
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

    def create_navigation_bar(self):
        """Create navigation bar for switching between views."""
        self.nav_bar = QWidget()
        self.nav_bar.setObjectName("navBar")
        nav_layout = QHBoxLayout(self.nav_bar)
        nav_layout.setContentsMargins(10, 5, 10, 5)

        # Navigation buttons
        self.nav_buttons = {}

        self.nav_buttons[ViewState.MAIN] = QPushButton("Home")
        self.nav_buttons[ViewState.MAIN].clicked.connect(
            lambda: self.switch_view(ViewState.MAIN)
        )

        # Settings button (opens unified config)
        settings_button = QPushButton("Settings")
        settings_button.clicked.connect(self.show_unified_settings)

        # Add buttons to layout
        for button in self.nav_buttons.values():
            button.setCheckable(True)
            nav_layout.addWidget(button)

        nav_layout.addWidget(settings_button)

        nav_layout.addStretch()

        # Hide navigation initially
        self.nav_bar.setVisible(False)

    def create_welcome_view(self):
        """Create welcome/landing view."""
        welcome_widget = QWidget()
        layout = QVBoxLayout(welcome_widget)
        layout.setAlignment(Qt.AlignCenter)

        # Logo/Icon placeholder
        icon_label = QLabel()
        icon_label.setPixmap(
            QPixmap(":/icons/app_icon.png").scaled(128, 128, Qt.KeepAspectRatio)
        )
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)

        # Title
        title_label = QLabel("Executive Summary Tool")
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # Subtitle
        subtitle_label = QLabel("Automate your executive summary generation")
        subtitle_font = QFont()
        subtitle_font.setPointSize(14)
        subtitle_label.setFont(subtitle_font)
        subtitle_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle_label)

        layout.addSpacing(40)

        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.setAlignment(Qt.AlignCenter)

        self.get_started_btn = QPushButton("Get Started")
        self.get_started_btn.setMinimumSize(150, 40)
        self.get_started_btn.clicked.connect(self.start_setup)
        button_layout.addWidget(self.get_started_btn)

        self.skip_setup_btn = QPushButton("Skip Setup")
        self.skip_setup_btn.setMinimumSize(150, 40)
        self.skip_setup_btn.clicked.connect(self.skip_setup)
        button_layout.addWidget(self.skip_setup_btn)

        layout.addLayout(button_layout)

        self.stacked_widget.addWidget(welcome_widget)

    def create_setup_view(self):
        """Create integrated setup view."""
        setup_widget = QWidget()
        main_layout = QVBoxLayout(setup_widget)

        # Setup header
        header_label = QLabel("Initial Setup")
        header_font = QFont()
        header_font.setPointSize(18)
        header_font.setBold(True)
        header_label.setFont(header_font)
        main_layout.addWidget(header_label)

        # Setup steps indicator
        self.setup_steps_widget = self.create_setup_steps_indicator()
        main_layout.addWidget(self.setup_steps_widget)

        # Setup content area with stacked widget
        self.setup_stack = QStackedWidget()
        main_layout.addWidget(self.setup_stack)

        # Create setup pages
        self.create_service_selection_page()
        self.create_jira_setup_page()
        self.create_gemini_setup_page()
        self.create_setup_summary_page()

        # Navigation buttons
        nav_layout = QHBoxLayout()
        self.prev_btn = QPushButton("Previous")
        self.prev_btn.clicked.connect(self.previous_setup_page)
        nav_layout.addWidget(self.prev_btn)

        nav_layout.addStretch()

        self.next_btn = QPushButton("Next")
        self.next_btn.clicked.connect(self.next_setup_page)
        nav_layout.addWidget(self.next_btn)

        self.finish_btn = QPushButton("Finish")
        self.finish_btn.clicked.connect(self.finish_setup)
        self.finish_btn.setVisible(False)
        nav_layout.addWidget(self.finish_btn)

        main_layout.addLayout(nav_layout)

        self.stacked_widget.addWidget(setup_widget)

    def create_setup_steps_indicator(self):
        """Create steps indicator for setup process."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setAlignment(Qt.AlignCenter)

        self.setup_steps = [
            "Service Selection",
            "Jira Setup",
            "Google Setup",
            "Gemini Setup",
            "Summary",
        ]

        self.step_labels = []
        for i, step in enumerate(self.setup_steps):
            if i > 0:
                # Add connector line
                line = QFrame()
                line.setFrameShape(QFrame.HLine)
                line.setFixedWidth(50)
                layout.addWidget(line)

            # Step indicator
            step_widget = QWidget()
            step_layout = QVBoxLayout(step_widget)
            step_layout.setAlignment(Qt.AlignCenter)

            # Circle with number
            circle_label = QLabel(str(i + 1))
            circle_label.setFixedSize(30, 30)
            circle_label.setAlignment(Qt.AlignCenter)
            circle_label.setObjectName(f"stepCircle_{i}")
            step_layout.addWidget(circle_label)

            # Step name
            name_label = QLabel(step)
            name_label.setAlignment(Qt.AlignCenter)
            step_layout.addWidget(name_label)

            self.step_labels.append((circle_label, name_label))
            layout.addWidget(step_widget)

        return widget

    def create_service_selection_page(self):
        """Create service selection page for setup."""
        page = QWidget()
        layout = QVBoxLayout(page)

        # Title
        title_label = QLabel("Select Services to Configure")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # Description
        desc_label = QLabel(
            "Choose which services you want to configure. "
            "You can always add or modify services later."
        )
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        layout.addSpacing(20)

        # Service checkboxes
        self.service_checkboxes = {}

        services = [
            ("jira", "Jira", "Connect to Jira for activity tracking"),
            ("gemini", "Google Gemini", "AI-powered summary generation"),
        ]

        for service_id, name, description in services:
            group = QGroupBox(name)
            group_layout = QVBoxLayout(group)

            checkbox = QCheckBox(f"Enable {name}")
            checkbox.setChecked(True)
            self.service_checkboxes[service_id] = checkbox
            group_layout.addWidget(checkbox)

            desc = QLabel(description)
            desc.setWordWrap(True)
            group_layout.addWidget(desc)

            layout.addWidget(group)

        layout.addStretch()

        self.setup_stack.addWidget(page)

    def create_jira_setup_page(self):
        """Create Jira setup page."""
        page = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)

        layout = QVBoxLayout(page)

        # Title
        title_label = QLabel("Jira Configuration")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # Form
        form_layout = QFormLayout()

        self.jira_url_input = QLineEdit()
        self.jira_url_input.setText("https://issues.redhat.com")  # Set default value
        form_layout.addRow("Jira URL:", self.jira_url_input)

        self.jira_username_input = QLineEdit()
        self.jira_username_input.setPlaceholderText("your.email@company.com")
        form_layout.addRow("Username:", self.jira_username_input)

        self.jira_token_input = QLineEdit()
        self.jira_token_input.setEchoMode(QLineEdit.Password)
        self.jira_token_input.setPlaceholderText("Your Jira API token")
        form_layout.addRow("API Token:", self.jira_token_input)

        layout.addLayout(form_layout)

        # Test connection button
        test_layout = QHBoxLayout()
        self.jira_test_btn = QPushButton("Test Connection")
        self.jira_test_btn.clicked.connect(lambda: self.test_credentials("jira"))
        test_layout.addWidget(self.jira_test_btn)

        self.jira_status_label = QLabel()
        test_layout.addWidget(self.jira_status_label)
        test_layout.addStretch()

        layout.addLayout(test_layout)

        layout.addStretch()

        self.setup_stack.addWidget(scroll)

    def create_gemini_setup_page(self):
        """Create Gemini setup page."""
        page = QWidget()
        layout = QVBoxLayout(page)

        # Title
        title_label = QLabel("Google Gemini Configuration")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # Form
        form_layout = QFormLayout()

        self.gemini_key_input = QLineEdit()
        self.gemini_key_input.setEchoMode(QLineEdit.Password)
        self.gemini_key_input.setPlaceholderText("Your Gemini API key")
        form_layout.addRow("API Key:", self.gemini_key_input)

        layout.addLayout(form_layout)

        # Test connection
        test_layout = QHBoxLayout()
        self.gemini_test_btn = QPushButton("Test Connection")
        self.gemini_test_btn.clicked.connect(lambda: self.test_credentials("gemini"))
        test_layout.addWidget(self.gemini_test_btn)

        self.gemini_status_label = QLabel()
        test_layout.addWidget(self.gemini_status_label)
        test_layout.addStretch()

        layout.addLayout(test_layout)

        layout.addStretch()

        self.setup_stack.addWidget(page)

    def create_setup_summary_page(self):
        """Create setup summary page."""
        page = QWidget()
        layout = QVBoxLayout(page)

        # Title
        title_label = QLabel("Setup Summary")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # Summary text
        self.setup_summary_text = QTextEdit()
        self.setup_summary_text.setReadOnly(True)
        layout.addWidget(self.setup_summary_text)

        self.setup_stack.addWidget(page)

    def create_main_view(self):
        """Create main application view with tabs."""
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)

        # Tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # Create tabs
        self.create_data_tab()
        self.create_summary_tab()
        self.create_output_tab()

        self.stacked_widget.addWidget(main_widget)

    def create_data_tab(self):
        """Create the data configuration tab."""
        data_tab = QWidget()
        self.tab_widget.addTab(data_tab, "Data Configuration")

        layout = QVBoxLayout(data_tab)

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

        # Export configuration group
        export_group = QGroupBox("Export Configuration")
        export_layout = QFormLayout(export_group)

        self.document_title_edit = QLineEdit()
        self.document_title_edit.setPlaceholderText(
            "Executive Summary - Week of {date}"
        )
        export_layout.addRow("Document Title:", self.document_title_edit)

        layout.addWidget(export_group)

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

        self.export_btn = QPushButton("Export Document")
        self.export_btn.clicked.connect(self.export_document)
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

    def create_config_view(self):
        """Create advanced configuration view."""
        config_widget = QWidget()
        layout = QVBoxLayout(config_widget)

        # Header
        header_label = QLabel("Advanced Configuration")
        header_font = QFont()
        header_font.setPointSize(18)
        header_font.setBold(True)
        header_label.setFont(header_font)
        layout.addWidget(header_label)

        # Tab widget for different config sections
        config_tabs = QTabWidget()
        layout.addWidget(config_tabs)

        # Jira config tab
        self.create_jira_config_tab(config_tabs)

        # AI config tab
        self.create_ai_config_tab(config_tabs)

        # App config tab
        self.create_app_config_tab(config_tabs)

        # Save button
        save_layout = QHBoxLayout()
        save_layout.addStretch()

        save_btn = QPushButton("Save Configuration")
        save_btn.clicked.connect(self.save_all_configuration)
        save_layout.addWidget(save_btn)

        layout.addLayout(save_layout)

        self.stacked_widget.addWidget(config_widget)

    def create_jira_config_tab(self, parent_tabs):
        """Create Jira configuration tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        form_layout = QFormLayout()

        self.config_jira_url = QLineEdit()
        self.config_jira_url.setText("https://issues.redhat.com")  # Set default value
        form_layout.addRow("Jira URL:", self.config_jira_url)

        self.config_jira_username = QLineEdit()
        form_layout.addRow("Username:", self.config_jira_username)

        self.config_jira_token = QLineEdit()
        self.config_jira_token.setEchoMode(QLineEdit.Password)
        form_layout.addRow("API Token:", self.config_jira_token)

        layout.addLayout(form_layout)
        layout.addStretch()

        parent_tabs.addTab(tab, "Jira")

    def create_ai_config_tab(self, parent_tabs):
        """Create AI configuration tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        form_layout = QFormLayout()

        self.config_gemini_key = QLineEdit()
        self.config_gemini_key.setEchoMode(QLineEdit.Password)
        form_layout.addRow("Gemini API Key:", self.config_gemini_key)

        self.config_ai_model = QComboBox()
        self.config_ai_model.addItems(["gemini-2.5-flash", "gemini-2.5-pro"])
        form_layout.addRow("Model:", self.config_ai_model)

        self.config_temperature = QSpinBox()
        self.config_temperature.setRange(0, 100)
        self.config_temperature.setValue(70)
        self.config_temperature.setSuffix("%")
        form_layout.addRow("Temperature:", self.config_temperature)

        self.config_max_tokens = QSpinBox()
        self.config_max_tokens.setRange(100, 8192)
        self.config_max_tokens.setValue(2048)
        form_layout.addRow("Max Tokens:", self.config_max_tokens)

        layout.addLayout(form_layout)
        layout.addStretch()

        parent_tabs.addTab(tab, "AI")

    def create_app_config_tab(self, parent_tabs):
        """Create application configuration tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        form_layout = QFormLayout()

        self.config_auto_save = QCheckBox()
        self.config_auto_save.setChecked(True)
        form_layout.addRow("Auto-save configuration:", self.config_auto_save)

        self.config_check_updates = QCheckBox()
        self.config_check_updates.setChecked(True)
        form_layout.addRow("Check for updates:", self.config_check_updates)

        layout.addLayout(form_layout)
        layout.addStretch()

        parent_tabs.addTab(tab, "Application")

    def create_progress_view(self):
        """Create embedded progress view."""
        progress_widget = QWidget()
        layout = QVBoxLayout(progress_widget)
        layout.setAlignment(Qt.AlignCenter)

        # Progress content container
        content_widget = QWidget()
        content_widget.setMaximumWidth(600)
        content_layout = QVBoxLayout(content_widget)

        # Main message
        self.progress_main_label = QLabel("Processing...")
        self.progress_main_label.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        self.progress_main_label.setFont(font)
        content_layout.addWidget(self.progress_main_label)

        # Detail message
        self.progress_detail_label = QLabel("")
        self.progress_detail_label.setAlignment(Qt.AlignCenter)
        self.progress_detail_label.setWordWrap(True)
        content_layout.addWidget(self.progress_detail_label)

        content_layout.addSpacing(20)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        content_layout.addWidget(self.progress_bar)

        # Log area
        self.progress_log = QTextEdit()
        self.progress_log.setMaximumHeight(200)
        self.progress_log.setReadOnly(True)
        content_layout.addWidget(self.progress_log)

        # Cancel button
        cancel_layout = QHBoxLayout()
        cancel_layout.setAlignment(Qt.AlignCenter)
        self.progress_cancel_btn = QPushButton("Cancel")
        self.progress_cancel_btn.clicked.connect(self.cancel_operation)
        cancel_layout.addWidget(self.progress_cancel_btn)
        content_layout.addLayout(cancel_layout)

        layout.addWidget(content_widget)

        self.stacked_widget.addWidget(progress_widget)

    def create_status_bar(self):
        """Create the status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Status label
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)

    def apply_styling(self):
        """Apply custom styling to the application."""
        style = """
        QMainWindow {
            background-color: #f5f5f5;
        }

        #navBar {
            background-color: #ffffff;
            border-bottom: 1px solid #e0e0e0;
        }

        #navBar QPushButton {
            background-color: transparent;
            border: none;
            padding: 8px 16px;
            margin: 0 5px;
            font-weight: bold;
            color: #666666;
        }

        #navBar QPushButton:hover {
            color: #4CAF50;
        }

        #navBar QPushButton:checked {
            color: #4CAF50;
            border-bottom: 2px solid #4CAF50;
        }

        QTabWidget::pane {
            border: 1px solid #e0e0e0;
            background-color: white;
        }

        QTabBar::tab {
            background-color: #f0f0f0;
            border: 1px solid #e0e0e0;
            padding: 8px 16px;
            margin-right: 2px;
        }

        QTabBar::tab:selected {
            background-color: white;
            border-bottom: 1px solid white;
        }

        QGroupBox {
            font-weight: bold;
            border: 1px solid #e0e0e0;
            border-radius: 5px;
            margin-top: 10px;
            padding-top: 10px;
            background-color: white;
        }

        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 10px;
            background-color: white;
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
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            padding: 5px;
            background-color: white;
        }

        QLineEdit:focus, QTextEdit:focus {
            border: 2px solid #4CAF50;
        }

        /* Setup steps styling */
        QLabel[objectName^="stepCircle_"] {
            background-color: #e0e0e0;
            border-radius: 15px;
            color: #666666;
        }

        QLabel#stepCircle_0 {
            background-color: #4CAF50;
            color: white;
        }
        """

        self.setStyleSheet(style)

    def check_initial_setup(self):
        """Check if initial setup is required."""
        # Use the new config detector to check state
        config_state = self.config_detector.detect_state(self.config_manager.config)

        if config_state == UnifiedConfigState.EMPTY:
            # No configuration at all, show welcome
            self.switch_view(ViewState.WELCOME)
        else:
            # Has some configuration, go to main view
            self.switch_view(ViewState.MAIN)
            self.nav_bar.setVisible(True)
            self.credential_monitor.start_monitoring()
            self.load_configuration()

            # If configuration is incomplete, show a message
            if config_state == UnifiedConfigState.INCOMPLETE:
                self.statusBar().showMessage(
                    "Configuration incomplete. Click Settings to complete setup.", 5000
                )

    def switch_view(self, view_state: ViewState):
        """Switch to a different view."""
        # Don't track progress view as previous view
        if self.current_view != ViewState.PROGRESS:
            self.previous_view = self.current_view

        self.current_view = view_state

        # Update navigation buttons
        for state, button in self.nav_buttons.items():
            button.setChecked(state == view_state)

        # Switch stacked widget
        if view_state == ViewState.WELCOME:
            self.stacked_widget.setCurrentIndex(0)
        elif view_state == ViewState.MAIN:
            self.stacked_widget.setCurrentIndex(1)
        elif view_state == ViewState.PROGRESS:
            self.stacked_widget.setCurrentIndex(2)

    def start_setup(self):
        """Start the setup process."""
        # Open unified settings dialog
        self.show_unified_settings()

    def skip_setup(self):
        """Skip setup and go to main view."""
        self.switch_view(ViewState.MAIN)
        self.nav_bar.setVisible(True)
        self.statusBar().showMessage(
            "Setup skipped. You can configure services later in Settings.", 5000
        )

    def show_unified_settings(self):
        """Show the unified settings dialog."""
        dialog = UnifiedConfigDialog(self.config_manager, self)

        # Connect to handle configuration updates
        dialog.configuration_complete.connect(self.on_configuration_updated)

        # Show dialog
        result = dialog.exec()

        if result == QDialog.DialogCode.Accepted:
            # Configuration was saved
            self.update_config_status()
            self.statusBar().showMessage("Configuration updated", 3000)

            # If we're on welcome screen and config is now complete,
            # switch to main view
            if self.current_view == ViewState.WELCOME:
                config_state = self.config_detector.detect_state(
                    self.config_manager.config
                )
                if config_state == UnifiedConfigState.COMPLETE:
                    self.switch_view(ViewState.MAIN)
                    self.nav_bar.setVisible(True)

    def on_configuration_updated(self, config: Dict[str, Any]):
        """Handle configuration updates from the unified dialog."""
        # Update any UI elements that depend on configuration
        self.update_config_status()

    def update_config_status(self):
        """Update configuration status display."""
        # This updates any status indicators in the UI

    # OLD SETUP METHODS - Replaced by UnifiedConfigDialog
    # These methods are kept commented for reference but are no longer used

    # def previous_setup_page(self):
    #     """Go to previous setup page."""
    #     current = self.setup_stack.currentIndex()
    #     if current > 0:
    #         self.setup_stack.setCurrentIndex(current - 1)
    #         self.update_setup_navigation()
    #
    # def next_setup_page(self):
    #     """Go to next setup page."""
    #     current = self.setup_stack.currentIndex()
    #     if current < self.setup_stack.count() - 1:
    #         # Validate current page before proceeding
    #         if self.validate_setup_page(current):
    #             self.setup_stack.setCurrentIndex(current + 1)
    #             self.update_setup_navigation()
    #
    # def validate_setup_page(self, page_index: int) -> bool:
    #     """Validate setup page before proceeding."""
    #     if page_index == 0:
    #         # Service selection - always valid
    #         return True
    #     elif page_index == 1:
    #         # Jira setup
    #         if not self.service_checkboxes["jira"].isChecked():
    #             return True
    #         if not self.jira_url_input.text() or not self.jira_username_input.text():
    #             self.show_error("Validation Error", "Please fill in all Jira fields")
    #             return False
    #         return True
    #     elif page_index == 2:
    #         # Google setup
    #         if not self.service_checkboxes["google"].isChecked():
    #             return True
    #         return True
    #     elif page_index == 3:
    #         # Gemini setup
    #         if not self.service_checkboxes["gemini"].isChecked():
    #             return True
    #         if not self.gemini_key_input.text():
    #             self.show_error("Validation Error", "Please enter Gemini API key")
    #             return False
    #         return True
    #     return True
    #
    # def update_setup_navigation(self):
    #     """Update setup navigation buttons and indicators."""
    #     current = self.setup_stack.currentIndex()
    #     total = self.setup_stack.count()
    #
    #     # Update buttons
    #     self.prev_btn.setEnabled(current > 0)
    #     self.next_btn.setVisible(current < total - 1)
    #     self.finish_btn.setVisible(current == total - 1)
    #
    #     # Update step indicators
    #     for i, (circle, name) in enumerate(self.step_labels):
    #         if i < current:
    #             circle.setStyleSheet("background-color: #4CAF50; color: white;")
    #         elif i == current:
    #             circle.setStyleSheet("background-color: #2196F3; color: white;")
    #         else:
    #             circle.setStyleSheet("background-color: #e0e0e0; color: #666666;")
    #
    #     # Update summary if on last page
    #     if current == total - 1:
    #         self.update_setup_summary()
    #
    # def update_setup_summary(self):
    #     """Update setup summary page."""
    #     summary_lines = ["Setup Summary\n" + "=" * 40 + "\n"]
    #
    #     if self.service_checkboxes["jira"].isChecked():
    #         summary_lines.append("Jira Configuration:")
    #         summary_lines.append(f"  URL: {self.jira_url_input.text()}")
    #         summary_lines.append(f"  Username: {self.jira_username_input.text()}")
    #         summary_lines.append("")
    #     if self.service_checkboxes["gemini"].isChecked():
    #         summary_lines.append("Google Gemini Configuration:")
    #         summary_lines.append(
    #             "  API Key: Configured"
    #             if self.gemini_key_input.text()
    #             else "  API Key: Not configured"
    #         )
    #         summary_lines.append("")
    #
    #     self.setup_summary_text.setPlainText("\n".join(summary_lines))
    #
    # def finish_setup(self):
    #     """Finish setup and save configuration."""
    #     try:
    #         # Save Jira config
    #         if self.service_checkboxes["jira"].isChecked():
    #             self.config_manager.update_jira_config(
    #                 url=self.jira_url_input.text(),
    #                 username=self.jira_username_input.text(),
    #             )
    #             if self.jira_token_input.text():
    #                 self.config_manager.store_credential(
    #                     "jira", "api_token", self.jira_token_input.text()
    #                 )
    #
    #         # Save Gemini config
    #         if self.service_checkboxes["gemini"].isChecked():
    #             if self.gemini_key_input.text():
    #                 self.config_manager.store_credential(
    #                     "gemini", "api_key", self.gemini_key_input.text()
    #                 )
    #
    #         self.setup_completed = True
    #         self.switch_view(ViewState.MAIN)
    #         self.credential_monitor.start_monitoring()
    #         self.load_configuration()
    #         self.show_info(
    #             "Setup Complete", "Your configuration has been saved successfully!"
    #         )
    #
    #     except Exception as e:
    #         self.logger.error(f"Failed to finish setup: {e}")
    #         self.show_error("Setup Error", str(e))

    # OLD TEST CREDENTIALS METHOD - Replaced by UnifiedConfigDialog's connection testing
    # def test_credentials(self, service: str):
    #     """Test credentials for a service."""
    #     self.show_progress_message(f"Testing {service} connection...", "Please wait...")
    #
    #     if service == "jira":
    #         credentials = {
    #             "url": self.jira_url_input.text(),
    #             "username": self.jira_username_input.text(),
    #             "api_token": self.jira_token_input.text(),
    #         }
    #         status_label = self.jira_status_label
    #     elif service == "gemini":
    #         credentials = {
    #             "api_key": self.gemini_key_input.text(),
    #         }
    #         status_label = self.gemini_status_label
    #     else:
    #         return
    #
    #     # Run validation in background
    #     def on_validation_complete(_svc: str, success: bool, message: str):
    #         self.hide_progress_message()
    #         if success:
    #             status_label.setText(f"✓ {message}")
    #             status_label.setStyleSheet("color: green;")
    #         else:
    #             status_label.setText(f"✗ {message}")
    #             status_label.setStyleSheet("color: red;")
    #
    #     # Create and run validation worker
    #     worker = ValidationWorker(service, credentials)
    #     worker.validation_complete.connect(on_validation_complete)
    #     worker.finished.connect(worker.deleteLater)
    #     worker.start()
    #     self.validation_threads.append(worker)

    def load_configuration(self):
        """Load configuration into UI elements."""
        try:
            # Load Jira config
            jira_config = self.config_manager.get_jira_config()
            if hasattr(self, "jira_url_input"):
                # Only set URL if it's not empty (preserve default otherwise)
                if jira_config.url:
                    self.jira_url_input.setText(jira_config.url)
                self.jira_username_input.setText(jira_config.username)

            # Load users
            if hasattr(self, "users_list"):
                self.users_list.clear()
                for user in jira_config.default_users:
                    self.users_list.addItem(user)

            # Load AI config
            ai_config = self.config_manager.get_ai_config()
            if hasattr(self, "ai_model_combo"):
                model_index = self.ai_model_combo.findText(ai_config.model_name)
                if model_index >= 0:
                    self.ai_model_combo.setCurrentIndex(model_index)
                self.temperature_spin.setValue(int(ai_config.temperature * 100))
                self.max_tokens_spin.setValue(ai_config.max_tokens)

        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")

    # OLD CONFIG VIEW METHODS - Replaced by UnifiedConfigDialog
    # def load_config_view(self):
    #     """Load configuration into config view."""
    #     try:
    #         # Load Jira config
    #         jira_config = self.config_manager.get_jira_config()
    #         # Only set URL if it's not empty (preserve default otherwise)
    #         if jira_config.url:
    #             self.config_jira_url.setText(jira_config.url)
    #         self.config_jira_username.setText(jira_config.username)
    #
    #         # Load AI config
    #         ai_config = self.config_manager.get_ai_config()
    #         model_index = self.config_ai_model.findText(ai_config.model_name)
    #         if model_index >= 0:
    #             self.config_ai_model.setCurrentIndex(model_index)
    #         self.config_temperature.setValue(int(ai_config.temperature * 100))
    #         self.config_max_tokens.setValue(ai_config.max_tokens)
    #
    #     except Exception as e:
    #         self.logger.error(f"Failed to load config view: {e}")
    #
    # def save_all_configuration(self):
    #     """Save all configuration from config view."""
    #     try:
    #         # Save Jira config
    #         self.config_manager.update_jira_config(
    #             url=self.config_jira_url.text(),
    #             username=self.config_jira_username.text(),
    #         )
    #         if self.config_jira_token.text():
    #             self.config_manager.store_credential(
    #                 "jira", "api_token", self.config_jira_token.text()
    #             )
    #
    #         # Save AI config
    #         self.config_manager.update_ai_config(
    #             model_name=self.config_ai_model.currentText(),
    #             temperature=self.config_temperature.value() / 100.0,
    #             max_tokens=self.config_max_tokens.value(),
    #         )
    #         if self.config_gemini_key.text():
    #             self.config_manager.store_credential(
    #                 "gemini", "api_key", self.config_gemini_key.text()
    #             )
    #
    #         self.load_configuration()
    #         self.show_info(
    #             "Configuration Saved", "All settings have been saved successfully!"
    #         )
    #
    #     except Exception as e:
    #         self.logger.error(f"Failed to save configuration: {e}")
    #         self.show_error("Save Error", str(e))

    def show_progress_message(self, message: str, detail: str = ""):
        """Show progress view with message."""
        self.progress_main_label.setText(message)
        self.progress_detail_label.setText(detail)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_log.clear()
        self.switch_view(ViewState.PROGRESS)

    def hide_progress_message(self):
        """Hide progress and return to previous view."""
        if self.current_view == ViewState.PROGRESS:
            # Return to the previous view instead of always going to MAIN
            self.switch_view(self.previous_view)

    def update_progress(self, value: int, message: str = ""):
        """Update progress bar and message."""
        if self.current_view == ViewState.PROGRESS:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(value)
            if message:
                self.progress_detail_label.setText(message)

    def add_progress_log(self, text: str):
        """Add text to progress log."""
        if self.current_view == ViewState.PROGRESS:
            self.progress_log.append(text)

    def cancel_operation(self):
        """Cancel current operation."""
        # This would be connected to actual cancellation logic
        self.hide_progress_message()

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

    def fetch_jira_data(self):
        """Fetch data from Jira."""
        try:
            # Show progress
            self.show_progress_message(
                "Fetching Jira data...", "Connecting to Jira server"
            )

            # TODO: Implement actual data fetching
            # Simulate progress
            QTimer.singleShot(
                1000, lambda: self.update_progress(50, "Retrieving issues...")
            )
            QTimer.singleShot(
                2000, lambda: self.update_progress(100, "Data fetched successfully")
            )
            QTimer.singleShot(2500, self.hide_progress_message)

            self.current_activity_data = [
                {"id": "DEMO-1", "title": "Demo issue", "assignee": "demo.user"}
            ]

            self.generate_summary_btn.setEnabled(True)
            self.status_label.setText(
                f"Fetched {len(self.current_activity_data)} activities"
            )

        except Exception as e:
            self.hide_progress_message()
            self.logger.error(f"Failed to fetch Jira data: {e}")
            self.show_error("Data Fetch Error", str(e))

    def generate_summary(self):
        """Generate AI summary."""
        try:
            if not self.current_activity_data:
                self.show_error("No Data", "Please fetch Jira data first")
                return

            # Show progress
            self.show_progress_message(
                "Generating summary...", "Processing with AI model"
            )

            # TODO: Implement actual summary generation
            # Simulate progress
            QTimer.singleShot(
                1000, lambda: self.update_progress(30, "Analyzing data...")
            )
            QTimer.singleShot(
                2000, lambda: self.update_progress(70, "Generating summary...")
            )
            QTimer.singleShot(
                3000, lambda: self.update_progress(100, "Summary complete")
            )
            QTimer.singleShot(3500, self.hide_progress_message)

            self.current_summary = {
                "content": "This is a demo executive summary based on the fetched Jira data.",
                "model": self.ai_model_combo.currentText(),
                "generated_at": datetime.now().isoformat(),
            }

            self.summary_text.setPlainText(self.current_summary["content"])

            self.preview_btn.setEnabled(True)
            self.create_doc_btn.setEnabled(True)
            self.status_label.setText("Summary generated successfully")

        except Exception as e:
            self.hide_progress_message()
            self.logger.error(f"Failed to generate summary: {e}")
            self.show_error("Summary Generation Error", str(e))

    def preview_document(self):
        """Preview the document."""
        if self.current_summary:
            title = self.document_title_edit.text() or "Executive Summary"
            content = f"# {title}\n\n{self.current_summary['content']}"
            self.preview_text.setPlainText(content)
            self.tab_widget.setCurrentIndex(2)  # Switch to output tab

    def export_document(self):
        """Export document to file."""
        try:
            if not self.current_summary:
                self.show_error("No Summary", "Please generate a summary first")
                return

            # Show progress
            self.show_progress_message("Exporting Document...", "Saving to file")

            # TODO: Implement actual file export
            # Simulate progress
            QTimer.singleShot(
                1000, lambda: self.update_progress(50, "Exporting document...")
            )
            QTimer.singleShot(
                2000, lambda: self.update_progress(100, "Document exported")
            )
            QTimer.singleShot(2500, self.hide_progress_message)

            self.status_label.setText("Document exported successfully")

        except Exception as e:
            self.hide_progress_message()
            self.logger.error(f"Failed to export document: {e}")
            self.show_error("Export Error", str(e))

    def new_summary(self):
        """Start a new summary."""
        self.current_activity_data = []
        self.current_summary = None
        if hasattr(self, "summary_text"):
            self.summary_text.clear()
        if hasattr(self, "preview_text"):
            self.preview_text.clear()
        if hasattr(self, "document_url_label"):
            self.document_url_label.clear()

        if hasattr(self, "generate_summary_btn"):
            self.generate_summary_btn.setEnabled(False)
        if hasattr(self, "preview_btn"):
            self.preview_btn.setEnabled(False)
        if hasattr(self, "export_btn"):
            self.export_btn.setEnabled(False)

        self.status_label.setText("Ready for new summary")
        self.switch_view(ViewState.MAIN)

    def save_configuration(self):
        """Save current configuration."""
        # Open the unified settings dialog - it handles saving internally
        self.show_unified_settings()

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
            <li>Multiple export formats</li>
            <li>Secure credential management</li>
        </ul>
        <p>Built with PySide6 and Python.</p>
        """

        QMessageBox.about(self, "About", about_text)

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

            # Clean up validation threads
            for worker in self.validation_threads:
                if worker.isRunning():
                    worker.quit()
                    worker.wait()

            # Accept the close event
            event.accept()

        except Exception as e:
            self.logger.error(f"Error during application close: {e}")
            event.accept()
