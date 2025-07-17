"""Custom exceptions for the Executive Summary Tool."""

from typing import Any, Dict, Optional


class WesError(Exception):
    """Base exception for Executive Summary Tool."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class SecurityError(WesError):
    """Security-related errors."""


class AuthenticationError(WesError):
    """Authentication failures."""


class AuthorizationError(WesError):
    """Authorization failures."""


class ValidationError(WesError):
    """Input validation errors."""


class ConfigurationError(WesError):
    """Configuration-related errors."""


class IntegrationError(WesError):
    """External integration errors."""


class JiraIntegrationError(IntegrationError):
    """Jira-specific integration errors."""


class GeminiIntegrationError(IntegrationError):
    """Google Gemini AI integration errors."""


class GoogleDocsIntegrationError(IntegrationError):
    """Google Docs integration errors."""


class RateLimitError(IntegrationError):
    """API rate limiting errors."""


class NetworkError(WesError):
    """Network connectivity errors."""


class ConnectionError(WesError):
    """Connection-related errors."""


class ExportError(WesError):
    """Export-related errors."""
