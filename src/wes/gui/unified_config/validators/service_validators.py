"""Service-specific validators for configuration validation."""

import os
import re
from typing import Any, Dict, Tuple
from urllib.parse import urlparse

from wes.gui.unified_config.types import JiraType, ServiceType, ValidationResult
from wes.gui.unified_config.validators.base_validator import BaseValidator


class JiraValidator(BaseValidator):
    """Validator for Jira configuration."""

    service_type = ServiceType.JIRA

    def validate_config(self, config: Dict[str, Any]) -> ValidationResult:
        """Validate Jira configuration."""
        # Get Jira type
        jira_type = JiraType(config.get("type", "cloud"))

        # Define required fields (all Jira types require API tokens)
        required_fields = ["url", "username", "api_token"]

        # Check required fields
        result = self.check_required_fields(config, required_fields)
        if result:
            return result

        # Validate URL format
        url = config["url"]
        if not self._is_valid_url(url):
            return ValidationResult(
                is_valid=False,
                message="Invalid URL format",
                service=ServiceType.JIRA,
                details={"field": "url", "value": url}
            )

        # Validate username format for cloud
        if jira_type == JiraType.CLOUD:
            username = config["username"]
            if "@" not in username:
                return ValidationResult(
                    is_valid=False,
                    message="Cloud Jira requires email address for username",
                    service=ServiceType.JIRA,
                    details={"field": "username", "value": username}
                )

        # All validations passed
        return ValidationResult(
            is_valid=True,
            message="Jira configuration is valid",
            service=ServiceType.JIRA,
            details={"validated_fields": ["url", "username", "api_token"]}
        )

    def validate_connection(self, config: Dict[str, Any]) -> Tuple[bool, str]:
        """Test Jira connection."""
        try:
            # Import here to avoid circular imports
            from wes.integrations.jira_client import JiraClient

            # Create client based on type
            jira_type = JiraType(config.get("type", "cloud"))

            if jira_type == JiraType.REDHAT:
                # Red Hat Jira uses different client
                try:
                    from wes.integrations.redhat_jira_client import RedHatJiraClient

                    client = RedHatJiraClient(
                        url=config["url"],
                        username=config["username"],
                        api_token=config["api_token"],
                    )
                except ImportError:
                    return False, "Red Hat Jira support not installed"
            else:
                client = JiraClient(
                    server_url=config["url"],
                    username=config["username"],
                    api_token=config.get("api_token", ""),
                )

            # Test connection
            client.test_connection()
            return True, "Successfully connected to Jira"

        except Exception as e:
            return False, f"Connection failed: {str(e)}"

    def validate_field(self, field_name: str, value: Any) -> Tuple[bool, str]:
        """Validate specific Jira field."""
        if field_name == "url":
            return self._validate_url(value)
        elif field_name == "username":
            return self._validate_username(value)
        elif field_name == "api_token":
            return self._validate_api_token(value)
        else:
            return super().validate_field(field_name, value)

    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid."""
        try:
            result = urlparse(url)
            return all([result.scheme in ["http", "https"], result.netloc])
        except Exception:
            return False

    def _validate_url(self, url: str) -> Tuple[bool, str]:
        """Validate Jira URL."""
        if not url:
            return False, "URL is required"

        if not self._is_valid_url(url):
            return False, "Must be a valid URL starting with http:// or https://"

        # Check for common Jira patterns
        if "atlassian.net" in url:
            return True, "Atlassian Cloud URL detected"
        elif "jira" in url.lower():
            return True, "Valid Jira URL"

        return True, "URL format is valid"

    def _validate_username(self, username: str) -> Tuple[bool, str]:
        """Validate username."""
        if not username:
            return False, "Username is required"

        # Basic length validation
        if len(username) < 3:
            return False, "Username too short"

        # Allow alphanumeric, hyphens, underscores, dots, and @ symbols
        # This supports various formats including Red Hat usernames like rhn-support-admiller
        import re

        if not re.match(r"^[a-zA-Z0-9._@-]+$", username):
            return False, "Username contains invalid characters"

        return True, "Username is valid"

    def _validate_api_token(self, token: str) -> Tuple[bool, str]:
        """Validate API token."""
        if not token:
            return False, "API token is required"

        if len(token) < 20:
            return False, "API token appears too short"

        return True, "Token format is valid"


class GeminiValidator(BaseValidator):
    """Validator for Gemini AI configuration."""

    service_type = ServiceType.GEMINI

    def validate_config(self, config: Dict[str, Any]) -> ValidationResult:
        """Validate Gemini configuration."""
        # Check required fields
        result = self.check_required_fields(config, ["api_key"])
        if result:
            return result

        # Validate API key format
        api_key = config["api_key"]
        is_valid, message = self._validate_api_key(api_key)
        if not is_valid:
            return ValidationResult(
                is_valid=False,
                message=message,
                service=ServiceType.GEMINI,
                details={"field": "api_key", "value": "***"}
            )

        # Validate model selection
        model = config.get("model", "")
        if not model:
            return ValidationResult(
                is_valid=False,
                message="Model selection is required",
                service=ServiceType.GEMINI,
                details={"field": "model", "value": model}
            )

        # Validate model name
        valid_models = ["gemini-2.5-pro", "gemini-2.5-flash"]
        if model not in valid_models:
            return ValidationResult(
                is_valid=False,
                message=f"Invalid model: {model}. Must be one of {valid_models}",
                service=ServiceType.GEMINI,
                details={"field": "model", "value": model, "valid_models": valid_models}
            )

        # Validate temperature
        temp = config.get("temperature", 0.7)
        if not 0 <= temp <= 1:
            return ValidationResult(
                is_valid=False,
                message="Temperature must be between 0 and 1",
                service=ServiceType.GEMINI,
                details={"field": "temperature", "value": temp}
            )

        return ValidationResult(
            is_valid=True,
            message="Gemini configuration is valid",
            service=ServiceType.GEMINI,
            details={"validated_fields": ["api_key", "model", "temperature"]}
        )

    def validate_connection(self, config: Dict[str, Any]) -> Tuple[bool, str]:
        """Test Gemini AI connection."""
        try:
            # Import here to avoid circular imports
            from wes.integrations.gemini_client import GeminiClient

            # Create client
            client = GeminiClient(
                api_key=config["api_key"], model=config.get("model", "gemini-2.5-pro")
            )

            # Test connection with a simple prompt
            response = client.test_connection()
            return True, "Successfully connected to Gemini AI"

        except Exception as e:
            return False, f"Connection failed: {str(e)}"

    def _validate_api_key(self, api_key: str) -> Tuple[bool, str]:
        """Validate Gemini API key format."""
        if not api_key:
            return False, "API key is required"

        # Gemini API keys typically start with 'AIza'
        if not api_key.startswith("AIza"):
            return False, "Invalid API key format (should start with 'AIza')"

        # Check for valid characters first
        if not re.match(r"^[A-Za-z0-9\-_]+$", api_key):
            return False, "API key contains invalid characters"

        # Check length
        if len(api_key) < 30:
            return False, "API key appears too short"

        return True, "API key format is valid"


# Validator registry
VALIDATORS = {
    ServiceType.JIRA: JiraValidator(),
    ServiceType.GEMINI: GeminiValidator(),
}


def get_validator(service_type: ServiceType) -> BaseValidator:
    """Get validator for a specific service type."""
    return VALIDATORS.get(service_type)
