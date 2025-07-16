# Design: Set "Include Comments" to Default to True

## Overview
Currently, the "Include comments" checkbox in the application settings defaults to `False`. This design outlines the changes needed to make it default to `True`.

## Current State
- In `app_settings_page.py` line 77: `self.include_comments = self._create_checkbox("Include comments", False)`
- The orchestrator always passes `include_comments=True` when fetching Jira data (hardcoded)
- The app settings value is not currently being used by the orchestrator

## Design Approach

### Option 1: Simple UI Default Change (Recommended)
**Changes Required:**
1. Update `app_settings_page.py` line 77 to set default to `True`
2. Update line 222 to also default to `True` when loading config

**Pros:**
- Minimal change (2 lines)
- User preference is preserved in saved configurations
- Aligns with current orchestrator behavior

**Cons:**
- Only affects new installations

### Option 2: Configuration Migration
**Changes Required:**
1. Same as Option 1, plus:
2. Add a configuration migration to update existing configs
3. Version the configuration schema

**Pros:**
- Updates existing installations
- Provides a pattern for future config changes

**Cons:**
- More complex implementation
- Requires config versioning system

### Option 3: Make Orchestrator Respect App Settings
**Changes Required:**
1. Update orchestrator to read include_comments from app settings
2. Remove hardcoded `include_comments=True` 
3. Update UI default to `True`

**Pros:**
- Makes the setting actually functional
- Users can disable comment fetching if desired

**Cons:**
- Requires more extensive changes
- May break existing behavior expectations

## Recommended Implementation

Go with **Option 1** for immediate fix, as it:
- Provides the requested default behavior
- Is the simplest change
- Maintains backward compatibility

## Implementation Details

### File: `src/wes/gui/unified_config/config_pages/app_settings_page.py`

**Line 77:**
```python
# Change from:
self.include_comments = self._create_checkbox("Include comments", False)
# To:
self.include_comments = self._create_checkbox("Include comments", True)
```

**Line 222:**
```python
# Change from:
self.include_comments.setChecked(app_config.get("include_comments", False))
# To:
self.include_comments.setChecked(app_config.get("include_comments", True))
```

## Testing
1. Delete or rename existing config file
2. Start application
3. Navigate to Settings → Application Settings
4. Verify "Include comments" is checked by default
5. Save settings and restart
6. Verify setting persists

## Future Considerations
- Consider implementing Option 3 to make the setting functional
- Add configuration versioning for future migrations
- Document the relationship between app settings and orchestrator behavior