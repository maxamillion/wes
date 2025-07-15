# Unified Configuration Dialog Utilities

This directory contains reusable utilities designed to improve code maintainability, reduce duplication, and enhance testability throughout the unified configuration dialog system.

## Overview

The utilities module provides several key components:

1. **Dialog Management** - Consistent dialog patterns and user interactions
2. **Style Management** - Centralized styling and theming
3. **Configuration Constants** - Elimination of magic values
4. **Responsive Layout** - Adaptive UI for different screen sizes
5. **Dependency Injection** - Improved testability and modularity

## Components

### DialogManager (`dialogs.py`)

Provides consistent dialog patterns across the application:

```python
from wes.gui.unified_config.utils import DialogManager

# Show various message types
DialogManager.show_info(parent, "Title", "Information message")
DialogManager.show_warning(parent, "Title", "Warning message")
DialogManager.show_error(parent, "Title", "Error message")
DialogManager.show_success(parent, "Title", "Success message")

# Ask questions
if DialogManager.ask_question(parent, "Title", "Continue?"):
    # User clicked Yes
    pass

# Confirmation with custom buttons
if DialogManager.ask_confirmation(parent, "Title", "Delete file?", 
                                confirm_text="Delete", 
                                cancel_text="Keep",
                                dangerous=True):
    # User confirmed
    pass
```

### FileDialogManager (`dialogs.py`)

Simplified file dialog operations:

```python
from wes.gui.unified_config.utils import FileDialogManager

# Get file path
file_path = FileDialogManager.get_open_file_path(
    parent, 
    "Select Config File",
    filter="JSON Files (*.json);;All Files (*)"
)

# Get JSON file specifically
json_path = FileDialogManager.get_json_file_path(parent, "Select JSON")

# Get directory
dir_path = FileDialogManager.get_directory_path(parent, "Select Output Directory")
```

### StyleManager (`styles.py`)

Centralized style definitions:

```python
from wes.gui.unified_config.utils import StyleManager

# Apply button styles
button.setStyleSheet(StyleManager.get_button_style("primary"))  # Blue button
button.setStyleSheet(StyleManager.get_button_style("danger"))   # Red button

# Apply label styles
label.setStyleSheet(StyleManager.get_label_style("success"))    # Green text
label.setStyleSheet(StyleManager.get_label_style("warning"))    # Orange text
label.setStyleSheet(StyleManager.get_label_style("muted"))      # Gray text

# Apply group box styles
group.setStyleSheet(StyleManager.get_group_box_style(collapsible=True))

# Apply compact mode for small screens
widget.setStyleSheet(StyleManager.get_compact_mode_style())
```

### ConfigConstants (`constants.py`)

Centralized configuration values:

```python
from wes.gui.unified_config.utils import ConfigConstants

# Use constants instead of magic values
spinbox.setRange(
    ConfigConstants.RETRY_ATTEMPTS_MIN,
    ConfigConstants.RETRY_ATTEMPTS_MAX
)
spinbox.setValue(ConfigConstants.RETRY_ATTEMPTS_DEFAULT)

# File paths
cred_file = Path.home() / ConfigConstants.WES_CONFIG_DIR / ConfigConstants.OAUTH_CREDENTIALS_FILE

# Permissions
os.chmod(file_path, ConfigConstants.CREDENTIALS_FILE_PERMISSIONS)
```

### ResponsiveConfigLayout (`responsive_layout.py`)

Adaptive layouts for different screen sizes:

```python
from wes.gui.unified_config.utils import ResponsiveConfigLayout

class MyConfigPage(ConfigPageBase):
    def __init__(self):
        super().__init__()
        self.responsive_layout = ResponsiveConfigLayout(self)
        
        # Create collapsible sections
        advanced_group = self.responsive_layout.create_collapsible_section(
            "Advanced Settings",
            content_widget,
            start_collapsed=True
        )
        
        # Create two-column layouts
        layout = self.responsive_layout.create_two_column_layout(widgets)
        
        # Make the page responsive
        self.responsive_layout.make_responsive()
```

### Dependency Injection

#### Factory Pattern (`factory.py`)

```python
from wes.gui.unified_config.utils import get_config_page_factory

# Get the factory
factory = get_config_page_factory()

# Create a page
page = factory.create_page(ServiceType.GOOGLE, config_manager)

# For testing - use a mock factory
from wes.gui.unified_config.utils import TestConfigPageFactory, set_config_page_factory

mock_factory = TestConfigPageFactory(mock_pages={
    ServiceType.GOOGLE: MockGooglePage()
})
set_config_page_factory(mock_factory)
```

#### Service Locator (`service_locator.py`)

```python
from wes.gui.unified_config.utils import register_service, get_service, inject

# Register a service
register_service(ConfigManager, config_manager_instance)

# Get a service
config_manager = get_service(ConfigManager)

# Use decorator for automatic injection
class MyClass:
    @inject(ConfigManager)
    def process_config(self, config_manager: ConfigManager):
        # config_manager is automatically injected
        pass

# Scoped services for testing
from wes.gui.unified_config.utils import ServiceScope

with ServiceScope() as scope:
    scope.register(ConfigManager, mock_config_manager)
    # Services are temporarily replaced within this scope
    run_tests()
# Original services restored here
```

## Design Patterns

### 1. Centralized Style Management

All styling is centralized in `StyleManager` to ensure consistency and make theme changes easier:

- Color palette defined in one place
- Consistent button styles across the app
- Easy to implement dark mode in the future

### 2. Elimination of Magic Values

All configuration values are defined as constants:

- Timeouts, retry attempts, limits
- File paths and permissions
- UI dimensions and thresholds
- Validation patterns

### 3. Consistent Error Handling

All dialogs follow the same patterns:

- Success/error states clearly communicated
- Consistent button text and behavior
- Proper validation feedback

### 4. Dependency Injection

Two patterns for improved testability:

1. **Factory Pattern**: For creating configuration pages with dependencies
2. **Service Locator**: For managing global services and dependencies

### 5. Responsive Design

The `ResponsiveConfigLayout` automatically adjusts:

- Spacing and padding for small screens
- Hides non-essential elements in compact mode
- Provides collapsible sections for better space usage

## Best Practices

1. **Always use DialogManager** instead of direct QMessageBox calls
2. **Apply styles through StyleManager** instead of hardcoding
3. **Reference ConfigConstants** instead of magic values
4. **Use FileDialogManager** for consistent file operations
5. **Inject dependencies** rather than creating them directly
6. **Make pages responsive** using ResponsiveConfigLayout

## Testing

The utilities are designed with testing in mind:

```python
# Example test with dependency injection
def test_config_page():
    # Create mock services
    mock_config_manager = Mock(spec=ConfigManager)
    
    # Use service scope for temporary registration
    with ServiceScope() as scope:
        scope.register(ConfigManager, mock_config_manager)
        
        # Create page with injected mock
        factory = get_config_page_factory()
        page = factory.create_page(ServiceType.GOOGLE, mock_config_manager)
        
        # Test the page
        assert page.validate()["is_valid"]
```

## Future Enhancements

1. **Theme Support**: Extend StyleManager for dark/light themes
2. **Animation Utilities**: Add consistent animation patterns
3. **Validation Framework**: More sophisticated validation helpers
4. **State Management**: Centralized state management utilities
5. **Plugin System**: Allow external configuration page plugins