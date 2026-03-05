"""Search commands: mentions, search."""

import json
import sys
from collections import defaultdict

import click

from ..cli import get_context, main, pass_state
from ..client import EXIT_ERROR
from ..formatters import enrich_posts, format_post_md
from ..helpers import fetch_root_context, resolve_authors, search_mentions
from ..resolve import Resolver
from ..time_utils import parse_since


@main.command()
@click.option("--since", "since", default="1d", show_default=True, help="Show mentions since (1h, 2d, today, 0 for all).")
@click.option("--limit", "limit", default=30, type=int, show_default=True, help="Max results.")
@pass_state
def mentions(state, since, limit):
    """Show recent posts that mention you. Defaults to last 24h."""
    ctx = get_context(state)
    resolver = Resolver(ctx.driver, ctx.user_id)

    since_ms = None
    if since and since != "0":
        try:
            since_ms = parse_since(since)
        except ValueError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(EXIT_ERROR)

    mentions_raw = search_mentions(ctx, since_ms, limit)

    posts_only = [p for p, _ in mentions_raw]
    team_by_post = {p["id"]: t for p, t in mentions_raw}

    user_map, authors = resolve_authors(resolver, posts_only)

    # Resolve channel names
    channel_by_post = {}
    for p in posts_only:
        ch = resolver.resolve_channel(p.get("channel_id", ""))
        channel_by_post[p["id"]] = ch["display_name"]

    # Fetch root post context for replies
    root_context = fetch_root_context(ctx, posts_only, user_map, authors)

    enriched = enrich_posts(posts_only, authors, team_by_post=team_by_post,
                            channel_by_post=channel_by_post)

    # Attach root context to reply mentions
    for entry in enriched:
        if entry["is_reply"]:
            rc = root_context.get(entry["thread_id"])
            if rc:
                entry["root"] = rc

    if not state.human:
        click.echo(json.dumps(enriched, indent=2))
    else:
        by_channel: dict[str, list[dict]] = defaultdict(list)
        for p in posts_only:
            ch = resolver.resolve_channel(p.get("channel_id", ""))
            by_channel[ch["display_name"]].append(p)

        lines = []
        for ch_name, ch_posts in by_channel.items():
            lines.append(f"## #{ch_name}\n")
            for p in ch_posts:
                author = authors.get(p.get("user_id", ""), "unknown")
                rc = root_context.get(p.get("root_id", ""))
                if rc:
                    lines.append(f"*re: {rc['author']}: {rc['message'][:80]}*\n")
                lines.append(format_post_md(p, author))
                lines.append("")
        click.echo("\n".join(lines).rstrip() if lines else "No mentions found.")


@main.command()
@click.argument("query")
@click.option("--limit", "limit", default=30, type=int, show_default=True, help="Max results.")
@pass_state
def search(state, query, limit):
    """Search messages across all teams.

    Supports Mattermost search modifiers: from:user, in:channel,
    before:date, after:date, on:date.
    """
    ctx = get_context(state)
    resolver = Resolver(ctx.driver, ctx.user_id)

    all_posts = []
    for team in ctx.teams:
        result = ctx.driver.posts.search_for_team_posts(team.id, {"terms": query, "is_or_search": False})
        order = result.get("order", [])
        posts_map = result.get("posts", {})

        for pid in order:
            if pid in posts_map:
                all_posts.append((posts_map[pid], team.display_name))

    seen_ids = set()
    deduped = []
    all_posts.sort(key=lambda pt: pt[0].get("create_at", 0), reverse=True)
    for p, t in all_posts:
        if p["id"] not in seen_ids:
            seen_ids.add(p["id"])
            deduped.append((p, t))
    deduped = deduped[:limit]

    posts_only = [p for p, _ in deduped]
    team_by_post = {p["id"]: t for p, t in deduped}

    _user_map, authors = resolve_authors(resolver, posts_only)

    channel_by_post = {}
    for p in posts_only:
        ch = resolver.resolve_channel(p.get("channel_id", ""))
        channel_by_post[p["id"]] = ch["display_name"]

    if not state.human:
        enriched = enrich_posts(posts_only, authors, team_by_post=team_by_post,
                                channel_by_post=channel_by_post)
        click.echo(json.dumps(enriched, indent=2))
    else:
        lines = []
        for p in posts_only:
            author = authors.get(p.get("user_id", ""), "unknown")
            ch = resolver.resolve_channel(p.get("channel_id", ""))
            lines.append(format_post_md(p, author, ch["display_name"]))
            lines.append("")
        click.echo("\n".join(lines).rstrip() if lines else "No results found.")
