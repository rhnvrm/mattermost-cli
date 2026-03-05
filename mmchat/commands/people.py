"""People commands: user, members, pinned."""

import json
import sys

import click

from ..cli import get_context, main, pass_state
from ..client import EXIT_ERROR
from ..formatters import enrich_posts, format_post_md
from ..helpers import resolve_authors, resolve_channel
from ..resolve import Resolver


@main.command()
@click.argument("username")
@pass_state
def user(state, username):
    """Show user profile and status.

    USERNAME can be with or without @ prefix.
    """
    ctx = get_context(state)
    username = username.lstrip("@")

    try:
        u = ctx.driver.users.get_user_by_username(username)
    except Exception:
        click.echo(f"Error: User '@{username}' not found.", err=True)
        sys.exit(EXIT_ERROR)

    try:
        status = ctx.driver.client.get(f"/users/{u['id']}/status")
        status_str = status.get("status", "unknown")
    except Exception:
        status_str = "unknown"

    info = {
        "user_id": u["id"],
        "username": u["username"],
        "display_name": f"{u.get('first_name', '')} {u.get('last_name', '')}".strip() or u["username"],
        "email": u.get("email", ""),
        "position": u.get("position", ""),
        "status": status_str,
        "locale": u.get("locale", ""),
    }
    tz = u.get("timezone", {})
    if tz.get("automaticTimezone"):
        info["timezone"] = tz["automaticTimezone"]
    elif tz.get("manualTimezone"):
        info["timezone"] = tz["manualTimezone"]

    info = {k: v for k, v in info.items() if v}

    if not state.human:
        click.echo(json.dumps(info, indent=2))
    else:
        lines = [f"**@{info['username']}** ({info.get('display_name', '')})"]
        if info.get("position"):
            lines.append(f"Position: {info['position']}")
        if info.get("email"):
            lines.append(f"Email: {info['email']}")
        lines.append(f"Status: {info.get('status', 'unknown')}")
        if info.get("timezone"):
            lines.append(f"Timezone: {info['timezone']}")
        click.echo("\n".join(lines))


@main.command()
@click.argument("channel")
@click.option("--limit", "limit", default=10, type=int, show_default=True, help="Max pinned posts to show.")
@pass_state
def pinned(state, channel, limit):
    """Show pinned posts in a channel."""
    ctx = get_context(state)
    resolver = Resolver(ctx.driver, ctx.user_id)

    ch = resolve_channel(ctx, resolver, channel)
    ch_id = ch["id"]
    ch_info = resolver.format_channel(ch)

    result = ctx.driver.client.get(f"/channels/{ch_id}/pinned")
    order = result.get("order", [])
    posts_map = result.get("posts", {})

    posts = []
    for pid in order:
        if pid in posts_map:
            posts.append(posts_map[pid])
    posts.sort(key=lambda p: p.get("create_at", 0), reverse=True)
    posts = posts[:limit]

    if not posts:
        click.echo("[]" if not state.human else "No pinned posts.")
        return

    _user_map, authors = resolve_authors(resolver, posts)

    if not state.human:
        enriched = enrich_posts(posts, authors, ch_info["display_name"])
        click.echo(json.dumps(enriched, indent=2))
    else:
        lines = [f"## #{ch_info['display_name']} - Pinned", ""]
        for p in posts:
            author = authors.get(p.get("user_id", ""), "unknown")
            lines.append(format_post_md(p, author, ch_info["display_name"]))
            lines.append("")
        click.echo("\n".join(lines).rstrip())


@main.command()
@click.argument("channel")
@pass_state
def members(state, channel):
    """List members of a channel."""
    ctx = get_context(state)
    resolver = Resolver(ctx.driver, ctx.user_id)

    ch = resolve_channel(ctx, resolver, channel)
    ch_id = ch["id"]

    # Paginate through all members
    all_members = []
    page = 0
    per_page = 200
    while True:
        batch = ctx.driver.client.get(f"/channels/{ch_id}/members?page={page}&per_page={per_page}")
        if not batch:
            break
        all_members.extend(batch)
        if len(batch) < per_page:
            break
        page += 1

    # Resolve usernames
    user_ids = [m["user_id"] for m in all_members]
    user_map = resolver.resolve_users(user_ids)

    # Get statuses in bulk
    try:
        statuses_raw = ctx.driver.client.post("/users/status/ids", options=user_ids)
        status_map = {s["user_id"]: s["status"] for s in statuses_raw}
    except Exception:
        status_map = {}

    members_out = []
    for m in all_members:
        uid = m["user_id"]
        info = user_map.get(uid, {})
        entry = {
            "user_id": uid,
            "username": info.get("username", "unknown"),
            "display_name": info.get("display_name", ""),
            "status": status_map.get(uid, "unknown"),
        }
        if info.get("position"):
            entry["position"] = info["position"]
        members_out.append(entry)

    status_order = {"online": 0, "away": 1, "dnd": 2, "offline": 3}
    members_out.sort(key=lambda m: (status_order.get(m["status"], 9), m["username"]))

    if not state.human:
        click.echo(json.dumps(members_out, indent=2))
    else:
        lines = []
        for m in members_out:
            status_icon = {"online": "+", "away": "~", "offline": "-", "dnd": "x"}.get(m["status"], "?")
            pos = f" ({m['position']})" if m.get("position") else ""
            lines.append(f"  {status_icon} @{m['username']}{pos}")
        click.echo(f"{len(members_out)} members:\n" + "\n".join(lines))
