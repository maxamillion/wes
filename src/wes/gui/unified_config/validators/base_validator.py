"""Base validator class for configuration validation."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple

from wes.gui.unified_config.types import ServiceType, ValidationResult


class BaseValidator(ABC):
    """Abstract base class for service validators."""

    service_type: ServiceType = None

    @abstractmethod
    def validate_config(self, config: Dict[str, Any]) -> ValidationResult:
        """
        Validate service configuration.

        Args:
            config: Service-specific configuration dictionary

        Returns:
            ValidationResult with validation status and details
        """

    @abstractmethod
    def validate_connection(self, config: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Test connection to the service.

        Args:
            config: Service-specific configuration dictionary

        Returns:
            Tuple of (success, message)
        """

    def validate_field(self, field_name: str, value: Any) -> Tuple[bool, str]:
        """
        Validate a specific field.

        Args:
            field_name: Name of the field to validate
            value: Field value

        Returns:
            Tuple of (is_valid, message)
        """
        # Default implementation - override in subclasses
        if not value:
            return False, f"{field_name} is required"
        return True, "Valid"

    def check_required_fields(
        self, config: Dict[str, Any], required_fields: list[str]
    ) -> Optional[ValidationResult]:
        """
        Check if all required fields are present and non-empty.

        Args:
            config: Configuration dictionary
            required_fields: List of required field names

        Returns:
            ValidationResult if validation fails, None if all fields present
        """
        for field in required_fields:
            if field not in config or not config[field]:
                return ValidationResult(
                    is_valid=False,
                    message=f"{field} is required",
                    service=self.service_type,
                    details={"field": field},
                )
        return None
