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

    pass


class AuthenticationError(WesError):
    """Authentication failures."""

    pass


class AuthorizationError(WesError):
    """Authorization failures."""

    pass


class ValidationError(WesError):
    """Input validation errors."""

    pass


class ConfigurationError(WesError):
    """Configuration-related errors."""

    pass


class IntegrationError(WesError):
    """External integration errors."""

    pass


class JiraIntegrationError(IntegrationError):
    """Jira-specific integration errors."""

    pass


class GeminiIntegrationError(IntegrationError):
    """Google Gemini AI integration errors."""

    pass


class GoogleDocsIntegrationError(IntegrationError):
    """Google Docs integration errors."""

    pass


class RateLimitError(IntegrationError):
    """API rate limiting errors."""

    pass


class NetworkError(WesError):
    """Network connectivity errors."""

    pass
