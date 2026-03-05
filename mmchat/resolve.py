"""User and channel ID resolution with in-memory caching."""

from typing import Optional


class Resolver:
    """Resolves Mattermost IDs to display names. Caches results per session."""

    def __init__(self, driver, my_user_id: str):
        self.driver = driver
        self.my_user_id = my_user_id
        self._users: dict[str, dict] = {}
        self._channels: dict[str, dict] = {}

    def resolve_user(self, user_id: str) -> dict:
        """Resolve a user ID to {id, username, display_name}."""
        if user_id in self._users:
            return self._users[user_id]

        try:
            u = self.driver.users.get_user(user_id)
        except Exception:
            result = {"id": user_id, "username": user_id, "display_name": user_id}
            self._users[user_id] = result
            return result

        result = {
            "id": u["id"],
            "username": u["username"],
            "display_name": _user_display_name(u),
        }
        self._users[user_id] = result
        return result

    def resolve_users(self, user_ids: list[str]) -> dict[str, dict]:
        """Batch resolve user IDs. Fetches only uncached ones."""
        uncached = [uid for uid in set(user_ids) if uid not in self._users]

        if uncached:
            try:
                users = self.driver.users.get_users_by_ids(uncached)
                for u in users:
                    self._users[u["id"]] = {
                        "id": u["id"],
                        "username": u["username"],
                        "display_name": _user_display_name(u),
                    }
            except Exception:
                # Fall back to individual lookups
                for uid in uncached:
                    self.resolve_user(uid)

        return {uid: self._users.get(uid, {"id": uid, "username": uid, "display_name": uid}) for uid in user_ids}

    def resolve_channel(self, channel_id: str) -> dict:
        """Resolve a channel ID to {id, name, display_name, type}."""
        if channel_id in self._channels:
            return self._channels[channel_id]

        try:
            ch = self.driver.channels.get_channel(channel_id)
        except Exception:
            result = {"id": channel_id, "name": channel_id, "display_name": channel_id, "type": "?"}
            self._channels[channel_id] = result
            return result

        result = self.format_channel(ch)
        self._channels[channel_id] = result
        return result

    def format_channel_display(self, channel: dict) -> str:
        """Get a human-friendly display name for a channel dict (from API)."""
        info = self._format_channel(channel)
        return info["display_name"]

    def format_channel(self, ch: dict) -> dict:
        """Format a raw channel dict into our standard shape with DM resolution."""
        ch_type = ch.get("type", "O")
        name = ch.get("name", "")
        display_name = ch.get("display_name", "")

        if ch_type == "D":
            # DM: name is "{uid1}__{uid2}", display_name is empty
            display_name = self._resolve_dm_name(name)
        elif ch_type == "G":
            # Group DM: display_name may be set by server, or resolve from name
            if not display_name:
                display_name = self._resolve_group_dm_name(name)

        if not display_name:
            display_name = name

        result = {
            "id": ch["id"],
            "name": name,
            "display_name": display_name,
            "type": ch_type,
        }
        # Pass through purpose/header if present
        if ch.get("purpose"):
            result["purpose"] = ch["purpose"]
        if ch.get("header"):
            result["header"] = ch["header"]
        return result

    def _resolve_dm_name(self, channel_name: str) -> str:
        """Resolve DM channel name to @username of the other user."""
        parts = channel_name.split("__")
        other_ids = [p for p in parts if p != self.my_user_id]
        if other_ids:
            user = self.resolve_user(other_ids[0])
            return f"@{user['username']}"
        return channel_name

    def _resolve_group_dm_name(self, channel_name: str) -> str:
        """Resolve group DM channel name to @user1, @user2, ..."""
        parts = channel_name.split("__")
        other_ids = [p for p in parts if p != self.my_user_id]
        if not other_ids:
            return channel_name
        users = self.resolve_users(other_ids)
        names = [f"@{users[uid]['username']}" for uid in other_ids]
        return ", ".join(sorted(names))

    def populate_channels(self, channels: list[dict]) -> None:
        """Pre-populate channel cache from a list of channel dicts."""
        for ch in channels:
            self._channels[ch["id"]] = self.format_channel(ch)


def _user_display_name(user: dict) -> str:
    """Build display name from user dict."""
    first = user.get("first_name", "")
    last = user.get("last_name", "")
    display = f"{first} {last}".strip()
    return display or user.get("username", "")
