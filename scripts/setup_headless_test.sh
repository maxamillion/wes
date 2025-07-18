#!/bin/bash

# Setup headless testing environment for GUI tests
# This script ensures tests can run without a graphical environment

set -e

echo "Setting up headless environment for GUI tests..."

# Set Qt platform to offscreen mode
export QT_QPA_PLATFORM=offscreen

# Disable Qt debug logging to reduce noise
export QT_LOGGING_RULES="*.debug=false;qt.qpa.xcb=false"

# Set default display if not set
if [ -z "$DISPLAY" ]; then
    export DISPLAY=:99
fi

# Check if Xvfb is available for virtual display
if command -v xvfb-run &> /dev/null; then
    echo "xvfb-run is available - using virtual display"
    # Run tests with virtual display
    exec xvfb-run -a -s "-screen 0 1024x768x24" "$@"
else
    echo "xvfb-run not available - using offscreen platform"
    # Run tests with offscreen platform
    exec "$@"
fi