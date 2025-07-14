"""Type definitions for unified configuration system."""

from enum import Enum, auto
from typing import Any, Dict, List, Optional, TypedDict


class UIMode(Enum):
    """Configuration UI presentation modes."""

    WIZARD = auto()  # First-time setup with guided flow
    GUIDED = auto()  # Incomplete config with highlighted missing items
    DIRECT = auto()  # Full access to all settings in tabbed interface


class ConfigState(Enum):
    """Configuration validation states."""

    EMPTY = auto()  # No configuration exists
    INCOMPLETE = auto()  # Partial configuration
    COMPLETE = auto()  # All required fields present
    INVALID = auto()  # Configuration exists but validation failed


class ServiceType(Enum):
    """Supported service types."""

    JIRA = "jira"
    GOOGLE = "google"
    GEMINI = "gemini"


class JiraType(Enum):
    """Jira instance types."""

    CLOUD = "cloud"
    SERVER = "server"
    REDHAT = "redhat"


class ValidationResult(TypedDict):
    """Validation result structure."""

    is_valid: bool
    message: str
    service: Optional[ServiceType]
    details: Optional[Dict[str, Any]]


class ConnectionTestResult(TypedDict):
    """Connection test result structure."""

    success: bool
    message: str
    details: Dict[str, Any]
    timestamp: float


class ConfigPageInfo(TypedDict):
    """Configuration page metadata."""

    title: str
    icon: Optional[str]
    description: str
    service_type: ServiceType
    required: bool
