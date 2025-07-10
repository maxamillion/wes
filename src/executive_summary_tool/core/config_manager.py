"""Configuration management with secure storage and validation."""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta

from ..utils.exceptions import ConfigurationError, ValidationError
from ..utils.validators import InputValidator
from ..utils.logging_config import get_logger
from .security_manager import SecurityManager


@dataclass
class JiraConfig:
    """Jira configuration settings."""
    url: str = ""
    username: str = ""
    api_token: str = ""
    default_project: str = ""
    default_users: list = field(default_factory=list)
    default_query: str = ""
    rate_limit: int = 100
    timeout: int = 30


@dataclass
class GoogleConfig:
    """Google services configuration."""
    service_account_path: str = ""
    oauth_client_id: str = ""
    oauth_client_secret: str = ""
    oauth_refresh_token: str = ""
    docs_folder_id: str = ""
    rate_limit: int = 100
    timeout: int = 30


@dataclass
class AIConfig:
    """AI service configuration."""
    gemini_api_key: str = ""
    model_name: str = "gemini-pro"
    temperature: float = 0.7
    max_tokens: int = 2048
    rate_limit: int = 60
    timeout: int = 60
    custom_prompt: str = ""


@dataclass
class AppConfig:
    """Application configuration."""
    theme: str = "system"
    language: str = "en"
    auto_save: bool = True
    log_level: str = "INFO"
    check_updates: bool = True
    telemetry_enabled: bool = False


@dataclass
class SecurityConfig:
    """Security configuration."""
    encryption_enabled: bool = True
    key_rotation_days: int = 90
    session_timeout_minutes: int = 60
    max_login_attempts: int = 5
    audit_logging: bool = True


@dataclass
class Configuration:
    """Main configuration container."""
    jira: JiraConfig = field(default_factory=JiraConfig)
    google: GoogleConfig = field(default_factory=GoogleConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    app: AppConfig = field(default_factory=AppConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    version: str = "1.0.0"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


class ConfigManager:
    """Manages application configuration with secure storage."""
    
    def __init__(self, config_dir: Optional[Path] = None):
        self.logger = get_logger(__name__)
        self.security_manager = SecurityManager()
        
        # Set configuration directory
        if config_dir:
            self.config_dir = config_dir
        else:
            self.config_dir = Path.home() / ".executive-summary-tool"
        
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / "config.json"
        
        # Initialize configuration
        self._config = Configuration()
        self._load_configuration()
    
    def _load_configuration(self) -> None:
        """Load configuration from file."""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    config_data = json.load(f)
                
                # Validate configuration
                InputValidator.validate_config_dict(config_data)
                
                # Update configuration object
                self._update_config_from_dict(config_data)
                
                self.logger.info(f"Configuration loaded from {self.config_file}")
            else:
                # Create default configuration
                self._save_configuration()
                self.logger.info("Default configuration created")
                
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            raise ConfigurationError(f"Failed to load configuration: {e}")
    
    def _update_config_from_dict(self, config_data: Dict[str, Any]) -> None:
        """Update configuration object from dictionary."""
        try:
            # Update each section
            if 'jira' in config_data:
                jira_data = config_data['jira']
                self._config.jira = JiraConfig(**jira_data)
            
            if 'google' in config_data:
                google_data = config_data['google']
                self._config.google = GoogleConfig(**google_data)
            
            if 'ai' in config_data:
                ai_data = config_data['ai']
                self._config.ai = AIConfig(**ai_data)
            
            if 'app' in config_data:
                app_data = config_data['app']
                self._config.app = AppConfig(**app_data)
            
            if 'security' in config_data:
                security_data = config_data['security']
                self._config.security = SecurityConfig(**security_data)
            
            # Update metadata
            self._config.version = config_data.get('version', self._config.version)
            self._config.created_at = config_data.get('created_at', self._config.created_at)
            self._config.updated_at = datetime.now().isoformat()
            
        except Exception as e:
            raise ConfigurationError(f"Failed to update configuration: {e}")
    
    def _save_configuration(self) -> None:
        """Save configuration to file."""
        try:
            # Update timestamp
            self._config.updated_at = datetime.now().isoformat()
            
            # Convert to dictionary
            config_dict = asdict(self._config)
            
            # Remove sensitive data before saving
            sanitized_config = self._sanitize_config_for_storage(config_dict)
            
            # Save to file
            with open(self.config_file, 'w') as f:
                json.dump(sanitized_config, f, indent=2)
            
            # Set restrictive permissions
            self.config_file.chmod(0o600)
            
            self.logger.info(f"Configuration saved to {self.config_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to save configuration: {e}")
            raise ConfigurationError(f"Failed to save configuration: {e}")
    
    def _sanitize_config_for_storage(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive data from configuration before storage."""
        sanitized = config_dict.copy()
        
        # Remove sensitive fields (they're stored encrypted separately)
        if 'jira' in sanitized:
            if 'api_token' in sanitized['jira']:
                del sanitized['jira']['api_token']
        
        if 'google' in sanitized:
            if 'oauth_client_secret' in sanitized['google']:
                del sanitized['google']['oauth_client_secret']
            if 'oauth_refresh_token' in sanitized['google']:
                del sanitized['google']['oauth_refresh_token']
        
        if 'ai' in sanitized:
            if 'gemini_api_key' in sanitized['ai']:
                del sanitized['ai']['gemini_api_key']
        
        return sanitized
    
    def get_config(self) -> Configuration:
        """Get current configuration."""
        return self._config
    
    def get_jira_config(self) -> JiraConfig:
        """Get Jira configuration."""
        return self._config.jira
    
    def get_google_config(self) -> GoogleConfig:
        """Get Google configuration."""
        return self._config.google
    
    def get_ai_config(self) -> AIConfig:
        """Get AI configuration."""
        return self._config.ai
    
    def get_app_config(self) -> AppConfig:
        """Get application configuration."""
        return self._config.app
    
    def get_security_config(self) -> SecurityConfig:
        """Get security configuration."""
        return self._config.security
    
    def update_jira_config(self, **kwargs) -> None:
        """Update Jira configuration."""
        try:
            # Validate inputs
            if 'url' in kwargs:
                InputValidator.validate_jira_url(kwargs['url'])
            
            if 'default_users' in kwargs:
                InputValidator.validate_user_list(kwargs['default_users'])
            
            if 'default_query' in kwargs:
                InputValidator.validate_jira_query(kwargs['default_query'])
            
            # Update configuration
            for key, value in kwargs.items():
                if hasattr(self._config.jira, key):
                    setattr(self._config.jira, key, value)
            
            self._save_configuration()
            self.logger.info("Jira configuration updated")
            
        except Exception as e:
            self.logger.error(f"Failed to update Jira configuration: {e}")
            raise ConfigurationError(f"Failed to update Jira configuration: {e}")
    
    def update_google_config(self, **kwargs) -> None:
        """Update Google configuration."""
        try:
            # Update configuration
            for key, value in kwargs.items():
                if hasattr(self._config.google, key):
                    setattr(self._config.google, key, value)
            
            self._save_configuration()
            self.logger.info("Google configuration updated")
            
        except Exception as e:
            self.logger.error(f"Failed to update Google configuration: {e}")
            raise ConfigurationError(f"Failed to update Google configuration: {e}")
    
    def update_ai_config(self, **kwargs) -> None:
        """Update AI configuration."""
        try:
            # Validate API key if provided
            if 'gemini_api_key' in kwargs:
                InputValidator.validate_api_key(kwargs['gemini_api_key'])
            
            # Update configuration
            for key, value in kwargs.items():
                if hasattr(self._config.ai, key):
                    setattr(self._config.ai, key, value)
            
            self._save_configuration()
            self.logger.info("AI configuration updated")
            
        except Exception as e:
            self.logger.error(f"Failed to update AI configuration: {e}")
            raise ConfigurationError(f"Failed to update AI configuration: {e}")
    
    def store_credential(self, service: str, credential_type: str, value: str) -> None:
        """Store sensitive credential securely."""
        try:
            username = f"{service}_{credential_type}"
            self.security_manager.store_credential(service, username, value)
            self.logger.info(f"Credential stored for {service}:{credential_type}")
            
        except Exception as e:
            self.logger.error(f"Failed to store credential: {e}")
            raise ConfigurationError(f"Failed to store credential: {e}")
    
    def retrieve_credential(self, service: str, credential_type: str) -> Optional[str]:
        """Retrieve sensitive credential securely."""
        try:
            username = f"{service}_{credential_type}"
            return self.security_manager.retrieve_credential(service, username)
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve credential: {e}")
            return None
    
    def delete_credential(self, service: str, credential_type: str) -> None:
        """Delete sensitive credential."""
        try:
            username = f"{service}_{credential_type}"
            self.security_manager.delete_credential(service, username)
            self.logger.info(f"Credential deleted for {service}:{credential_type}")
            
        except Exception as e:
            self.logger.error(f"Failed to delete credential: {e}")
            raise ConfigurationError(f"Failed to delete credential: {e}")
    
    def validate_configuration(self) -> bool:
        """Validate current configuration."""
        try:
            # Validate Jira configuration
            jira_config = self.get_jira_config()
            if jira_config.url:
                InputValidator.validate_jira_url(jira_config.url)
            
            if jira_config.default_users:
                InputValidator.validate_user_list(jira_config.default_users)
            
            if jira_config.default_query:
                InputValidator.validate_jira_query(jira_config.default_query)
            
            # Validate AI configuration
            ai_config = self.get_ai_config()
            if ai_config.gemini_api_key:
                InputValidator.validate_api_key(ai_config.gemini_api_key)
            
            self.logger.info("Configuration validation passed")
            return True
            
        except Exception as e:
            self.logger.error(f"Configuration validation failed: {e}")
            return False
    
    def export_configuration(self, file_path: Path, include_secrets: bool = False) -> None:
        """Export configuration to file."""
        try:
            config_dict = asdict(self._config)
            
            if not include_secrets:
                config_dict = self._sanitize_config_for_storage(config_dict)
            
            with open(file_path, 'w') as f:
                json.dump(config_dict, f, indent=2)
            
            self.logger.info(f"Configuration exported to {file_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to export configuration: {e}")
            raise ConfigurationError(f"Failed to export configuration: {e}")
    
    def import_configuration(self, file_path: Path) -> None:
        """Import configuration from file."""
        try:
            with open(file_path, 'r') as f:
                config_data = json.load(f)
            
            # Validate configuration
            InputValidator.validate_config_dict(config_data)
            
            # Update configuration
            self._update_config_from_dict(config_data)
            self._save_configuration()
            
            self.logger.info(f"Configuration imported from {file_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to import configuration: {e}")
            raise ConfigurationError(f"Failed to import configuration: {e}")
    
    def reset_configuration(self) -> None:
        """Reset configuration to defaults."""
        try:
            self._config = Configuration()
            self._save_configuration()
            self.logger.info("Configuration reset to defaults")
            
        except Exception as e:
            self.logger.error(f"Failed to reset configuration: {e}")
            raise ConfigurationError(f"Failed to reset configuration: {e}")
    
    def is_configured(self) -> bool:
        """Check if application is properly configured."""
        try:
            # Check essential configurations
            jira_config = self.get_jira_config()
            ai_config = self.get_ai_config()
            
            # Need at least Jira URL and AI API key
            has_jira = bool(jira_config.url)
            has_ai = bool(ai_config.gemini_api_key)
            
            return has_jira and has_ai
            
        except Exception:
            return False