"""One-time script to get Calendar OAuth token. Run: python scripts/calendar_auth.py"""
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
import os
from dotenv import load_dotenv

load_dotenv()

creds_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "./secrets/credentials.json")
flow = InstalledAppFlow.from_client_secrets_file(
    creds_path, scopes=["https://www.googleapis.com/auth/calendar"]
)
creds = flow.run_local_server(port=0)
p = Path("secrets/tokens/calendar_token.json")
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(creds.to_json())
print("Calendar token saved!")
