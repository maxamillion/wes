# Fixing Google OAuth "401: invalid_client" Error

## Problem
When attempting to login with Google OAuth, you receive:
```
Error 401: invalid_client
Request details: flowName=GeneralOAuthFlow
```

## Root Cause
The application doesn't have valid Google OAuth credentials configured. The default placeholder credentials are being rejected by Google.

## Solutions

### Option 1: Use Service Account Authentication (Recommended for Quick Fix)

1. Open WES Settings
2. Go to the Google tab
3. Select "Service Account" instead of "OAuth 2.0"
4. Create a service account:
   - Go to [Google Cloud Console](https://console.cloud.google.com)
   - Create a new project or select existing
   - Enable Google Docs API and Google Drive API
   - Go to "IAM & Admin" > "Service Accounts"
   - Create a new service account
   - Create and download a JSON key
5. In WES, click "Browse..." and select the downloaded JSON key file
6. Click "Test Connection" to verify

### Option 2: Set Up OAuth Credentials (No Website Required)

1. **Run the setup script**:
   ```bash
   uv run python setup_google_oauth.py
   ```
   This interactive script will guide you through the process.

2. **Or manually create OAuth credentials**:
   - Go to [Google Cloud Console](https://console.cloud.google.com)
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Choose "Desktop app" as application type
   - Copy the Client ID and Client Secret

3. **Configure WES with the credentials**:

   **Method A: Environment Variables**
   ```bash
   export GOOGLE_OAUTH_CLIENT_ID="your-actual-client-id.apps.googleusercontent.com"
   export GOOGLE_OAUTH_CLIENT_SECRET="your-actual-client-secret"
   uv run wes
   ```

   **Method B: Credentials File**
   ```bash
   # Create credentials file
   mkdir -p ~/.wes
   cat > ~/.wes/google_oauth_credentials.json << EOF
   {
     "client_id": "your-actual-client-id.apps.googleusercontent.com",
     "client_secret": "your-actual-client-secret"
   }
   EOF
   ```

## Verification

After implementing any solution:
1. Open WES Settings
2. Go to Google tab
3. Click "Test Connection"
4. Verify successful authentication

## Important Notes

- **Service Account** is simpler and doesn't require user interaction or OAuth flow
- **OAuth** allows using your personal Google account but requires creating credentials in Google Cloud Console
- Both methods work completely offline - no website or proxy service required
- The OAuth flow opens a browser to Google's servers, but the callback is handled locally on your machine