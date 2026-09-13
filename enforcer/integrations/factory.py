"""Select fake or live integration implementations based on config."""
from __future__ import annotations
from enforcer.core.config import Settings

from enforcer.integrations.calendar.fake import FakeCalendarService
from enforcer.integrations.sheets.fake import FakeSheetsService
from enforcer.integrations.spotify.fake import FakeSpotifyService
from enforcer.integrations.discord.fake import FakeDiscordService


def make_calendar(settings: Settings):
    if settings.enforcer_integrations in ("live", "mixed"):
        from enforcer.integrations.calendar.google import GoogleCalendarService
        return GoogleCalendarService(
            credentials_path=settings.google_credentials_path,
            token_dir=settings.google_token_dir,
            ledger_token_path=settings.google_ledger_token_path,
        )
    return FakeCalendarService()


def make_sheets(settings: Settings):
    if settings.enforcer_integrations in ("live", "mixed"):
        from enforcer.integrations.sheets.live import LiveSheetsService
        return LiveSheetsService(
            sheet_id=settings.google_sheets_id,
            token_path=settings.google_ledger_token_path,
            credentials_path=settings.google_credentials_path,
            debts_range=settings.sheets_debts_range,
        )
    return FakeSheetsService()


def make_spotify(settings: Settings):
    if settings.enforcer_integrations == "live" and settings.spotify_refresh_token:
        from enforcer.integrations.spotify.live import LiveSpotifyService
        return LiveSpotifyService(
            client_id=settings.spotify_client_id,
            client_secret=settings.spotify_client_secret,
            refresh_token=settings.spotify_refresh_token,
        )
    return FakeSpotifyService()


def make_discord():
    return FakeDiscordService()
