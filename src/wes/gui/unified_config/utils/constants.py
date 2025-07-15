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
    OAUTH_CREDENTIALS_FILE: Final[str] = "google_oauth_credentials.json"

    # Google OAuth constants
    GOOGLE_CLIENT_ID_SUFFIX: Final[str] = ".apps.googleusercontent.com"
    GOOGLE_OAUTH_TIMEOUT_MS: Final[int] = 300000  # 5 minutes
    GOOGLE_OAUTH_CHECK_INTERVAL_MS: Final[int] = 500

    # Jira constants
    JIRA_URL_MIN_LENGTH: Final[int] = 8
    JIRA_DEFAULT_JQL: Final[str] = "assignee = currentUser() AND resolved >= -7d"
    JIRA_MAX_RESULTS_DEFAULT: Final[int] = 50
    JIRA_MAX_RESULTS_MIN: Final[int] = 10
    JIRA_MAX_RESULTS_MAX: Final[int] = 200

    # UI Constants
    DIALOG_MIN_WIDTH: Final[int] = 600
    DIALOG_MIN_HEIGHT: Final[int] = 400
    OAUTH_DIALOG_WIDTH: Final[int] = 600
    OAUTH_DIALOG_HEIGHT: Final[int] = 500
    INSTRUCTIONS_MAX_HEIGHT: Final[int] = 150

    # Port constants
    OAUTH_CALLBACK_PORT_DEFAULT: Final[int] = 8080

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
    GOOGLE_AUTH_URI: Final[str] = "https://accounts.google.com/o/oauth2/auth"
    GOOGLE_TOKEN_URI: Final[str] = "https://oauth2.googleapis.com/token"
    GOOGLE_REVOKE_URI: Final[str] = "https://oauth2.googleapis.com/revoke"

    # OAuth redirect URIs
    OAUTH_REDIRECT_URI_TEMPLATE: Final[str] = "http://localhost:{port}/callback"

    # Documentation URLs
    DOCS_GOOGLE_OAUTH_SETUP: Final[str] = "docs/GOOGLE_OAUTH_SETUP.md"
    DOCS_GOOGLE_OAUTH_FIX: Final[str] = "docs/GOOGLE_OAUTH_FIX.md"


class ServiceScopes:
    """OAuth scopes for various services."""

    # Google scopes
    GOOGLE_DOCS_READ_WRITE: Final[str] = "https://www.googleapis.com/auth/documents"
    GOOGLE_DRIVE_FILE: Final[str] = "https://www.googleapis.com/auth/drive.file"
    GOOGLE_SHEETS_OPTIONAL: Final[str] = "https://www.googleapis.com/auth/spreadsheets"

    # Default Google scopes
    GOOGLE_DEFAULT_SCOPES: Final[list[str]] = [
        GOOGLE_DOCS_READ_WRITE,
        GOOGLE_DRIVE_FILE,
    ]


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
