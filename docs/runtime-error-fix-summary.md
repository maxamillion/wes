# Runtime Error Fix: ConfigManager Missing 'config' Attribute

## Problem
The application was failing to start with the error:
```
Failed to start application: 'ConfigManager' object has no attribute 'config'
```

## Root Cause Analysis

### 1. Missing Property
The `ConfigManager` class didn't expose a `config` property. The unified configuration integration was attempting to access `self.config_manager.config`, but only `get_config()` method existed.

### 2. Type Mismatch  
The `ConfigDetector.detect_state()` method expects a `Dict[str, Any]` parameter, but `ConfigManager.get_config()` returns a `Configuration` dataclass object.

### 3. Field Name Mismatch
- The `Configuration` dataclass has an "ai" section, but `ConfigDetector` expects "gemini"
- The `AIConfig` has `gemini_api_key` field, but `ConfigDetector` expects `api_key`

## Solution Implemented

### Added `config` Property to ConfigManager
```python
@property
def config(self) -> Dict[str, Any]:
    """Get current configuration as dictionary for compatibility."""
    from dataclasses import asdict
    config_dict = asdict(self._config)
    
    # Map 'ai' section to 'gemini' for unified config compatibility
    if "ai" in config_dict:
        gemini_config = config_dict["ai"].copy()
        # Map field names for compatibility
        if "gemini_api_key" in gemini_config:
            gemini_config["api_key"] = gemini_config["gemini_api_key"]
        config_dict["gemini"] = gemini_config
        
    return config_dict
```

### Field Mapping
- Maps the "ai" section to "gemini" section for unified config compatibility
- Maps `gemini_api_key` field to `api_key` field for ConfigDetector compatibility

## Files Modified
- `/src/wes/core/config_manager.py` - Added the `config` property with field mapping

## Verification
✅ `config_manager.config` property works correctly  
✅ Returns dictionary with expected structure  
✅ ConfigDetector can process the configuration  
✅ Field mappings work (ai → gemini, gemini_api_key → api_key)  
✅ Main window can now start without the configuration error  

## Impact
- **Backward Compatible**: Existing `get_config()` method unchanged
- **Forward Compatible**: New `config` property supports unified configuration system
- **Type Safe**: Returns properly typed `Dict[str, Any]` as expected by ConfigDetector
- **Field Compatible**: Maps legacy field names to new expected names

## Testing
The fix was validated by:
1. Testing direct property access
2. Testing ConfigDetector integration  
3. Testing main window initialization
4. Verifying field mappings work correctly

The original error is now resolved and the application can start successfully.