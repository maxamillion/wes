"""
Example of integrating the Unified Configuration Dialog into MainWindow.

This shows the key changes needed to replace the existing configuration
system with the new unified dialog.
"""

# Add this import at the top of main_window_single.py
from .unified_config import UnifiedConfigDialog, ConfigState

class MainWindow(QMainWindow):
    """Main window with unified configuration integration."""
    
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.logger = get_logger(__name__)
        
        # ... existing initialization ...
        
    def create_menu_bar(self):
        """Create menu bar with updated settings action."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        # ... existing file menu items ...
        
        # Edit menu  
        edit_menu = menubar.addMenu("Edit")
        
        # Updated Settings action
        settings_action = QAction("Settings...", self)
        settings_action.setShortcut("Ctrl+,")  # Standard settings shortcut
        settings_action.triggered.connect(self.show_unified_settings)
        edit_menu.addAction(settings_action)
        
        # View menu (remove Configuration option as it's now in Settings)
        view_menu = menubar.addMenu("View")
        
        home_action = QAction("Home", self)
        home_action.triggered.connect(lambda: self.switch_view(ViewState.MAIN))
        view_menu.addAction(home_action)
        
        # Remove setup and config views - now handled by unified dialog
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        # ... existing help menu items ...
    
    def show_unified_settings(self):
        """Show the unified configuration dialog."""
        dialog = UnifiedConfigDialog(self.config_manager, self)
        
        # Connect to handle configuration updates
        dialog.configuration_complete.connect(self.on_configuration_updated)
        
        # Show dialog
        result = dialog.exec()
        
        if result == QDialog.Accepted:
            # Configuration was saved
            self.update_ui_state()
            self.statusBar().showMessage("Configuration updated", 3000)
    
    def on_configuration_updated(self, config: Dict[str, Any]):
        """Handle configuration updates from the unified dialog."""
        # Update any UI elements that depend on configuration
        self.update_connection_status()
        
        # If we're on the welcome screen and config is now complete,
        # automatically switch to main view
        if self.current_view == ViewState.WELCOME:
            config_state = self.check_configuration_state()
            if config_state == ConfigState.COMPLETE:
                self.switch_view(ViewState.MAIN)
    
    def check_configuration_state(self) -> ConfigState:
        """Check the current configuration state."""
        from wes.gui.unified_config.utils.config_detector import ConfigDetector
        
        detector = ConfigDetector()
        return detector.detect_state(self.config_manager.config)
    
    def switch_view(self, view_state: ViewState):
        """Switch between different views."""
        # Remove CONFIG and SETUP states - now handled by unified dialog
        if view_state in [ViewState.CONFIG, ViewState.SETUP]:
            # Redirect to unified settings
            self.show_unified_settings()
            return
            
        self.current_view = view_state
        
        if view_state == ViewState.WELCOME:
            self.main_stack.setCurrentWidget(self.welcome_widget)
        elif view_state == ViewState.MAIN:
            self.main_stack.setCurrentWidget(self.main_widget)
        elif view_state == ViewState.PROGRESS:
            self.main_stack.setCurrentWidget(self.progress_widget)
    
    def check_initial_setup(self):
        """Check if initial setup is needed."""
        config_state = self.check_configuration_state()
        
        if config_state == ConfigState.EMPTY:
            # First time user - show unified config in wizard mode
            QTimer.singleShot(500, self.show_initial_setup)
        elif config_state == ConfigState.INCOMPLETE:
            # Incomplete setup - show unified config in guided mode
            QTimer.singleShot(500, self.show_incomplete_setup_warning)
        else:
            # Configuration complete - go to main view
            self.switch_view(ViewState.MAIN)
    
    def show_initial_setup(self):
        """Show initial setup dialog."""
        QMessageBox.information(
            self,
            "Welcome to WES",
            "Welcome! Let's set up WES to create executive summaries.\n\n"
            "Click OK to begin the setup wizard."
        )
        self.show_unified_settings()
    
    def show_incomplete_setup_warning(self):
        """Show warning about incomplete setup."""
        reply = QMessageBox.question(
            self,
            "Incomplete Configuration",
            "Your configuration is incomplete. Some features may not work.\n\n"
            "Would you like to complete the setup now?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        if reply == QMessageBox.Yes:
            self.show_unified_settings()
    
    def create_welcome_view(self):
        """Create simplified welcome view."""
        self.welcome_widget = QWidget()
        layout = QVBoxLayout(self.welcome_widget)
        layout.setAlignment(Qt.AlignCenter)
        
        # Logo
        logo_label = QLabel()
        logo_label.setPixmap(QPixmap(":/icons/wes_logo.png").scaled(200, 200, Qt.KeepAspectRatio))
        logo_label.setAlignment(Qt.AlignCenter)
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
        
        # Setup button
        setup_button = QPushButton("Get Started")
        setup_button.setFixedSize(200, 50)
        setup_button.setStyleSheet("""
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
        """)
        setup_button.clicked.connect(self.show_unified_settings)
        layout.addWidget(setup_button, alignment=Qt.AlignCenter)
    
    def update_connection_status(self):
        """Update connection status indicators."""
        # This would update any status indicators in the main view
        # based on the current configuration state
        if hasattr(self, 'connection_status_widget'):
            from wes.gui.unified_config.utils.config_detector import ConfigDetector
            
            detector = ConfigDetector()
            service_status = detector.get_service_status(self.config_manager.config)
            
            # Update UI based on service status
            for service, status in service_status.items():
                if status['is_valid']:
                    # Show connected status
                    pass
                else:
                    # Show disconnected status
                    pass


# Key changes summary:
# 1. Replace existing setup wizard with UnifiedConfigDialog
# 2. Remove separate CONFIG and SETUP views
# 3. Add Settings menu item that opens unified dialog
# 4. Simplify initial setup flow
# 5. Auto-detect configuration state on startup
# 6. Remove redundant configuration UI from main window