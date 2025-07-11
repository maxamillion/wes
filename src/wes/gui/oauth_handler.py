"""Google OAuth flow handler with embedded browser."""

import json
import secrets
import threading
import time
from typing import Dict, Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from PySide6.QtCore import QObject, Signal, QTimer
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from ..utils.logging_config import get_logger, get_security_logger


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler for OAuth callback."""

    def do_GET(self):
        """Handle GET request for OAuth callback."""
        self.server.callback_received = True

        # Parse query parameters
        parsed_url = urlparse(self.path)
        query_params = parse_qs(parsed_url.query)

        # Store authorization code or error
        if "code" in query_params:
            self.server.auth_code = query_params["code"][0]
            self.server.auth_state = query_params.get("state", [""])[0]

            # Send success response
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()

            success_html = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Authorization Successful</title>
                <style>
                    body { font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }
                    .success { color: #4CAF50; font-size: 24px; }
                    .info { color: #666; margin-top: 20px; }
                </style>
            </head>
            <body>
                <div class="success">✅ Authorization Successful!</div>
                <div class="info">You can now close this window and return to the application.</div>
            </body>
            </html>
            """
            self.wfile.write(success_html.encode())

        elif "error" in query_params:
            self.server.auth_error = query_params["error"][0]
            error_description = query_params.get(
                "error_description", ["Unknown error"]
            )[0]

            # Send error response
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()

            error_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Authorization Failed</title>
                <style>
                    body {{ font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }}
                    .error {{ color: #f44336; font-size: 24px; }}
                    .info {{ color: #666; margin-top: 20px; }}
                </style>
            </head>
            <body>
                <div class="error">❌ Authorization Failed</div>
                <div class="info">{error_description}</div>
                <div class="info">Please close this window and try again.</div>
            </body>
            </html>
            """
            self.wfile.write(error_html.encode())

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


class GoogleOAuthHandler(QObject):
    """Handle Google OAuth 2.0 flow."""

    auth_complete = Signal(dict)
    auth_error = Signal(str)

    # OAuth configuration for Google Drive and Docs
    CLIENT_CONFIG = {
        "web": {
            "client_id": "your-client-id.apps.googleusercontent.com",
            "client_secret": "your-client-secret",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost:8080/callback"],
        }
    }

    SCOPES = [
        "https://www.googleapis.com/auth/documents",
        "https://www.googleapis.com/auth/drive.file",
    ]

    def __init__(self, config_manager=None):
        super().__init__()
        self.logger = get_logger(__name__)
        self.security_logger = get_security_logger()
        self.config_manager = config_manager

        self.callback_server = None
        self.flow = None
        self.state = None

        # Check for existing client configuration
        self._load_client_config()

    def _load_client_config(self):
        """Load OAuth client configuration."""
        try:
            # Try to load from config manager if available
            if self.config_manager:
                google_config = self.config_manager.get_google_config()
                client_id = google_config.oauth_client_id
                client_secret = self.config_manager.retrieve_credential(
                    "google", "oauth_client_secret"
                )

                if client_id and client_secret:
                    self.CLIENT_CONFIG["web"]["client_id"] = client_id
                    self.CLIENT_CONFIG["web"]["client_secret"] = client_secret
                    self.logger.info(
                        "Loaded OAuth client configuration from config manager"
                    )
                    return

            # Try to load from environment variables
            import os

            client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
            client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")

            if client_id and client_secret:
                self.CLIENT_CONFIG["web"]["client_id"] = client_id
                self.CLIENT_CONFIG["web"]["client_secret"] = client_secret
                self.logger.info(
                    "Loaded OAuth client configuration from environment variables"
                )
                return

            # Try to load from a credentials file
            from pathlib import Path

            cred_file = Path.home() / ".wes" / "google_oauth_credentials.json"
            if cred_file.exists():
                with open(cred_file, "r") as f:
                    creds = json.load(f)
                    if "client_id" in creds and "client_secret" in creds:
                        self.CLIENT_CONFIG["web"]["client_id"] = creds["client_id"]
                        self.CLIENT_CONFIG["web"]["client_secret"] = creds[
                            "client_secret"
                        ]
                        self.logger.info(
                            "Loaded OAuth client configuration from credentials file"
                        )
                        return

            # Log warning if no valid credentials found
            if (
                self.CLIENT_CONFIG["web"]["client_id"]
                == "your-client-id.apps.googleusercontent.com"
            ):
                self.logger.warning(
                    "No valid OAuth client credentials found. Please configure Google OAuth credentials."
                )

        except Exception as e:
            self.logger.error(f"Failed to load OAuth client configuration: {e}")

    def start_flow(self, port: int = 8080):
        """Start the OAuth flow."""
        try:
            # Generate state for CSRF protection
            self.state = secrets.token_urlsafe(32)

            # Setup callback server
            self._setup_callback_server(port)

            # Create OAuth flow
            redirect_uri = f"http://localhost:{port}/callback"

            # Update client config with dynamic redirect URI
            client_config = self.CLIENT_CONFIG.copy()
            client_config["web"]["redirect_uris"] = [redirect_uri]

            self.flow = Flow.from_client_config(
                client_config, scopes=self.SCOPES, state=self.state
            )
            self.flow.redirect_uri = redirect_uri

            # Get authorization URL
            auth_url, _ = self.flow.authorization_url(
                access_type="offline", include_granted_scopes="true", state=self.state
            )

            # Open browser
            import webbrowser

            webbrowser.open(auth_url)

            self.security_logger.log_security_event(
                "oauth_flow_started", severity="INFO", redirect_uri=redirect_uri
            )

            # Start monitoring for callback
            self._monitor_callback()

        except Exception as e:
            self.logger.error(f"Failed to start OAuth flow: {e}")
            self.auth_error.emit(f"Failed to start OAuth flow: {e}")

    def _setup_callback_server(self, port: int):
        """Setup HTTP server for OAuth callback."""
        try:
            self.callback_server = HTTPServer(("localhost", port), OAuthCallbackHandler)
            self.callback_server.callback_received = False
            self.callback_server.auth_code = None
            self.callback_server.auth_state = None
            self.callback_server.auth_error = None

            # Start server in background thread
            server_thread = threading.Thread(
                target=self.callback_server.serve_forever, daemon=True
            )
            server_thread.start()

        except Exception as e:
            raise Exception(f"Failed to setup callback server: {e}")

    def _monitor_callback(self):
        """Monitor for OAuth callback."""
        # Use QTimer to periodically check for callback
        self.callback_timer = QTimer()
        self.callback_timer.timeout.connect(self._check_callback)
        self.callback_timer.start(500)  # Check every 500ms

        # Timeout after 5 minutes
        self.timeout_timer = QTimer()
        self.timeout_timer.timeout.connect(self._handle_timeout)
        self.timeout_timer.setSingleShot(True)
        self.timeout_timer.start(300000)  # 5 minutes

    def _check_callback(self):
        """Check if OAuth callback was received."""
        if not self.callback_server:
            return

        if self.callback_server.callback_received:
            self.callback_timer.stop()
            self.timeout_timer.stop()

            if self.callback_server.auth_code:
                self._handle_auth_code(
                    self.callback_server.auth_code, self.callback_server.auth_state
                )
            elif self.callback_server.auth_error:
                self.auth_error.emit(self.callback_server.auth_error)

            # Cleanup server
            self.callback_server.shutdown()
            self.callback_server = None

    def _handle_timeout(self):
        """Handle OAuth flow timeout."""
        self.callback_timer.stop()

        if self.callback_server:
            self.callback_server.shutdown()
            self.callback_server = None

        self.auth_error.emit("OAuth flow timed out. Please try again.")

    def _handle_auth_code(self, auth_code: str, received_state: str):
        """Handle received authorization code."""
        try:
            # Verify state parameter
            if received_state != self.state:
                raise Exception("Invalid state parameter - possible CSRF attack")

            # Exchange code for credentials
            self.flow.fetch_token(code=auth_code)

            # Get credentials
            credentials = self.flow.credentials

            # Extract credential data
            cred_data = {
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "refresh_token": credentials.refresh_token,
                "access_token": credentials.token,
                "token_uri": credentials.token_uri,
                "scopes": list(credentials.scopes) if credentials.scopes else [],
            }

            self.security_logger.log_security_event(
                "oauth_flow_completed", severity="INFO", scopes=cred_data["scopes"]
            )

            self.auth_complete.emit(cred_data)

        except Exception as e:
            self.logger.error(f"Failed to handle auth code: {e}")
            self.auth_error.emit(f"Failed to complete authentication: {e}")

    def test_credentials(self, cred_data: Dict[str, str]) -> tuple[bool, str]:
        """Test Google credentials."""
        try:
            # Create credentials object
            credentials = Credentials(
                token=cred_data.get("access_token"),
                refresh_token=cred_data.get("refresh_token"),
                token_uri=cred_data.get("token_uri"),
                client_id=cred_data.get("client_id"),
                client_secret=cred_data.get("client_secret"),
                scopes=cred_data.get("scopes", self.SCOPES),
            )

            # Refresh if needed
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())

            # Test with simple API call
            from googleapiclient.discovery import build

            # Test Drive API
            drive_service = build("drive", "v3", credentials=credentials)
            about = drive_service.about().get(fields="user").execute()

            user_email = about.get("user", {}).get("emailAddress", "Unknown")

            return True, f"Successfully connected as {user_email}"

        except Exception as e:
            return False, f"Credential test failed: {e}"

    def refresh_credentials(
        self, cred_data: Dict[str, str]
    ) -> Optional[Dict[str, str]]:
        """Refresh OAuth credentials."""
        try:
            credentials = Credentials(
                token=cred_data.get("access_token"),
                refresh_token=cred_data.get("refresh_token"),
                token_uri=cred_data.get("token_uri"),
                client_id=cred_data.get("client_id"),
                client_secret=cred_data.get("client_secret"),
                scopes=cred_data.get("scopes", self.SCOPES),
            )

            # Refresh credentials
            credentials.refresh(Request())

            # Return updated credential data
            return {
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "refresh_token": credentials.refresh_token,
                "access_token": credentials.token,
                "token_uri": credentials.token_uri,
                "scopes": list(credentials.scopes) if credentials.scopes else [],
            }

        except Exception as e:
            self.logger.error(f"Failed to refresh credentials: {e}")
            return None

    def revoke_credentials(self, cred_data: Dict[str, str]) -> bool:
        """Revoke OAuth credentials."""
        try:
            credentials = Credentials(
                token=cred_data.get("access_token"),
                refresh_token=cred_data.get("refresh_token"),
                token_uri=cred_data.get("token_uri"),
                client_id=cred_data.get("client_id"),
                client_secret=cred_data.get("client_secret"),
                scopes=cred_data.get("scopes", self.SCOPES),
            )

            # Revoke credentials
            import requests

            revoke_url = "https://oauth2.googleapis.com/revoke"
            requests.post(
                revoke_url,
                params={"token": credentials.token},
                headers={"content-type": "application/x-www-form-urlencoded"},
            )

            self.security_logger.log_security_event(
                "oauth_credentials_revoked", severity="INFO"
            )

            return True

        except Exception as e:
            self.logger.error(f"Failed to revoke credentials: {e}")
            return False


class OAuthManager:
    """Manage OAuth configurations and flows."""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.handlers = {"google": GoogleOAuthHandler()}

    def get_handler(self, provider: str) -> Optional[GoogleOAuthHandler]:
        """Get OAuth handler for provider."""
        return self.handlers.get(provider)

    def configure_google_client(self, client_id: str, client_secret: str):
        """Configure Google OAuth client."""
        handler = self.handlers.get("google")
        if handler:
            handler.CLIENT_CONFIG["web"]["client_id"] = client_id
            handler.CLIENT_CONFIG["web"]["client_secret"] = client_secret

    def is_provider_configured(self, provider: str) -> bool:
        """Check if OAuth provider is configured."""
        handler = self.handlers.get(provider)
        if not handler:
            return False

        if provider == "google":
            config = handler.CLIENT_CONFIG["web"]
            return (
                config["client_id"] != "your-client-id.apps.googleusercontent.com"
                and config["client_secret"] != "your-client-secret"
            )

        return False

    def get_authorization_url(self, provider: str, **kwargs) -> Optional[str]:
        """Get authorization URL for provider."""
        handler = self.handlers.get(provider)
        if not handler:
            return None

        # This would generate the auth URL without starting the full flow
        # Implementation depends on specific requirements
        return None

    def handle_callback(
        self, provider: str, _callback_data: Dict[str, str]
    ) -> tuple[bool, str, Optional[Dict]]:
        """Handle OAuth callback."""
        handler = self.handlers.get(provider)
        if not handler:
            return False, "Unknown provider", None

        # Process callback data and return credentials
        # Implementation depends on specific requirements
        return True, "Success", {}
