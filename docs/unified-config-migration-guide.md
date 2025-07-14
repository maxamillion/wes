# Unified Configuration Migration Guide

This guide explains how to migrate from the current triple-configuration system to the new unified configuration dialog.

## Overview of Changes

### Before (Current System)
- **SetupWizard**: First-time setup wizard (6 pages)
- **ConfigDialog**: Traditional tabbed dialog
- **MainWindow Config View**: Embedded configuration in main window
- **Redundant Code**: Validation logic duplicated across components

### After (Unified System)
- **Single Entry Point**: UnifiedConfigDialog handles all configuration
- **Adaptive UI**: Automatically switches between wizard, guided, and direct modes
- **Consistent Testing**: Connection testing available everywhere
- **Code Reuse**: Shared components and validation logic

## Migration Steps

### 1. Update Imports

Replace existing imports:

```python
# Old imports
from .setup_wizard import SetupWizard
from .config_dialog import ConfigDialog

# New import
from .unified_config import UnifiedConfigDialog, ConfigState
```

### 2. Update MainWindow

#### Remove Old Views

Remove the CONFIG and SETUP view states:

```python
# Old
class ViewState(Enum):
    WELCOME = "welcome"
    SETUP = "setup"      # Remove this
    MAIN = "main"
    CONFIG = "config"    # Remove this
    PROGRESS = "progress"

# New
class ViewState(Enum):
    WELCOME = "welcome"
    MAIN = "main"
    PROGRESS = "progress"
```

#### Update Menu Bar

Replace configuration menu items:

```python
# Old - Multiple entry points
setup_action = QAction("Setup", self)
setup_action.triggered.connect(lambda: self.switch_view(ViewState.SETUP))

config_action = QAction("Configuration", self)
config_action.triggered.connect(lambda: self.switch_view(ViewState.CONFIG))

# New - Single settings action
settings_action = QAction("Settings...", self)
settings_action.setShortcut("Ctrl+,")
settings_action.triggered.connect(self.show_settings)
edit_menu.addAction(settings_action)
```

#### Add Settings Handler

```python
def show_settings(self):
    """Show the unified settings dialog."""
    dialog = UnifiedConfigDialog(self.config_manager, self)
    
    # Connect to handle configuration updates
    dialog.configuration_complete.connect(self.on_configuration_updated)
    
    # Show dialog
    result = dialog.exec()
    
    if result == QDialog.Accepted:
        self.update_ui_state()
        self.statusBar().showMessage("Configuration updated", 3000)
```

### 3. Update Initial Setup Flow

Replace complex setup logic with automatic detection:

```python
def check_initial_setup(self):
    """Check if initial setup is needed."""
    from wes.gui.unified_config.utils.config_detector import ConfigDetector
    
    detector = ConfigDetector()
    config_state = detector.detect_state(self.config_manager.config)
    
    if config_state == ConfigState.EMPTY:
        # First time user - show wizard
        QTimer.singleShot(500, self.show_initial_setup)
    elif config_state == ConfigState.INCOMPLETE:
        # Incomplete setup - show guided mode
        QTimer.singleShot(500, self.show_incomplete_setup_warning)
    else:
        # Configuration complete
        self.switch_view(ViewState.MAIN)
```

### 4. Remove Old Configuration Views

Delete or comment out:
- `create_setup_view()` method
- `create_config_view()` method  
- All setup page creation methods
- Embedded configuration tabs in main window

### 5. Update Connection Testing

Replace scattered test buttons with unified approach:

```python
# Old - Multiple test implementations
self.jira_test_btn.clicked.connect(lambda: self.test_jira_connection())
self.google_test_btn.clicked.connect(lambda: self.test_google_connection())

# New - Handled internally by unified config pages
# Each page has consistent "Test Connection" functionality
```

### 6. Simplify Configuration Access

```python
# Old - Check multiple places
if self.config_manager.has_jira_config():
    # ...
elif self.setup_needed:
    # ...

# New - Single source of truth
config_state = self.config_detector.detect_state(self.config_manager.config)
if config_state == ConfigState.COMPLETE:
    # Ready to go
```

## Testing the Migration

### 1. Test First-Time User Experience
```bash
# Clear existing config
rm -rf ~/.wes/config

# Run application - should show wizard mode
python -m wes
```

### 2. Test Incomplete Configuration
```bash
# Manually create partial config
# Run application - should show guided mode
```

### 3. Test Returning User
```bash
# With complete config
# Run application - should go directly to main view
# Settings menu should open in direct mode
```

### 4. Test Connection Testing
- Verify "Test Connection" works in all modes
- Check that status indicators update correctly
- Ensure error messages are helpful

## Rollback Plan

If issues arise:

1. Keep old components but mark as deprecated
2. Add feature flag to toggle between old and new
3. Gradual migration over multiple releases

```python
# Feature flag approach
USE_UNIFIED_CONFIG = True  # Set to False to use old system

def show_settings(self):
    if USE_UNIFIED_CONFIG:
        dialog = UnifiedConfigDialog(self.config_manager, self)
    else:
        dialog = ConfigDialog(self.config_manager, self)  # Old dialog
```

## Benefits After Migration

1. **Code Reduction**: ~40% less configuration-related code
2. **Consistency**: Single configuration experience
3. **Maintainability**: Shared components and validation
4. **User Experience**: Clearer, more intuitive setup
5. **Testing**: Easier to test single component

## Common Issues and Solutions

### Issue: Custom validation logic
**Solution**: Move to shared validators in `unified_config/validators/`

### Issue: Service-specific features
**Solution**: Extend base ConfigPageBase class

### Issue: UI customization needs
**Solution**: Use style sheets and custom widgets in `unified_config/components/`

### Issue: Backward compatibility
**Solution**: Config format unchanged, only UI is different

## Next Steps

1. Review and test the unified configuration dialog
2. Update any service-specific logic
3. Remove deprecated components
4. Update documentation and help files
5. Train support team on new flow