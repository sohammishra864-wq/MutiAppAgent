from __future__ import annotations
import asyncio
import logging
import re
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

import discord
from discord import app_commands

from enforcer.core.clock import Clock, RealClock
from enforcer.core.config import Settings
from enforcer.core.schemas import ActivityType, Submission, ConsequencePlan
from enforcer.core.ledger import JsonlLedger
from enforcer.core.leaderboard import leaderboard, find_loser
from enforcer.core.injection import detect_injection, log_injection_attempt
from enforcer.agent.judge import judge, hash_image
from enforcer.agent.planner import plan_consequences
from enforcer.actions.consequence import execute_consequence_chain
from enforcer.integrations.factory import make_calendar, make_sheets, make_spotify
from enforcer.llm.client import BedrockClient
from enforcer.bot.embeds import verdict_embed, leaderboard_embed, consequence_embed

log = logging.getLogger(__name__)

MAX_IMAGE_SIZE = 10 * 1024 * 1024
ALLOWED_CDN_HOSTS = {"cdn.discordapp.com", "media.discordapp.net"}
MENTION_PATTERN = re.compile(r"@(everyone|here|&\d+)")
IST = timezone(timedelta(hours=5, minutes=30))


def sanitize_model_output(text: str) -> str:
    return MENTION_PATTERN.sub("[mention removed]", text)


class EnforcerBot(discord.Client):
    def __init__(self, settings: Settings, clock: Clock | None = None):
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(intents=intents)
        self.settings = settings
        self.tree = app_commands.CommandTree(self)
        self.clock = clock or RealClock(tz=IST)
        self.ledger = JsonlLedger(settings.enforcer_ledger_path)
        self.llm = BedrockClient(settings.aws_region, settings.bedrock_vl_model_id, bearer_token=settings.aws_bearer_token_bedrock)
        self._judge_semaphore = asyncio.Semaphore(3)
        self._setup_commands()

    def _setup_commands(self):
        guild_obj = discord.Object(id=int(self.settings.discord_guild_id))

        # --- /log ---
        @self.tree.command(name="log", description="Log a workout with photo proof", guild=guild_obj)
        @app_commands.describe(
            activity="Activity type",
            duration="Duration in minutes (optional)",
            distance="Distance in km (optional)",
            photo="Photo evidence",
            note="Optional note",
        )
        @app_commands.choices(activity=[
            app_commands.Choice(name=a.value, value=a.value) for a in ActivityType
        ])
        async def log_workout(
            interaction: discord.Interaction,
            activity: str,
            photo: discord.Attachment,
            duration: int | None = None,
            distance: float | None = None,
            note: str | None = None,
        ):
            await interaction.response.defer(thinking=True)

            if photo.size > MAX_IMAGE_SIZE:
                await interaction.followup.send("Image too large (max 10 MB).", ephemeral=True)
                return

            if photo.url and not any(host in photo.url for host in ALLOWED_CDN_HOSTS):
                await interaction.followup.send("Only Discord-hosted images are accepted.", ephemeral=True)
                return

            try:
                image_bytes = await photo.read()
            except Exception:
                await interaction.followup.send("Could not download the image.", ephemeral=True)
                return

            if not (image_bytes[:2] == b"\xff\xd8" or
                    image_bytes[:8] == b"\x89PNG\r\n\x1a\n" or
                    (image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP")):
                await interaction.followup.send("Unsupported image format. Use JPEG, PNG, or WebP.", ephemeral=True)
                return

            if note and len(note) > 500:
                note = note[:500]

            submission = Submission(
                member_id=str(interaction.user.id),
                guild_id=str(interaction.guild_id),
                submitted_at=self.clock.now(),
                claimed_activity=ActivityType(activity),
                claimed_duration_min=duration,
                claimed_distance_km=distance,
                image_ref=photo.url,
                note=note,
            )

            if detect_injection(note):
                log_injection_attempt(submission.member_id, note or "", submission.correlation_id)

            # Load known hashes for duplicate detection
            known_hashes = self.ledger.recent_hashes(str(interaction.guild_id))

            async with self._judge_semaphore:
                verdict = await asyncio.to_thread(
                    judge,
                    submission=submission,
                    image_bytes=image_bytes,
                    llm=self.llm,
                    clock=self.clock,
                    known_hashes=known_hashes,
                    policy_path=self.settings.enforcer_policy_path,
                )

            verdict.rationale = sanitize_model_output(verdict.rationale)
            self.ledger.append(verdict)

            embed = verdict_embed(verdict)
            await interaction.followup.send(
                embed=embed,
                allowed_mentions=discord.AllowedMentions.none(),
            )

        # --- /leaderboard ---
        @self.tree.command(name="leaderboard", description="Show the current weekly leaderboard", guild=guild_obj)
        async def show_leaderboard(interaction: discord.Interaction):
            await interaction.response.defer()

            now = self.clock.now()
            week_start = (now - timedelta(days=now.weekday())).date()  # Monday
            week_end = week_start + timedelta(days=6)  # Sunday

            verdicts = self.ledger.read_all(str(interaction.guild_id))
            standings = leaderboard(verdicts, week_start, week_end)

            week_label = f"{week_start} to {week_end}"
            embed = leaderboard_embed(standings, week_label)
            await interaction.followup.send(
                embed=embed,
                allowed_mentions=discord.AllowedMentions.none(),
            )

        # --- /settle ---
        @self.tree.command(name="settle", description="Settle the week — announce loser and execute consequences", guild=guild_obj)
        async def settle_week(interaction: discord.Interaction):
            await interaction.response.defer()

            # Only server owner or admin can settle
            if not interaction.user.guild_permissions.administrator:
                await interaction.followup.send("Only admins can settle the week.", ephemeral=True)
                return

            now = self.clock.now()
            week_start = (now - timedelta(days=now.weekday())).date()
            week_end = week_start + timedelta(days=6)

            guild = interaction.guild
            verdicts = self.ledger.read_all(str(interaction.guild_id))
            standings = leaderboard(verdicts, week_start, week_end)

            all_member_ids = [str(m.id) for m in guild.members if not m.bot] if guild else []
            loser = find_loser(standings, all_member_ids, str(interaction.guild_id))

            if not loser:
                await interaction.followup.send("No members to settle.", ephemeral=True)
                return

            # Show leaderboard first
            week_label = f"{week_start} to {week_end}"
            lb_embed = leaderboard_embed(standings, week_label)
            await interaction.followup.send(
                embed=lb_embed,
                allowed_mentions=discord.AllowedMentions.none(),
            )

            # Assign last place role
            role_id = self.settings.discord_last_place_role_id
            if role_id and guild:
                # Remove role from previous holder
                role = guild.get_role(int(role_id))
                if role:
                    for member in role.members:
                        try:
                            await member.remove_roles(role)
                        except Exception:
                            pass
                    # Assign to new loser
                    loser_member = guild.get_member(int(loser)) if loser.isdigit() else None
                    if loser_member:
                        try:
                            await loser_member.add_roles(role)
                        except Exception as e:
                            log.error(f"Failed to assign role: {e}")

            # Resolve loser display name
            loser_name = loser
            if guild and loser.isdigit():
                lm = guild.get_member(int(loser))
                if lm:
                    loser_name = lm.display_name

            # Execute consequence chain
            plan = plan_consequences(
                loser_id=loser,
                guild_id=str(interaction.guild_id),
                week_start=week_start,
                member_ids=all_member_ids,
                debt_amount=self.settings.upi_default_amount,
            )
            plan.loser_name = loser_name

            cal = make_calendar(self.settings)
            sheets = make_sheets(self.settings)
            spotify = make_spotify(self.settings)

            results = await asyncio.to_thread(
                execute_consequence_chain,
                plan=plan,
                calendar=cal,
                sheets=sheets,
                spotify=spotify,
                dry_run=self.settings.enforcer_dry_run,
                log_path=self.settings.enforcer_action_log_path,
            )

            action_summary = [
                {"kind": r.kind, "success": r.success,
                 "detail": str(r.result)[:100] if r.result else "done",
                 "error": r.error}
                for r in results
            ]

            embed = consequence_embed(loser, action_summary)

            # Add UPI QR if configured
            upi = self.settings.upi_payee_address
            if upi:
                embed.add_field(
                    name="Payment",
                    value=f"UPI: `{upi}` — ₹{self.settings.upi_default_amount}",
                    inline=False,
                )

            succeeded = sum(1 for r in results if r.success)
            embed.set_footer(text=f"{succeeded}/{len(results)} actions completed")

            await interaction.channel.send(
                embed=embed,
                allowed_mentions=discord.AllowedMentions.none(),
            )

    async def on_ready(self):
        log.info(f"Bot ready as {self.user}")
        guild = discord.Object(id=int(self.settings.discord_guild_id))
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        log.info("Commands synced")


def run_bot(settings: Settings | None = None):
    if settings is None:
        settings = Settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    bot = EnforcerBot(settings)
    bot.run(settings.discord_bot_token, log_handler=None)


if __name__ == "__main__":
    run_bot()
