from __future__ import annotations
import logging

log = logging.getLogger(__name__)

PLAYLIST_ID = "7weUPipMVYr7bTGcUjbqPe"
PLAYLIST_URL = f"https://open.spotify.com/playlist/{PLAYLIST_ID}"


class FakeSpotifyService:
    """Offline Spotify service that returns a real playlist link."""

    def __init__(self):
        self._created: set[str] = set()

    def create_playlist(self, name: str, description: str, idempotency_key: str) -> str:
        if idempotency_key in self._created:
            log.info(f"Playlist already exists, skipping")
            return PLAYLIST_ID
        self._created.add(idempotency_key)
        log.info(f"Created Spotify playlist '{name}' -> {PLAYLIST_URL}")
        return PLAYLIST_ID

    def add_tracks(self, playlist_id: str, track_query: str, count: int) -> int:
        log.info(f"Added {count} tracks to playlist {PLAYLIST_URL}")
        return count
