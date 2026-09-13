from __future__ import annotations
import logging
from datetime import datetime
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from enforcer.core.schemas import TimeSlot

log = logging.getLogger(__name__)

SCOPES_READONLY = ["https://www.googleapis.com/auth/calendar.readonly"]
SCOPES_WRITE = ["https://www.googleapis.com/auth/calendar"]


def _load_creds(token_path: Path, credentials_path: Path, scopes: list[str]) -> Credentials:
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), scopes)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), scopes)
            creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json())
    return creds


class GoogleCalendarService:
    def __init__(self, credentials_path: Path, token_dir: Path, ledger_token_path: Path):
        self._credentials_path = credentials_path
        self._token_dir = token_dir
        self._ledger_token_path = ledger_token_path
        self._created_events: dict[str, str] = {}

    def _cal_token_path(self) -> Path:
        return self._token_dir / "calendar_token.json"

    def freebusy(self, member_ids: list[str], min_date: str, max_date: str) -> list[TimeSlot]:
        creds = _load_creds(self._cal_token_path(), self._credentials_path, SCOPES_WRITE)
        service = build("calendar", "v3", credentials=creds)

        # Collect calendars from per-member tokens
        calendars = []
        for mid in member_ids:
            token_path = self._token_dir / f"{mid}.json"
            if token_path.exists():
                member_creds = Credentials.from_authorized_user_file(str(token_path), SCOPES_READONLY)
                calendars.append({"id": member_creds.client_id or "primary"})
            else:
                calendars.append({"id": "primary"})

        body = {
            "timeMin": f"{min_date}T00:00:00Z",
            "timeMax": f"{max_date}T23:59:59Z",
            "items": calendars,
        }

        try:
            result = service.freebusy().query(body=body).execute()
        except Exception as e:
            log.error(f"Freebusy query failed: {e}")
            return []

        # Find free slots (simplified: return evening slots for each day)
        slots = []
        from datetime import timedelta
        current = datetime.fromisoformat(f"{min_date}T18:00:00+05:30")
        end_dt = datetime.fromisoformat(f"{max_date}T23:59:59+05:30")
        while current < end_dt:
            slots.append(TimeSlot(start=current, end=current + timedelta(hours=2)))
            current += timedelta(days=1)

        return slots[:5]

    def create_event(self, slot: TimeSlot, summary: str, attendees: list[str], idempotency_key: str) -> str:
        if idempotency_key in self._created_events:
            return self._created_events[idempotency_key]

        creds = _load_creds(self._cal_token_path(), self._credentials_path, SCOPES_WRITE)
        service = build("calendar", "v3", credentials=creds)

        event = {
            "summary": summary,
            "start": {"dateTime": slot.start.isoformat()},
            "end": {"dateTime": slot.end.isoformat()},
            "attendees": [{"email": a} for a in attendees],
        }

        result = service.events().insert(
            calendarId="primary",
            body=event,
            sendUpdates="all",
        ).execute()

        event_id = result.get("id", idempotency_key)
        self._created_events[idempotency_key] = event_id
        log.info(f"Created calendar event: {event_id}")
        return event_id

    def delete_event(self, event_id: str) -> None:
        creds = _load_creds(self._cal_token_path(), self._credentials_path, SCOPES_WRITE)
        service = build("calendar", "v3", credentials=creds)
        service.events().delete(calendarId="primary", eventId=event_id).execute()
