from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class RealClock:
    def __init__(self, tz: timezone | None = None):
        self._tz = tz

    def now(self) -> datetime:
        return datetime.now(self._tz)


class SimulatedClock:
    def __init__(self, start: datetime):
        self._now = start

    def now(self) -> datetime:
        return self._now

    def advance(self, **kwargs) -> None:
        self._now += timedelta(**kwargs)
