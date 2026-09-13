from __future__ import annotations
import logging
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class LiveSheetsService:
    def __init__(self, sheet_id: str, token_path: Path, credentials_path: Path, debts_range: str = "debts!A:G"):
        self._sheet_id = sheet_id
        self._token_path = token_path
        self._credentials_path = credentials_path
        self._debts_range = debts_range

    def _get_service(self):
        creds = None
        if self._token_path.exists():
            creds = Credentials.from_authorized_user_file(str(self._token_path), SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
        return build("sheets", "v4", credentials=creds)

    def get_existing_keys(self) -> set[str]:
        service = self._get_service()
        result = service.spreadsheets().values().get(
            spreadsheetId=self._sheet_id,
            range="debts!A2:A",
        ).execute()
        rows = result.get("values", [])
        return {r[0] for r in rows if r}

    def append_debt(self, row: list, idempotency_key: str) -> bool:
        existing = self.get_existing_keys()
        if idempotency_key in existing:
            log.info(f"Debt row {idempotency_key} already exists, skipping")
            return False

        service = self._get_service()
        service.spreadsheets().values().append(
            spreadsheetId=self._sheet_id,
            range=self._debts_range,
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()
        log.info(f"Appended debt row: {idempotency_key}")
        return True
