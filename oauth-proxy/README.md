# Wes OAuth Proxy Service

This service simplifies Google OAuth authentication for Wes users by providing a centralized OAuth application.

## Overview

Instead of requiring each user to create their own Google Cloud Project and OAuth credentials, this proxy service handles the OAuth flow on behalf of users. It never stores user credentials - it only facilitates the token exchange.

## Architecture

```
User's Wes App → OAuth Proxy → Google OAuth → Google APIs
```

## Security

- **No credential storage**: The proxy never stores user tokens
- **HTTPS only**: All communication is encrypted
- **Rate limiting**: Prevents abuse with per-IP rate limits
- **CORS protection**: Only allows requests from Wes applications
- **State validation**: CSRF protection with state parameter

## Deployment

### Option 1: Vercel (Recommended)

1. Fork this repository
2. Connect to Vercel
3. Set environment variables:
   - `GOOGLE_OAUTH_CLIENT_ID`: Your Google OAuth client ID
   - `GOOGLE_OAUTH_CLIENT_SECRET`: Your Google OAuth client secret
   - `REDIS_URL`: Redis connection URL (for state storage)
4. Deploy

### Option 2: AWS Lambda

Use the provided `serverless.yml` configuration:

```bash
serverless deploy
```

### Option 3: Docker

```bash
docker build -t wes-oauth-proxy .
docker run -p 8000:8000 \
  -e GOOGLE_OAUTH_CLIENT_ID=your-client-id \
  -e GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret \
  -e REDIS_URL=redis://redis:6379 \
  wes-oauth-proxy
```

## Local Development

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set environment variables:
   ```bash
   export GOOGLE_OAUTH_CLIENT_ID="your-client-id"
   export GOOGLE_OAUTH_CLIENT_SECRET="your-client-secret"
   export REDIS_URL="redis://localhost:6379"
   ```

3. Run the service:
   ```bash
   python main.py
   ```

## API Endpoints

- `GET /health` - Health check
- `GET /auth/google` - Start OAuth flow
- `GET /callback/google` - OAuth callback
- `POST /token/exchange` - Exchange auth code for tokens
- `POST /token/refresh` - Refresh access token

## Setting Up Google OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project or select existing
3. Enable Google Drive API and Google Docs API
4. Create OAuth 2.0 credentials:
   - Application type: Web application
   - Authorized redirect URIs: `https://oauth.wes-app.com/callback/google`
5. Copy the client ID and secret to environment variables

## Privacy Policy

This service:
- Does not store user credentials
- Does not log personal information
- Only facilitates OAuth token exchange
- Complies with GDPR requirements

## Support

For issues or questions, please open an issue on GitHub.