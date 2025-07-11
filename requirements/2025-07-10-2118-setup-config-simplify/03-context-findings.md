# Context Findings

Based on the discovery answers and detailed codebase analysis, here are the key findings for combining and simplifying the setup and configuration sections.

## Current Implementation Overview

### Two Separate Components
1. **SetupWizard** (`src/wes/gui/setup_wizard.py`):
   - Modal dialog with 6 pages
   - Guided step-by-step flow
   - Basic settings only
   - First-time user focused

2. **ConfigDialog** (`src/wes/gui/config_dialog.py`):
   - Tabbed interface with 5 tabs
   - All settings (basic + advanced)
   - Power user focused
   - Non-linear navigation

### Key Implementation Files

#### Primary Files to Modify
- `src/wes/gui/setup_wizard.py:1-1250` - Current wizard implementation
- `src/wes/gui/config_dialog.py:1-750` - Current config dialog
- `src/wes/gui/main_window.py:482-490,732` - Menu actions and dialog invocation
- `src/wes/gui/main_window_single.py` - Single-window version integration

#### Supporting Files
- `src/wes/gui/credential_validators.py` - Shared validation logic
- `src/wes/gui/oauth_handler.py:577-798` - OAuth flow components
- `src/wes/core/config_manager.py:18-78` - Configuration schema
- `src/wes/utils/validators.py` - Input validation utilities

## Identified Redundancies

### 1. Duplicate UI Elements
- **Jira Configuration**:
  - SetupWizard: Lines 195-416 (JiraSetupPage)
  - ConfigDialog: Lines 98-165 (Jira tab)
  - Both have URL, username, API token fields

- **Google Configuration**:
  - SetupWizard: Lines 577-798 (GoogleSetupPage)
  - ConfigDialog: Lines 166-220 (Google tab)
  - OAuth flow duplicated

- **Validation Logic**:
  - SetupWizard: Inline validation in each page
  - ConfigDialog: Centralized validation (lines 622-701)
  - Different implementations of same checks

### 2. Missing Features in SetupWizard
- Rate limiting settings
- Timeout configurations
- Custom JQL queries
- Service account option for Google
- AI temperature/token settings
- Theme and language preferences
- Security settings (encryption, audit)

## UI Patterns for Unified Interface

### 1. Progressive Disclosure Pattern
```
Basic Settings (Always Visible)
├── Essential fields (URL, credentials)
├── Test Connection button
└── [▼ Advanced Settings] (Expandable)
    ├── Performance (rate limits, timeouts)
    ├── Defaults (JQL, folder paths)
    └── Service-specific options
```

### 2. Hybrid Navigation Model
- **First-time users**: Wizard-style with Next/Back
- **Returning users**: Direct tab/section access
- **Smart defaults**: Pre-populate from existing config

### 3. Validation Strategy
- Real-time field validation
- Background connection testing
- Inline error messages
- Progressive save (section by section)

## Technical Approach

### 1. New Unified Component Structure
```python
UnifiedConfigDialog(QDialog):
    ├── ConfigMode (enum): WIZARD | DIRECT
    ├── NavigationWidget: Steps or Tabs
    ├── ContentStack: QStackedWidget
    │   ├── WelcomePage (wizard mode only)
    │   ├── JiraConfigPage (basic + advanced)
    │   ├── GoogleConfigPage (basic + advanced)
    │   ├── GeminiConfigPage (basic + advanced)
    │   ├── AppSettingsPage (optional in wizard)
    │   └── SummaryPage (wizard mode only)
    └── ButtonBar: Dynamic based on mode
```

### 2. State Management
- Track which settings are "required" vs "optional"
- Remember expansion state of advanced sections
- Save partial progress during wizard flow
- Validate only visible/required fields

### 3. Migration Path
1. Create new `unified_config_dialog.py`
2. Extract common components to shared modules
3. Implement mode switching (wizard vs direct)
4. Update menu actions to use unified dialog
5. Deprecate separate components

## Implementation Constraints

### 1. Backward Compatibility
- Maintain existing ConfigManager interface
- Preserve all current settings
- Support existing config file format

### 2. User Experience
- No modal blocking for returning users
- Maintain quick access to frequently changed settings
- Clear visual distinction between basic/advanced

### 3. Performance
- Lazy loading of advanced sections
- Async validation to prevent UI freezing
- Efficient state updates

## Recommended Implementation Order

1. **Phase 1**: Create unified dialog structure
   - Base dialog with mode switching
   - Navigation framework (wizard/tabs)
   - Content container setup

2. **Phase 2**: Migrate settings pages
   - Start with Jira (most complex)
   - Add progressive disclosure
   - Integrate validation

3. **Phase 3**: Polish and integration
   - Update menu system
   - Remove old components
   - Update documentation

## Testing Considerations

1. **User Flows**:
   - First-time setup completion
   - Returning user configuration changes
   - Mode switching behavior

2. **Validation**:
   - All existing validations work
   - Advanced settings properly hidden/shown
   - Connection tests function correctly

3. **State Persistence**:
   - Partial wizard progress saved
   - Advanced section states remembered
   - Configuration correctly applied