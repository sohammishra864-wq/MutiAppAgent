from __future__ import annotations
import logging
from datetime import datetime
from pathlib import Path

from enforcer.actions.base import ActionResult, execute_action
from enforcer.core.schemas import ConsequencePlan
from enforcer.integrations.calendar.base import CalendarService
from enforcer.integrations.sheets.base import SheetsService
from enforcer.integrations.spotify.base import SpotifyService

log = logging.getLogger(__name__)


def execute_consequence_chain(
    plan: ConsequencePlan,
    calendar: CalendarService,
    sheets: SheetsService,
    spotify: SpotifyService,
    dry_run: bool = False,
    log_path: Path | None = None,
) -> list[ActionResult]:
    """Execute in order: Calendar, Sheets, Spotify.
    Discord announcement + role handled by the bot before calling this.
    Continue on failure — report what completed and what didn't."""
    results: list[ActionResult] = []

    # 1. Calendar — find a slot then book it
    cal_key = f"cal:{plan.week_start}:{plan.loser_id}"
    if not plan.chosen_slot:
        slot_result = execute_action(
            kind="calendar_freebusy",
            idempotency_key=f"freebusy:{plan.week_start}:{plan.loser_id}",
            fn=lambda: calendar.freebusy(
                member_ids=[],
                min_date=str(plan.week_start),
                max_date=str(plan.week_start),
            ),
            description=f"Query free/busy for party slot",
            dry_run=dry_run,
            log_path=log_path,
        )
        if slot_result.success and slot_result.result and not dry_run:
            plan.chosen_slot = slot_result.result[0]
            plan.proposed_slots = slot_result.result

    if plan.chosen_slot:
        r = execute_action(
            kind="calendar",
            idempotency_key=cal_key,
            fn=lambda: calendar.create_event(
                slot=plan.chosen_slot,
                summary=f"Party courtesy of {plan.loser_name or plan.loser_id}",
                attendees=[],
                idempotency_key=cal_key,
            ),
            description=f"Create party event for {plan.loser_id} on {plan.chosen_slot.start}",
            dry_run=dry_run,
            log_path=log_path,
        )
        results.append(r)
    else:
        results.append(ActionResult(
            success=False, kind="calendar", idempotency_key=cal_key,
            error="No free slot found", dry_run=dry_run,
        ))

    # 2. Sheets
    debt_key = f"debt:{plan.week_start}:{plan.loser_id}"
    r = execute_action(
        kind="sheets",
        idempotency_key=debt_key,
        fn=lambda: sheets.append_debt(
            row=[debt_key, str(plan.week_start), plan.loser_name or plan.loser_id,
                 plan.debt_amount, "group", "unpaid",
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
            idempotency_key=debt_key,
        ),
        description=f"Log debt of {plan.debt_amount} for {plan.loser_name or plan.loser_id}",
        dry_run=dry_run,
        log_path=log_path,
    )
    results.append(r)

    # 3. Spotify
    playlist_key = f"playlist:{plan.week_start}:{plan.loser_id}"
    r = execute_action(
        kind="spotify",
        idempotency_key=playlist_key,
        fn=lambda: spotify.create_playlist(
            name=f"Shame Playlist — {plan.loser_name or plan.loser_id} ({plan.week_start})",
            description=plan.playlist_theme or "Last place consequences",
            idempotency_key=playlist_key,
        ),
        description=f"Create shame playlist for {plan.loser_id}",
        dry_run=dry_run,
        log_path=log_path,
    )
    results.append(r)
    if r.success and not dry_run and plan.playlist_theme:
        execute_action(
            kind="spotify_tracks",
            idempotency_key=f"{playlist_key}:tracks",
            fn=lambda: spotify.add_tracks(r.result, plan.playlist_theme, 10),
            description="Add tracks to shame playlist",
            dry_run=dry_run,
            log_path=log_path,
        )

    succeeded = sum(1 for r in results if r.success)
    log.info(f"Consequence chain: {succeeded}/{len(results)} actions completed")
    return results
