# Makefile for Executive Summary Tool
# Cross-platform build automation using UV and PyInstaller

.PHONY: help install install-dev clean test test-unit test-integration test-security test-e2e
.PHONY: lint format typecheck security-scan coverage build build-all build-linux build-windows build-macos
.PHONY: dev run debug release clean-build clean-dist clean-cache docker-build docker-run
.PHONY: docs docs-serve pre-commit setup-hooks validate-env

# Default target
help: ## Show this help message
	@echo "Executive Summary Tool - Build Automation"
	@echo "==========================================="
	@echo ""
	@echo "Available targets:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "Environment Variables:"
	@echo "  BUILD_MODE     - dev|prod (default: dev)"
	@echo "  TARGET_OS      - linux|windows|macos|all (default: current)"
	@echo "  SKIP_TESTS     - true|false (default: false)"
	@echo "  VERBOSE        - true|false (default: false)"

# Environment setup
PYTHON := python3
UV := uv
BUILD_MODE ?= dev
TARGET_OS ?= current
SKIP_TESTS ?= false
VERBOSE ?= false
PROJECT_NAME := wes
VERSION := $(shell grep '^version = ' pyproject.toml | cut -d '"' -f 2)
DIST_DIR := dist
BUILD_DIR := build
SRC_DIR := src
TESTS_DIR := tests
DOCS_DIR := docs

# Platform detection
UNAME_S := $(shell uname -s)
UNAME_M := $(shell uname -m)

ifeq ($(UNAME_S),Linux)
    PLATFORM := linux
    PYTHON_EXECUTABLE := python3
endif
ifeq ($(UNAME_S),Darwin)
    PLATFORM := macos
    PYTHON_EXECUTABLE := python3
endif
ifeq ($(OS),Windows_NT)
    PLATFORM := windows
    PYTHON_EXECUTABLE := python
endif

# Conditional flags
ifeq ($(VERBOSE),true)
    VERBOSE_FLAG := -v
    QUIET_FLAG := 
else
    VERBOSE_FLAG := 
    QUIET_FLAG := -q
endif

# Validate environment
validate-env: ## Validate development environment
	@echo "Validating development environment..."
	@which $(UV) > /dev/null || (echo "Error: UV not found. Please install UV first." && exit 1)
	@which $(PYTHON) > /dev/null || (echo "Error: Python not found." && exit 1)
	@echo "Environment validation passed"

# Installation targets
install: validate-env ## Install production dependencies
	@echo "Installing production dependencies..."
	$(UV) sync --frozen $(QUIET_FLAG)
	@echo "Production dependencies installed"

install-dev: validate-env ## Install development dependencies
	@echo "Installing development dependencies..."
	$(UV) sync --frozen --extra dev $(QUIET_FLAG)
	@echo "Development dependencies installed"

setup-hooks: install-dev ## Setup pre-commit hooks
	@echo "Setting up pre-commit hooks..."
	$(UV) run pre-commit install
	$(UV) run pre-commit install --hook-type commit-msg
	@echo "Pre-commit hooks installed"

# Development targets
dev: install-dev ## Setup development environment
	@echo "Setting up development environment..."
	@$(MAKE) setup-hooks
	@$(MAKE) validate-env
	@echo "Development environment ready"

run: ## Run the application in development mode
	@echo "Starting application in development mode..."
	$(UV) run $(PYTHON_EXECUTABLE) -m wes.main $(VERBOSE_FLAG)

debug: ## Run the application with debug logging
	@echo "Starting application in debug mode..."
	DEBUG=1 $(UV) run $(PYTHON_EXECUTABLE) -m wes.main -v

# Testing targets
test: test-unit test-integration ## Run all tests
	@echo "All tests completed"

test-unit: ## Run unit tests
	@echo "Running unit tests..."
	$(UV) run pytest $(TESTS_DIR)/unit/ $(VERBOSE_FLAG) \
		--cov=$(SRC_DIR)/wes \
		--cov-report=html:htmlcov \
		--cov-report=term-missing \
		--cov-fail-under=95 \
		--junitxml=test-results-unit.xml

test-integration: ## Run integration tests
	@echo "Running integration tests..."
	$(UV) run pytest $(TESTS_DIR)/integration/ $(VERBOSE_FLAG) \
		--junitxml=test-results-integration.xml

test-security: ## Run security tests
	@echo "Running security tests..."
	$(UV) run pytest $(TESTS_DIR)/security/ $(VERBOSE_FLAG) \
		--junitxml=test-results-security.xml

test-e2e: ## Run end-to-end tests
	@echo "Running end-to-end tests..."
	$(UV) run pytest $(TESTS_DIR)/e2e/ $(VERBOSE_FLAG) \
		--junitxml=test-results-e2e.xml

coverage: ## Generate test coverage report
	@echo "Generating coverage report..."
	$(UV) run pytest $(TESTS_DIR)/ \
		--cov=$(SRC_DIR)/wes \
		--cov-report=html:htmlcov \
		--cov-report=term-missing \
		--cov-report=xml:coverage.xml \
		--cov-fail-under=95
	@echo "Coverage report generated in htmlcov/"

# Code quality targets
lint: ## Run linting
	@echo "Running linting..."
	$(UV) run flake8 $(SRC_DIR) $(TESTS_DIR) $(VERBOSE_FLAG)
	$(UV) run pylint $(SRC_DIR)/wes $(VERBOSE_FLAG)

format: ## Format code
	@echo "Formatting code..."
	$(UV) run black $(SRC_DIR) $(TESTS_DIR) $(VERBOSE_FLAG)
	$(UV) run isort $(SRC_DIR) $(TESTS_DIR) $(VERBOSE_FLAG)

typecheck: ## Run type checking
	@echo "Running type checking..."
	$(UV) run mypy $(SRC_DIR)/wes $(VERBOSE_FLAG)

# Security targets
security-scan: ## Run security scans
	@echo "Running security scans..."
	$(UV) run bandit -r $(SRC_DIR) -f json -o security-report.json $(VERBOSE_FLAG)
	$(UV) run safety check --json --output security-deps.json $(QUIET_FLAG)
	$(UV) run semgrep --config=auto $(SRC_DIR) --json --output=security-semgrep.json $(QUIET_FLAG)
	@echo "Security scan results saved to security-*.json files"

# Pre-commit target
pre-commit: ## Run pre-commit checks
	@echo "Running pre-commit checks..."
	$(UV) run pre-commit run --all-files $(VERBOSE_FLAG)

# Build targets
build: ## Build executable for current platform
ifeq ($(SKIP_TESTS),false)
	@$(MAKE) test
endif
	@$(MAKE) build-$(PLATFORM)

build-all: ## Build executables for all platforms
ifeq ($(SKIP_TESTS),false)
	@$(MAKE) test
endif
	@$(MAKE) build-linux
	@$(MAKE) build-windows
	@$(MAKE) build-macos

build-linux: ## Build Linux executable
	@echo "Building Linux executable..."
	$(UV) run pyinstaller \
		--onefile \
		--windowed \
		--name $(PROJECT_NAME)-linux-$(VERSION) \
		--distpath $(DIST_DIR)/linux \
		--workpath $(BUILD_DIR)/linux \
		--specpath $(BUILD_DIR)/linux \
		--hidden-import PySide6.QtCore \
		--hidden-import PySide6.QtGui \
		--hidden-import PySide6.QtWidgets \
		--hidden-import cryptography \
		--hidden-import google.auth \
		--hidden-import jira \
		--collect-all wes \
		$(SRC_DIR)/wes/main.py
	@echo "Linux executable built: $(DIST_DIR)/linux/$(PROJECT_NAME)-linux-$(VERSION)"

build-windows: ## Build Windows executable
	@echo "Building Windows executable..."
	$(UV) run pyinstaller \
		--onefile \
		--windowed \
		--name $(PROJECT_NAME)-windows-$(VERSION).exe \
		--distpath $(DIST_DIR)/windows \
		--workpath $(BUILD_DIR)/windows \
		--specpath $(BUILD_DIR)/windows \
		--hidden-import PySide6.QtCore \
		--hidden-import PySide6.QtGui \
		--hidden-import PySide6.QtWidgets \
		--hidden-import cryptography \
		--hidden-import google.auth \
		--hidden-import jira \
		--collect-all wes \
		$(SRC_DIR)/wes/main.py
	@echo "Windows executable built: $(DIST_DIR)/windows/$(PROJECT_NAME)-windows-$(VERSION).exe"

build-macos: ## Build macOS executable
	@echo "Building macOS executable..."
	$(UV) run pyinstaller \
		--onefile \
		--windowed \
		--name $(PROJECT_NAME)-macos-$(VERSION) \
		--distpath $(DIST_DIR)/macos \
		--workpath $(BUILD_DIR)/macos \
		--specpath $(BUILD_DIR)/macos \
		--hidden-import PySide6.QtCore \
		--hidden-import PySide6.QtGui \
		--hidden-import PySide6.QtWidgets \
		--hidden-import cryptography \
		--hidden-import google.auth \
		--hidden-import jira \
		--collect-all wes \
		$(SRC_DIR)/wes/main.py
	@echo "macOS executable built: $(DIST_DIR)/macos/$(PROJECT_NAME)-macos-$(VERSION)"

# Release targets
release: ## Build release version
	@echo "Building release version..."
	@$(MAKE) clean
	@$(MAKE) install
	@$(MAKE) security-scan
	@$(MAKE) test
	@$(MAKE) build-all
	@$(MAKE) package-release

package-release: ## Package release artifacts
	@echo "Packaging release artifacts..."
	@mkdir -p $(DIST_DIR)/release
	@cd $(DIST_DIR) && tar -czf release/$(PROJECT_NAME)-$(VERSION)-linux.tar.gz linux/
	@cd $(DIST_DIR) && zip -r release/$(PROJECT_NAME)-$(VERSION)-windows.zip windows/
	@cd $(DIST_DIR) && tar -czf release/$(PROJECT_NAME)-$(VERSION)-macos.tar.gz macos/
	@echo "Release packages created in $(DIST_DIR)/release/"

# Docker targets
docker-build: ## Build Docker image
	@echo "Building Docker image..."
	docker build -t $(PROJECT_NAME):$(VERSION) -t $(PROJECT_NAME):latest .

docker-run: ## Run application in Docker container
	@echo "Running application in Docker container..."
	docker run -it --rm \
		-v $(PWD)/config:/app/config \
		-v $(PWD)/logs:/app/logs \
		$(PROJECT_NAME):latest

# Documentation targets
docs: ## Build documentation
	@echo "Building documentation..."
	$(UV) run sphinx-build -b html $(DOCS_DIR) $(DOCS_DIR)/_build/html

docs-serve: docs ## Serve documentation locally
	@echo "Serving documentation on http://localhost:8000"
	@cd $(DOCS_DIR)/_build/html && $(PYTHON) -m http.server 8000

# Cleanup targets
clean: clean-cache clean-build clean-dist ## Clean all generated files

clean-cache: ## Clean cache files
	@echo "Cleaning cache files..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@find . -type f -name "*.pyd" -delete 2>/dev/null || true
	@find . -type f -name ".coverage" -delete 2>/dev/null || true
	@rm -rf htmlcov/ 2>/dev/null || true
	@rm -rf .coverage.* 2>/dev/null || true

clean-build: ## Clean build files
	@echo "Cleaning build files..."
	@rm -rf $(BUILD_DIR)/ 2>/dev/null || true
	@rm -rf *.egg-info/ 2>/dev/null || true
	@rm -rf .tox/ 2>/dev/null || true

clean-dist: ## Clean distribution files
	@echo "Cleaning distribution files..."
	@rm -rf $(DIST_DIR)/ 2>/dev/null || true

# Maintenance targets
update-deps: ## Update dependencies
	@echo "Updating dependencies..."
	$(UV) sync --upgrade

check-deps: ## Check for dependency vulnerabilities
	@echo "Checking dependencies for vulnerabilities..."
	$(UV) run safety check
	$(UV) run pip-audit

# CI/CD targets
ci-test: ## Run CI test suite
	@echo "Running CI test suite..."
	@$(MAKE) install-dev
	@$(MAKE) lint
	@$(MAKE) typecheck
	@$(MAKE) security-scan
	@$(MAKE) test
	@$(MAKE) coverage

ci-build: ## Run CI build process
	@echo "Running CI build process..."
	@$(MAKE) ci-test
	@$(MAKE) build

# Information targets
info: ## Show build information
	@echo "Build Information"
	@echo "=================="
	@echo "Project Name: $(PROJECT_NAME)"
	@echo "Version: $(VERSION)"
	@echo "Platform: $(PLATFORM)"
	@echo "Python: $(PYTHON_EXECUTABLE)"
	@echo "UV: $(shell $(UV) --version)"
	@echo "Build Mode: $(BUILD_MODE)"
	@echo "Target OS: $(TARGET_OS)"
	@echo "Skip Tests: $(SKIP_TESTS)"
	@echo "Verbose: $(VERBOSE)"
	@echo ""
	@echo "Directories:"
	@echo "  Source: $(SRC_DIR)"
	@echo "  Tests: $(TESTS_DIR)"
	@echo "  Build: $(BUILD_DIR)"
	@echo "  Dist: $(DIST_DIR)"
	@echo "  Docs: $(DOCS_DIR)"

# Health check
health: ## Run health checks
	@echo "Running health checks..."
	@$(MAKE) validate-env
	@$(MAKE) check-deps
	@$(MAKE) lint
	@$(MAKE) typecheck
	@$(MAKE) security-scan
	@echo "Health checks completed"

# Default target points to help
.DEFAULT_GOAL := help