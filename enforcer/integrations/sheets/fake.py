from __future__ import annotations
import logging

log = logging.getLogger(__name__)


class FakeSheetsService:
    def __init__(self):
        self._rows: dict[str, list] = {}

    def append_debt(self, row: list, idempotency_key: str) -> bool:
        if idempotency_key in self._rows:
            log.info(f"[FAKE] debt row {idempotency_key} already exists, skipping")
            return False
        self._rows[idempotency_key] = row
        log.info(f"[FAKE] appended debt row {idempotency_key}: {row}")
        return True

    def get_existing_keys(self) -> set[str]:
        return set(self._rows.keys())
