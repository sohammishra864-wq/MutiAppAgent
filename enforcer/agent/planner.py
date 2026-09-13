"""Planner: given standings + loser, produce a ConsequencePlan."""
from __future__ import annotations
from datetime import date
from enforcer.core.schemas import ConsequencePlan, PlannedAction


def plan_consequences(
    loser_id: str,
    guild_id: str,
    week_start: date,
    member_ids: list[str],
    debt_amount: float = 500.0,
) -> ConsequencePlan:
    plan = ConsequencePlan(
        loser_id=loser_id,
        guild_id=guild_id,
        week_start=week_start,
        debt_amount=debt_amount,
        playlist_theme="workout motivation",
        actions=[
            PlannedAction(
                kind="discord_announce",
                idempotency_key=f"announce:{week_start}:{loser_id}",
                description=f"Announce {loser_id} as last place",
            ),
            PlannedAction(
                kind="discord_role",
                idempotency_key=f"role:{week_start}:{loser_id}",
                description=f"Assign last place role to {loser_id}",
            ),
            PlannedAction(
                kind="calendar",
                idempotency_key=f"cal:{week_start}:{loser_id}",
                description=f"Book party for {loser_id}",
            ),
            PlannedAction(
                kind="sheets",
                idempotency_key=f"debt:{week_start}:{loser_id}",
                description=f"Log debt of {debt_amount} for {loser_id}",
            ),
            PlannedAction(
                kind="spotify",
                idempotency_key=f"playlist:{week_start}:{loser_id}",
                description=f"Create shame playlist for {loser_id}",
            ),
        ],
    )
    return plan
