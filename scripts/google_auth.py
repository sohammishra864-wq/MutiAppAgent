"""One-time script to get Google OAuth tokens for Calendar + Sheets.
Run: python scripts/google_auth.py
"""
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

load_dotenv()

CREDS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "./secrets/credentials.json")
TOKEN_DIR = Path(os.getenv("GOOGLE_TOKEN_DIR", "./secrets/tokens"))
LEDGER_TOKEN_PATH = Path(os.getenv("GOOGLE_LEDGER_TOKEN_PATH", "./secrets/ledger_token.json"))

CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]
SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

TOKEN_DIR.mkdir(parents=True, exist_ok=True)
LEDGER_TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)


def do_oauth(scopes: list[str], label: str) -> Credentials:
    print(f"\n--- {label} ---")
    print(f"Scopes: {scopes}")
    print("A browser window will open. Log in and grant access.\n")
    flow = InstalledAppFlow.from_client_secrets_file(CREDS_PATH, scopes=scopes)
    creds = flow.run_local_server(port=0)
    return creds


def save_token(creds: Credentials, path: Path):
    path.write_text(creds.to_json())
    print(f"Token saved to: {path}")


if __name__ == "__main__":
    print("Google OAuth setup for The Enforcer")
    print(f"Using credentials: {CREDS_PATH}\n")

    print("Step 1/2: Calendar access")
    cal_creds = do_oauth(CALENDAR_SCOPES, "Google Calendar")
    cal_token_path = TOKEN_DIR / "calendar_token.json"
    save_token(cal_creds, cal_token_path)

    print("\nStep 2/2: Sheets access")
    sheets_creds = do_oauth(SHEETS_SCOPES, "Google Sheets")
    save_token(sheets_creds, LEDGER_TOKEN_PATH)

    print("\n✓ All done! Calendar and Sheets tokens saved.")
    print(f"  Calendar: {cal_token_path}")
    print(f"  Sheets:   {LEDGER_TOKEN_PATH}")
