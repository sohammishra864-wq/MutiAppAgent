from __future__ import annotations
import hashlib
import logging
from datetime import date
from pathlib import Path

from enforcer.core.clock import Clock
from enforcer.core.schemas import (
    ActivityType, ObservedMetrics, ReasonCode, Submission, Verdict,
    ACTIVITY_THRESHOLDS,
)
from enforcer.core.validation import (
    ValidationResult, check_below_threshold, check_duplicate, check_implausible,
    check_stale, compute_points, grounding_score, validate_observation,
    validate_reason_code,
)
from enforcer.core.policy import load_policy, policy_version
from enforcer.llm.client import BedrockClient, parse_tool_output

log = logging.getLogger(__name__)

OBSERVED_METRICS_SCHEMA = ObservedMetrics.model_json_schema()


def hash_image(image_bytes: bytes) -> str:
    return hashlib.sha256(image_bytes).hexdigest()


def detect_image_format(image_bytes: bytes) -> str:
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if image_bytes[:2] == b"\xff\xd8":
        return "jpeg"
    if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "webp"
    return "jpeg"


def extract_exif_date(image_bytes: bytes) -> date | None:
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(image_bytes))
        exif = img.getexif()
        if not exif:
            return None
        for tag in (36867, 306):
            val = exif.get(tag)
            if val:
                return date.fromisoformat(val.split(" ")[0].replace(":", "-"))
    except Exception:
        pass
    return None


def judge(
    submission: Submission,
    image_bytes: bytes,
    llm: BedrockClient,
    clock: Clock,
    known_hashes: set[str],
    policy_path: Path,
    extract_prompt_path: Path = Path("enforcer/llm/prompts/extract.md"),
) -> Verdict:
    now = clock.now()
    img_hash = hash_image(image_bytes)
    submission.image_hash = img_hash
    pol_version = policy_version(policy_path)
    claimed_date = submission.submitted_at.date()

    def _v(verdict: str, rc: ReasonCode | None, pts: int, g_score: float,
           rationale: str, obs: ObservedMetrics) -> Verdict:
        return Verdict(
            submission_id=submission.id,
            guild_id=submission.guild_id,
            member_id=submission.member_id,
            verdict=verdict,
            reason_code=rc,
            points=pts,
            confidence=g_score,
            grounding_score=g_score,
            rationale=rationale,
            observed=obs,
            image_hash=img_hash,
            policy_version=pol_version,
            judged_at=now,
            correlation_id=submission.correlation_id,
        )

    # --- Deterministic pre-checks (before any model call) ---

    # R1: duplicate image hash
    if check_duplicate(img_hash, known_hashes):
        return _v("REJECT", ReasonCode.R1_DUPLICATE, 0, 1.0,
                   "This image has already been submitted.", ObservedMetrics())

    # R2: EXIF date check
    exif_date = extract_exif_date(image_bytes)
    if exif_date is not None and check_stale(
        ObservedMetrics(date_seen=exif_date, date_source="EXIF"), claimed_date,
    ):
        return _v("REJECT", ReasonCode.R2_STALE, 0, 1.0,
                   f"Image EXIF date ({exif_date}) doesn't match the submission date.",
                   ObservedMetrics(date_seen=exif_date, date_source="EXIF"))

    # --- Pass 1: EXTRACT (image only, claim withheld) ---
    extract_prompt = extract_prompt_path.read_text(encoding="utf-8")
    img_format = detect_image_format(image_bytes)

    raw_obs = llm.converse_with_image(
        system_prompt=extract_prompt,
        user_text="Examine this image and report what you observe. Leave fields null if not legible.",
        image_bytes=image_bytes,
        image_format=img_format,
        tool_schema=OBSERVED_METRICS_SCHEMA,
        tool_name="ObservedMetrics",
    )

    obs = parse_tool_output(raw_obs, ObservedMetrics)
    if obs is None:
        return _v("ESCALATE", None, 0, 0.0,
                   "Could not extract metrics from the image.", ObservedMetrics())

    # --- Hallucination guards ---
    checks = validate_observation(obs)
    g_score = grounding_score(obs, checks)

    if not checks.ok:
        log.warning(f"Grounding violations: {checks.problems}")
        return _v("ESCALATE", None, 0, g_score,
                   f"Extraction flagged: {'; '.join(checks.problems)}.", obs)

    # --- Pass 2: COMPARE (deterministic, no model) ---

    # R2: date from image vs claimed date
    if obs.date_seen is not None and check_stale(obs, claimed_date):
        return _v("REJECT", ReasonCode.R2_STALE, 0, g_score,
                   f"Image date ({obs.date_seen}) doesn't match submission date ({claimed_date}).", obs)

    # R6: no metrics at all
    if obs.evidence_kind == "unclear" or (
        obs.duration_min is None and obs.distance_km is None and obs.activity_seen is None
    ):
        return _v("REJECT", ReasonCode.R6_UNVERIFIABLE, 0, g_score,
                   "No readable metrics or identifiable activity in the image.", obs)

    # R7: implausible speed
    if check_implausible(submission.claimed_activity, obs.duration_min, obs.distance_km):
        return _v("REJECT", ReasonCode.R7_IMPLAUSIBLE, 0, g_score,
                   "The reported speed is not physically plausible.", obs)

    # R4: below threshold (use observed values, not claimed)
    if obs.duration_min is not None or obs.distance_km is not None:
        if check_below_threshold(submission.claimed_activity, obs.duration_min, obs.distance_km):
            return _v("REJECT", ReasonCode.R4_BELOW_THRESHOLD, 0, g_score,
                       "Activity doesn't meet the minimum threshold for the claimed type.", obs)

    # R5: activity mismatch
    if obs.activity_seen and _activity_clearly_mismatches(obs.activity_seen, submission.claimed_activity):
        return _v("REJECT", ReasonCode.R5_MISMATCH, 0, g_score,
                   f"Image shows '{obs.activity_seen}' but claim is '{submission.claimed_activity.value}'.", obs)

    # --- Grounding score gating ---

    if g_score < 0.50:
        return _v("ESCALATE", ReasonCode.R6_UNVERIFIABLE, 0, g_score,
                   "Evidence quality too low to make a confident judgment.", obs)

    if g_score < 0.75:
        # --- Monitor pass (optional 3rd model call, only for borderline) ---
        monitor_result = _run_monitor_pass(llm, obs, submission, policy_path)
        if monitor_result == "confirmed":
            is_early = submission.submitted_at.hour < 7
            points = compute_points(submission.claimed_activity, is_early)
            return _v("ACCEPT", None, points, g_score,
                       "Activity verified (confirmed by monitor pass).", obs)
        return _v("ESCALATE", None, 0, g_score,
                   "Evidence is present but grounding score is below threshold.", obs)

    # --- ACCEPT ---
    is_early = submission.submitted_at.hour < 7
    points = compute_points(submission.claimed_activity, is_early)
    return _v("ACCEPT", None, points, g_score,
               "Activity verified and meets the threshold.", obs)


def _run_monitor_pass(
    llm: BedrockClient,
    obs: ObservedMetrics,
    submission: Submission,
    policy_path: Path,
) -> str:
    """Pass 3: narrow question — does the observation actually support an ACCEPT?
    Only called for borderline grounding scores (0.50–0.75). Actor/Monitor split."""
    policy_text = load_policy(policy_path)
    obs_summary = []
    if obs.activity_seen:
        obs_summary.append(f"Activity seen: {obs.activity_seen}")
    if obs.duration_min is not None:
        obs_summary.append(f"Duration: {obs.duration_min} min (source: {obs.duration_source})")
    if obs.distance_km is not None:
        obs_summary.append(f"Distance: {obs.distance_km} km (source: {obs.distance_source})")
    if obs.evidence_kind:
        obs_summary.append(f"Evidence type: {obs.evidence_kind}")

    user_text = (
        f"The extraction pass observed the following from a submission image:\n"
        f"{chr(10).join(obs_summary)}\n\n"
        f"The user claims this is a '{submission.claimed_activity.value}' activity.\n\n"
        f"Does this observation plausibly support that claim? "
        f"Answer 'confirmed' if yes, 'disputed' if no."
    )

    # Simple text call — no tool use needed, just a yes/no
    monitor_schema = {
        "type": "object",
        "properties": {"result": {"type": "string", "enum": ["confirmed", "disputed"]}},
        "required": ["result"],
    }

    raw = llm.converse_text(
        system_prompt=f"You are a monitor verifying whether an observation supports a fitness claim.\n\nPolicy:\n{policy_text}",
        user_text=user_text,
        tool_schema=monitor_schema,
        tool_name="MonitorResult",
    )

    if raw and raw.get("result") == "confirmed":
        return "confirmed"
    return "disputed"


def _activity_clearly_mismatches(seen: str, claimed: ActivityType) -> bool:
    seen_lower = seen.lower()
    claim_keywords: dict[ActivityType, list[str]] = {
        ActivityType.RUN: ["run", "jog", "treadmill"],
        ActivityType.CYCLE: ["cycle", "bike", "cycling", "biking"],
        ActivityType.GYM: ["gym", "weight", "strength", "bench", "squat", "deadlift"],
        ActivityType.SWIM: ["swim", "pool", "lap"],
        ActivityType.WALK: ["walk", "hike", "hiking", "step"],
        ActivityType.SPORT: ["football", "badminton", "tennis", "basketball", "cricket", "sport"],
        ActivityType.HOME_WORKOUT: ["yoga", "home", "workout", "stretch", "pilates"],
    }
    matched_activities = []
    for activity, keywords in claim_keywords.items():
        if any(kw in seen_lower for kw in keywords):
            matched_activities.append(activity)
    if not matched_activities:
        return False
    return claimed not in matched_activities
