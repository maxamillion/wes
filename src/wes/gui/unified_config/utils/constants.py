"""Configuration constants for the unified configuration dialog.

This module provides centralized constants to reduce magic values throughout
the codebase and improve maintainability.
"""

from typing import Final


class ConfigConstants:
    """Configuration constants for the application."""

    # Timeouts (in seconds)
    REQUEST_TIMEOUT_DEFAULT: Final[int] = 30
    REQUEST_TIMEOUT_MIN: Final[int] = 10
    REQUEST_TIMEOUT_MAX: Final[int] = 300
    CONNECTION_TEST_TIMEOUT: Final[int] = 60

    # Retry settings
    RETRY_ATTEMPTS_DEFAULT: Final[int] = 3
    RETRY_ATTEMPTS_MIN: Final[int] = 0
    RETRY_ATTEMPTS_MAX: Final[int] = 10
    RETRY_DELAY_SECONDS: Final[float] = 1.0

    # Validation settings
    VALIDATION_DELAY_MS: Final[int] = 500  # Delay before validation after changes

    # Path constants
    WES_CONFIG_DIR: Final[str] = ".wes"

    # Jira constants
    JIRA_URL_MIN_LENGTH: Final[int] = 8
    JIRA_DEFAULT_JQL: Final[str] = "assignee = currentUser() AND resolved >= -7d"
    JIRA_MAX_RESULTS_DEFAULT: Final[int] = 50
    JIRA_MAX_RESULTS_MIN: Final[int] = 10
    JIRA_MAX_RESULTS_MAX: Final[int] = 200

    # UI Constants
    DIALOG_MIN_WIDTH: Final[int] = 600
    DIALOG_MIN_HEIGHT: Final[int] = 400
    INSTRUCTIONS_MAX_HEIGHT: Final[int] = 150


    # File permissions
    CREDENTIALS_FILE_PERMISSIONS: Final[int] = 0o600

    # Summary settings
    SUMMARY_LENGTH_DEFAULT: Final[int] = 500
    SUMMARY_LENGTH_MIN: Final[int] = 100
    SUMMARY_LENGTH_MAX: Final[int] = 2000

    # Animation durations (ms)
    FADE_ANIMATION_DURATION: Final[int] = 300

    # Security settings
    MIN_PASSWORD_LENGTH: Final[int] = 8
    ENCRYPTION_KEY_ITERATIONS: Final[int] = 100000

    # Cache settings
    CACHE_EXPIRY_SECONDS: Final[int] = 3600  # 1 hour


class URLConstants:
    """URL constants for external services."""

    # Google URLs
    GOOGLE_CLOUD_CONSOLE_CREDENTIALS: Final[str] = (
        "https://console.cloud.google.com/apis/credentials"
    )




class ValidationPatterns:
    """Regular expression patterns for validation."""

    # Email patterns
    EMAIL_PATTERN: Final[str] = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

    # URL patterns
    URL_PATTERN: Final[str] = r"^https?://[a-zA-Z0-9.-]+(:[0-9]+)?(/.*)?$"
    JIRA_URL_PATTERN: Final[str] = r"^https?://[a-zA-Z0-9.-]+(:[0-9]+)?/?$"

    # Token patterns
    API_TOKEN_PATTERN: Final[str] = r"^[A-Za-z0-9_-]{20,}$"

    # File path patterns
    JSON_FILE_PATTERN: Final[str] = r".*\.json$"
