# Simplified Google OAuth Guide

## Overview

Wes now provides a simplified OAuth authentication method that doesn't require users to create their own Google Cloud credentials. This guide explains how it works and how to use it.

## For Users

### Connecting Your Google Account

1. Open Wes and go to Settings → Google Services
2. Click "Authenticate with Google"
3. Your browser will open to Google's login page
4. Log in with your Google account
5. Approve the permissions (Google Docs and Drive access)
6. You'll be redirected back to Wes automatically
7. That's it! No configuration needed.

### What Permissions Are Requested?

Wes requests only the minimum permissions needed:
- **Google Docs**: Create and edit documents
- **Google Drive**: Create files in your Drive

We do NOT have access to:
- Your existing documents (unless you explicitly share them)
- Your email or personal information
- Files outside of what Wes creates

### Troubleshooting

**"Connection timed out"**
- Check your internet connection
- Try disabling VPN if you're using one
- Make sure your firewall allows connections to oauth.wes-app.com

**"Authentication failed"**
- Make sure you're using a valid Google account
- Try clearing your browser cookies and cache
- Use a different browser if the issue persists

## For Developers

### How It Works

The simplified OAuth uses a proxy service that handles the OAuth flow:

```
Wes App → Wes OAuth Proxy → Google OAuth → Google APIs
```

The proxy service:
- Manages the OAuth application registration with Google
- Facilitates the token exchange
- Never stores user credentials
- Returns tokens to the Wes app for local storage

### Implementation Details

#### Client-Side (Wes App)

The `SimplifiedGoogleOAuthHandler` class handles the OAuth flow:

```python
from wes.gui.simplified_oauth_handler import SimplifiedGoogleOAuthHandler

# Create handler
handler = SimplifiedGoogleOAuthHandler(config_manager)

# Connect signals
handler.auth_complete.connect(on_auth_success)
handler.auth_error.connect(on_auth_error)

# Start OAuth flow
handler.start_flow()
```

#### Fallback to Manual Configuration

If the proxy service is unavailable, the handler automatically falls back to manual OAuth configuration:

```python
# In SimplifiedGoogleOAuthHandler
if not self.is_proxy_available():
    self.use_fallback()  # Uses GoogleOAuthHandler
```

#### Token Storage

Tokens are stored securely using the existing SecurityManager:

```python
# Storing tokens
config_manager.store_credential("google", "oauth_access_token", token)
config_manager.store_credential("google", "oauth_refresh_token", refresh_token)

# Retrieving tokens
access_token = config_manager.retrieve_credential("google", "oauth_access_token")
```

### Running Locally with Development Proxy

For development, you can run the OAuth proxy locally:

1. Set up the proxy:
   ```bash
   cd oauth-proxy
   pip install -r requirements.txt
   export GOOGLE_OAUTH_CLIENT_ID="your-dev-client-id"
   export GOOGLE_OAUTH_CLIENT_SECRET="your-dev-client-secret"
   python main.py
   ```

2. Configure Wes to use local proxy:
   ```bash
   export WES_USE_LOCAL_PROXY=true
   ```

3. The app will now use `http://localhost:8000` instead of the production proxy.

### Security Considerations

1. **Token Security**: Access and refresh tokens are encrypted using AES-256
2. **No Credential Sharing**: Each user's tokens are stored locally
3. **HTTPS Only**: All communication with the proxy uses HTTPS
4. **State Validation**: CSRF protection using state parameter
5. **Rate Limiting**: Prevents abuse of the proxy service

### Enterprise Deployments

For enterprise environments that cannot use external services:

1. **Deploy Your Own Proxy**: Use the provided Docker/Kubernetes configurations
2. **Service Account**: Use Google Workspace service accounts instead
3. **Manual Configuration**: Fall back to the original manual OAuth setup

### API Integration

The Google Docs client automatically handles both simplified and manual OAuth:

```python
# In GoogleDocsClient._get_oauth_credentials()
if client_id == "proxy-managed":
    # Handle simplified OAuth tokens
    # Refresh through proxy if needed
else:
    # Standard OAuth flow
    # Refresh using client credentials
```

## Privacy and Compliance

### Data Handling

- **No Storage**: The proxy service does not store any user data
- **Token Isolation**: Each user's tokens are stored only on their device
- **Audit Logging**: Only anonymous usage metrics are logged
- **GDPR Compliant**: No personal data is collected or stored

### Open Source

The OAuth proxy service is open source and can be audited:
- Source code: [GitHub repository]
- Deployment: Vercel/AWS Lambda
- Security audits: Available on request

## Migration Guide

### For Existing Users

If you've already configured OAuth manually:
1. Your existing configuration will continue to work
2. You can optionally migrate to simplified OAuth
3. Go to Settings → Google Services → Re-authenticate

### For New Users

New users will automatically use the simplified OAuth flow. No migration needed.

## FAQ

**Q: Is this secure?**
A: Yes. The proxy only facilitates authentication and never stores credentials. Your tokens are encrypted and stored locally.

**Q: What if the proxy service is down?**
A: Wes automatically falls back to manual OAuth configuration.

**Q: Can I still use manual configuration?**
A: Yes. Click "Advanced Options" in the Google configuration page.

**Q: Does this work with Google Workspace?**
A: Yes, it works with both personal and Workspace accounts.

**Q: How do I revoke access?**
A: Go to https://myaccount.google.com/permissions and revoke access to "Wes".