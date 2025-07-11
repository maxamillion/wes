# Requirements Specification: Combine and Simplify Setup/Configuration UI

Generated: 2025-07-10 21:20
Status: Complete

## Overview

The WES application currently has two separate interfaces for configuration: a SetupWizard for initial setup and a ConfigDialog for advanced settings. This creates confusion for users and maintenance overhead. This project will combine these into a unified configuration interface that adapts to the user's context while maintaining both guided setup for new users and quick access to all settings for experienced users.

## Detailed Requirements

### Functional Requirements

1. **Unified Configuration Interface**
   - Single entry point for all configuration needs
   - Adaptive UI that detects first-time vs returning users
   - Maintains wizard-style flow for initial setup
   - Provides direct access to all settings for configuration changes

2. **Progressive Disclosure**
   - Basic settings visible by default
   - Advanced settings hidden in expandable sections
   - User preference persistence for expanded sections
   - Clear visual hierarchy between essential and optional settings

3. **Service Organization**
   - Maintain separate sections for Jira, Google, and Gemini
   - Each service section contains both basic and advanced settings
   - Consistent layout pattern across all service sections

4. **Navigation Models**
   - Wizard mode: Step-by-step with Back/Next buttons for first-time setup
   - Direct mode: Tab-based navigation for returning users
   - Modal behavior retained for first-time setup only

5. **Validation and Testing**
   - Preserve "Test Connection" functionality for each service
   - Real-time validation with inline error messages
   - Background validation using existing threading patterns
   - Skip validation for optional/hidden sections

6. **User Experience**
   - Allow skipping optional sections during initial setup
   - No application restart required for configuration changes
   - Clear indication of required vs optional fields
   - Progress indication during wizard flow

### Technical Requirements

#### Affected Files
1. **New Components**
   - `src/wes/gui/unified_config_dialog.py` - New unified dialog implementation

2. **Files to Modify**
   - `src/wes/gui/main_window.py:146-150,482-490,732` - Update menu actions
   - `src/wes/gui/main_window_single.py` - Update configuration view integration

3. **Files to Deprecate** (after migration)
   - `src/wes/gui/setup_wizard.py` - Current wizard implementation
   - `src/wes/gui/config_dialog.py` - Current config dialog

4. **Shared Components to Extract**
   - Service validation logic from both components
   - OAuth flow handling
   - Credential storage patterns

#### New Components Architecture
```python
class UnifiedConfigDialog(QDialog):
    """Unified configuration dialog with adaptive modes"""
    
    class ConfigMode(Enum):
        WIZARD = "wizard"  # First-time setup
        DIRECT = "direct"  # Configuration changes
    
    def __init__(self, parent=None, mode=None):
        # Auto-detect mode if not specified
        # Create appropriate navigation widget
        # Setup content pages with progressive disclosure
```

#### Database/Storage Changes
- No database schema changes required
- Add UI state persistence for:
  - Expanded section states
  - Last active tab/page
  - Wizard progress (for resume capability)

### Implementation Notes

1. **Phased Migration**
   - Phase 1: Create unified dialog alongside existing components
   - Phase 2: Update menu system to use unified dialog
   - Phase 3: Deprecate and remove old components

2. **Component Reuse**
   - Extract common validation logic to shared module
   - Create reusable ExpandableSection widget
   - Centralize threading patterns for background operations

3. **State Management**
   - Use ConfigManager for all persistent settings
   - Add UI state manager for dialog preferences
   - Implement partial save during wizard flow

4. **Visual Design**
   - Follow existing green/white color scheme
   - Use consistent spacing and grouping
   - Clear visual distinction for advanced sections
   - Maintain existing icon patterns

### Acceptance Criteria

1. **First-Time User Flow**
   - [ ] Application detects no configuration and launches unified dialog in wizard mode
   - [ ] User can complete basic setup with only required fields
   - [ ] User can skip optional sections and complete setup
   - [ ] Modal behavior prevents app usage until setup complete
   - [ ] All services can be tested before finishing setup

2. **Returning User Flow**
   - [ ] "Settings" menu item opens unified dialog in direct mode
   - [ ] All settings accessible via tabbed interface
   - [ ] Advanced sections remember expansion state
   - [ ] Changes can be applied without restart
   - [ ] No modal blocking for configuration changes

3. **Feature Parity**
   - [ ] All SetupWizard functionality available
   - [ ] All ConfigDialog settings accessible
   - [ ] Validation logic works identically
   - [ ] Connection testing preserved
   - [ ] OAuth flow functions correctly

4. **Code Quality**
   - [ ] No duplicate validation code
   - [ ] Shared components properly extracted
   - [ ] Comprehensive test coverage
   - [ ] Documentation updated
   - [ ] Old components cleanly removed

5. **User Experience**
   - [ ] Clear indication of required fields
   - [ ] Intuitive navigation between modes
   - [ ] Responsive UI during validation
   - [ ] Helpful error messages
   - [ ] Consistent visual design

## Risk Mitigation

1. **Backward Compatibility**: Maintain existing ConfigManager interface
2. **User Confusion**: Provide clear mode indicators and help text
3. **Testing Complexity**: Implement comprehensive automated tests
4. **Performance**: Use lazy loading for advanced sections