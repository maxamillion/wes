# GitHub Actions Workflows

This directory contains GitHub Actions workflows for automated testing, security scanning, and building of the Executive Summary Tool.

## Workflows Overview

### 1. Quick Checks (`quick-checks.yml`)
**Trigger:** Every push and pull request
**Purpose:** Fast feedback on code quality and basic tests
**Runtime:** ~5-10 minutes

- Code formatting checks (Black, isort)
- Basic linting (flake8)
- Type checking (mypy)
- Quick unit tests
- Basic security scan
- Project structure validation

### 2. Tests (`tests.yml`)
**Trigger:** Push to main/develop branches, pull requests
**Purpose:** Comprehensive testing across platforms
**Runtime:** ~20-30 minutes

- Runs on Ubuntu, Windows, and macOS
- Tests Python 3.11 and 3.12
- Unit and integration tests
- Code coverage reporting
- Security scans
- Build testing

### 3. Comprehensive Tests (`comprehensive-tests.yml`)
**Trigger:** Daily at 2 AM UTC, manual trigger, push to main
**Purpose:** Complete test suite including e2e tests
**Runtime:** ~45-60 minutes

- All test types (unit, integration, security, e2e)
- Full coverage reporting
- Complete security scanning
- Build matrix testing
- Detailed reporting

### 4. Security (`security.yml`)
**Trigger:** Push to main, pull requests, daily at 3 AM UTC
**Purpose:** Security vulnerability scanning
**Runtime:** ~10-15 minutes

- Bandit static analysis
- Safety dependency scanning
- Semgrep security patterns
- SARIF results upload
- Security test execution

## Environment Variables

The workflows use these environment variables:

- `DISPLAY=":99"` - Virtual display for GUI testing
- `QT_QPA_PLATFORM="offscreen"` - Qt platform for headless testing

## Test Commands

The workflows utilize these Makefile targets:

```bash
# Unit tests
make test-unit

# Integration tests  
make test-integration

# Security tests
make test-security

# End-to-end tests
make test-e2e

# All tests
make test

# Build targets
make build-linux
make build-windows
make build-macos
```

## Artifacts

Each workflow produces artifacts:

- **Test Results:** JUnit XML files for test reporting
- **Coverage Reports:** HTML and XML coverage reports
- **Security Reports:** JSON and SARIF format security scan results
- **Build Artifacts:** Executable files for each platform

## Coverage Requirements

- Unit tests: 50% minimum coverage
- Comprehensive tests: 50% minimum coverage
- Individual test files may have higher coverage

## Security Integration

Security workflows integrate with GitHub's Security tab:

- SARIF results are uploaded for code scanning
- Dependency vulnerabilities are tracked
- Security test results are reported

## Local Testing

To run the same tests locally:

```bash
# Install dependencies
uv sync --extra dev

# Run quick checks
uv run black --check src tests
uv run flake8 src tests
uv run mypy src/executive_summary_tool
uv run pytest tests/unit/ -x

# Run comprehensive tests
make test
make coverage

# Run security scans
uv run bandit -r src/
uv run safety check
```

## Troubleshooting

### Common Issues

1. **GUI Tests Failing:**
   - Ensure `QT_QPA_PLATFORM=offscreen` is set
   - Check virtual display setup on Linux

2. **Coverage Too Low:**
   - Add more unit tests
   - Adjust coverage threshold if needed

3. **Security Scan Failures:**
   - Review security reports in artifacts
   - Update dependencies if vulnerabilities found

4. **Build Failures:**
   - Check PyInstaller dependencies
   - Verify platform-specific requirements

### Debugging Steps

1. Check workflow logs in GitHub Actions tab
2. Download artifacts for detailed reports
3. Run tests locally with same environment
4. Review recent code changes for issues