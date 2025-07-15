#!/usr/bin/env python
"""Test script for the responsive settings dialog."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from PySide6.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget, QLabel
from PySide6.QtCore import QTimer

from wes.core.config_manager import ConfigManager
from wes.gui.unified_config.unified_config_dialog import UnifiedConfigDialog


def test_responsive_dialog():
    """Test the responsive settings dialog."""
    app = QApplication(sys.argv)
    
    # Create config manager
    config_manager = ConfigManager()
    
    # Create test window with buttons to launch dialog
    test_window = QWidget()
    test_window.setWindowTitle("Responsive Dialog Test")
    test_window.resize(400, 300)
    
    layout = QVBoxLayout(test_window)
    
    # Add instructions
    instructions = QLabel(
        "Test the responsive settings dialog:\n"
        "1. Click 'Open Settings' to launch the dialog\n"
        "2. Resize the dialog to test scrolling\n"
        "3. Try on different screen sizes\n"
        "4. Check that all tabs have scroll bars when needed"
    )
    instructions.setWordWrap(True)
    layout.addWidget(instructions)
    
    # Button to open settings
    def open_settings():
        dialog = UnifiedConfigDialog(config_manager, test_window)
        
        # Test with different sizes
        def test_sizes():
            sizes = [
                (600, 400),   # Minimum size
                (800, 600),   # Small screen
                (1024, 768),  # Medium screen
                (1200, 800),  # Large screen
            ]
            
            current_size = [0]
            
            def next_size():
                if current_size[0] < len(sizes):
                    width, height = sizes[current_size[0]]
                    dialog.resize(width, height)
                    dialog.setWindowTitle(f"WES Configuration - {width}x{height}")
                    current_size[0] += 1
            
            # Change size every 3 seconds for demo
            # timer = QTimer()
            # timer.timeout.connect(next_size)
            # timer.start(3000)
            # next_size()
        
        # test_sizes()
        dialog.exec()
    
    open_button = QPushButton("Open Settings Dialog")
    open_button.clicked.connect(open_settings)
    layout.addWidget(open_button)
    
    # Button to simulate small screen
    def small_screen():
        dialog = UnifiedConfigDialog(config_manager, test_window)
        dialog.resize(600, 400)  # Force small size
        dialog.setWindowTitle("WES Configuration - Small Screen Mode")
        dialog.exec()
    
    small_button = QPushButton("Open Settings (Small Screen)")
    small_button.clicked.connect(small_screen)
    layout.addWidget(small_button)
    
    # Button to simulate large screen
    def large_screen():
        dialog = UnifiedConfigDialog(config_manager, test_window)
        dialog.resize(1200, 800)  # Force large size
        dialog.setWindowTitle("WES Configuration - Large Screen Mode")
        dialog.exec()
    
    large_button = QPushButton("Open Settings (Large Screen)")
    large_button.clicked.connect(large_screen)
    layout.addWidget(large_button)
    
    layout.addStretch()
    
    test_window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    test_responsive_dialog()