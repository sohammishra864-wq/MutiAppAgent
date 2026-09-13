from __future__ import annotations
from datetime import date, datetime
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field
import uuid


class ActivityType(str, Enum):
    RUN = "run"
    CYCLE = "cycle"
    GYM = "gym"
    SWIM = "swim"
    WALK = "walk"
    SPORT = "sport"
    HOME_WORKOUT = "home_workout"


class ReasonCode(str, Enum):
    R1_DUPLICATE = "R1_DUPLICATE"
    R2_STALE = "R2_STALE"
    R3_NOT_SUBMITTER = "R3_NOT_SUBMITTER"
    R4_BELOW_THRESHOLD = "R4_BELOW_THRESHOLD"
    R5_MISMATCH = "R5_MISMATCH"
    R6_UNVERIFIABLE = "R6_UNVERIFIABLE"
    R7_IMPLAUSIBLE = "R7_IMPLAUSIBLE"


ACTIVITY_THRESHOLDS: dict[ActivityType, dict] = {
    ActivityType.RUN:          {"min_minutes": 20, "min_km": 3.0, "points": 2},
    ActivityType.CYCLE:        {"min_minutes": 30, "min_km": 8.0, "points": 2},
    ActivityType.GYM:          {"min_minutes": 30, "min_km": None, "points": 2},
    ActivityType.SWIM:         {"min_minutes": 20, "min_km": None, "points": 2},
    ActivityType.WALK:         {"min_minutes": 45, "min_km": 5.0, "points": 1},
    ActivityType.SPORT:        {"min_minutes": 30, "min_km": None, "points": 2},
    ActivityType.HOME_WORKOUT: {"min_minutes": 25, "min_km": None, "points": 1},
}

# Speed limits for R7_IMPLAUSIBLE (km/h)
MAX_PLAUSIBLE_SPEED: dict[ActivityType, float] = {
    ActivityType.RUN:   25.0,
    ActivityType.CYCLE: 60.0,
    ActivityType.SWIM:  8.0,
    ActivityType.WALK:  10.0,
}


def _gen_id() -> str:
    return uuid.uuid4().hex[:12]


class Submission(BaseModel):
    id: str = Field(default_factory=_gen_id)
    member_id: str
    guild_id: str
    submitted_at: datetime
    claimed_activity: ActivityType
    claimed_duration_min: int | None = None
    claimed_distance_km: float | None = None
    image_ref: str
    image_hash: str | None = None
    note: str | None = None
    correlation_id: str = Field(default_factory=_gen_id)


class ObservedMetrics(BaseModel):
    activity_seen: str | None = None
    duration_min: float | None = None
    duration_source: str | None = None
    distance_km: float | None = None
    distance_source: str | None = None
    date_seen: date | None = None
    date_source: str | None = None
    evidence_kind: Literal["tracker_screenshot", "photo", "watch_face", "unclear"] = "unclear"


class Verdict(BaseModel):
    submission_id: str
    guild_id: str
    member_id: str
    verdict: Literal["ACCEPT", "REJECT", "ESCALATE"]
    reason_code: ReasonCode | None = None
    points: int = 0
    confidence: float = 0.0
    rationale: str = ""
    observed: ObservedMetrics = Field(default_factory=ObservedMetrics)
    image_hash: str | None = None
    grounding_score: float = 0.0
    policy_version: str = "v1"
    judged_at: datetime | None = None
    correlation_id: str = ""


class TimeSlot(BaseModel):
    start: datetime
    end: datetime


class PlannedAction(BaseModel):
    kind: str
    idempotency_key: str
    description: str
    params: dict = Field(default_factory=dict)


class ConsequencePlan(BaseModel):
    loser_id: str
    loser_name: str = ""
    guild_id: str
    week_start: date
    proposed_slots: list[TimeSlot] = Field(default_factory=list)
    chosen_slot: TimeSlot | None = None
    venue_hint: str | None = None
    debt_amount: float = 500.0
    playlist_theme: str = ""
    actions: list[PlannedAction] = Field(default_factory=list)


class Standing(BaseModel):
    member_id: str
    guild_id: str
    points: int = 0
    valid_days: int = 0
    first_submission_at: datetime | None = None
