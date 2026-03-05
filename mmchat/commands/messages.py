"""Message reading commands: messages, thread."""

import json
import sys

import click

from ..cli import State, get_context, main, pass_state
from ..client import EXIT_ERROR, MMContext
from ..formatters import _iso_ts, format_posts_json, format_posts_md
from ..helpers import fetch_post_silent, resolve_authors, resolve_channel
from ..resolve import Resolver
from ..time_utils import parse_since


@main.command()
@click.argument("channel")
@click.option("--since", "since", default=None, help="Show messages since (1h, 2d, today, 2026-03-05).")
@click.option("--limit", "limit", default=30, type=int, show_default=True, help="Max messages (max 200).")
@click.option("--threads", is_flag=True, default=False, help="Group by thread: show root + last reply + reply count.")
@pass_state
def messages(state, channel, since, limit, threads):
    """Read messages from a channel.

    CHANNEL can be a channel name, @username (for DMs), or a channel ID.
    Use --threads to see a thread index instead of flat messages.
    """
    ctx = get_context(state)
    resolver = Resolver(ctx.driver, ctx.user_id)

    ch = resolve_channel(ctx, resolver, channel)
    ch_info = resolver.format_channel(ch)

    params = {"per_page": min(limit, 200)}
    if since:
        try:
            params["since"] = parse_since(since)
        except ValueError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(EXIT_ERROR)

    result = ctx.driver.posts.get_posts_for_channel(ch["id"], params=params)

    order = result.get("order", [])
    posts_map = result.get("posts", {})

    posts = [posts_map[pid] for pid in order if pid in posts_map]
    posts.reverse()  # chronological order
    posts = posts[:limit]

    user_map, authors = resolve_authors(resolver, posts)

    if threads:
        _render_thread_index(state, ctx, ch_info, posts, user_map, authors)
        return

    if not state.human:
        click.echo(format_posts_json(posts, authors, ch_info["display_name"]))
    else:
        click.echo(format_posts_md(posts, authors, ch_info["display_name"]))


def _render_thread_index(state: State, ctx: MMContext, ch_info: dict,
                         posts: list[dict], user_map: dict, authors: dict) -> None:
    """Group messages by thread and render a summary index."""
    thread_map: dict[str, list[dict]] = {}
    for p in posts:
        tid = p.get("root_id") or p["id"]
        thread_map.setdefault(tid, []).append(p)

    thread_summaries = []
    for tid, tposts in thread_map.items():
        root = fetch_post_silent(ctx.driver, tid)
        if root:
            root_uid = root.get("user_id", "")
            if root_uid not in user_map:
                extra = Resolver(ctx.driver, ctx.user_id).resolve_users([root_uid])
                user_map.update(extra)
                authors.update({u: f"@{info['username']}" for u, info in extra.items()})
        else:
            root = next((tp for tp in tposts if not tp.get("root_id")), tposts[0])

        last_reply = tposts[-1] if tposts[-1]["id"] != root["id"] else None
        reply_count = root.get("reply_count") or max(0, len(tposts) - 1)

        summary = {
            "thread_id": tid,
            "root_author": authors.get(root.get("user_id", ""), "unknown"),
            "root_message": root.get("message", "")[:200],
            "root_created_at": _iso_ts(root.get("create_at", 0)),
            "reply_count": reply_count,
            "channel": ch_info["display_name"],
        }
        if last_reply:
            summary["last_reply_author"] = authors.get(last_reply.get("user_id", ""), "unknown")
            summary["last_reply_message"] = last_reply.get("message", "")[:200]
            summary["last_reply_at"] = _iso_ts(last_reply.get("create_at", 0))
        thread_summaries.append(summary)

    thread_summaries.sort(
        key=lambda t: t.get("last_reply_at", t["root_created_at"]),
        reverse=True,
    )

    if not state.human:
        click.echo(json.dumps(thread_summaries, indent=2))
    else:
        lines = [f"## #{ch_info['display_name']} - {len(thread_summaries)} active threads\n"]
        for t in thread_summaries:
            rc = t["reply_count"]
            lines.append(f"**{t['root_author']}** ({t['root_created_at']}) [{rc} replies]")
            lines.append(f"  {t['root_message'][:80]}")
            if t.get("last_reply_author"):
                lines.append(f"  > last: {t['last_reply_author']} ({t['last_reply_at']}): {t.get('last_reply_message', '')[:60]}")
            lines.append(f"  thread_id: {t['thread_id']}")
            lines.append("")
        click.echo("\n".join(lines).rstrip())


@main.command()
@click.argument("post_id")
@click.option("--limit", "limit", default=10, type=int, show_default=True, help="Max messages (root + last N-1 replies). 0 for all.")
@click.option("--since", "since", default=None, help="Show replies since (1h, 2d, today). Root always included.")
@pass_state
def thread(state, post_id, limit, since):
    """Read a thread by post ID.

    POST_ID can be any post in the thread (root or reply).
    Returns root message + last 9 replies by default.
    Use --limit 0 for full thread.
    """
    ctx = get_context(state)
    resolver = Resolver(ctx.driver, ctx.user_id)

    try:
        result = ctx.driver.posts.get_thread(post_id)
    except Exception as e:
        click.echo(f"Error: Could not fetch thread '{post_id}': {e}", err=True)
        sys.exit(EXIT_ERROR)

    order = result.get("order", [])
    posts_map = result.get("posts", {})

    posts = [posts_map[pid] for pid in order if pid in posts_map]
    posts.sort(key=lambda p: p.get("create_at", 0))

    # Apply --since filter (keep root + replies after since)
    if since and posts:
        try:
            since_ms = parse_since(since)
        except ValueError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(EXIT_ERROR)
        root = posts[0]
        replies = [p for p in posts[1:] if p.get("create_at", 0) >= since_ms]
        posts = [root] + replies

    # Apply --limit (keep root + last N-1 replies). 0 = no limit.
    if limit and limit > 0 and len(posts) > limit:
        root = posts[0]
        posts = [root] + posts[-(limit - 1):]

    _user_map, authors = resolve_authors(resolver, posts)

    # Resolve channel name for context
    ch_name = None
    if posts:
        ch_info = resolver.resolve_channel(posts[0].get("channel_id", ""))
        ch_name = ch_info["display_name"]

    if not state.human:
        click.echo(format_posts_json(posts, authors, ch_name))
    else:
        click.echo(format_posts_md(posts, authors, ch_name))
