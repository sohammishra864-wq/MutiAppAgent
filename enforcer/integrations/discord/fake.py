from __future__ import annotations
import logging

log = logging.getLogger(__name__)


class FakeDiscordService:
    def __init__(self):
        self._messages: list[dict] = []
        self._roles: dict[str, set[str]] = {}

    def send_embed(self, channel_id: str, embed: dict) -> str:
        msg_id = f"fake_msg_{len(self._messages)}"
        self._messages.append({"id": msg_id, "channel": channel_id, "embed": embed})
        log.info(f"[FAKE] sent embed to {channel_id}: {embed.get('title', '?')}")
        return msg_id

    def assign_role(self, guild_id: str, member_id: str, role_id: str) -> None:
        self._roles.setdefault(member_id, set()).add(role_id)
        log.info(f"[FAKE] assigned role {role_id} to {member_id}")

    def remove_role(self, guild_id: str, member_id: str, role_id: str) -> None:
        self._roles.get(member_id, set()).discard(role_id)
        log.info(f"[FAKE] removed role {role_id} from {member_id}")
