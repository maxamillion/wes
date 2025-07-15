"""Simplified Google OAuth handler using Wes proxy service."""

import json
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict, Optional, Tuple
from urllib.parse import parse_qs, urlparse

import requests
from PySide6.QtCore import QObject, QTimer, Signal

from ..utils.logging_config import get_logger, get_security_logger
from .oauth_handler import GoogleOAuthHandler


class SimplifiedOAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler for simplified OAuth callback."""

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
                    body { 
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
                        text-align: center; 
                        margin-top: 50px;
                        background-color: #f5f5f5;
                    }
                    .container {
                        background: white;
                        border-radius: 8px;
                        padding: 40px;
                        max-width: 400px;
                        margin: 0 auto;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    }
                    .success { 
                        color: #28a745; 
                        font-size: 24px; 
                        margin-bottom: 20px;
                    }
                    .info { 
                        color: #666; 
                        margin-top: 20px;
                        line-height: 1.5;
                    }
                    .logo {
                        width: 64px;
                        height: 64px;
                        margin-bottom: 20px;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="success">✅ Authorization Successful!</div>
                    <div class="info">
                        You can now close this window and return to Wes.<br>
                        Your Google account has been connected successfully.
                    </div>
                </div>
                <script>
                    // Auto-close after 3 seconds
                    setTimeout(() => window.close(), 3000);
                </script>
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
                    body {{ 
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
                        text-align: center; 
                        margin-top: 50px;
                        background-color: #f5f5f5;
                    }}
                    .container {{
                        background: white;
                        border-radius: 8px;
                        padding: 40px;
                        max-width: 400px;
                        margin: 0 auto;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    }}
                    .error {{ 
                        color: #dc3545; 
                        font-size: 24px;
                        margin-bottom: 20px;
                    }}
                    .info {{ 
                        color: #666; 
                        margin-top: 20px;
                        line-height: 1.5;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="error">❌ Authorization Failed</div>
                    <div class="info">
                        {error_description}<br><br>
                        Please close this window and try again.
                    </div>
                </div>
            </body>
            </html>
            """
            self.wfile.write(error_html.encode())

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


class SimplifiedGoogleOAuthHandler(QObject):
    """Simplified Google OAuth handler using Wes proxy service."""

    auth_complete = Signal(dict)
    auth_error = Signal(str)

    # Proxy service configuration
    PROXY_URL = "https://oauth.wes-app.com"
    PROXY_URL_DEV = "http://localhost:8000"  # For development

    # Check if we should use local proxy for development
    USE_LOCAL_PROXY = False  # Set via environment variable in production

    def __init__(self, config_manager=None):
        super().__init__()
        self.logger = get_logger(__name__)
        self.security_logger = get_security_logger()
        self.config_manager = config_manager

        # Fallback handler for manual configuration
        self.fallback_handler = GoogleOAuthHandler(config_manager)

        self.callback_server = None
        self.state = None
        self.callback_port = 8080

        # Check environment for proxy settings
        import os

        if os.environ.get("WES_USE_LOCAL_PROXY") == "true":
            self.USE_LOCAL_PROXY = True
            self.logger.info("Using local OAuth proxy for development")

    @property
    def proxy_url(self):
        """Get the appropriate proxy URL."""
        return self.PROXY_URL_DEV if self.USE_LOCAL_PROXY else self.PROXY_URL

    def is_proxy_available(self) -> bool:
        """Check if the OAuth proxy service is available."""
        try:
            response = requests.get(f"{self.proxy_url}/health", timeout=5)
            return response.status_code == 200
        except Exception as e:
            self.logger.warning(f"OAuth proxy not available: {e}")
            return False

    def start_flow(self, port: int = 8080):
        """Start the simplified OAuth flow."""
        try:
            self.callback_port = port

            # Always use the fallback (direct OAuth) since proxy doesn't exist
            self.logger.info("Using direct OAuth authentication")
            self.use_fallback()
            return

        except Exception as e:
            self.logger.error(f"Failed to start OAuth flow: {e}")
            self.auth_error.emit(f"Failed to start authentication: {e}")

    def use_fallback(self):
        """Use fallback manual OAuth configuration."""
        self.logger.info("Using manual OAuth configuration fallback")

        # Connect fallback signals with lambda to ensure proper signal propagation
        self.fallback_handler.auth_complete.connect(
            lambda data: self.auth_complete.emit(data)
        )
        self.fallback_handler.auth_error.connect(
            lambda error: self.auth_error.emit(error)
        )

        # Start fallback flow
        self.fallback_handler.start_flow(self.callback_port)

    def _setup_callback_server(self, port: int):
        """Setup HTTP server for OAuth callback."""
        try:
            self.callback_server = HTTPServer(
                ("localhost", port), SimplifiedOAuthCallbackHandler
            )
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
                self.auth_error.emit(
                    f"Authentication failed: {self.callback_server.auth_error}"
                )

            # Cleanup server
            self.callback_server.shutdown()
            self.callback_server = None

    def _handle_timeout(self):
        """Handle OAuth flow timeout."""
        self.callback_timer.stop()

        if self.callback_server:
            self.callback_server.shutdown()
            self.callback_server = None

        self.auth_error.emit("Authentication timed out. Please try again.")

    def _handle_auth_code(self, auth_code: str, received_state: str):
        """Handle received authorization code."""
        try:
            # Verify state parameter
            if received_state != self.state:
                raise Exception("Invalid state parameter - possible security issue")

            # Exchange code for tokens via proxy
            response = requests.post(
                f"{self.proxy_url}/token/exchange",
                json={"code": auth_code, "state": self.state},
                headers={"X-Client-Id": "wes-desktop", "User-Agent": "Wes/1.0.0"},
                timeout=30,
            )

            if response.status_code == 200:
                token_data = response.json()

                # Convert to format expected by Wes
                cred_data = {
                    "access_token": token_data["access_token"],
                    "refresh_token": token_data["refresh_token"],
                    "token_type": token_data["token_type"],
                    "expires_in": token_data.get("expires_in", 3600),
                    "scope": token_data.get("scope", ""),
                    # These are not provided by proxy, but needed for compatibility
                    "client_id": "proxy-managed",
                    "client_secret": "proxy-managed",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }

                self.security_logger.log_security_event(
                    "simplified_oauth_completed", severity="INFO"
                )

                self.auth_complete.emit(cred_data)

            else:
                error_msg = f"Token exchange failed: {response.text}"
                self.logger.error(error_msg)
                self.auth_error.emit(error_msg)

        except Exception as e:
            self.logger.error(f"Failed to handle auth code: {e}")
            self.auth_error.emit(f"Failed to complete authentication: {e}")

    def test_credentials(self, cred_data: Dict[str, str]) -> Tuple[bool, str]:
        """Test Google credentials."""
        # For simplified auth, we can use the fallback handler's test method
        return self.fallback_handler.test_credentials(cred_data)

    def refresh_credentials(
        self, cred_data: Dict[str, str]
    ) -> Optional[Dict[str, str]]:
        """Refresh OAuth credentials via proxy."""
        try:
            response = requests.post(
                f"{self.proxy_url}/token/refresh",
                json={"refresh_token": cred_data["refresh_token"]},
                headers={"X-Client-Id": "wes-desktop", "User-Agent": "Wes/1.0.0"},
                timeout=30,
            )

            if response.status_code == 200:
                refresh_data = response.json()

                # Update credential data
                cred_data["access_token"] = refresh_data["access_token"]
                if "expires_in" in refresh_data:
                    cred_data["expires_in"] = refresh_data["expires_in"]

                return cred_data
            else:
                self.logger.error(f"Token refresh failed: {response.text}")
                return None

        except Exception as e:
            self.logger.error(f"Failed to refresh credentials: {e}")
            return None

    def revoke_credentials(self, cred_data: Dict[str, str]) -> bool:
        """Revoke OAuth credentials."""
        # Use the fallback handler's revoke method
        return self.fallback_handler.revoke_credentials(cred_data)
