#!/bin/bash
# Development environment setup script for Executive Summary Tool

set -e  # Exit on any error

echo "🚀 Setting up Executive Summary Tool development environment..."

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ UV is not installed. Please install UV first:"
    echo "   curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "   For more info: https://github.com/astral-sh/uv"
    exit 1
fi

echo "✅ UV is installed"

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
REQUIRED_VERSION="3.11"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "❌ Python $REQUIRED_VERSION or higher is required. Found: $PYTHON_VERSION"
    echo "   Please install Python $REQUIRED_VERSION+ and try again"
    exit 1
fi

echo "✅ Python $PYTHON_VERSION is compatible"

# Create virtual environment and install dependencies
echo "📦 Installing dependencies..."
uv sync --frozen --extra dev

echo "🔧 Setting up pre-commit hooks..."
uv run pre-commit install
uv run pre-commit install --hook-type commit-msg

# Create necessary directories
echo "📁 Creating application directories..."
mkdir -p ~/.executive-summary-tool/{logs,config,cache}

# Run initial tests to verify setup
echo "🧪 Running initial tests..."
uv run pytest tests/unit/test_security_manager.py -v

# Check code quality
echo "🔍 Running code quality checks..."
uv run black --check src tests
uv run isort --check-only src tests
uv run flake8 src tests
uv run mypy src

echo ""
echo "✅ Development environment setup complete!"
echo ""
echo "Next steps:"
echo "  1. Run the application:          make run"
echo "  2. Run all tests:               make test"
echo "  3. Check code quality:          make lint"
echo "  4. View available commands:     make help"
echo ""
echo "Happy coding! 🎉"