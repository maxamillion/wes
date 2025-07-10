"""Credential health monitoring and automatic maintenance."""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from pathlib import Path
import json

from PySide6.QtCore import QObject, QTimer, Signal

from ..utils.logging_config import get_logger, get_security_logger
from ..utils.exceptions import SecurityError, ConfigurationError
from .config_manager import ConfigManager
from ..gui.credential_validators import CredentialValidator, CredentialHealthMonitor


@dataclass
class CredentialStatus:
    """Status information for a credential."""

    service: str
    credential_type: str
    healthy: bool
    last_checked: datetime
    last_success: Optional[datetime]
    error_count: int
    last_error: Optional[str]
    expires_at: Optional[datetime]
    auto_refresh_enabled: bool
    next_check: datetime


@dataclass
class MonitoringConfig:
    """Configuration for credential monitoring."""

    check_interval_minutes: int = 60
    health_check_timeout: int = 30
    max_consecutive_failures: int = 3
    auto_refresh_enabled: bool = True
    notification_enabled: bool = True
    expiration_warning_days: int = 7


class CredentialMonitor(QObject):
    """Monitor credential health and handle automatic maintenance."""

    # Signals for credential status changes
    credential_status_changed = Signal(str, str, bool)  # service, type, healthy
    credential_expiring = Signal(str, str, int)  # service, type, days_until_expiry
    credential_failed = Signal(str, str, str)  # service, type, error
    credentials_refreshed = Signal(str, str)  # service, type

    def __init__(
        self,
        config_manager: ConfigManager,
        monitoring_config: Optional[MonitoringConfig] = None,
    ):
        super().__init__()

        self.config_manager = config_manager
        self.monitoring_config = monitoring_config or MonitoringConfig()

        self.logger = get_logger(__name__)
        self.security_logger = get_security_logger()

        self.validator = CredentialValidator()
        self.health_monitor = CredentialHealthMonitor()

        # Credential status tracking
        self.credential_statuses: Dict[str, CredentialStatus] = {}
        self.monitoring_active = False

        # Setup monitoring timer
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self.check_all_credentials)

        # Load existing status
        self._load_status_from_disk()

        # Setup auto-refresh handlers
        self.refresh_handlers = {
            "google": self._refresh_google_credentials,
            "jira": self._refresh_jira_credentials,
            "gemini": self._refresh_gemini_credentials,
        }

    def start_monitoring(self):
        """Start credential monitoring."""
        if self.monitoring_active:
            return

        self.monitoring_active = True

        # Start periodic checks
        interval_ms = self.monitoring_config.check_interval_minutes * 60 * 1000
        self.monitor_timer.start(interval_ms)

        # Perform initial check
        asyncio.create_task(self.check_all_credentials())

        self.logger.info(
            f"Credential monitoring started (interval: {self.monitoring_config.check_interval_minutes}m)"
        )

        self.security_logger.log_security_event(
            "credential_monitoring_started",
            severity="INFO",
            interval_minutes=self.monitoring_config.check_interval_minutes,
        )

    def stop_monitoring(self):
        """Stop credential monitoring."""
        if not self.monitoring_active:
            return

        self.monitoring_active = False
        self.monitor_timer.stop()

        # Save current status
        self._save_status_to_disk()

        self.logger.info("Credential monitoring stopped")

        self.security_logger.log_security_event(
            "credential_monitoring_stopped", severity="INFO"
        )

    async def check_all_credentials(self):
        """Check all configured credentials."""
        if not self.monitoring_active:
            return

        credentials_to_check = self._get_configured_credentials()

        for service, cred_type in credentials_to_check:
            try:
                await self._check_credential(service, cred_type)
            except Exception as e:
                self.logger.error(f"Error checking {service}:{cred_type}: {e}")

        # Save status after checks
        self._save_status_to_disk()

    async def _check_credential(self, service: str, credential_type: str):
        """Check a specific credential."""
        status_key = f"{service}:{credential_type}"

        # Get or create status
        if status_key not in self.credential_statuses:
            self.credential_statuses[status_key] = CredentialStatus(
                service=service,
                credential_type=credential_type,
                healthy=False,
                last_checked=datetime.now(),
                last_success=None,
                error_count=0,
                last_error=None,
                expires_at=None,
                auto_refresh_enabled=self.monitoring_config.auto_refresh_enabled,
                next_check=datetime.now()
                + timedelta(minutes=self.monitoring_config.check_interval_minutes),
            )

        status = self.credential_statuses[status_key]
        previous_health = status.healthy

        try:
            # Get credentials from config manager
            credentials = self._get_credentials_for_service(service)

            if not credentials:
                raise Exception("No credentials found")

            # Perform health check
            health_result = await self._perform_health_check(service, credentials)

            # Update status
            status.last_checked = datetime.now()
            status.healthy = health_result.get("healthy", False)

            if status.healthy:
                status.last_success = datetime.now()
                status.error_count = 0
                status.last_error = None
            else:
                status.error_count += 1
                status.last_error = health_result.get("error", "Unknown error")

            # Check for expiration
            expires_at = health_result.get("expires_at")
            if expires_at:
                status.expires_at = expires_at
                days_until_expiry = (expires_at - datetime.now()).days

                if days_until_expiry <= self.monitoring_config.expiration_warning_days:
                    self.credential_expiring.emit(
                        service, credential_type, days_until_expiry
                    )

                    # Attempt auto-refresh if enabled
                    if status.auto_refresh_enabled and days_until_expiry <= 1:
                        await self._attempt_auto_refresh(service, credential_type)

            # Emit status change signal if health changed
            if previous_health != status.healthy:
                self.credential_status_changed.emit(
                    service, credential_type, status.healthy
                )

            # Handle consecutive failures
            if status.error_count >= self.monitoring_config.max_consecutive_failures:
                self.credential_failed.emit(
                    service,
                    credential_type,
                    status.last_error or "Multiple consecutive failures",
                )

            # Schedule next check
            status.next_check = datetime.now() + timedelta(
                minutes=self.monitoring_config.check_interval_minutes
            )

        except Exception as e:
            status.last_checked = datetime.now()
            status.healthy = False
            status.error_count += 1
            status.last_error = str(e)

            self.logger.error(
                f"Credential check failed for {service}:{credential_type}: {e}"
            )

            if previous_health != status.healthy:
                self.credential_status_changed.emit(
                    service, credential_type, status.healthy
                )

    async def _perform_health_check(
        self, service: str, credentials: Dict[str, str]
    ) -> Dict[str, Any]:
        """Perform health check for specific service."""
        try:
            if service == "jira":
                success, message = self.validator.validate_jira_credentials(
                    credentials.get("url", ""),
                    credentials.get("username", ""),
                    credentials.get("api_token", ""),
                )
                return {"healthy": success, "error": message if not success else None}

            elif service == "google":
                success, message = self.validator.validate_google_credentials(
                    credentials
                )

                # Check token expiration for Google OAuth
                expires_at = None
                if "expires_at" in credentials:
                    try:
                        expires_at = datetime.fromisoformat(credentials["expires_at"])
                    except Exception:
                        pass

                return {
                    "healthy": success,
                    "error": message if not success else None,
                    "expires_at": expires_at,
                }

            elif service == "gemini":
                success, message = self.validator.validate_gemini_credentials(
                    credentials.get("api_key", "")
                )
                return {"healthy": success, "error": message if not success else None}

            else:
                return {"healthy": False, "error": f"Unknown service: {service}"}

        except Exception as e:
            return {"healthy": False, "error": f"Health check failed: {e}"}

    async def _attempt_auto_refresh(self, service: str, credential_type: str):
        """Attempt to automatically refresh credentials."""
        if service in self.refresh_handlers:
            try:
                success = await self.refresh_handlers[service](credential_type)
                if success:
                    self.credentials_refreshed.emit(service, credential_type)

                    self.security_logger.log_security_event(
                        "credential_auto_refreshed",
                        severity="INFO",
                        service=service,
                        credential_type=credential_type,
                    )

                    # Re-check after refresh
                    await self._check_credential(service, credential_type)

            except Exception as e:
                self.logger.error(
                    f"Auto-refresh failed for {service}:{credential_type}: {e}"
                )

    async def _refresh_google_credentials(self, credential_type: str) -> bool:
        """Refresh Google OAuth credentials."""
        try:
            from ..gui.oauth_handler import GoogleOAuthHandler

            # Get current credentials
            current_creds = self._get_credentials_for_service("google")
            if not current_creds:
                return False

            # Attempt refresh
            oauth_handler = GoogleOAuthHandler()
            refreshed_creds = oauth_handler.refresh_credentials(current_creds)

            if refreshed_creds:
                # Store refreshed credentials
                for key, value in refreshed_creds.items():
                    if key in ["client_secret", "refresh_token", "access_token"]:
                        self.config_manager.store_credential("google", key, value)

                return True

            return False

        except Exception as e:
            self.logger.error(f"Failed to refresh Google credentials: {e}")
            return False

    async def _refresh_jira_credentials(self, credential_type: str) -> bool:
        """Refresh Jira credentials (typically not auto-refreshable)."""
        # Jira API tokens don't auto-refresh, but we can validate and suggest renewal
        self.logger.info("Jira API tokens require manual renewal")
        return False

    async def _refresh_gemini_credentials(self, credential_type: str) -> bool:
        """Refresh Gemini credentials (typically not auto-refreshable)."""
        # Gemini API keys don't auto-refresh
        self.logger.info("Gemini API keys require manual renewal")
        return False

    def _get_configured_credentials(self) -> List[tuple[str, str]]:
        """Get list of configured credentials to monitor."""
        credentials = []

        # Check Jira
        jira_config = self.config_manager.get_jira_config()
        if jira_config.url and jira_config.username:
            if self.config_manager.retrieve_credential("jira", "api_token"):
                credentials.append(("jira", "api_token"))

        # Check Google
        google_config = self.config_manager.get_google_config()
        if google_config.oauth_client_id:
            if self.config_manager.retrieve_credential("google", "oauth_refresh_token"):
                credentials.append(("google", "oauth"))

        # Check Gemini
        ai_config = self.config_manager.get_ai_config()
        if self.config_manager.retrieve_credential("ai", "gemini_api_key"):
            credentials.append(("gemini", "api_key"))

        return credentials

    def _get_credentials_for_service(self, service: str) -> Optional[Dict[str, str]]:
        """Get all credentials for a service."""
        try:
            if service == "jira":
                config = self.config_manager.get_jira_config()
                api_token = self.config_manager.retrieve_credential("jira", "api_token")

                if api_token:
                    return {
                        "url": config.url,
                        "username": config.username,
                        "api_token": api_token,
                    }

            elif service == "google":
                config = self.config_manager.get_google_config()
                client_secret = self.config_manager.retrieve_credential(
                    "google", "oauth_client_secret"
                )
                refresh_token = self.config_manager.retrieve_credential(
                    "google", "oauth_refresh_token"
                )
                access_token = self.config_manager.retrieve_credential(
                    "google", "oauth_access_token"
                )

                if client_secret and refresh_token:
                    return {
                        "client_id": config.oauth_client_id,
                        "client_secret": client_secret,
                        "refresh_token": refresh_token,
                        "access_token": access_token,
                        "token_uri": "https://oauth2.googleapis.com/token",
                    }

            elif service == "gemini":
                api_key = self.config_manager.retrieve_credential(
                    "ai", "gemini_api_key"
                )
                if api_key:
                    return {"api_key": api_key}

            return None

        except Exception as e:
            self.logger.error(f"Failed to get credentials for {service}: {e}")
            return None

    def get_credential_status(
        self, service: str, credential_type: str
    ) -> Optional[CredentialStatus]:
        """Get status for a specific credential."""
        status_key = f"{service}:{credential_type}"
        return self.credential_statuses.get(status_key)

    def get_all_statuses(self) -> Dict[str, CredentialStatus]:
        """Get all credential statuses."""
        return self.credential_statuses.copy()

    def get_health_summary(self) -> Dict[str, Any]:
        """Get overall credential health summary."""
        total_credentials = len(self.credential_statuses)
        healthy_credentials = sum(
            1 for status in self.credential_statuses.values() if status.healthy
        )

        expiring_soon = []
        failed_credentials = []

        for status_key, status in self.credential_statuses.items():
            if status.expires_at:
                days_until_expiry = (status.expires_at - datetime.now()).days
                if days_until_expiry <= self.monitoring_config.expiration_warning_days:
                    expiring_soon.append(status_key)

            if not status.healthy:
                failed_credentials.append(status_key)

        return {
            "total_credentials": total_credentials,
            "healthy_credentials": healthy_credentials,
            "health_percentage": (
                (healthy_credentials / total_credentials * 100)
                if total_credentials > 0
                else 0
            ),
            "expiring_soon": expiring_soon,
            "failed_credentials": failed_credentials,
            "last_check": max(
                (status.last_checked for status in self.credential_statuses.values()),
                default=None,
            ),
            "monitoring_active": self.monitoring_active,
        }

    def force_check(self, service: str, credential_type: str):
        """Force immediate check of specific credential."""
        asyncio.create_task(self._check_credential(service, credential_type))

    def force_check_all(self):
        """Force immediate check of all credentials."""
        asyncio.create_task(self.check_all_credentials())

    def update_monitoring_config(self, new_config: MonitoringConfig):
        """Update monitoring configuration."""
        self.monitoring_config = new_config

        # Restart timer with new interval if monitoring is active
        if self.monitoring_active:
            self.monitor_timer.stop()
            interval_ms = self.monitoring_config.check_interval_minutes * 60 * 1000
            self.monitor_timer.start(interval_ms)

        self.logger.info(f"Monitoring configuration updated: {new_config}")

    def _load_status_from_disk(self):
        """Load credential status from disk."""
        try:
            status_file = self.config_manager.config_dir / "credential_status.json"

            if status_file.exists():
                with open(status_file, "r") as f:
                    data = json.load(f)

                for status_key, status_data in data.items():
                    # Convert datetime strings back to datetime objects
                    for date_field in [
                        "last_checked",
                        "last_success",
                        "expires_at",
                        "next_check",
                    ]:
                        if status_data.get(date_field):
                            try:
                                status_data[date_field] = datetime.fromisoformat(
                                    status_data[date_field]
                                )
                            except Exception:
                                status_data[date_field] = None

                    self.credential_statuses[status_key] = CredentialStatus(
                        **status_data
                    )

                self.logger.info(
                    f"Loaded credential status for {len(self.credential_statuses)} credentials"
                )

        except Exception as e:
            self.logger.error(f"Failed to load credential status: {e}")

    def _save_status_to_disk(self):
        """Save credential status to disk."""
        try:
            status_file = self.config_manager.config_dir / "credential_status.json"

            # Convert to serializable format
            serializable_data = {}
            for status_key, status in self.credential_statuses.items():
                status_dict = asdict(status)

                # Convert datetime objects to strings
                for date_field in [
                    "last_checked",
                    "last_success",
                    "expires_at",
                    "next_check",
                ]:
                    if status_dict[date_field]:
                        status_dict[date_field] = status_dict[date_field].isoformat()

                serializable_data[status_key] = status_dict

            with open(status_file, "w") as f:
                json.dump(serializable_data, f, indent=2)

            # Set restrictive permissions
            status_file.chmod(0o600)

        except Exception as e:
            self.logger.error(f"Failed to save credential status: {e}")


class CredentialNotificationManager:
    """Manage notifications for credential events."""

    def __init__(self, monitor: CredentialMonitor):
        self.monitor = monitor
        self.logger = get_logger(__name__)

        # Connect to monitor signals
        self.monitor.credential_status_changed.connect(self.on_status_changed)
        self.monitor.credential_expiring.connect(self.on_credential_expiring)
        self.monitor.credential_failed.connect(self.on_credential_failed)
        self.monitor.credentials_refreshed.connect(self.on_credentials_refreshed)

        # Notification callbacks
        self.notification_callbacks: List[Callable] = []

    def add_notification_callback(self, callback: Callable):
        """Add a notification callback function."""
        self.notification_callbacks.append(callback)

    def remove_notification_callback(self, callback: Callable):
        """Remove a notification callback function."""
        if callback in self.notification_callbacks:
            self.notification_callbacks.remove(callback)

    def on_status_changed(self, service: str, credential_type: str, healthy: bool):
        """Handle credential status change."""
        message = f"Credential {service}:{credential_type} is now {'healthy' if healthy else 'unhealthy'}"
        severity = "info" if healthy else "warning"

        self._send_notification(
            message,
            severity,
            {
                "service": service,
                "credential_type": credential_type,
                "healthy": healthy,
            },
        )

    def on_credential_expiring(
        self, service: str, credential_type: str, days_until_expiry: int
    ):
        """Handle credential expiration warning."""
        message = f"Credential {service}:{credential_type} expires in {days_until_expiry} days"
        severity = "warning" if days_until_expiry > 1 else "error"

        self._send_notification(
            message,
            severity,
            {
                "service": service,
                "credential_type": credential_type,
                "days_until_expiry": days_until_expiry,
            },
        )

    def on_credential_failed(self, service: str, credential_type: str, error: str):
        """Handle credential failure."""
        message = f"Credential {service}:{credential_type} has failed: {error}"

        self._send_notification(
            message,
            "error",
            {"service": service, "credential_type": credential_type, "error": error},
        )

    def on_credentials_refreshed(self, service: str, credential_type: str):
        """Handle successful credential refresh."""
        message = (
            f"Credential {service}:{credential_type} has been automatically refreshed"
        )

        self._send_notification(
            message, "info", {"service": service, "credential_type": credential_type}
        )

    def _send_notification(self, message: str, severity: str, data: Dict[str, Any]):
        """Send notification to all registered callbacks."""
        for callback in self.notification_callbacks:
            try:
                callback(message, severity, data)
            except Exception as e:
                self.logger.error(f"Notification callback failed: {e}")
