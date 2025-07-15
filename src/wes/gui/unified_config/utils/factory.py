"""Factory classes for dependency injection and improved testability.

This module provides factory patterns to create instances with dependencies
injected, making the code more testable and maintainable.
"""

from typing import Dict, Optional, Protocol, Type, runtime_checkable

from PySide6.QtWidgets import QWidget

from wes.core.config_manager import ConfigManager
from wes.gui.unified_config.config_pages.base_page import ConfigPageBase
from wes.gui.unified_config.types import ServiceType


@runtime_checkable
class ConfigPageFactory(Protocol):
    """Protocol for config page factories."""

    def create_page(
        self,
        service_type: ServiceType,
        config_manager: ConfigManager,
        parent: Optional[QWidget] = None,
    ) -> ConfigPageBase:
        """Create a configuration page for the given service type."""
        ...


class DefaultConfigPageFactory:
    """Default factory for creating configuration pages."""

    def __init__(self):
        """Initialize the factory with page mappings."""
        self._page_registry: Dict[ServiceType, Type[ConfigPageBase]] = {}
        self._initialize_defaults()

    def _initialize_defaults(self) -> None:
        """Initialize default page mappings."""
        # Import here to avoid circular imports
        from wes.gui.unified_config.config_pages.app_settings_page import (
            AppSettingsPage,
        )
        from wes.gui.unified_config.config_pages.gemini_page import GeminiConfigPage
        from wes.gui.unified_config.config_pages.google_page import GoogleConfigPage
        from wes.gui.unified_config.config_pages.jira_page import JiraConfigPage
        from wes.gui.unified_config.config_pages.security_page import (
            SecurityPage,
        )

        self._page_registry = {
            ServiceType.GOOGLE: GoogleConfigPage,
            ServiceType.JIRA: JiraConfigPage,
            ServiceType.GEMINI: GeminiConfigPage,
        }

    def register_page(
        self, service_type: ServiceType, page_class: Type[ConfigPageBase]
    ) -> None:
        """Register a custom page class for a service type.

        Args:
            service_type: The service type to register.
            page_class: The page class to use for this service type.
        """
        self._page_registry[service_type] = page_class

    def create_page(
        self,
        service_type: ServiceType,
        config_manager: ConfigManager,
        parent: Optional[QWidget] = None,
    ) -> ConfigPageBase:
        """Create a configuration page for the given service type.

        Args:
            service_type: The type of service to create a page for.
            config_manager: The configuration manager instance.
            parent: Optional parent widget.

        Returns:
            ConfigPageBase: The created configuration page.

        Raises:
            ValueError: If no page is registered for the service type.
        """
        if service_type not in self._page_registry:
            raise ValueError(f"No page registered for service type: {service_type}")

        page_class = self._page_registry[service_type]
        return page_class(config_manager, parent)

    def get_supported_services(self) -> list[ServiceType]:
        """Get list of supported service types.

        Returns:
            list[ServiceType]: List of service types with registered pages.
        """
        return list(self._page_registry.keys())


class TestConfigPageFactory:
    """Test factory for creating mock configuration pages."""

    def __init__(self, mock_pages: Optional[Dict[ServiceType, ConfigPageBase]] = None):
        """Initialize with optional mock pages.

        Args:
            mock_pages: Optional dictionary of pre-created mock pages.
        """
        self.mock_pages = mock_pages or {}
        self.created_pages: list[tuple[ServiceType, ConfigManager]] = []

    def create_page(
        self,
        service_type: ServiceType,
        config_manager: ConfigManager,
        parent: Optional[QWidget] = None,
    ) -> ConfigPageBase:
        """Create or return a mock page.

        Args:
            service_type: The type of service to create a page for.
            config_manager: The configuration manager instance.
            parent: Optional parent widget.

        Returns:
            ConfigPageBase: The mock configuration page.
        """
        # Track what was requested
        self.created_pages.append((service_type, config_manager))

        # Return mock if available
        if service_type in self.mock_pages:
            return self.mock_pages[service_type]

        # Otherwise create a real page (for integration tests)
        factory = DefaultConfigPageFactory()
        return factory.create_page(service_type, config_manager, parent)


# Singleton instance
_default_factory = DefaultConfigPageFactory()


def get_config_page_factory() -> ConfigPageFactory:
    """Get the default config page factory.

    Returns:
        ConfigPageFactory: The factory instance.
    """
    return _default_factory


def set_config_page_factory(factory: ConfigPageFactory) -> None:
    """Set a custom config page factory (useful for testing).

    Args:
        factory: The factory to use.
    """
    global _default_factory
    _default_factory = factory
