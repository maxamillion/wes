# Headless Testing Setup

This document describes how to run GUI tests in headless environments (without a graphical display) for the WES project.

## Overview

The WES project uses PySide6 (Qt6) for its GUI components, which normally require a graphical display. However, tests can be run in headless environments like CI/CD pipelines by using Qt's offscreen platform.

## Configuration

### Automatic Setup

The test suite automatically configures headless mode when no display is available:

1. **conftest.py** - Automatically sets `QT_QPA_PLATFORM=offscreen` if not already set
2. **Makefile** - Updated to use headless environment variables
3. **pyproject.toml** - Configured for Qt testing

### Manual Setup

To manually run tests in headless mode:

```bash
# Set environment variables
export QT_QPA_PLATFORM=offscreen
export QT_LOGGING_RULES="*.debug=false;qt.qpa.xcb=false"
export DISPLAY=:99  # Optional, for fallback

# Run tests
uv run pytest tests/unit/gui/
```

## Running Tests

### Using Make Targets

```bash
# Run all tests in headless mode
make test-headless

# Run specific test types with headless support
make test-unit
make test-e2e
make coverage
```

### Using pytest Directly

```bash
# Run specific GUI tests
QT_QPA_PLATFORM=offscreen uv run pytest tests/unit/gui/ -v

# Run headless verification tests
QT_QPA_PLATFORM=offscreen uv run pytest tests/test_headless.py -v

# Run with coverage
QT_QPA_PLATFORM=offscreen uv run pytest tests/unit/gui/ --cov=src/wes
```

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `QT_QPA_PLATFORM` | Qt platform plugin | `offscreen` |
| `QT_LOGGING_RULES` | Reduce Qt debug output | `*.debug=false;qt.qpa.xcb=false` |
| `DISPLAY` | X11 display (fallback) | `:99` |

## Alternative: Using Xvfb

If `xvfb-run` is available, it can be used instead:

```bash
# Install xvfb (on Ubuntu/Debian)
sudo apt-get install xvfb

# Run tests with virtual display
xvfb-run -a -s "-screen 0 1024x768x24" make test
```

## CI/CD Integration

### GitHub Actions

```yaml
- name: Run GUI tests in headless mode
  env:
    QT_QPA_PLATFORM: offscreen
    QT_LOGGING_RULES: "*.debug=false;qt.qpa.xcb=false"
  run: |
    uv run pytest tests/unit/gui/ -v
```

### GitLab CI

```yaml
test:
  variables:
    QT_QPA_PLATFORM: offscreen
    QT_LOGGING_RULES: "*.debug=false;qt.qpa.xcb=false"
  script:
    - uv run pytest tests/unit/gui/ -v
```

### Jenkins

```groovy
pipeline {
    agent any
    environment {
        QT_QPA_PLATFORM = 'offscreen'
        QT_LOGGING_RULES = '*.debug=false;qt.qpa.xcb=false'
    }
    stages {
        stage('Test') {
            steps {
                sh 'uv run pytest tests/unit/gui/ -v'
            }
        }
    }
}
```

## Troubleshooting

### Common Issues

1. **Qt platform plugin not found**
   - Ensure PySide6 is installed: `uv add PySide6`
   - Check `QT_QPA_PLATFORM` is set to `offscreen`

2. **X11 connection errors**
   - Set `QT_QPA_PLATFORM=offscreen` before importing Qt
   - Verify no Qt imports happen before environment setup

3. **Tests hanging**
   - Check for async tests that might be causing issues
   - Use `pytest-qt` for proper Qt event loop handling

4. **Missing display warnings**
   - Set `QT_LOGGING_RULES` to suppress debug output
   - Ensure `DISPLAY` variable is set (even if virtual)

### Verification

Run the headless verification tests to ensure everything is working:

```bash
QT_QPA_PLATFORM=offscreen uv run pytest tests/test_headless.py -v
```

This will test:
- QApplication creation
- Widget creation and manipulation
- Signal/slot connections
- Layout operations
- Style operations
- Environment variable configuration

## Performance Considerations

Headless testing typically provides:
- **Faster execution** - No GUI rendering overhead
- **Better CI/CD integration** - No display dependencies
- **Consistent results** - No window manager interference
- **Parallel execution** - Multiple test processes can run simultaneously

## Limitations

- No visual debugging - widgets can't be inspected visually
- Some platform-specific behaviors may differ
- Screenshot testing is not possible (unless using virtual display)

## Files Modified

- `tests/conftest.py` - Auto-headless configuration
- `Makefile` - Headless environment variables
- `pyproject.toml` - Qt testing configuration
- `scripts/setup_headless_test.sh` - Headless setup script
- `tests/test_headless.py` - Headless verification tests

## Best Practices

1. **Always test headless mode** in CI/CD pipelines
2. **Use pytest-qt** for GUI test fixtures
3. **Set environment variables early** in test setup
4. **Mock external dependencies** that might require display
5. **Test both headless and display modes** during development