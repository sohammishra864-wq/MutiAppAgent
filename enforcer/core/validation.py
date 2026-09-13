from __future__ import annotations
from dataclasses import dataclass
from datetime import date, timedelta
from enforcer.core.schemas import (
    ActivityType, ObservedMetrics, ReasonCode, Submission, Verdict,
    ACTIVITY_THRESHOLDS, MAX_PLAUSIBLE_SPEED,
)


@dataclass
class ValidationResult:
    problems: list[str]
    all_metrics_have_sources: bool
    contradictions: bool

    @property
    def ok(self) -> bool:
        return len(self.problems) == 0


def validate_observation(obs: ObservedMetrics) -> ValidationResult:
    """Catch hallucinated metrics. Returns structured result for grounding_score."""
    problems = []
    contradictions = False

    if obs.evidence_kind == "unclear" and (obs.distance_km or obs.duration_min):
        problems.append("metrics reported from unclear evidence")
        contradictions = True

    all_sourced = True
    for field, source_field in [
        ("distance_km", "distance_source"),
        ("duration_min", "duration_source"),
    ]:
        if getattr(obs, field) is not None and not getattr(obs, source_field):
            problems.append(f"{field} reported with no source span")
            all_sourced = False

    return ValidationResult(
        problems=problems,
        all_metrics_have_sources=all_sourced,
        contradictions=contradictions,
    )


def grounding_score(obs: ObservedMetrics, checks: ValidationResult) -> float:
    """Confidence derived from evidence quality, not model self-report."""
    s = 0.0
    legible = sum(x is not None for x in (obs.duration_min, obs.distance_km, obs.date_seen))
    s += 0.40 * (legible / 3)
    s += 0.25 if checks.all_metrics_have_sources else 0.0
    s += {"tracker_screenshot": 0.20, "watch_face": 0.15,
          "photo": 0.10, "unclear": 0.0}[obs.evidence_kind]
    s += 0.15 if not checks.contradictions else 0.0
    return round(s, 3)


def check_duplicate(image_hash: str | None, known_hashes: set[str]) -> bool:
    """R1 — deterministic, never model-decided."""
    return image_hash is not None and image_hash in known_hashes


def check_stale(obs: ObservedMetrics, claimed_date: date, tolerance_days: int = 1) -> bool:
    """R2 — deterministic date check."""
    if obs.date_seen is None:
        return False
    return abs((obs.date_seen - claimed_date).days) > tolerance_days


def check_below_threshold(
    claimed_activity: ActivityType,
    duration_min: float | None,
    distance_km: float | None,
) -> bool:
    """R4 — deterministic threshold comparison."""
    thresh = ACTIVITY_THRESHOLDS[claimed_activity]
    min_min = thresh["min_minutes"]
    min_km = thresh["min_km"]

    if min_km is not None:
        # Duration OR distance meets it
        dur_ok = duration_min is not None and duration_min >= min_min
        dist_ok = distance_km is not None and distance_km >= min_km
        return not (dur_ok or dist_ok)
    else:
        # Duration only
        if duration_min is None:
            return False  # Can't determine — leave to model
        return duration_min < min_min


def check_implausible(
    activity: ActivityType,
    duration_min: float | None,
    distance_km: float | None,
) -> bool:
    """R7 — deterministic speed plausibility."""
    if duration_min is None or distance_km is None or duration_min <= 0:
        return False
    speed_kmh = distance_km / (duration_min / 60.0)
    max_speed = MAX_PLAUSIBLE_SPEED.get(activity)
    if max_speed is None:
        return False
    return speed_kmh > max_speed


def compute_points(activity: ActivityType, is_early_morning: bool) -> int:
    base = ACTIVITY_THRESHOLDS[activity]["points"]
    return base + (1 if is_early_morning else 0)


def validate_reason_code(
    reason_code: ReasonCode | None,
    obs: ObservedMetrics,
) -> ReasonCode | None:
    """Ensure reason code is consistent with observation. Rewrite if not."""
    if reason_code is None:
        return None

    if reason_code == ReasonCode.R4_BELOW_THRESHOLD:
        if obs.duration_min is None and obs.distance_km is None:
            return ReasonCode.R6_UNVERIFIABLE

    if reason_code == ReasonCode.R5_MISMATCH:
        if obs.activity_seen is None:
            return ReasonCode.R6_UNVERIFIABLE

    if reason_code == ReasonCode.R2_STALE:
        if obs.date_seen is None:
            return ReasonCode.R6_UNVERIFIABLE

    return reason_code
