"""Configuration state detection utilities."""

from typing import Any, Dict, Optional, Tuple

from wes.gui.unified_config.types import ConfigState, ServiceType, ValidationResult


class ConfigDetector:
    """Analyzes configuration state and completeness."""

    def __init__(self):
        self.required_fields = {
            ServiceType.JIRA: ["url", "username", "api_token"],
            ServiceType.GOOGLE: [],  # Google uses OAuth or service account, checked separately
            ServiceType.GEMINI: ["api_key"],
        }

    def detect_state(self, config: Dict[str, Any]) -> ConfigState:
        """
        Detect overall configuration state.

        Args:
            config: Configuration dictionary

        Returns:
            Current configuration state
        """
        if not config or all(not v for v in config.values()):
            return ConfigState.EMPTY

        # Check each service
        service_states = {
            ServiceType.JIRA: self._check_service_config(
                config.get("jira", {}), ServiceType.JIRA
            ),
            ServiceType.GOOGLE: self._check_service_config(
                config.get("google", {}), ServiceType.GOOGLE
            ),
            ServiceType.GEMINI: self._check_service_config(
                config.get("gemini", {}), ServiceType.GEMINI
            ),
        }

        # Determine overall state
        complete_count = sum(1 for state in service_states.values() if state)

        if complete_count == len(service_states):
            return ConfigState.COMPLETE
        elif complete_count > 0:
            return ConfigState.INCOMPLETE
        else:
            return ConfigState.INVALID

    def _check_service_config(
        self, service_config: Dict[str, Any], service_type: ServiceType
    ) -> bool:
        """
        Check if a service configuration is complete.

        Args:
            service_config: Service-specific configuration
            service_type: Type of service to check

        Returns:
            True if configuration is complete
        """
        if not service_config:
            return False

        # Special handling for Google service which can use OAuth or service account
        if service_type == ServiceType.GOOGLE:
            # Check if OAuth credentials exist (client ID and either refresh token or service account)
            has_oauth = bool(service_config.get("oauth_client_id"))
            has_service_account = bool(service_config.get("service_account_path"))
            return has_oauth or has_service_account

        # Special handling for Gemini service
        if service_type == ServiceType.GEMINI:
            # Check for either api_key or gemini_api_key (handles both field names)
            has_api_key = bool(service_config.get("api_key")) or bool(
                service_config.get("gemini_api_key")
            )
            return has_api_key

        required = self.required_fields.get(service_type, [])
        return all(
            field in service_config and service_config[field] for field in required
        )

    def get_missing_services(self, config: Dict[str, Any]) -> list[ServiceType]:
        """
        Get list of services with incomplete configuration.

        Args:
            config: Configuration dictionary

        Returns:
            List of service types that need configuration
        """
        missing = []

        for service_type in ServiceType:
            service_config = config.get(service_type.value, {})
            if not self._check_service_config(service_config, service_type):
                missing.append(service_type)

        return missing

    def get_service_status(
        self, config: Dict[str, Any]
    ) -> Dict[ServiceType, ValidationResult]:
        """
        Get detailed status for each service.

        Args:
            config: Configuration dictionary

        Returns:
            Dictionary mapping service types to their validation results
        """
        results = {}

        for service_type in ServiceType:
            service_config = config.get(service_type.value, {})
            is_complete = self._check_service_config(service_config, service_type)

            if not service_config:
                message = "Not configured"
            elif is_complete:
                message = "Configuration complete"
            else:
                missing = self._get_missing_fields(service_config, service_type)
                message = f"Missing: {', '.join(missing)}"

            results[service_type] = ValidationResult(
                is_valid=is_complete,
                message=message,
                service=service_type,
                details={"configured": bool(service_config)},
            )

        return results

    def _get_missing_fields(
        self, service_config: Dict[str, Any], service_type: ServiceType
    ) -> list[str]:
        """Get list of missing required fields for a service."""
        # Special handling for Google service
        if service_type == ServiceType.GOOGLE:
            # Check what's actually missing
            has_oauth = bool(service_config.get("oauth_client_id"))
            has_service_account = bool(service_config.get("service_account_path"))

            if not has_oauth and not has_service_account:
                return ["OAuth or Service Account credentials"]
            return []

        # Special handling for Gemini service
        if service_type == ServiceType.GEMINI:
            # Check for either api_key or gemini_api_key
            has_api_key = bool(service_config.get("api_key")) or bool(
                service_config.get("gemini_api_key")
            )

            if not has_api_key:
                return ["API key"]
            return []

        required = self.required_fields.get(service_type, [])
        return [
            field
            for field in required
            if field not in service_config or not service_config[field]
        ]

    def suggest_next_action(
        self, config: Dict[str, Any]
    ) -> Tuple[str, Optional[ServiceType]]:
        """
        Suggest the next configuration action based on current state.

        Args:
            config: Configuration dictionary

        Returns:
            Tuple of (action_message, service_to_configure)
        """
        state = self.detect_state(config)

        if state == ConfigState.EMPTY:
            return "Let's start by configuring Jira", ServiceType.JIRA

        missing = self.get_missing_services(config)
        if missing:
            service = missing[0]  # Configure in order
            return f"Configure {service.value.title()} to continue", service

        return "All services configured! You're ready to go.", None
