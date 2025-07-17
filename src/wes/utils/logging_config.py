"""Secure logging configuration for the Executive Summary Tool."""

import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import structlog


class LogSanitizer:
    """Sanitize sensitive data from log messages."""

    # Patterns for sensitive data
    SENSITIVE_PATTERNS = [
        (r'password["\']?\s*[:=]\s*["\']?([^"\'\\s]+)', "[PASSWORD_REDACTED]"),
        (r'token["\']?\s*[:=]\s*["\']?([^"\'\\s]+)', "[TOKEN_REDACTED]"),
        (r'key["\']?\s*[:=]\s*["\']?([^"\'\\s]+)', "[KEY_REDACTED]"),
        (r'secret["\']?\s*[:=]\s*["\']?([^"\'\\s]+)', "[SECRET_REDACTED]"),
        (r'authorization["\']?\s*[:=]\s*["\']?([^"\'\\s]+)', "[AUTH_REDACTED]"),
        (r"bearer\s+([a-zA-Z0-9_-]+)", "bearer [TOKEN_REDACTED]"),
        (r"basic\s+([a-zA-Z0-9+/=]+)", "basic [CREDENTIALS_REDACTED]"),
        # Email patterns (partially redacted)
        (r"([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", r"\1***@\2"),
        # Credit card patterns
        (r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b", "[CARD_REDACTED]"),
        # API keys (common patterns)
        (r"AIza[0-9A-Za-z\\-_]{35}", "[GOOGLE_API_KEY_REDACTED]"),
        (r"AKIA[0-9A-Z]{16}", "[AWS_ACCESS_KEY_REDACTED]"),
        (
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "[UUID_REDACTED]",
        ),
    ]

    @classmethod
    def sanitize_message(cls, message: str) -> str:
        """Sanitize log message by removing sensitive data."""
        if not message:
            return message

        sanitized = message

        for pattern, replacement in cls.SENSITIVE_PATTERNS:
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)

        return sanitized

    @classmethod
    def sanitize_value(cls, value: Any) -> Any:
        """Sanitize individual value."""
        if isinstance(value, str):
            return cls.sanitize_message(value)
        elif isinstance(value, dict):
            return {k: cls.sanitize_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [cls.sanitize_value(v) for v in value]
        else:
            return value


class SecureFormatter(logging.Formatter):
    """Custom formatter that sanitizes sensitive data."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.sanitizer = LogSanitizer()

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with sanitization."""
        # Sanitize the message
        if hasattr(record, "msg"):
            record.msg = self.sanitizer.sanitize_message(str(record.msg))

        # Sanitize args
        if hasattr(record, "args") and record.args:
            record.args = tuple(
                self.sanitizer.sanitize_value(arg) for arg in record.args
            )

        return super().format(record)


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    enable_console: bool = True,
    enable_structured: bool = True,
    sanitize: bool = True,
) -> None:
    """Setup secure logging configuration."""

    # Clear existing handlers
    logging.getLogger().handlers.clear()

    # Configure log level
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Setup structlog if enabled
    if enable_structured:
        processors = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
        ]

        if sanitize:
            processors.append(
                lambda _, __, event_dict: {
                    k: LogSanitizer.sanitize_value(v) for k, v in event_dict.items()
                }
            )

        processors.append(structlog.processors.JSONRenderer())

        structlog.configure(
            processors=processors,
            wrapper_class=structlog.stdlib.BoundLogger,
            logger_factory=structlog.stdlib.LoggerFactory(),
            context_class=dict,
            cache_logger_on_first_use=True,
        )

    # Setup console handler
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)

        if sanitize:
            console_formatter = SecureFormatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        else:
            console_formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )

        console_handler.setFormatter(console_formatter)
        logging.getLogger().addHandler(console_handler)

    # Setup file handler
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(log_level)

        if sanitize:
            file_formatter = SecureFormatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
            )
        else:
            file_formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
            )

        file_handler.setFormatter(file_formatter)
        logging.getLogger().addHandler(file_handler)

    # Set root logger level
    logging.getLogger().setLevel(log_level)

    # Suppress noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)
    logging.getLogger("googleapiclient").setLevel(logging.WARNING)


class SecurityLogger:
    """Specialized logger for security events."""

    def __init__(self, name: str = "security") -> None:
        self.logger = structlog.get_logger(name)
        self.sanitizer = LogSanitizer()

    def log_security_event(
        self, event_type: str, severity: str = "INFO", **kwargs: Any
    ) -> None:
        """Log security event with sanitization."""
        # Sanitize all values
        sanitized_kwargs = {
            k: self.sanitizer.sanitize_value(v) for k, v in kwargs.items()
        }

        log_method = getattr(self.logger, severity.lower(), self.logger.info)
        log_method("security_event", event_type=event_type, **sanitized_kwargs)

    def log_authentication_attempt(
        self,
        service: str,
        username: Optional[str] = None,
        success: bool = False,
        **kwargs: Any,
    ) -> None:
        """Log authentication attempt."""
        self.log_security_event(
            "authentication_attempt",
            severity="INFO" if success else "WARNING",
            service=service,
            username=username,
            success=success,
            **kwargs,
        )

    def log_api_request(
        self,
        service: str,
        endpoint: str,
        method: str = "GET",
        status_code: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        """Log API request."""
        self.log_security_event(
            "api_request",
            service=service,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            **kwargs,
        )

    def log_configuration_change(
        self, component: str, change_type: str, **kwargs: Any
    ) -> None:
        """Log configuration change."""
        self.log_security_event(
            "configuration_change",
            severity="INFO",
            component=component,
            change_type=change_type,
            **kwargs,
        )

    def log_error(self, error_type: str, error_message: str, **kwargs: Any) -> None:
        """Log error event."""
        self.log_security_event(
            "error_occurred",
            severity="ERROR",
            error_type=error_type,
            error_message=error_message,
            **kwargs,
        )


def get_logger(name: str) -> logging.Logger:
    """Get a configured logger instance."""
    return logging.getLogger(name)


def get_security_logger() -> SecurityLogger:
    """Get security logger instance."""
    return SecurityLogger()
