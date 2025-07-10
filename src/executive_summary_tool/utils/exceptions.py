"""Custom exceptions for the Executive Summary Tool."""

from typing import Any, Dict, Optional


class ExecutiveSummaryToolError(Exception):
    """Base exception for Executive Summary Tool."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class SecurityError(ExecutiveSummaryToolError):
    """Security-related errors."""
    pass


class AuthenticationError(ExecutiveSummaryToolError):
    """Authentication failures."""
    pass


class AuthorizationError(ExecutiveSummaryToolError):
    """Authorization failures."""
    pass


class ValidationError(ExecutiveSummaryToolError):
    """Input validation errors."""
    pass


class ConfigurationError(ExecutiveSummaryToolError):
    """Configuration-related errors."""
    pass


class IntegrationError(ExecutiveSummaryToolError):
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


class NetworkError(ExecutiveSummaryToolError):
    """Network connectivity errors."""
    pass