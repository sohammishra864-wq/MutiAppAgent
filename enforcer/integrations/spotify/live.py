from __future__ import annotations
import logging
import httpx

log = logging.getLogger(__name__)

TOKEN_URL = "https://accounts.spotify.com/api/token"
API_BASE = "https://api.spotify.com/v1"


class LiveSpotifyService:
    def __init__(self, client_id: str, client_secret: str, refresh_token: str):
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._access_token: str | None = None
        self._created: dict[str, str] = {}

    def _ensure_token(self) -> str:
        if self._access_token:
            return self._access_token
        resp = httpx.post(TOKEN_URL, data={
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }, timeout=10)
        resp.raise_for_status()
        self._access_token = resp.json()["access_token"]
        return self._access_token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._ensure_token()}"}

    def create_playlist(self, name: str, description: str, idempotency_key: str) -> str:
        if idempotency_key in self._created:
            return self._created[idempotency_key]

        # Get current user ID
        me = httpx.get(f"{API_BASE}/me", headers=self._headers(), timeout=10)
        me.raise_for_status()
        user_id = me.json()["id"]

        resp = httpx.post(
            f"{API_BASE}/users/{user_id}/playlists",
            headers=self._headers(),
            json={"name": name, "description": description, "public": True},
            timeout=10,
        )
        resp.raise_for_status()
        playlist_id = resp.json()["id"]
        self._created[idempotency_key] = playlist_id
        log.info(f"Created Spotify playlist: {playlist_id}")
        return playlist_id

    def add_tracks(self, playlist_id: str, track_query: str, count: int) -> int:
        # Search for tracks
        resp = httpx.get(
            f"{API_BASE}/search",
            headers=self._headers(),
            params={"q": track_query, "type": "track", "limit": count},
            timeout=10,
        )
        resp.raise_for_status()
        tracks = resp.json().get("tracks", {}).get("items", [])
        if not tracks:
            return 0

        uris = [t["uri"] for t in tracks[:count]]
        httpx.post(
            f"{API_BASE}/playlists/{playlist_id}/tracks",
            headers=self._headers(),
            json={"uris": uris},
            timeout=10,
        ).raise_for_status()
        log.info(f"Added {len(uris)} tracks to playlist {playlist_id}")
        return len(uris)
