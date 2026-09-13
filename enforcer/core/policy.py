from __future__ import annotations
from pathlib import Path

_CACHED: tuple[str, str] | None = None


def load_policy(path: Path) -> str:
    global _CACHED
    text = path.read_text(encoding="utf-8")
    if _CACHED and _CACHED[0] == text:
        return _CACHED[1]
    _CACHED = (text, text)
    return text


def policy_version(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("Policy version:"):
            return line.split(":", 1)[1].strip().rstrip(".")
    return "unknown"
