"""Channel commands: channel, channels, unread."""

import json
import sys

import click

from ..cli import get_context, main, pass_state
from ..client import EXIT_ERROR
from ..formatters import (
    TYPE_LABELS,
    _iso_ts,
    format_channels_json,
    format_channels_md,
    format_unread_json,
    format_unread_md,
)
from ..helpers import compute_unreads, get_channels_and_members, resolve_channel
from ..resolve import Resolver
from ..time_utils import parse_since


@main.command()
@click.argument("channel")
@pass_state
def channel(state, channel):
    """Show info about a single channel.

    CHANNEL can be a name, @username for DMs, or a channel ID.
    """
    ctx = get_context(state)
    resolver = Resolver(ctx.driver, ctx.user_id)

    ch = resolve_channel(ctx, resolver, channel)
    ch_info = resolver.format_channel(ch)

    # Get member count
    try:
        stats = ctx.driver.client.get(f"/channels/{ch['id']}/stats")
        member_count = stats.get("member_count", 0)
    except Exception:
        member_count = None

    # Count pinned posts
    try:
        pinned_result = ctx.driver.client.get(f"/channels/{ch['id']}/pinned")
        pinned_count = len(pinned_result.get("order", []))
    except Exception:
        pinned_count = 0

    info = {
        "id": ch["id"],
        "name": ch_info["display_name"],
        "type": TYPE_LABELS.get(ch.get("type", ""), ch.get("type", "")),
        "purpose": ch.get("purpose", ""),
        "header": ch.get("header", ""),
        "last_post_at": _iso_ts(ch.get("last_post_at", 0)),
        "created_at": _iso_ts(ch.get("create_at", 0)),
        "pinned_count": pinned_count,
    }
    if member_count is not None:
        info["member_count"] = member_count

    info = {k: v for k, v in info.items() if v or v == 0}

    if not state.human:
        click.echo(json.dumps(info, indent=2))
    else:
        lines = [f"## #{info['name']}"]
        lines.append(f"Type: {info.get('type', '?')}")
        if info.get("purpose"):
            lines.append(f"Purpose: {info['purpose']}")
        if info.get("header"):
            lines.append(f"Header: {info['header']}")
        if member_count is not None:
            lines.append(f"Members: {member_count}")
        lines.append(f"Pinned: {pinned_count}")
        lines.append(f"Last post: {info.get('last_post_at', '?')}")
        lines.append(f"Created: {info.get('created_at', '?')}")
        click.echo("\n".join(lines))


@main.command()
@click.option("--type", "ch_type", type=click.Choice(["public", "private", "dm", "group"]), help="Filter by channel type.")
@click.option("--since", "since", default=None, help="Only channels with posts since (1h, 6h, 1d, today).")
@pass_state
def channels(state, ch_type, since):
    """List channels you belong to."""
    ctx = get_context(state)
    resolver = Resolver(ctx.driver, ctx.user_id)

    type_filter = {"public": "O", "private": "P", "dm": "D", "group": "G"}.get(ch_type)

    since_ms = None
    if since:
        try:
            since_ms = parse_since(since)
        except ValueError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(EXIT_ERROR)

    all_channels = []
    for team in ctx.teams:
        raw = ctx.driver.channels.get_channels_for_user(ctx.user_id, team.id)
        for ch in raw:
            if type_filter and ch["type"] != type_filter:
                continue
            if since_ms and (ch.get("last_post_at", 0) or 0) < since_ms:
                continue
            info = resolver.format_channel(ch)
            info["team_name"] = team.display_name
            info["team_id"] = team.id
            info["last_post_at"] = ch.get("last_post_at", 0)
            all_channels.append(info)

    if since:
        all_channels.sort(key=lambda c: -(c.get("last_post_at", 0) or 0))
    else:
        type_order = {"O": 0, "P": 1, "G": 2, "D": 3}
        all_channels.sort(key=lambda c: (type_order.get(c["type"], 9), c["display_name"].lower()))

    seen = set()
    deduped = []
    for ch in all_channels:
        if ch["id"] not in seen:
            seen.add(ch["id"])
            deduped.append(ch)

    if not state.human:
        click.echo(format_channels_json(deduped))
    else:
        click.echo(format_channels_md(deduped))


@main.command()
@click.option("--include-muted", is_flag=True, default=False, help="Include muted channels (hidden by default).")
@pass_state
def unread(state, include_muted):
    """Show channels with unread messages. Muted channels are hidden by default."""
    ctx = get_context(state)
    resolver = Resolver(ctx.driver, ctx.user_id)

    channels_members = get_channels_and_members(ctx)
    unreads = compute_unreads(channels_members, resolver, include_muted)

    seen_ids = set()
    deduped = []
    for u in unreads:
        if u["channel_id"] not in seen_ids:
            seen_ids.add(u["channel_id"])
            deduped.append(u)

    if not state.human:
        click.echo(format_unread_json(deduped))
    else:
        click.echo(format_unread_md(deduped))
