"""Output formatting - markdown tables and JSON."""

import json
from datetime import datetime, timezone
from typing import Optional


# Channel type labels
TYPE_LABELS = {
    "O": "Public",
    "P": "Private",
    "D": "DM",
    "G": "Group DM",
}


def _iso_ts(epoch_ms: int) -> str:
    """Convert epoch milliseconds to ISO 8601 string."""
    if not epoch_ms:
        return ""
    return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def format_channels_md(channels: list[dict]) -> str:
    """Format channel list as markdown table."""
    if not channels:
        return "No channels found."

    lines = ["| Channel | Type | Team |", "|---------|------|------|"]
    for ch in channels:
        name = ch["display_name"]
        ch_type = TYPE_LABELS.get(ch["type"], ch["type"])
        team = ch.get("team_name", "")
        lines.append(f"| {name} | {ch_type} | {team} |")

    return "\n".join(lines)


def format_channels_json(channels: list[dict]) -> str:
    """Format channel list as JSON with useful fields for agents.

    Includes 'ref' field - the argument to pass to `mm messages <ref>`.
    """
    out = []
    for ch in channels:
        ch_type = ch.get("type", "")
        # For DMs/group DMs, ref is channel_id since names aren't addressable
        if ch_type in ("D", "G"):
            ref = ch["id"]
        else:
            ref = ch.get("name", "") or ch["id"]
        entry = {
            "id": ch["id"],
            "name": ch.get("display_name", ch.get("name", "")),
            "ref": ref,
            "type": TYPE_LABELS.get(ch_type, ch_type),
            "team": ch.get("team_name", ""),
        }
        # Include purpose/header if present and non-empty
        purpose = ch.get("purpose", "")
        header = ch.get("header", "")
        if purpose:
            entry["purpose"] = purpose
        if header:
            entry["header"] = header
        out.append(entry)
    return json.dumps(out, indent=2)


def format_unread_md(unreads: list[dict]) -> str:
    """Format unread list as markdown table."""
    if not unreads:
        return "No unread messages."

    lines = ["| Channel | Unread | Mentions | Team |", "|---------|--------|----------|------|"]
    for u in unreads:
        name = u["display_name"]
        mentions = f"**{u['mentions']}**" if u["mentions"] > 0 else "0"
        team = u.get("team_name", "")
        lines.append(f"| {name} | {u['unread']} | {mentions} | {team} |")

    return "\n".join(lines)


def format_unread_json(unreads: list[dict]) -> str:
    """Format unread list as JSON with ISO timestamps.

    Includes 'ref' field - the argument to pass to `mm messages <ref>`.
    For named channels this is the channel name, for DMs/group DMs it's the channel_id.
    """
    out = []
    for u in unreads:
        ch_type = u.get("type", "")
        # For DMs and group DMs, use channel_id as the ref since display names aren't addressable
        if ch_type in ("D", "G"):
            ref = u["channel_id"]
        else:
            ref = u.get("channel", "") or u["channel_id"]
        out.append({
            "channel_id": u["channel_id"],
            "channel": u["display_name"],
            "ref": ref,
            "type": TYPE_LABELS.get(ch_type, ch_type),
            "unread": u["unread"],
            "mentions": u["mentions"],
            "team": u.get("team_name", ""),
            "last_post_at": _iso_ts(u.get("last_post_at", 0)),
        })
    return json.dumps(out, indent=2)


def format_post_md(
    post: dict,
    author: str,
    channel_name: Optional[str] = None,
    indent: bool = False,
) -> str:
    """Format a single post as markdown."""
    ts = _format_timestamp(post.get("create_at", 0))
    msg = post.get("message", "").strip()
    prefix = "> " if indent else ""
    header = f"{prefix}**{author}** ({ts})"

    if channel_name:
        header = f"{prefix}**{author}** in #{channel_name} ({ts})"

    # Metadata annotations
    annotations = []
    reply_count = post.get("reply_count")
    if reply_count and not post.get("root_id"):
        annotations.append(f"{reply_count} replies")
    file_ids = post.get("file_ids") or []
    file_names = []
    if file_ids and post.get("metadata", {}).get("files"):
        file_names = [f.get("name", "") for f in post["metadata"]["files"] if f.get("name")]
    if file_names:
        annotations.append(f"files: {', '.join(file_names)}")
    elif file_ids:
        annotations.append(f"{len(file_ids)} file{'s' if len(file_ids) > 1 else ''}")

    suffix = f" [{', '.join(annotations)}]" if annotations else ""

    if not msg:
        if file_names:
            return header + suffix
        post_type = post.get("type", "")
        if post_type:
            return header + f" *({post_type})*"
        return header + " *(no text)*" + suffix

    if indent and "\n" in msg:
        msg_lines = msg.split("\n")
        msg = "\n> ".join(msg_lines)

    return f"{header}{suffix}\n{prefix}{msg}"


def format_posts_md(
    posts: list[dict],
    authors: dict[str, str],
    channel_name: Optional[str] = None,
) -> str:
    """Format a list of posts as markdown."""
    if not posts:
        return "No messages."

    lines = []
    if channel_name:
        lines.append(f"## #{channel_name}\n")

    for post in posts:
        author = authors.get(post.get("user_id", ""), "unknown")
        is_reply = bool(post.get("root_id"))
        lines.append(format_post_md(post, author, indent=is_reply))
        lines.append("")

    return "\n".join(lines).rstrip()


def format_posts_json(
    posts: list[dict],
    authors: dict[str, str],
    channel_name: Optional[str] = None,
) -> str:
    """Format posts as JSON with resolved names and ISO timestamps.

    Includes thread_id (root_id if reply, own id if root) so agents
    can always follow up with `mm thread <thread_id>`.
    """
    enriched = []
    for post in posts:
        uid = post.get("user_id", "")
        root_id = post.get("root_id", "")
        file_ids = post.get("file_ids") or []
        entry = {
            "id": post["id"],
            "thread_id": root_id if root_id else post["id"],
            "is_reply": bool(root_id),
            "author": authors.get(uid, "unknown"),
            "message": post.get("message", ""),
            "created_at": _iso_ts(post.get("create_at", 0)),
            "channel_id": post.get("channel_id", ""),
            "file_count": len(file_ids),
        }
        # reply_count only meaningful on root posts
        if not root_id and post.get("reply_count"):
            entry["reply_count"] = post["reply_count"]
        # File metadata if available
        if file_ids and post.get("metadata", {}).get("files"):
            entry["files"] = [
                {"name": f.get("name", ""), "size": f.get("size", 0)}
                for f in post["metadata"]["files"]
            ]
        if channel_name:
            entry["channel"] = channel_name
        enriched.append(entry)
    return json.dumps(enriched, indent=2)


def _format_timestamp(create_at_ms: int) -> str:
    """Format a Mattermost timestamp for human display (HH:MM or date HH:MM)."""
    if not create_at_ms:
        return "??:??"
    dt = datetime.fromtimestamp(create_at_ms / 1000, tz=timezone.utc)
    now = datetime.now(timezone.utc)

    if dt.date() == now.date():
        return dt.strftime("%H:%M")
    return dt.strftime("%Y-%m-%d %H:%M")
