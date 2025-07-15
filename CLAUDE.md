# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WES (Wes) is a cross-platform desktop application that automates executive summary creation by integrating Jira activity data with Google's Gemini AI and exporting summaries in multiple formats (Markdown, HTML, PDF, Text). The application uses PySide6 (Qt6) for the GUI and is built with Python 3.11+.

## Essential Commands

### Development Setup
```bash
make dev          # Complete dev environment setup (installs UV, dependencies, pre-commit hooks)
make install-dev  # Install development dependencies only
```

### Running the Application
```bash
make run    # Run in development mode
make debug  # Run with debug logging
```

### Testing
```bash
make test              # Run all tests (unit, integration, security, e2e)
make test-unit         # Run unit tests only
make coverage          # Generate coverage report (95% minimum required)
pytest tests/unit/test_specific.py::TestClass::test_method  # Run single test
```

### Code Quality (MUST run before committing)
```bash
make format     # Format code with black and isort
make lint       # Run flake8 and pylint
make typecheck  # Run mypy type checking
make pre-commit # Run all pre-commit checks
```

### Building
```bash
make build      # Build for current platform
make build-all  # Build for all platforms (Linux, Windows, macOS)
```

## Architecture Overview

### Core Components

1. **src/wes/core/orchestrator.py** - Central workflow coordinator that manages the entire summary generation process
2. **src/wes/core/config_manager.py** - Configuration management with encryption for sensitive data
3. **src/wes/gui/main_window.py** - Main application window using PySide6
4. **src/wes/core/export_manager.py** - Export functionality for multiple output formats

### Integration Flow

```
User Input → Orchestrator → Jira Client → Gemini AI → Export Manager → File/Clipboard
                    ↓
             Security Manager (encryption/decryption of credentials)
```

### Key Integrations

- **Jira**: Two implementations:
  - `integrations/jira_client.py` - Standard Jira (uses API token)
  - `integrations/redhat_jira_client.py` - Red Hat Jira (uses rhjira library with Kerberos)
- **AI Service**: 
  - `integrations/gemini_client.py` - Google Gemini AI for summary generation
- **Export Formats**:
  - Markdown (.md)
  - HTML (.html)
  - PDF (.pdf)
  - Plain Text (.txt)
  - Clipboard copy

### Security Architecture

- All credentials stored with AES-256 encryption
- Security manager handles all encryption/decryption operations
- Comprehensive input validation and sanitization
- Audit logging for all sensitive operations
- Multiple security scanning tools integrated (bandit, safety, semgrep)

## Development Guidelines

### Package Management
This project uses UV (not pip/poetry). Always use UV for dependency management:
```bash
uv add package-name       # Add dependency
uv add --dev package-name # Add dev dependency
```

### Testing Requirements
- Maintain 95% code coverage minimum
- Write tests for all new features
- Security tests required for credential handling
- Integration tests use mocking for external services

### GUI Development
- Uses PySide6 (Qt6) - check existing components in `src/wes/gui/` for patterns
- Follow existing signal/slot patterns for event handling
- Use the custom OAuth handler for Google authentication flows

### Configuration
- User configs stored in platform-specific directories
- Sensitive data always encrypted before storage
- Configuration templates in `core/config_templates.py`

## Important Notes

1. **Pre-commit hooks are mandatory** - installed automatically with `make dev`
2. **Red Hat Jira integration** is optional - requires `make install-dev` or installation with `[redhat]` extra
3. **Cross-platform building** requires platform-specific environments (use GitHub Actions for full builds)
4. **Only 2 services to configure** - Jira credentials and Gemini AI API key
5. **Security scans** run automatically in CI but can be run locally with `make security-scan`