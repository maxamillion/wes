"""Utility modules for the unified configuration dialog.

This package provides reusable utilities to improve code maintainability,
reduce duplication, and enhance testability.
"""

# Existing utilities
from .config_detector import ConfigDetector
from .responsive_layout import ResponsiveConfigLayout

# Dialog utilities
from .dialogs import DialogManager, ValidationDialog, FileDialogManager, MessageType

# Style management
from .styles import StyleManager, StyleConstants

# Configuration constants
from .constants import ConfigConstants, URLConstants, ServiceScopes, ValidationPatterns

# Dependency injection
from .factory import (
    ConfigPageFactory,
    DefaultConfigPageFactory,
    TestConfigPageFactory,
    get_config_page_factory,
    set_config_page_factory,
)
from .service_locator import (
    ServiceLocator,
    ServiceNotFoundError,
    get_service,
    register_service,
    register_service_factory,
    inject,
    ServiceScope,
)

__all__ = [
    # Existing
    "ConfigDetector",
    "ResponsiveConfigLayout",
    # Dialogs
    "DialogManager",
    "ValidationDialog",
    "FileDialogManager",
    "MessageType",
    # Styles
    "StyleManager",
    "StyleConstants",
    # Constants
    "ConfigConstants",
    "URLConstants",
    "ServiceScopes",
    "ValidationPatterns",
    # Factory
    "ConfigPageFactory",
    "DefaultConfigPageFactory",
    "TestConfigPageFactory",
    "get_config_page_factory",
    "set_config_page_factory",
    # Service Locator
    "ServiceLocator",
    "ServiceNotFoundError",
    "get_service",
    "register_service",
    "register_service_factory",
    "inject",
    "ServiceScope",
]
