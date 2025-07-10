# Google OAuth Setup Guide

This guide explains how to configure Google OAuth credentials for the Executive Summary Tool.

## Problem: "The OAuth client was not found. Error 401: invalid_client"

This error occurs when the application doesn't have valid Google OAuth credentials configured. Follow these steps to resolve it:

## Setting Up Google OAuth Credentials

### Step 1: Create a Google Cloud Project

1. Go to the [Google Cloud Console](https://console.cloud.google.com)
2. Click "Select a project" → "New Project"
3. Enter a project name (e.g., "Executive Summary Tool")
4. Click "Create"

### Step 2: Enable Required APIs

1. In your project, go to "APIs & Services" → "Library"
2. Search for and enable these APIs:
   - Google Drive API
   - Google Docs API

### Step 3: Create OAuth 2.0 Credentials

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "OAuth client ID"
3. If prompted, configure the OAuth consent screen:
   - Choose "Internal" if using a Google Workspace account
   - Choose "External" for personal accounts
   - Fill in the required fields (app name, user support email)
   - Add your email to test users if choosing "External"
4. For Application type, select "Desktop app"
5. Name it (e.g., "Executive Summary Tool Desktop")
6. Click "Create"
7. Copy the Client ID and Client Secret

### Step 4: Configure the Application

The application now supports multiple ways to configure OAuth credentials:

#### Option 1: Through the Setup Wizard (Recommended)
- When you click "Connect to Google Account" in the setup wizard, you'll be prompted to enter your OAuth credentials
- Paste the Client ID and Client Secret you copied earlier
- The credentials will be saved securely

#### Option 2: Environment Variables
```bash
export GOOGLE_OAUTH_CLIENT_ID="your-client-id.apps.googleusercontent.com"
export GOOGLE_OAUTH_CLIENT_SECRET="your-client-secret"
```

#### Option 3: Configuration File
Create a file at `~/.wes/google_oauth_credentials.json`:
```json
{
  "client_id": "your-client-id.apps.googleusercontent.com",
  "client_secret": "your-client-secret"
}
```

## Security Notes

- Never commit OAuth credentials to version control
- The application stores credentials securely using the system keyring when possible
- Client secrets are encrypted when stored in configuration files

## Troubleshooting

1. **"Access blocked" error**: Make sure you've added your email to the test users in the OAuth consent screen configuration
2. **"Redirect URI mismatch"**: The application uses `http://localhost:8080/callback` as the redirect URI. This is automatically configured for desktop applications.
3. **"Invalid client"**: Double-check that you've copied the complete Client ID and Client Secret without any extra spaces

## Additional Resources

- [Google OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [Google Cloud Console](https://console.cloud.google.com)