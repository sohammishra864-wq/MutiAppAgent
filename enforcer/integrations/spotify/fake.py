from __future__ import annotations
import logging

log = logging.getLogger(__name__)


class FakeSpotifyService:
    def __init__(self):
        self._playlists: dict[str, dict] = {}

    def create_playlist(self, name: str, description: str, idempotency_key: str) -> str:
        if idempotency_key in self._playlists:
            log.info(f"[FAKE] playlist {idempotency_key} already exists, skipping")
            return idempotency_key
        self._playlists[idempotency_key] = {"name": name, "description": description, "tracks": []}
        log.info(f"[FAKE] created playlist: {name}")
        return idempotency_key

    def add_tracks(self, playlist_id: str, track_query: str, count: int) -> int:
        log.info(f"[FAKE] added {count} tracks matching '{track_query}' to {playlist_id}")
        return count
