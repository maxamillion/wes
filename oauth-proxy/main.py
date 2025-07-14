"""Wes OAuth Proxy Service - Simplifies Google OAuth for users."""

import os
import secrets
import time
from typing import Dict, Optional
from urllib.parse import urlencode

from fastapi import FastAPI, HTTPException, Query, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from pydantic import BaseModel
import redis
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address


# Configuration
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
ALLOWED_ORIGINS = [
    "http://localhost:*",
    "app://wes",
    "https://wes-app.com"
]

# OAuth configuration
OAUTH_CONFIG = {
    "web": {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["https://oauth.wes-app.com/callback/google"]
    }
}

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.file"
]

# Initialize app
app = FastAPI(
    title="Wes OAuth Proxy",
    description="Simplified OAuth service for Wes application",
    version="1.0.0"
)

# Rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(429, _rate_limit_exceeded_handler)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Redis for temporary state storage
redis_client = redis.from_url(REDIS_URL, decode_responses=True)


class TokenExchangeRequest(BaseModel):
    """Request model for token exchange."""
    code: str
    state: str


class TokenExchangeResponse(BaseModel):
    """Response model for token exchange."""
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    scope: str


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "wes-oauth-proxy"}


@app.get("/auth/google")
@limiter.limit("20/minute")
async def start_oauth(
    request: Request,
    state: str = Query(..., description="CSRF protection token from client"),
    redirect_uri: str = Query(..., description="Client callback URL")
):
    """Initiate OAuth flow with Google."""
    try:
        # Store state temporarily (5 minutes expiry)
        state_data = {
            "client_redirect": redirect_uri,
            "timestamp": time.time()
        }
        redis_client.setex(f"oauth_state:{state}", 300, str(state_data))
        
        # Create OAuth flow
        flow = Flow.from_client_config(
            OAUTH_CONFIG,
            scopes=SCOPES,
            state=state
        )
        flow.redirect_uri = OAUTH_CONFIG["web"]["redirect_uris"][0]
        
        # Get authorization URL
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent"
        )
        
        return RedirectResponse(url=auth_url)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start OAuth: {str(e)}")


@app.get("/callback/google")
async def oauth_callback(
    code: str = Query(None),
    state: str = Query(None),
    error: str = Query(None)
):
    """Handle OAuth callback from Google."""
    try:
        # Handle errors
        if error:
            state_data = redis_client.get(f"oauth_state:{state}")
            if state_data:
                client_redirect = eval(state_data)["client_redirect"]
                error_url = f"{client_redirect}?error={error}"
                redis_client.delete(f"oauth_state:{state}")
                return RedirectResponse(url=error_url)
            raise HTTPException(status_code=400, detail=error)
        
        # Validate state
        state_data = redis_client.get(f"oauth_state:{state}")
        if not state_data:
            raise HTTPException(status_code=400, detail="Invalid or expired state")
        
        state_info = eval(state_data)
        client_redirect = state_info["client_redirect"]
        
        # Clean up state
        redis_client.delete(f"oauth_state:{state}")
        
        # Redirect back to client with code
        callback_url = f"{client_redirect}?code={code}&state={state}"
        return RedirectResponse(url=callback_url)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Callback failed: {str(e)}")


@app.post("/token/exchange", response_model=TokenExchangeResponse)
@limiter.limit("10/minute")
async def exchange_token(
    request: Request,
    token_request: TokenExchangeRequest,
    x_client_id: Optional[str] = Header(None)
):
    """Exchange authorization code for tokens."""
    try:
        # Create flow for token exchange
        flow = Flow.from_client_config(
            OAUTH_CONFIG,
            scopes=SCOPES,
            state=token_request.state
        )
        flow.redirect_uri = OAUTH_CONFIG["web"]["redirect_uris"][0]
        
        # Exchange code for tokens
        flow.fetch_token(code=token_request.code)
        
        credentials = flow.credentials
        
        # Return tokens (never store them)
        return TokenExchangeResponse(
            access_token=credentials.token,
            refresh_token=credentials.refresh_token,
            token_type="Bearer",
            expires_in=3600,  # Default 1 hour
            scope=" ".join(credentials.scopes) if credentials.scopes else ""
        )
        
    except Exception as e:
        # Log error for monitoring (but don't expose details)
        print(f"Token exchange error: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail="Failed to exchange authorization code"
        )


@app.post("/token/refresh")
@limiter.limit("30/minute")
async def refresh_token(
    request: Request,
    refresh_token: str,
    x_client_id: Optional[str] = Header(None)
):
    """Refresh an access token."""
    try:
        credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri=OAUTH_CONFIG["web"]["token_uri"],
            client_id=GOOGLE_CLIENT_ID,
            client_secret=GOOGLE_CLIENT_SECRET,
            scopes=SCOPES
        )
        
        # Refresh the token
        credentials.refresh(GoogleRequest())
        
        return {
            "access_token": credentials.token,
            "token_type": "Bearer",
            "expires_in": 3600
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail="Failed to refresh token"
        )


@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "Wes OAuth Proxy",
        "version": "1.0.0",
        "description": "Simplified OAuth service for Wes application",
        "endpoints": {
            "start_auth": "/auth/google",
            "callback": "/callback/google",
            "exchange_token": "/token/exchange",
            "refresh_token": "/token/refresh",
            "health": "/health"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)