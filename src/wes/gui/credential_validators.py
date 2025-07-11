"""Credential validation utilities for testing API connections."""

import asyncio
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse
import requests
from requests.auth import HTTPBasicAuth

import google.generativeai as genai
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from jira import JIRA, JIRAError

from ..utils.logging_config import get_logger, get_security_logger
from ..integrations.redhat_jira_client import RedHatJiraClient, is_redhat_jira
from ..utils.exceptions import (
    ValidationError,
    JiraIntegrationError,
    GoogleDocsIntegrationError,
    GeminiIntegrationError,
    AuthenticationError,
)


class CredentialValidator:
    """Validate credentials for various services."""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.security_logger = get_security_logger()

    def validate_jira_credentials(
        self, url: str, username: str, api_token: str
    ) -> Tuple[bool, str]:
        """Validate Jira credentials."""
        try:
            # Basic validation
            if not all([url, username, api_token]):
                return False, "All fields are required"

            # URL validation
            if not self._validate_url(url):
                return False, "Invalid URL format"

            # Username validation - email required for Atlassian Cloud, flexible for on-premise
            if not self._validate_username(url, username):
                if self._is_atlassian_cloud(url):
                    return (
                        False,
                        "Username must be a valid email address for Jira Cloud",
                    )
                else:
                    return False, "Username is required"

            # API token format validation
            if not self._validate_jira_token(api_token):
                return False, "Invalid API token format"

            # Test connection with appropriate client
            url = url.rstrip("/")

            # Check if this is a Red Hat Jira instance
            if is_redhat_jira(url):
                # Use Red Hat Jira client for Red Hat instances
                rh_jira_client = RedHatJiraClient(
                    url=url,
                    username=username,
                    api_token=api_token,
                    timeout=10,
                    verify_ssl=True,
                )
                current_user = rh_jira_client._client.current_user()
                client_type = "Red Hat Jira"
            else:
                # Use standard JIRA library for other instances
                jira_client = JIRA(
                    server=url,
                    basic_auth=(username, api_token),
                    timeout=10,
                    options={"verify": True, "check_update": False},
                )
                current_user = jira_client.current_user()
                client_type = "Jira"

            self.security_logger.log_security_event(
                "jira_credential_validation_success",
                severity="INFO",
                url=url,
                username=username,
                client_type=client_type,
            )

            return True, f"Connected successfully to {client_type} as {current_user}"

        except JIRAError as e:
            error_msg = self._parse_jira_error(e)
            self.security_logger.log_security_event(
                "jira_credential_validation_failed",
                severity="WARNING",
                url=url,
                username=username,
                error=str(e),
            )
            return False, error_msg

        except AuthenticationError as e:
            # Handle Red Hat Jira OAuth authentication errors specifically
            error_msg = str(e)
            self.security_logger.log_security_event(
                "jira_credential_validation_failed",
                severity="WARNING",
                url=url,
                username=username,
                error=error_msg,
            )
            return False, error_msg

        except Exception as e:
            self.logger.error(f"Jira validation error: {e}")
            return False, f"Connection failed: {e}"

    def validate_google_credentials(
        self, cred_data: Dict[str, str]
    ) -> Tuple[bool, str]:
        """Validate Google OAuth credentials."""
        try:
            required_fields = ["client_id", "client_secret", "refresh_token"]
            missing_fields = [
                field for field in required_fields if not cred_data.get(field)
            ]

            if missing_fields:
                return False, f"Missing required fields: {', '.join(missing_fields)}"

            # Create credentials object
            credentials = Credentials(
                token=cred_data.get("access_token"),
                refresh_token=cred_data.get("refresh_token"),
                token_uri=cred_data.get(
                    "token_uri", "https://oauth2.googleapis.com/token"
                ),
                client_id=cred_data.get("client_id"),
                client_secret=cred_data.get("client_secret"),
                scopes=cred_data.get(
                    "scopes",
                    [
                        "https://www.googleapis.com/auth/documents",
                        "https://www.googleapis.com/auth/drive.file",
                    ],
                ),
            )

            # Refresh if needed
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())

            # Test Drive API access
            drive_service = build("drive", "v3", credentials=credentials)
            about = drive_service.about().get(fields="user,storageQuota").execute()

            user_info = about.get("user", {})
            user_email = user_info.get("emailAddress", "Unknown")

            # Test Docs API access
            docs_service = build("docs", "v1", credentials=credentials)

            self.security_logger.log_security_event(
                "google_credential_validation_success",
                severity="INFO",
                user_email=user_email,
            )

            return True, f"Connected successfully as {user_email}"

        except HttpError as e:
            error_msg = self._parse_google_error(e)
            self.security_logger.log_security_event(
                "google_credential_validation_failed", severity="WARNING", error=str(e)
            )
            return False, error_msg

        except Exception as e:
            self.logger.error(f"Google validation error: {e}")
            return False, f"Authentication failed: {e}"

    def validate_gemini_credentials(self, api_key: str) -> Tuple[bool, str]:
        """Validate Google Gemini API key."""
        try:
            if not api_key:
                return False, "API key is required"

            # Basic format validation
            if not self._validate_gemini_key_format(api_key):
                return False, "Invalid API key format"

            # Configure Gemini
            genai.configure(api_key=api_key)

            # Test with a simple request
            model = genai.GenerativeModel("gemini-2.5-flash")
            response = model.generate_content(
                "What is 2 + 2? Please respond with just the number.",
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=10, temperature=0.1
                ),
            )

            # Check various response scenarios
            if hasattr(response, "text") and response.text:
                # Normal successful response
                pass
            elif hasattr(response, "candidates") and response.candidates:
                # Check if blocked by safety filters
                candidate = response.candidates[0]
                if hasattr(candidate, "finish_reason"):
                    if candidate.finish_reason in [2, 3]:  # SAFETY or RECITATION
                        # This is still a valid connection, just filtered content
                        self.logger.info(
                            "Gemini API key valid (test response filtered)"
                        )
                    else:
                        return (
                            False,
                            f"API response blocked: finish_reason={candidate.finish_reason}",
                        )
            elif response:
                # We got a response object, so connection is valid
                self.logger.info("Gemini API key valid (empty test response)")
            else:
                return False, "No response from Gemini API"

            # Get model info for validation
            models = list(genai.list_models())
            available_models = [
                model.name for model in models if "gemini" in model.name.lower()
            ]

            self.security_logger.log_security_event(
                "gemini_credential_validation_success",
                severity="INFO",
                available_models=len(available_models),
            )

            return True, f"API key valid. {len(available_models)} models available."

        except Exception as e:
            error_msg = self._parse_gemini_error(e)
            self.security_logger.log_security_event(
                "gemini_credential_validation_failed", severity="WARNING", error=str(e)
            )
            return False, error_msg

    def _validate_url(self, url: str) -> bool:
        """Validate URL format."""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False

    def _validate_email(self, email: str) -> bool:
        """Validate email format."""
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return re.match(pattern, email) is not None

    def _validate_username(self, url: str, username: str) -> bool:
        """Validate username based on Jira instance type."""
        if not username or not username.strip():
            return False

        # For Atlassian Cloud, username must be an email
        if self._is_atlassian_cloud(url):
            return self._validate_email(username)

        # For on-premise/server instances, allow any reasonable username
        # Username should be at least 2 characters and contain only valid characters
        if len(username.strip()) < 2:
            return False

        # Allow alphanumeric, dots, underscores, hyphens, and @ symbol
        pattern = r"^[a-zA-Z0-9._@-]+$"
        return re.match(pattern, username.strip()) is not None

    def _is_atlassian_cloud(self, url: str) -> bool:
        """Check if URL is an Atlassian Cloud instance."""
        try:
            parsed = urlparse(url.lower())
            return "atlassian.net" in parsed.netloc
        except Exception:
            return False

    def _is_redhat_jira(self, url: str) -> bool:
        """Check if URL is a Red Hat Jira instance."""
        return is_redhat_jira(url)

    def _validate_jira_token(self, token: str) -> bool:
        """Validate Jira API token format."""
        # Jira API tokens are typically 24 characters long and alphanumeric
        if len(token) < 10:
            return False

        # Should not contain spaces or special characters except possibly hyphens
        pattern = r"^[A-Za-z0-9\-_]+$"
        return re.match(pattern, token) is not None

    def _validate_gemini_key_format(self, api_key: str) -> bool:
        """Validate Gemini API key format."""
        # Google API keys typically start with 'AI' and are 39 characters long
        if not api_key.startswith("AI"):
            return False

        if len(api_key) != 39:
            return False

        # Should be alphanumeric with some special characters
        pattern = r"^AI[A-Za-z0-9\-_]+$"
        return re.match(pattern, api_key) is not None

    def _parse_jira_error(self, error: JIRAError) -> str:
        """Parse Jira error into user-friendly message."""
        status_code = getattr(error, "status_code", 0)

        if status_code == 401:
            return "Authentication failed. Please check your username and API token."
        elif status_code == 403:
            return "Access forbidden. Your account may not have sufficient permissions."
        elif status_code == 404:
            return "Jira instance not found. Please check the URL."
        elif status_code == 429:
            return "Rate limit exceeded. Please try again later."
        elif 500 <= status_code < 600:
            return "Jira server error. Please try again later."
        else:
            return f"Connection failed: {error}"

    def _parse_google_error(self, error: HttpError) -> str:
        """Parse Google API error into user-friendly message."""
        status_code = error.resp.status

        if status_code == 401:
            return "Authentication failed. Please re-authorize the application."
        elif status_code == 403:
            return "Access forbidden. Please check API permissions and quotas."
        elif status_code == 404:
            return "Resource not found."
        elif status_code == 429:
            return "Rate limit exceeded. Please try again later."
        else:
            return f"Google API error: {error}"

    def _parse_gemini_error(self, error: Exception) -> str:
        """Parse Gemini error into user-friendly message."""
        error_str = str(error).lower()

        if "api key" in error_str:
            return "Invalid API key. Please check your Gemini API key."
        elif "quota" in error_str or "limit" in error_str:
            return "API quota exceeded. Please check your usage limits."
        elif "permission" in error_str:
            return (
                "Permission denied. Please ensure the API key has proper permissions."
            )
        elif "network" in error_str or "connection" in error_str:
            return "Network error. Please check your internet connection."
        else:
            return f"Gemini API error: {error}"


class ServiceDiscovery:
    """Discover and auto-configure service connections."""

    def __init__(self):
        self.logger = get_logger(__name__)

    def discover_jira_url(self, company_name: str) -> List[str]:
        """Discover possible Jira URLs for a company."""
        possible_urls = []

        if company_name:
            # Clean company name
            clean_name = re.sub(r"[^a-zA-Z0-9]", "", company_name.lower())

            # Common Jira Cloud patterns
            patterns = [
                f"https://{clean_name}.atlassian.net",
                f"https://{company_name.lower()}.atlassian.net",
                f"https://{company_name.replace(' ', '')}.atlassian.net",
                f"https://{company_name.replace(' ', '-')}.atlassian.net",
            ]

            for url in patterns:
                if self._test_jira_url_accessibility(url):
                    possible_urls.append(url)

        return possible_urls

    def _test_jira_url_accessibility(self, url: str) -> bool:
        """Test if a Jira URL is accessible."""
        try:
            response = requests.get(f"{url}/status", timeout=5)
            return response.status_code == 200
        except Exception:
            return False

    def suggest_oauth_scopes(
        self, service: str, use_case: str = "executive_summary"
    ) -> List[str]:
        """Suggest appropriate OAuth scopes for a service."""
        scope_suggestions = {
            "google": {
                "executive_summary": [
                    "https://www.googleapis.com/auth/documents",
                    "https://www.googleapis.com/auth/drive.file",
                ],
                "full_access": [
                    "https://www.googleapis.com/auth/documents",
                    "https://www.googleapis.com/auth/drive",
                    "https://www.googleapis.com/auth/spreadsheets",
                ],
            }
        }

        return scope_suggestions.get(service, {}).get(use_case, [])

    def detect_existing_credentials(self) -> Dict[str, bool]:
        """Detect if there are existing credentials in common locations."""
        detected = {
            "google_application_credentials": False,
            "jira_config": False,
            "browser_saved_passwords": False,
        }

        # Check for Google Application Credentials
        import os

        if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            detected["google_application_credentials"] = True

        # Check for common Jira config files
        from pathlib import Path

        jira_config_paths = [
            Path.home() / ".jira" / "config",
            Path.home() / ".config" / "jira" / "config.json",
        ]

        for path in jira_config_paths:
            if path.exists():
                detected["jira_config"] = True
                break

        return detected


class CredentialHealthMonitor:
    """Monitor credential health and expiration."""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.security_logger = get_security_logger()

    def check_credential_health(
        self, service: str, credentials: Dict[str, str]
    ) -> Dict[str, any]:
        """Check the health of credentials."""
        health_status = {
            "service": service,
            "healthy": False,
            "issues": [],
            "expires_soon": False,
            "last_tested": None,
            "recommendations": [],
        }

        try:
            validator = CredentialValidator()

            if service == "jira":
                success, message = validator.validate_jira_credentials(
                    credentials.get("url", ""),
                    credentials.get("username", ""),
                    credentials.get("api_token", ""),
                )
            elif service == "google":
                success, message = validator.validate_google_credentials(credentials)
            elif service == "gemini":
                success, message = validator.validate_gemini_credentials(
                    credentials.get("api_key", "")
                )
            else:
                success = False
                message = "Unknown service"

            health_status["healthy"] = success
            health_status["last_tested"] = "now"

            if not success:
                health_status["issues"].append(message)
                health_status["recommendations"].append(
                    "Please re-configure credentials"
                )

            # Check for expiration warnings (OAuth tokens)
            if service == "google" and success:
                self._check_google_token_expiration(credentials, health_status)

        except Exception as e:
            health_status["issues"].append(f"Health check failed: {e}")
            health_status["recommendations"].append("Manual verification recommended")

        return health_status

    def _check_google_token_expiration(
        self, credentials: Dict[str, str], health_status: Dict
    ):
        """Check Google token expiration."""
        try:
            # This would check token expiration dates
            # For now, just add a general recommendation
            health_status["recommendations"].append("Monitor token expiration dates")
        except Exception as e:
            self.logger.error(f"Failed to check token expiration: {e}")

    def get_health_recommendations(
        self, health_results: List[Dict[str, any]]
    ) -> List[str]:
        """Get overall health recommendations."""
        recommendations = []

        unhealthy_services = [r for r in health_results if not r["healthy"]]

        if unhealthy_services:
            recommendations.append(
                f"Fix credentials for: {', '.join([r['service'] for r in unhealthy_services])}"
            )

        if any(r.get("expires_soon", False) for r in health_results):
            recommendations.append("Renew expiring credentials")

        if not recommendations:
            recommendations.append("All credentials are healthy")

        return recommendations
