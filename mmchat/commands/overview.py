"""Overview command - the agent's starting point."""

import json
import sys

import click

from ..cli import get_context, main, pass_state
from ..client import EXIT_ERROR
from ..formatters import TYPE_LABELS, _iso_ts, channel_ref
from ..helpers import (
    compute_unreads,
    fetch_root_context,
    get_channels_and_members,
    resolve_authors,
    search_mentions,
)
from ..resolve import Resolver
from ..time_utils import parse_since


@main.command()
@click.option("--since", "since", default="6h", show_default=True, help="Look back period (1h, 6h, 1d, 0 for all).")
@pass_state
def overview(state, since):
    """Get oriented: mentions, unread, and active channels in one call.

    This is the command to run first. Returns a structured summary of
    what needs attention, sorted by priority.
    """
    ctx = get_context(state)
    resolver = Resolver(ctx.driver, ctx.user_id)

    since_ms = None
    if since and since != "0":
        try:
            since_ms = parse_since(since)
        except ValueError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(EXIT_ERROR)

    # 1. Mentions
    mentions_raw = search_mentions(ctx, since_ms)
    mention_posts = [p for p, _ in mentions_raw]
    user_map, authors = resolve_authors(resolver, mention_posts)
    root_context = fetch_root_context(ctx, mention_posts, user_map, authors)

    mention_entries = []
    for p, _team_name in mentions_raw:
        uid = p.get("user_id", "")
        ch = resolver.resolve_channel(p.get("channel_id", ""))
        root_id = p.get("root_id", "")
        entry = {
            "author": authors.get(uid, "unknown"),
            "message": p.get("message", "")[:200],
            "created_at": _iso_ts(p.get("create_at", 0)),
            "channel": ch["display_name"],
            "thread_id": root_id if root_id else p["id"],
            "is_reply": bool(root_id),
        }
        if root_id:
            rc = root_context.get(root_id)
            if rc:
                entry["root_message"] = rc["message"]
                entry["root_author"] = rc["author"]
        if p.get("props", {}).get("from_webhook") == "true":
            entry["is_bot"] = True
        mention_entries.append(entry)

    # 2. Channels + members (single fetch, reused for unreads + active)
    channels_members = get_channels_and_members(ctx)

    # 3. Unreads
    unreads_raw = compute_unreads(channels_members, resolver)
    unreads = []
    for u in unreads_raw:
        ch_type = u.get("type", "")
        unreads.append({
            "channel": u["display_name"],
            "ref": channel_ref(u),
            "type": TYPE_LABELS.get(ch_type, ch_type),
            "unread": u["unread"],
            "last_post_at": _iso_ts(u.get("last_post_at", 0)),
        })
    unreads.sort(key=lambda x: -x["unread"])

    # 4. Active channels (with posts since cutoff)
    active = []
    if since_ms:
        for ch, _member, _team in channels_members:
            if (ch.get("last_post_at", 0) or 0) >= since_ms:
                info = resolver.format_channel(ch)
                ch_type = ch.get("type", "")
                active.append({
                    "channel": info["display_name"],
                    "ref": channel_ref(ch),
                    "type": TYPE_LABELS.get(ch_type, ch_type),
                    "last_post_at": _iso_ts(ch.get("last_post_at", 0)),
                })
        active.sort(key=lambda c: c["last_post_at"], reverse=True)

    overview_data = {
        "since": since,
        "mentions": mention_entries,
        "unread": unreads,
    }
    if active:
        overview_data["active_channels"] = active

    if not state.human:
        click.echo(json.dumps(overview_data, indent=2))
    else:
        lines = [f"# Overview (last {since})\n"]

        lines.append(f"## Mentions ({len(mention_entries)})\n")
        if mention_entries:
            for m in mention_entries:
                bot = " [bot]" if m.get("is_bot") else ""
                lines.append(f"**{m['author']}**{bot} in #{m['channel']} ({m['created_at']})")
                if m.get("root_message"):
                    lines.append(f"  re: {m['root_author']}: {m['root_message'][:80]}")
                lines.append(f"  {m['message'][:80]}")
                lines.append("")
        else:
            lines.append("No mentions.\n")

        lines.append(f"## Unread ({len(unreads)} channels)\n")
        if unreads:
            for u in unreads:
                lines.append(f"  {u['channel']:40s} {u['unread']:4d} unread  ({u['type']})")
        else:
            lines.append("All caught up.\n")

        if active:
            lines.append(f"\n## Active Channels ({len(active)})\n")
            for c in active:
                lines.append(f"  {c['channel']:40s} last: {c['last_post_at']}  ({c['type']})")

        click.echo("\n".join(lines).rstrip())
