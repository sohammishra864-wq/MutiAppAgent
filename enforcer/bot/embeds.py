from __future__ import annotations
import discord
from enforcer.core.schemas import Verdict, Standing


VERDICT_COLORS = {
    "ACCEPT": discord.Color.green(),
    "REJECT": discord.Color.red(),
    "ESCALATE": discord.Color.orange(),
}

VERDICT_EMOJI = {
    "ACCEPT": "✅",
    "REJECT": "❌",
    "ESCALATE": "❓",
}


def verdict_embed(verdict: Verdict) -> discord.Embed:
    color = VERDICT_COLORS.get(verdict.verdict, discord.Color.greyple())
    emoji = VERDICT_EMOJI.get(verdict.verdict, "")

    embed = discord.Embed(
        title=f"{emoji} {verdict.verdict}",
        description=verdict.rationale,
        color=color,
    )
    if verdict.reason_code:
        embed.add_field(name="Reason", value=verdict.reason_code.value, inline=True)
    embed.add_field(name="Points", value=str(verdict.points), inline=True)
    embed.add_field(name="Confidence", value=f"{verdict.confidence:.0%}", inline=True)

    obs = verdict.observed
    details = []
    if obs.activity_seen:
        details.append(f"Activity: {obs.activity_seen}")
    if obs.duration_min is not None:
        details.append(f"Duration: {obs.duration_min} min ({obs.duration_source or '?'})")
    if obs.distance_km is not None:
        details.append(f"Distance: {obs.distance_km} km ({obs.distance_source or '?'})")
    if obs.date_seen:
        details.append(f"Date: {obs.date_seen} ({obs.date_source or '?'})")
    if details:
        embed.add_field(name="Observed", value="\n".join(details), inline=False)

    embed.set_footer(text=f"Policy {verdict.policy_version} | {verdict.correlation_id}")
    return embed


def leaderboard_embed(standings: list[Standing], week_label: str) -> discord.Embed:
    embed = discord.Embed(
        title=f"\U0001f3c6 Leaderboard — {week_label}",
        color=discord.Color.gold(),
    )
    if not standings:
        embed.description = "No submissions this week."
        return embed

    lines = []
    for i, s in enumerate(standings):
        medal = {0: "\U0001f947", 1: "\U0001f948", 2: "\U0001f949"}.get(i, f"{i+1}.")
        lines.append(f"{medal} <@{s.member_id}> — {s.points} pts ({s.valid_days} days)")

    embed.description = "\n".join(lines)
    return embed


def consequence_embed(loser_id: str, results: list[dict]) -> discord.Embed:
    embed = discord.Embed(
        title="\U0001f40c The Reckoning",
        description=f"<@{loser_id}> is last place and owes the group a party!",
        color=discord.Color.dark_red(),
    )
    for r in results:
        status = "✅" if r.get("success") else "❌"
        embed.add_field(
            name=f"{status} {r['kind']}",
            value=r.get("detail", "done") if r.get("success") else r.get("error", "failed"),
            inline=False,
        )
    return embed
