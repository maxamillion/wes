#!/usr/bin/env python
"""Setup script for Google OAuth credentials."""

import json
import os
import sys
from pathlib import Path


def setup_oauth():
    """Interactive setup for Google OAuth credentials."""
    print("=== WES Google OAuth Setup ===\n")
    
    print("This script will help you set up Google OAuth for WES.")
    print("You'll need to create OAuth credentials in Google Cloud Console first.\n")
    
    print("Steps to create OAuth credentials:")
    print("1. Go to https://console.cloud.google.com")
    print("2. Create a new project or select an existing one")
    print("3. Enable Google Docs API and Google Drive API")
    print("4. Go to 'APIs & Services' > 'Credentials'")
    print("5. Click 'Create Credentials' > 'OAuth client ID'")
    print("6. Choose 'Desktop app' as the application type")
    print("7. Name it 'WES Desktop App'")
    print("8. Download the credentials or copy the Client ID and Secret\n")
    
    input("Press Enter when you have your credentials ready...")
    
    # Get credentials from user
    print("\nEnter your OAuth credentials:")
    client_id = input("Client ID: ").strip()
    client_secret = input("Client Secret: ").strip()
    
    if not client_id or not client_secret:
        print("\nError: Both Client ID and Client Secret are required.")
        sys.exit(1)
    
    # Validate format
    if not client_id.endswith(".apps.googleusercontent.com"):
        print("\nWarning: Client ID doesn't look like a valid Google OAuth client ID.")
        print("It should end with '.apps.googleusercontent.com'")
        confirm = input("Continue anyway? (y/N): ")
        if confirm.lower() != 'y':
            sys.exit(1)
    
    # Ask where to save
    print("\nWhere would you like to save the credentials?")
    print("1. As environment variables (recommended for development)")
    print("2. In a credentials file (~/.wes/google_oauth_credentials.json)")
    print("3. Both")
    
    choice = input("\nChoice (1-3): ").strip()
    
    saved_locations = []
    
    # Save as environment variables
    if choice in ['1', '3']:
        print("\nTo use environment variables, add these to your shell profile:")
        print(f"export GOOGLE_OAUTH_CLIENT_ID=\"{client_id}\"")
        print(f"export GOOGLE_OAUTH_CLIENT_SECRET=\"{client_secret}\"")
        
        # Try to detect shell
        shell = os.environ.get('SHELL', '').split('/')[-1]
        if shell in ['bash', 'zsh']:
            profile_file = f".{shell}rc"
            print(f"\nOr add them to ~/{profile_file}")
        
        saved_locations.append("environment variables")
    
    # Save as credentials file
    if choice in ['2', '3']:
        wes_dir = Path.home() / ".wes"
        wes_dir.mkdir(exist_ok=True)
        
        cred_file = wes_dir / "google_oauth_credentials.json"
        
        credentials = {
            "client_id": client_id,
            "client_secret": client_secret
        }
        
        try:
            with open(cred_file, 'w') as f:
                json.dump(credentials, f, indent=2)
            
            # Set permissions to be readable only by user
            os.chmod(cred_file, 0o600)
            
            print(f"\nCredentials saved to: {cred_file}")
            saved_locations.append(str(cred_file))
        except Exception as e:
            print(f"\nError saving credentials file: {e}")
    
    # Summary
    print("\n=== Setup Complete ===")
    if saved_locations:
        print(f"Credentials saved to: {', '.join(saved_locations)}")
        print("\nYou can now:")
        print("1. Run WES")
        print("2. Go to Settings > Google")
        print("3. Select 'OAuth 2.0' and click 'Authenticate with Google'")
    else:
        print("No credentials were saved.")
    
    print("\nNote: If you prefer not to use OAuth, you can always use Service Account")
    print("authentication instead, which doesn't require this setup.")


if __name__ == "__main__":
    try:
        setup_oauth()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled.")
        sys.exit(1)