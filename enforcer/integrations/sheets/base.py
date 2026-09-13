from __future__ import annotations
from typing import Protocol


class SheetsService(Protocol):
    def append_debt(self, row: list, idempotency_key: str) -> bool: ...
    def get_existing_keys(self) -> set[str]: ...
