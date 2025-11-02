#!/usr/bin/env python3
"""
OAuth Token Generator - RUN THIS ON YOUR LOCAL LAPTOP

This script generates oauth_token.json for your personal Google account.
Run this on your laptop, NOT in the Docker container.

Prerequisites:
    pip install google-auth google-auth-oauthlib google-auth-httplib2

Steps:
    1. Download this file to your laptop
    2. Put oauth_client_secret.json in the same folder
    3. Run: python3 generate_oauth_token.py
    4. Browser opens → login with your personal email
    5. Copy generated oauth_token.json back to container
"""

import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow

def main():
    print("=" * 60)
    print("🔐 OAuth Token Generator for Patent Pipeline")
    print("=" * 60)
    print()
    print("📍 Current directory:", os.getcwd())
    print()

    # Check for client secret file
    client_secret_file = "oauth_client_secret.json"

    if not os.path.exists(client_secret_file):
        print("❌ ERROR: oauth_client_secret.json NOT FOUND!")
        print()
        print("Please download it:")
        print("1. Go to: https://console.cloud.google.com/apis/credentials")
        print("2. Find your OAuth 2.0 Client ID")
        print("3. Click download button (⬇)")
        print("4. Save as: oauth_client_secret.json")
        print("5. Put it in the SAME folder as this script")
        print()
        return

    print("✅ Found: oauth_client_secret.json")
    print()

    # Set up OAuth flow
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]

    flow = InstalledAppFlow.from_client_secrets_file(
        client_secret_file,
        scopes=scopes
    )

    print("🌐 Starting OAuth authentication...")
    print("👤 Browser will open - log in with your PERSONAL email")
    print()

    # Try different ports
    ports_to_try = [8080, 8081, 8082, 0]  # 0 = random available port
    creds = None

    for port in ports_to_try:
        try:
            if port == 0:
                print("🔄 Trying random available port...")
            else:
                print(f"🔄 Trying port {port}...")

            creds = flow.run_local_server(port=port)
            print(f"✅ Successfully authenticated on port {port if port != 0 else 'random'}!")
            break
        except OSError as e:
            if port == 0:
                print(f"❌ All ports failed: {e}")
                return
            print(f"⚠️  Port {port} busy, trying next...")
            continue

    if not creds:
        print("❌ Authentication failed!")
        return

    # Save token
    token_info = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': creds.scopes,
        'expiry': creds.expiry.isoformat() if creds.expiry else None
    }

    output_file = 'oauth_token.json'
    with open(output_file, 'w') as f:
        json.dump(token_info, f, indent=2)

    print()
    print("=" * 60)
    print("✅ SUCCESS! Token saved:", output_file)
    print("=" * 60)
    print()
    print("📋 Next steps:")
    print("1. You should see 'oauth_token.json' in this folder")
    print("2. Copy it to the Docker container:")
    print()
    print("   docker cp oauth_token.json patent-pipeline:/app/AI_pipeline/google_sheets_integration/")
    print()
    print("3. Verify in container:")
    print()
    print("   docker exec patent-pipeline ls -la /app/AI_pipeline/google_sheets_integration/oauth_token.json")
    print()
    print("🎉 Done! Your web interface can now use Google Sheets!")

if __name__ == "__main__":
    main()
