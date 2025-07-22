# Building WES

This document describes how to build WES for different platforms and packaging formats.

## Prerequisites

### All Platforms
- Python 3.11 or higher
- UV package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Git

### Platform-Specific Requirements

#### Linux
- Qt6 development libraries
- X11/Wayland libraries
- For Flatpak: `flatpak` and `flatpak-builder`
- For AppImage: `wget` and FUSE

#### Windows
- Visual Studio Build Tools or MinGW
- Windows SDK (for code signing, optional)
- Inno Setup (for installer creation, optional)

#### macOS
- Xcode Command Line Tools
- create-dmg (install with `brew install create-dmg`)
- Developer ID certificate (for code signing, optional)

## Quick Build

The simplest way to build for your current platform:

```bash
make build
```

This will:
1. Run tests
2. Build an executable for your platform
3. Place it in `dist/<platform>/`

## Platform Builds

### Linux Executable

Standard standalone executable:
```bash
make build-linux
# Output: dist/linux/wes-linux-<version>
```

### Linux Flatpak

Flatpak provides sandboxed distribution:
```bash
cd flatpak
./build.sh
# Output: wes-<version>.flatpak
```

Install the Flatpak:
```bash
flatpak install --user wes-*.flatpak
flatpak run com.company.wes
```

### Linux AppImage

Portable executable that runs on most Linux distributions:
```bash
./scripts/build/build-appimage.sh
# Output: dist/appimage/wes-<version>-x86_64.AppImage
```

### Windows Executable

Standalone portable executable:
```bash
make build-windows
# Output: dist/windows/wes-windows-<version>.exe
```

### Windows Installer

Create a proper Windows installer (requires Inno Setup):
```powershell
./scripts/build/build-windows-installer.ps1
# Output: dist/windows-installer/wes-setup-<version>.exe
```

### macOS Application

Build macOS app bundle:
```bash
make build-macos
# Output: dist/macos/wes-macos-<version>
```

Create DMG for distribution:
```bash
./scripts/build/build-macos-dmg.sh
# Output: dist/macos/wes-<version>.dmg
```

## Automated Builds

### Nightly Builds

The project includes GitHub Actions workflow for automated nightly builds:

- Runs daily at 2 AM UTC
- Builds for all platforms (Linux, Windows, macOS)
- Creates Flatpak packages
- Uploads artifacts with 30-day retention
- Can be triggered manually via GitHub Actions UI

### Release Builds

Tagged releases trigger automatic builds:
```bash
git tag v1.0.1
git push origin v1.0.1
```

This will:
- Build all platforms
- Create GitHub Release
- Upload all artifacts to the release

## Build Options

### Skip Tests
```bash
SKIP_TESTS=true make build
```

### Verbose Output
```bash
VERBOSE=true make build
```

### Clean Build
```bash
make clean
make build
```

### All Platforms
Build for all platforms (requires appropriate environment):
```bash
make build-all
```

## Packaging Formats

### Executable Formats

| Platform | Format | Description |
|----------|---------|-------------|
| Linux | Binary | Standalone executable with bundled dependencies |
| Linux | Flatpak | Sandboxed application with runtime isolation |
| Linux | AppImage | Portable executable, no installation needed |
| Windows | .exe | Portable executable, no installation needed |
| Windows | Installer | Traditional Windows installer with uninstall support |
| macOS | App Bundle | Standard macOS application |
| macOS | DMG | Disk image for easy distribution |

### Distribution Recommendations

- **Linux Desktop Users**: Flatpak (best integration) or AppImage (most portable)
- **Linux Server/CLI**: Standard binary
- **Windows Users**: Installer for permanent installation, .exe for portable use
- **macOS Users**: DMG for easy drag-and-drop installation

## Troubleshooting

### Linux Build Issues

**Missing Qt libraries**:
```bash
sudo apt-get install libgl1-mesa-glx libxcb-xinerama0 libxcb-cursor0
```

**Flatpak runtime not found**:
```bash
flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak install flathub org.kde.Platform//6.6 org.kde.Sdk//6.6
```

### Windows Build Issues

**PyInstaller not creating single file**:
Ensure hidden imports are specified in the Makefile.

**Missing Visual C++ Runtime**:
Users may need to install Visual C++ Redistributables.

### macOS Build Issues

**Code signing errors**:
Build without signing for local use, or obtain a Developer ID certificate.

**DMG creation fails**:
Install create-dmg: `brew install create-dmg`

## Security Considerations

### Code Signing

**Windows**:
- Use Authenticode certificate for .exe and installer
- Signs can be verified with `signtool verify`

**macOS**:
- Requires Apple Developer ID
- Notarization needed for distribution outside App Store

### Verification

All builds can be verified with checksums:
```bash
sha256sum dist/*/wes-*
```

Nightly builds automatically generate `checksums.txt` with all artifacts.