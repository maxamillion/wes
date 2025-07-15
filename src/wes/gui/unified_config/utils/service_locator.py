"""Service locator for dependency injection and improved testability.

This module provides a simple service locator pattern to manage dependencies
across the application, making it easier to test and maintain.
"""

from typing import Any, Dict, Type, TypeVar, Optional, Callable
from functools import wraps

from wes.core.config_manager import ConfigManager
from wes.utils.logging_config import get_logger


T = TypeVar("T")


class ServiceNotFoundError(Exception):
    """Raised when a requested service is not found."""

    pass


class ServiceLocator:
    """Service locator for managing application dependencies."""

    def __init__(self):
        """Initialize the service locator."""
        self._services: Dict[Type, Any] = {}
        self._factories: Dict[Type, Callable[[], Any]] = {}
        self.logger = get_logger(__name__)

    def register(self, service_type: Type[T], instance: T) -> None:
        """Register a service instance.

        Args:
            service_type: The type/interface of the service.
            instance: The service instance.
        """
        self._services[service_type] = instance
        self.logger.debug(f"Registered service: {service_type.__name__}")

    def register_factory(self, service_type: Type[T], factory: Callable[[], T]) -> None:
        """Register a factory function for lazy service creation.

        Args:
            service_type: The type/interface of the service.
            factory: A callable that creates the service instance.
        """
        self._factories[service_type] = factory
        self.logger.debug(f"Registered factory for: {service_type.__name__}")

    def get(self, service_type: Type[T]) -> T:
        """Get a service instance.

        Args:
            service_type: The type/interface of the service.

        Returns:
            The service instance.

        Raises:
            ServiceNotFoundError: If the service is not registered.
        """
        # Check if we have an instance
        if service_type in self._services:
            return self._services[service_type]

        # Check if we have a factory
        if service_type in self._factories:
            # Create and cache the instance
            instance = self._factories[service_type]()
            self._services[service_type] = instance
            return instance

        raise ServiceNotFoundError(
            f"Service not found: {service_type.__name__}. "
            f"Available services: {list(self._services.keys())}"
        )

    def get_optional(
        self, service_type: Type[T], default: Optional[T] = None
    ) -> Optional[T]:
        """Get a service instance or return a default.

        Args:
            service_type: The type/interface of the service.
            default: Default value if service not found.

        Returns:
            The service instance or default.
        """
        try:
            return self.get(service_type)
        except ServiceNotFoundError:
            return default

    def clear(self) -> None:
        """Clear all registered services (useful for testing)."""
        self._services.clear()
        self._factories.clear()

    def remove(self, service_type: Type) -> None:
        """Remove a specific service.

        Args:
            service_type: The type/interface of the service to remove.
        """
        self._services.pop(service_type, None)
        self._factories.pop(service_type, None)


# Global service locator instance
_service_locator = ServiceLocator()


def get_service(service_type: Type[T]) -> T:
    """Get a service from the global service locator.

    Args:
        service_type: The type/interface of the service.

    Returns:
        The service instance.
    """
    return _service_locator.get(service_type)


def register_service(service_type: Type[T], instance: T) -> None:
    """Register a service in the global service locator.

    Args:
        service_type: The type/interface of the service.
        instance: The service instance.
    """
    _service_locator.register(service_type, instance)


def register_service_factory(service_type: Type[T], factory: Callable[[], T]) -> None:
    """Register a service factory in the global service locator.

    Args:
        service_type: The type/interface of the service.
        factory: A callable that creates the service instance.
    """
    _service_locator.register_factory(service_type, factory)


def inject(service_type: Type[T]) -> Callable:
    """Decorator for injecting services into methods.

    Usage:
        @inject(ConfigManager)
        def my_method(self, config_manager: ConfigManager):
            # config_manager is automatically injected
            pass

    Args:
        service_type: The type of service to inject.

    Returns:
        Decorator function.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Inject the service as a keyword argument
            service_name = service_type.__name__.lower()
            if service_name not in kwargs:
                kwargs[service_name] = get_service(service_type)
            return func(*args, **kwargs)

        return wrapper

    return decorator


class ServiceScope:
    """Context manager for temporary service registration."""

    def __init__(self):
        """Initialize the service scope."""
        self._original_services: Dict[Type, Any] = {}
        self._original_factories: Dict[Type, Callable[[], Any]] = {}

    def __enter__(self):
        """Enter the scope, saving current services."""
        self._original_services = _service_locator._services.copy()
        self._original_factories = _service_locator._factories.copy()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the scope, restoring original services."""
        _service_locator._services = self._original_services
        _service_locator._factories = self._original_factories

    def register(self, service_type: Type[T], instance: T) -> None:
        """Register a service within this scope."""
        _service_locator.register(service_type, instance)

    def register_factory(self, service_type: Type[T], factory: Callable[[], T]) -> None:
        """Register a factory within this scope."""
        _service_locator.register_factory(service_type, factory)


# Initialize default services
def initialize_default_services():
    """Initialize default services for the application."""
    # Register ConfigManager factory
    register_service_factory(ConfigManager, lambda: ConfigManager())


# Call on module import
initialize_default_services()
