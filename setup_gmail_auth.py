"""
setup_gmail_auth.py — One-time Gmail authorization.
Uses copy-paste flow — NO local server, NO port conflicts, NO redirect URI issues.

Usage:  uv run python setup_gmail_auth.py
"""
import os
import webbrowser
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES      = ["https://www.googleapis.com/auth/gmail.readonly"]
SECRET_FILE = "gmail_client_secret.json"
TOKEN_FILE  = "gmail_token.json"

def main():
    # If token already exists and is valid, just confirm
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        if creds.valid:
            print("✅ Gmail already connected! Token is valid.")
            print("   Run the webhook:  bash run_webhook.sh")
            return
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_FILE, "w") as f:
                f.write(creds.to_json())
            print("✅ Token refreshed successfully!")
            return

    # Use out-of-band (copy-paste) flow — no local server needed
    flow = Flow.from_client_secrets_file(
        SECRET_FILE,
        scopes=SCOPES,
        redirect_uri="urn:ietf:wg:oauth:2.0:oob",
    )

    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    print()
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  INBOX DIGEST — Gmail Authorization")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()
    print("Opening browser... Sign in with Aryavivekiitbhu@gmail.com")
    print()

    webbrowser.open(auth_url)

    print("After you click 'Allow', Google will show a CODE.")
    print("Copy that code and paste it below.")
    print()
    code = input("  ▶ Paste the code here: ").strip()

    flow.fetch_token(code=code)
    creds = flow.credentials

    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())

    print()
    print("✅ Gmail connected! Token saved.")
    print()
    print("🎉 Now restart the webhook:")
    print("   bash run_webhook.sh")
    print()
    print("Then WhatsApp any message to +1 (555) 173-3583")
    print("to get your real inbox digest! 📬")

if __name__ == "__main__":
    main()
