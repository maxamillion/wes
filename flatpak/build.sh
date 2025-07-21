#!/bin/bash
# Flatpak build script for WES

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Building WES Flatpak package...${NC}"

# Check if flatpak is installed
if ! command -v flatpak &> /dev/null; then
    echo -e "${RED}Error: flatpak is not installed${NC}"
    echo "Install it with: sudo apt-get install flatpak flatpak-builder"
    exit 1
fi

# Check if required runtime is installed
if ! flatpak list | grep -q "org.kde.Platform.*6.6"; then
    echo -e "${YELLOW}Installing required runtime...${NC}"
    flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
    flatpak install -y flathub org.kde.Platform//6.6 org.kde.Sdk//6.6
fi

# Get version from pyproject.toml
VERSION=$(grep '^version = ' ../pyproject.toml | cut -d '"' -f 2)
echo -e "${GREEN}Building version: $VERSION${NC}"

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf build-dir repo *.flatpak

# Build the flatpak
echo "Building flatpak..."
flatpak-builder --force-clean --repo=repo build-dir com.company.wes.yml

# Create bundle
echo "Creating flatpak bundle..."
flatpak build-bundle repo wes-${VERSION}.flatpak com.company.wes

echo -e "${GREEN}Build complete!${NC}"
echo -e "Flatpak bundle created: ${YELLOW}wes-${VERSION}.flatpak${NC}"
echo ""
echo "To install locally:"
echo "  flatpak install --user wes-${VERSION}.flatpak"
echo ""
echo "To run:"
echo "  flatpak run com.company.wes"