"""Input validation utilities for security and data integrity."""

import html
import re
import unicodedata
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from .exceptions import ValidationError


class InputValidator:
    """Secure input validation and sanitization."""

    # Dangerous patterns for JQL injection prevention
    DANGEROUS_JQL_PATTERNS = [
        r";\s*DROP\s+TABLE",
        r";\s*DELETE\s+FROM",
        r";\s*UPDATE\s+SET",
        r"<script",
        r"javascript:",
        r"vbscript:",
        r"onload\s*=",
        r"onerror\s*=",
        r"eval\s*\(",
        r"expression\s*\(",
    ]

    # Valid URL schemes
    VALID_SCHEMES = ["https"]

    @staticmethod
    def validate_url(url: str) -> bool:
        """Validate URL format and security."""
        if not url:
            return False

        try:
            parsed = urlparse(url)

            # Must use HTTPS
            if parsed.scheme not in InputValidator.VALID_SCHEMES:
                raise ValidationError(f"Only HTTPS URLs allowed, got: {parsed.scheme}")

            # Must have hostname
            if not parsed.hostname:
                raise ValidationError("URL must have a valid hostname")

            # Basic domain validation
            if not re.match(
                r"^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*$",
                parsed.hostname,
            ):
                raise ValidationError("Invalid hostname format")

            return True

        except Exception as e:
            raise ValidationError(f"Invalid URL format: {e}")

    @staticmethod
    def validate_jira_url(url: str) -> bool:
        """Validate Jira URL specifically."""
        if not InputValidator.validate_url(url):
            return False

        # Additional Jira-specific validation
        parsed = urlparse(url)

        # Common Jira URL patterns
        jira_patterns = [
            r"\.atlassian\.net$",
            r"\.atlassian\.com$",
            r"jira\.",
            r"-jira\.",
        ]

        # Check if it looks like a Jira URL
        hostname = parsed.hostname.lower()
        is_jira_url = any(re.search(pattern, hostname) for pattern in jira_patterns)

        if not is_jira_url:
            # Allow any HTTPS URL as Jira might be self-hosted
            pass

        return True

    @staticmethod
    def validate_jira_query(query: str) -> bool:
        """Validate Jira JQL query for security."""
        if not query:
            return False

        # Check for dangerous patterns
        for pattern in InputValidator.DANGEROUS_JQL_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                raise ValidationError(f"Query contains dangerous pattern: {pattern}")

        # Basic JQL syntax validation
        # Allow common JQL operators and functions
        allowed_pattern = r'^[a-zA-Z0-9\s\-_=<>!(),"\'.\+\*\[\]]+$'
        if not re.match(allowed_pattern, query):
            raise ValidationError("Query contains invalid characters")

        return True

    @staticmethod
    def validate_user_list(users: List[str]) -> bool:
        """Validate list of user identifiers."""
        if not users:
            return False

        for user in users:
            if not InputValidator.validate_user_identifier(user):
                raise ValidationError(f"Invalid user identifier: {user}")

        return True

    @staticmethod
    def validate_user_identifier(user: str) -> bool:
        """Validate individual user identifier."""
        if not user:
            return False

        # Minimum length check (except for UUIDs which have specific format)
        if len(user) < 3 and not re.match(
            r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
            user,
        ):
            raise ValidationError("User identifier too short (minimum 3 characters)")

        # Allow common user identifier formats
        # - Email addresses
        # - Usernames (alphanumeric, hyphens, underscores, dots)
        # - UUIDs
        # - Red Hat style usernames (e.g., rhn-support-admiller)
        patterns = [
            r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",  # Email
            r"^[a-zA-Z0-9._@-]+$",  # Username (includes Red Hat format with hyphens)
            r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",  # UUID
        ]

        for pattern in patterns:
            if re.match(pattern, user):
                return True

        raise ValidationError(f"Invalid user identifier format: {user}")

    @staticmethod
    def validate_date_range(start_date: str, end_date: str) -> bool:
        """Validate date range format."""
        from datetime import datetime

        try:
            # Parse dates
            start = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))

            # End must be after start
            if end <= start:
                raise ValidationError("End date must be after start date")

            # Reasonable date range (not more than 1 year)
            if (end - start).days > 365:
                raise ValidationError("Date range cannot exceed 1 year")

            return True

        except ValueError as e:
            raise ValidationError(f"Invalid date format: {e}")

    @staticmethod
    def sanitize_text(text: str) -> str:
        """Sanitize text input for security."""
        if not text:
            return ""

        # Remove null bytes
        text = text.replace("\x00", "")

        # HTML escape
        text = html.escape(text)

        # Normalize unicode
        text = unicodedata.normalize("NFKC", text)

        # Remove control characters except newlines and tabs
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)

        return text.strip()

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename for security."""
        if not filename:
            return ""

        # Remove path separators and dangerous characters
        filename = re.sub(r'[<>:"/\\|?*]', "", filename)

        # Remove control characters
        filename = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", filename)

        # Normalize unicode
        filename = unicodedata.normalize("NFKC", filename)

        # Truncate to reasonable length
        filename = filename[:255]

        return filename.strip()

    @staticmethod
    def validate_config_dict(config: Dict[str, Any]) -> bool:
        """Validate configuration dictionary."""
        if not isinstance(config, dict):
            raise ValidationError("Configuration must be a dictionary")

        # Check for required keys
        required_keys = ["jira", "ai"]
        for key in required_keys:
            if key not in config:
                raise ValidationError(f"Missing required configuration key: {key}")

        # Validate Jira config
        jira_config = config.get("jira", {})
        if not isinstance(jira_config, dict):
            raise ValidationError("Jira configuration must be a dictionary")

        if "url" in jira_config:
            InputValidator.validate_jira_url(jira_config["url"])

        # Validate AI config
        ai_config = config.get("ai", {})
        if not isinstance(ai_config, dict):
            raise ValidationError("AI configuration must be a dictionary")

        return True

    @staticmethod
    def validate_api_key(api_key: str) -> bool:
        """Validate API key format."""
        if not api_key:
            raise ValidationError("API key cannot be empty")

        # Basic format validation
        if len(api_key) < 10:
            raise ValidationError("API key too short")

        if len(api_key) > 500:
            raise ValidationError("API key too long")

        # Check for basic format (alphanumeric, hyphens, underscores)
        if not re.match(r"^[a-zA-Z0-9_-]+$", api_key):
            raise ValidationError("API key contains invalid characters")

        return True
