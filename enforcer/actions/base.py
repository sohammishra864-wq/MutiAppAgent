from __future__ import annotations
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger(__name__)


@dataclass
class ActionResult:
    success: bool
    kind: str
    idempotency_key: str
    dry_run: bool = False
    result: Any = None
    error: str | None = None
    latency_ms: float = 0


def log_action(path: Path, result: ActionResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": time.time(),
        "kind": result.kind,
        "idempotency_key": result.idempotency_key,
        "dry_run": result.dry_run,
        "success": result.success,
        "latency_ms": result.latency_ms,
        "error": result.error,
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def execute_action(
    kind: str,
    idempotency_key: str,
    fn: Callable[[], Any],
    description: str,
    dry_run: bool = False,
    log_path: Path | None = None,
) -> ActionResult:
    if dry_run:
        result = ActionResult(
            success=True, kind=kind, idempotency_key=idempotency_key,
            dry_run=True, result=description,
        )
        log.info(f"[DRY RUN] {kind}: {description}")
        if log_path:
            log_action(log_path, result)
        return result

    t0 = time.monotonic()
    try:
        out = fn()
        elapsed = (time.monotonic() - t0) * 1000
        result = ActionResult(
            success=True, kind=kind, idempotency_key=idempotency_key,
            result=out, latency_ms=elapsed,
        )
    except Exception as e:
        elapsed = (time.monotonic() - t0) * 1000
        result = ActionResult(
            success=False, kind=kind, idempotency_key=idempotency_key,
            error=str(e), latency_ms=elapsed,
        )
        log.error(f"Action {kind} ({idempotency_key}) failed: {e}")

    if log_path:
        log_action(log_path, result)
    return result
