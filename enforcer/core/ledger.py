from __future__ import annotations
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Protocol

from enforcer.core.schemas import Verdict


class LedgerRepo(Protocol):
    def append(self, verdict: Verdict) -> None: ...
    def read_all(self, guild_id: str | None = None) -> list[Verdict]: ...
    def recent_hashes(self, guild_id: str, days: int = 14) -> set[str]: ...


class JsonlLedger:
    def __init__(self, path: Path):
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, verdict: Verdict) -> None:
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(verdict.model_dump_json() + "\n")

    def read_all(self, guild_id: str | None = None) -> list[Verdict]:
        if not self._path.exists():
            return []
        verdicts = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            v = Verdict.model_validate_json(line)
            if guild_id and v.guild_id != guild_id:
                continue
            verdicts.append(v)
        return verdicts

    def recent_hashes(self, guild_id: str, days: int = 14) -> set[str]:
        cutoff = datetime.now().date() - timedelta(days=days)
        hashes: set[str] = set()
        for v in self.read_all(guild_id):
            if v.judged_at and v.judged_at.date() >= cutoff and v.image_hash:
                hashes.add(v.image_hash)
        return hashes
