#!/usr/bin/env python
"""Test script for the integrated OAuth setup in Google config page."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from PySide6.QtWidgets import QApplication

from wes.core.config_manager import ConfigManager
from wes.gui.unified_config.unified_config_dialog import UnifiedConfigDialog
from wes.gui.unified_config.types import ServiceType


def test_oauth_setup():
    """Test the integrated OAuth setup flow."""
    app = QApplication(sys.argv)
    
    # Create config manager
    config_manager = ConfigManager()
    
    # Create and show config dialog
    dialog = UnifiedConfigDialog(config_manager)
    
    # Switch to direct mode to see all settings
    from wes.gui.unified_config.types import UIMode
    dialog.set_mode(UIMode.DIRECT)
    
    # Show Google service tab
    if hasattr(dialog, 'direct_widget') and dialog.direct_widget:
        dialog.direct_widget.show_service(ServiceType.GOOGLE)
    
    # Show dialog
    dialog.exec()
    
    sys.exit(0)


if __name__ == "__main__":
    test_oauth_setup()