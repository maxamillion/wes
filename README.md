# Wes - Weekly Executive Summary
[![Tests](https://github.com/maxamillion/wes/actions/workflows/tests.yml/badge.svg)](https://github.com/maxamillion/wes/actions/workflows/tests.yml)

A cross-platform desktop application that automates the creation of executive summaries by integrating Jira activity data with Google's Gemini AI and exporting summaries in multiple formats.

## Features

- **Jira Integration**: Fetch team activity data from configurable Jira instances
- **AI-Powered Summarization**: Generate intelligent executive summaries using Google Gemini AI
- **Multiple Export Formats**: Export summaries as Markdown, HTML, PDF, or plain text
- **Cross-Platform**: Runs on Windows, macOS, and Linux
- **Secure**: Enterprise-grade security with encrypted credential storage
- **User-Friendly**: Intuitive desktop GUI built with PySide6

## Architecture

### Technology Stack
- **Framework**: PySide6 (Qt6) for cross-platform GUI
- **Language**: Python 3.11+
- **Package Management**: UV for dependency management
- **AI Integration**: Google Gemini API
- **Testing**: pytest with comprehensive coverage
- **Build System**: PyInstaller for executable generation

### Security Features
- AES-256 encryption for credential storage
- Secure input validation and sanitization
- HTTPS-only API communications
- Comprehensive audit logging
- Zero-trust architecture

## Quick Start

### Prerequisites

- Python 3.11 or higher
- UV package manager ([installation guide](https://github.com/astral-sh/uv))
- Git

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd wes
   ```

2. **Set up development environment**:
   ```bash
   make dev
   ```

3. **Configure the application**:
   - Launch the application: `make run`
   - Complete the initial setup wizard
   - Configure your Jira and AI credentials

### Configuration

The application requires configuration for two main services:

#### Jira Configuration
- **Jira URL**: Your Atlassian instance URL
- **Username**: Your Jira username/email
- **API Token**: Generate from Jira account settings

#### AI Configuration
- **Gemini API Key**: Get from Google AI Studio
- **Model Selection**: Choose between available models
- **Custom Prompts**: Optional customization of summary generation

## Usage

### Basic Workflow

1. **Configure Data Sources**:
   - Set date range for activity data
   - Select users to include in the summary
   - Optionally filter by Jira projects

2. **Generate Summary**:
   - Fetch data from Jira
   - Process with AI to generate executive summary
   - Preview the generated content

3. **Export Document**:
   - Choose export format (Markdown, HTML, PDF, or text)
   - Save to local file system
   - Copy to clipboard for sharing

### Command Line Interface

```bash
# Run the application
wes

# Test API connections
wes --test-connections

# Enable debug logging
wes --debug

# Show version
wes --version
```

## Development

### Setting Up Development Environment

1. **Install dependencies**:
   ```bash
   make install-dev
   ```

2. **Run tests**:
   ```bash
   make test
   ```

3. **Code quality checks**:
   ```bash
   make lint
   make typecheck
   make security-scan
   ```

### Testing

The project follows Test-Driven Development (TDD) with comprehensive test coverage:

```bash
# Run all tests
make test

# Run specific test categories
make test-unit
make test-integration
make test-security
make test-e2e

# Generate coverage report
make coverage
```

### Code Quality

```bash
# Format code
make format

# Lint code
make lint

# Type checking
make typecheck

# Security scanning
make security-scan

# Run all quality checks
make pre-commit
```

### Building

```bash
# Build for current platform
make build

# Build for all platforms
make build-all

# Build specific platform
make build-linux
make build-windows
make build-macos
```

## Security

### Security Features

- **Credential Encryption**: All API keys and tokens are encrypted using AES-256
- **Input Validation**: Comprehensive validation prevents injection attacks
- **Secure Communications**: HTTPS-only with certificate validation
- **Audit Logging**: Security events are logged for compliance
- **Rate Limiting**: Protects against API abuse

### Security Best Practices

1. **Credential Management**:
   - Never commit credentials to version control
   - Use service accounts for production deployments
   - Rotate API keys regularly (90-day default)

2. **Network Security**:
   - Application communicates only over HTTPS
   - Certificate pinning for critical APIs
   - Configurable proxy support for corporate environments

3. **Data Protection**:
   - Minimal data retention (7-day default for cached data)
   - Secure deletion of sensitive information
   - No logging of confidential data

### Compliance

The application is designed to meet enterprise security requirements:

- **OWASP Top 10**: Addresses all current vulnerabilities
- **SOC 2 Type II**: Security, availability, and confidentiality controls
- **GDPR/CCPA**: Data protection and privacy compliance
- **NIST Cybersecurity Framework**: Implements core security functions

## Deployment

### Single User Deployment

1. Download the executable for your platform
2. Run the application and complete setup wizard
3. Configure your API credentials

### Enterprise Deployment

1. **Prepare Configuration**:
   ```bash
   # Create configuration template
   wes --export-config template.json
   ```

2. **Mass Deployment**:
   - Use service account credentials
   - Deploy configuration via group policy or MDM
   - Configure centralized logging if required

3. **Monitoring**:
   - Enable audit logging
   - Set up log aggregation
   - Configure security monitoring

## Troubleshooting

### Common Issues

**Authentication Errors**:
- Verify API credentials are correct and not expired
- Check network connectivity and proxy settings
- Ensure required permissions are granted

**Performance Issues**:
- Adjust rate limits in configuration
- Reduce date range for large datasets
- Check system resources and network bandwidth

**Export Issues**:
- Verify output directory permissions
- Check available disk space
- Ensure selected format is supported

### Logging

Enable debug logging for troubleshooting:

```bash
wes --debug --log-file debug.log
```

Log files are stored in:
- **Windows**: `%USERPROFILE%\.wes\logs\`
- **macOS**: `~/.wes/logs/`
- **Linux**: `~/.wes/logs/`

### Getting Help

1. **Check Logs**: Review application logs for error details
2. **Test Connections**: Use `--test-connections` to verify API access
3. **Documentation**: Refer to the troubleshooting guide
4. **Support**: Contact your system administrator or support team

## Contributing

### Development Workflow

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/new-feature`
3. **Write tests**: Follow TDD principles
4. **Implement feature**: Ensure all tests pass
5. **Security review**: Run security scans
6. **Submit pull request**: Include comprehensive description

### Coding Standards

- **Python Style**: Follow PEP 8 with Black formatting
- **Type Hints**: Use type annotations throughout
- **Documentation**: Docstrings for all public methods
- **Testing**: 95% code coverage requirement
- **Security**: Security review for all changes

### Testing Requirements

- Unit tests for all new functionality
- Integration tests for API interactions
- Security tests for input validation
- End-to-end tests for complete workflows

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Changelog

### Version 1.0.0
- Initial release
- Jira integration with configurable queries
- Google Gemini AI summarization
- Multiple format document export
- Cross-platform GUI application
- Enterprise-grade security features
- Comprehensive test suite
- Multi-platform build support

## Support

For support, documentation, and updates:

- **Documentation**: [Project Wiki](docs/)
- **Issues**: [GitHub Issues](https://github.com/company/wes/issues)
- **Security**: Report security issues to security@company.com

---

**Executive Summary Tool** - Streamlining executive reporting through intelligent automation.
