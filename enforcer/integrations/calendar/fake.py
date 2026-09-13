from __future__ import annotations
import logging
from datetime import datetime, timedelta
from enforcer.core.schemas import TimeSlot

log = logging.getLogger(__name__)


class FakeCalendarService:
    def __init__(self):
        self._events: dict[str, dict] = {}

    def freebusy(self, member_ids: list[str], min_date: str, max_date: str) -> list[TimeSlot]:
        tomorrow = datetime.fromisoformat(min_date) + timedelta(days=1)
        slot = TimeSlot(
            start=tomorrow.replace(hour=18, minute=0),
            end=tomorrow.replace(hour=20, minute=0),
        )
        log.info(f"[FAKE] freebusy for {member_ids} -> {slot}")
        return [slot]

    def create_event(self, slot: TimeSlot, summary: str, attendees: list[str], idempotency_key: str) -> str:
        if idempotency_key in self._events:
            log.info(f"[FAKE] event {idempotency_key} already exists, skipping")
            return idempotency_key
        self._events[idempotency_key] = {"slot": slot, "summary": summary, "attendees": attendees}
        log.info(f"[FAKE] created event {idempotency_key}: {summary}")
        return idempotency_key

    def delete_event(self, event_id: str) -> None:
        self._events.pop(event_id, None)
        log.info(f"[FAKE] deleted event {event_id}")
