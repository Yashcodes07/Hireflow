"""
scripts/auth_gmail.py
══════════════════════════════════════════════════════════════════
Run this ONCE to generate credentials/token.json
which gives your app access to Gmail + Google Calendar.

Usage:
    python scripts/auth_gmail.py

What it does:
    1. Opens browser → sign in with yashk40491@gmail.com
    2. Grant access to Gmail (send) + Calendar (create events)
    3. Saves credentials/token.json (auto-refreshes, never expires)
"""

import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar",
]

CREDENTIALS_PATH = "credentials/credentials.json"
TOKEN_PATH       = "credentials/token.json"


def main():
    os.makedirs("credentials", exist_ok=True)

    if not os.path.exists(CREDENTIALS_PATH):
        print("❌ credentials/credentials.json not found!")
        print()
        print("Steps to get it:")
        print("  1. Go to: https://console.cloud.google.com/apis/credentials?project=project-agent-491814")
        print("  2. Click: + Create Credentials → OAuth Client ID")
        print("  3. Application type: Desktop App")
        print("  4. Name: hireflow-mcp")
        print("  5. Click Create → Download JSON")
        print("  6. Save it as: credentials/credentials.json")
        return

    creds = None

    # Load existing token if available
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    # Refresh or re-authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Refreshing expired token...")
            creds.refresh(Request())
        else:
            print("🌐 Opening browser for Google OAuth...")
            print("   Sign in with: yashk40491@gmail.com")
            print("   Grant access to Gmail + Calendar")
            print()
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)

    # Save token
    with open(TOKEN_PATH, "w") as f:
        f.write(creds.to_json())

    print()
    print("✅ Authentication successful!")
    print(f"   Token saved to: {TOKEN_PATH}")
    print()
    print("Your app can now:")
    print("  ✅ Send emails via Gmail API")
    print("  ✅ Create calendar events via Google Calendar API")
    print()
    print("The token auto-refreshes — you don't need to run this again.")


if __name__ == "__main__":
    main()