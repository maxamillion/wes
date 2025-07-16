"""Factory for creating integration service clients."""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Protocol, Type

from ..core.config_manager import ConfigManager
from ..integrations.base_client import BaseIntegrationClient
from ..integrations.gemini_client import GeminiClient
from ..integrations.jira_client import JiraClient
from ..integrations.redhat_jira_client import RedHatJiraClient, is_redhat_jira
from ..utils.exceptions import ConfigurationError
from ..utils.logging_config import get_logger


class ServiceClientProtocol(Protocol):
    """Protocol defining the interface for service clients."""

    async def validate_connection(self) -> bool:
        """Validate connection to the service."""
        ...

    async def close(self) -> None:
        """Close the client connection."""
        ...


class ServiceFactory:
    """Factory for creating and managing integration service clients."""

    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.logger = get_logger(__name__)
        self._clients: Dict[str, BaseIntegrationClient] = {}
        self._client_classes: Dict[str, Type[BaseIntegrationClient]] = {
            "jira": JiraClient,
            "redhat_jira": RedHatJiraClient,
            "gemini": GeminiClient,
        }

    def register_client_class(
        self, service_name: str, client_class: Type[BaseIntegrationClient]
    ) -> None:
        """Register a new client class for a service."""
        self._client_classes[service_name] = client_class
        self.logger.info(f"Registered client class for service: {service_name}")

    async def create_jira_client(self) -> JiraClient:
        """Create and configure Jira client."""
        if "jira" in self._clients:
            return self._clients["jira"]

        # Get configuration
        jira_config = self.config_manager.get_jira_config()
        api_token = self.config_manager.retrieve_credential("jira", "api_token")

        if not api_token:
            raise ConfigurationError("Jira API token not configured")

        # Check if it's Red Hat Jira
        if is_redhat_jira(jira_config.url):
            client = RedHatJiraClient(
                url=jira_config.url,
                username=jira_config.username,
                api_token=api_token,
                rate_limit=jira_config.rate_limit,
                timeout=jira_config.timeout,
            )
            self._clients["redhat_jira"] = client
        else:
            client = JiraClient(
                url=jira_config.url,
                username=jira_config.username,
                api_token=api_token,
                rate_limit=jira_config.rate_limit,
                timeout=jira_config.timeout,
            )
            self._clients["jira"] = client

        # Validate connection
        try:
            await client.validate_connection()
            self.logger.info(f"Successfully created Jira client for {jira_config.url}")
        except Exception as e:
            self.logger.error(f"Failed to validate Jira connection: {e}")
            raise

        return client

    async def create_gemini_client(self) -> GeminiClient:
        """Create and configure Gemini client."""
        if "gemini" in self._clients:
            return self._clients["gemini"]

        # Get configuration
        ai_config = self.config_manager.get_ai_config()
        api_key = self.config_manager.retrieve_credential("ai", "gemini_api_key")

        if not api_key:
            raise ConfigurationError("Gemini API key not configured")

        client = GeminiClient(
            api_key=api_key,
            model_name=ai_config.model_name,
            rate_limit=ai_config.rate_limit,
            timeout=ai_config.timeout,
        )

        # Validate connection
        try:
            is_valid = await client.validate_api_key()
            if not is_valid:
                raise ConfigurationError("Invalid Gemini API key")
            self.logger.info("Successfully created Gemini client")
        except Exception as e:
            self.logger.error(f"Failed to validate Gemini connection: {e}")
            raise

        self._clients["gemini"] = client
        return client

    async def get_client(self, service_name: str) -> BaseIntegrationClient:
        """Get or create a client for the specified service."""
        # Check if client already exists
        if service_name in self._clients:
            return self._clients[service_name]

        # Create client based on service name
        if service_name == "jira":
            return await self.create_jira_client()
        elif service_name == "gemini":
            return await self.create_gemini_client()
        else:
            raise ValueError(f"Unknown service: {service_name}")

    async def close_all(self) -> None:
        """Close all active clients."""
        close_tasks = []

        for service_name, client in self._clients.items():
            self.logger.info(f"Closing {service_name} client")
            close_tasks.append(client.close())

        if close_tasks:
            await asyncio.gather(*close_tasks, return_exceptions=True)

        self._clients.clear()
        self.logger.info("All clients closed")

    async def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """Perform health check on all configured services."""
        results = {}

        # Check Jira
        try:
            jira_client = await self.get_client("jira")
            results["jira"] = await jira_client.health_check()
        except Exception as e:
            results["jira"] = {
                "healthy": False,
                "error": str(e),
            }

        # Check Gemini
        try:
            gemini_client = await self.get_client("gemini")
            results["gemini"] = await gemini_client.health_check()
        except Exception as e:
            results["gemini"] = {
                "healthy": False,
                "error": str(e),
            }

        return results

    def get_active_clients(self) -> Dict[str, BaseIntegrationClient]:
        """Get all active clients."""
        return self._clients.copy()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        _ = exc_type, exc_val, exc_tb  # Unused but required by protocol
        await self.close_all()


class ServiceRegistry:
    """Registry for service client implementations."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._registry = {}
        return cls._instance

    def register(self, service_type: str, client_class: Type[BaseIntegrationClient]):
        """Register a client implementation for a service type."""
        self._registry[service_type] = client_class

    def get(self, service_type: str) -> Optional[Type[BaseIntegrationClient]]:
        """Get the client class for a service type."""
        return self._registry.get(service_type)

    def list_services(self) -> list[str]:
        """List all registered service types."""
        return list(self._registry.keys())


# Global registry instance
service_registry = ServiceRegistry()

# Register default implementations
service_registry.register("jira", JiraClient)
service_registry.register("redhat_jira", RedHatJiraClient)
service_registry.register("gemini", GeminiClient)
