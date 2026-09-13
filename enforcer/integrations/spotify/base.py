from __future__ import annotations
from typing import Protocol


class SpotifyService(Protocol):
    def create_playlist(self, name: str, description: str, idempotency_key: str) -> str: ...
    def add_tracks(self, playlist_id: str, track_query: str, count: int) -> int: ...
