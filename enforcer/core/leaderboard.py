from __future__ import annotations
from datetime import date, datetime, timedelta
from enforcer.core.schemas import Standing, Verdict


def leaderboard(verdicts: list[Verdict], week_start: date, week_end: date) -> list[Standing]:
    by_member: dict[str, Standing] = {}

    for v in verdicts:
        if v.verdict != "ACCEPT" or v.judged_at is None:
            continue
        d = v.judged_at.date()
        if not (week_start <= d <= week_end):
            continue

        key = v.member_id
        if key not in by_member:
            by_member[key] = Standing(
                member_id=v.member_id,
                guild_id=v.guild_id,
                points=0,
                valid_days=0,
                first_submission_at=v.judged_at,
            )

        s = by_member[key]
        s.points += v.points
        # Track unique valid days
        # (recounted below for simplicity)
        if s.first_submission_at is None or v.judged_at < s.first_submission_at:
            s.first_submission_at = v.judged_at

    # Count distinct valid days per member
    for v in verdicts:
        if v.verdict != "ACCEPT" or v.judged_at is None:
            continue
        d = v.judged_at.date()
        if not (week_start <= d <= week_end):
            continue
        # We need a set per member — build it
    days_map: dict[str, set[date]] = {}
    for v in verdicts:
        if v.verdict != "ACCEPT" or v.judged_at is None:
            continue
        d = v.judged_at.date()
        if not (week_start <= d <= week_end):
            continue
        days_map.setdefault(v.member_id, set()).add(d)

    for mid, days in days_map.items():
        if mid in by_member:
            by_member[mid].valid_days = len(days)

    standings = list(by_member.values())
    # Sort: most points first; ties broken by most valid days, then earliest first submission
    standings.sort(key=lambda s: (-s.points, -s.valid_days, s.first_submission_at or datetime.max))
    return standings


def find_loser(standings: list[Standing], all_member_ids: list[str], guild_id: str) -> str | None:
    if not all_member_ids:
        return None

    member_set = set(s.member_id for s in standings)
    # Members with zero submissions are automatic last place
    zero_members = [m for m in all_member_ids if m not in member_set]
    if zero_members:
        return sorted(zero_members)[0]

    if not standings:
        return None
    return standings[-1].member_id
