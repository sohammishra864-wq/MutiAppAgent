"""Simulate a full week from a fixture file, fast-forwarding through the clock."""
from __future__ import annotations
import json
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from enforcer.core.clock import SimulatedClock
from enforcer.core.config import Settings
from enforcer.core.schemas import (
    ActivityType, ConsequencePlan, Submission, Verdict, Standing,
)
from enforcer.core.ledger import JsonlLedger
from enforcer.core.leaderboard import leaderboard, find_loser
from enforcer.agent.judge import judge
from enforcer.llm.client import BedrockClient
from enforcer.actions.consequence import execute_consequence_chain
from enforcer.integrations.calendar.fake import FakeCalendarService
from enforcer.integrations.sheets.fake import FakeSheetsService
from enforcer.integrations.spotify.fake import FakeSpotifyService

log = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))


def load_fixture(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_simulation(
    fixture_path: Path,
    settings: Settings | None = None,
    use_real_llm: bool = True,
) -> dict:
    settings = settings or Settings()
    fixture = load_fixture(fixture_path)

    week_start = date.fromisoformat(fixture["week_start"])
    week_end = date.fromisoformat(fixture["week_end"])
    members = fixture["members"]
    submissions_data = fixture["submissions"]

    start_dt = datetime.combine(week_start, datetime.min.time()).replace(tzinfo=IST)
    clock = SimulatedClock(start_dt)

    ledger = JsonlLedger(settings.enforcer_ledger_path)
    llm = BedrockClient(settings.aws_region, settings.bedrock_vl_model_id, bearer_token=settings.aws_bearer_token_bedrock) if use_real_llm else None

    verdicts: list[Verdict] = []

    for entry in sorted(submissions_data, key=lambda e: e["submitted_at"]):
        ts = datetime.fromisoformat(entry["submitted_at"])
        clock._now = ts

        sub = Submission(
            member_id=entry["member_id"],
            guild_id=settings.discord_guild_id,
            submitted_at=ts,
            claimed_activity=ActivityType(entry["claimed_activity"]),
            claimed_duration_min=entry.get("claimed_duration_min"),
            claimed_distance_km=entry.get("claimed_distance_km"),
            image_ref=entry.get("image_ref", "fixture"),
            note=entry.get("note"),
        )

        if use_real_llm and llm:
            # Load image from fixture reference
            img_path = fixture_path.parent / entry.get("image", "")
            if img_path.exists():
                image_bytes = img_path.read_bytes()
            else:
                image_bytes = b"\xff\xd8\xff\xe0"  # minimal JPEG stub
            v = judge(
                submission=sub,
                image_bytes=image_bytes,
                llm=llm,
                clock=clock,
                known_hashes=set(),
                policy_path=settings.enforcer_policy_path,
            )
        else:
            # Offline simulation — use expected verdict from fixture
            v = Verdict(
                submission_id=sub.id,
                guild_id=sub.guild_id,
                member_id=sub.member_id,
                verdict=entry.get("expected_verdict", "ACCEPT"),
                points=entry.get("expected_points", 2),
                confidence=0.9,
                rationale="Simulated verdict",
                policy_version="v1",
                judged_at=ts,
                correlation_id=sub.correlation_id,
            )

        ledger.append(v)
        verdicts.append(v)
        log.info(f"[{ts.date()}] {sub.member_id}: {v.verdict} ({v.points} pts)")

    # Settlement
    standings = leaderboard(verdicts, week_start, week_end)
    loser = find_loser(standings, members, settings.discord_guild_id)

    log.info(f"\nStandings for week {week_start}:")
    for s in standings:
        log.info(f"  {s.member_id}: {s.points} pts, {s.valid_days} days")
    log.info(f"Last place: {loser}")

    # Execute consequences with fakes
    if loser:
        plan = ConsequencePlan(
            loser_id=loser,
            guild_id=settings.discord_guild_id,
            week_start=week_start,
            debt_amount=settings.upi_default_amount,
            playlist_theme="workout motivation gone wrong",
        )
        results = execute_consequence_chain(
            plan=plan,
            calendar=FakeCalendarService(),
            sheets=FakeSheetsService(),
            spotify=FakeSpotifyService(),
            dry_run=settings.enforcer_dry_run,
            log_path=settings.enforcer_action_log_path,
        )
    else:
        results = []

    return {
        "standings": standings,
        "loser": loser,
        "verdicts": verdicts,
        "action_results": results,
    }


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    fixture = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("evals/fixtures/week_01.json")
    use_llm = "--offline" not in sys.argv

    result = run_simulation(fixture, use_real_llm=use_llm)
    print(f"\nLoser: {result['loser']}")
    print(f"Verdicts: {len(result['verdicts'])}")
    print(f"Actions: {len(result['action_results'])} "
          f"({sum(1 for r in result['action_results'] if r.success)} succeeded)")
