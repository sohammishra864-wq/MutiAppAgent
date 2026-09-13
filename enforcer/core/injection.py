"""Detect and log prompt injection attempts in user-submitted text."""
from __future__ import annotations
import logging
import re

log = logging.getLogger(__name__)

INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(previous|prior|all|above)\s+(instructions?|rules?|prompts?)", re.I),
    re.compile(r"(you\s+are|act\s+as|pretend|new\s+instructions?)", re.I),
    re.compile(r"(system\s*prompt|override|bypass|disregard)", re.I),
    re.compile(r"accept\s+this\s+(submission|workout|entry)", re.I),
    re.compile(r"(give|award)\s+(me\s+)?(full\s+)?points", re.I),
]


def detect_injection(text: str | None) -> bool:
    if not text:
        return False
    return any(p.search(text) for p in INJECTION_PATTERNS)


def log_injection_attempt(member_id: str, text: str, correlation_id: str) -> None:
    log.warning(
        f"Injection attempt detected | member={member_id} "
        f"correlation={correlation_id} text={text[:200]!r}"
    )
