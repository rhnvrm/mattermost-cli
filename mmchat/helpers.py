"""Shared helpers used across CLI commands."""

import contextlib
import io
import re
import sys
from datetime import datetime, timezone
from typing import Optional

import click

from .client import EXIT_ERROR, MMContext
from .formatters import TYPE_LABELS, _iso_ts, channel_ref
from .resolve import Resolver
from .time_utils import parse_since


def resolve_channel(ctx: MMContext, resolver: Resolver, channel_arg: str) -> dict:
    """Resolve a channel argument to a channel dict.

    Supports:
      @username  -> find existing DM channel with that user
      26-char ID -> direct channel ID lookup
      name       -> channel by name (tries each team)
    """
    # @username -> find DM channel by scanning user's channels
    if channel_arg.startswith("@"):
        username = channel_arg[1:]
        try:
            users = ctx.driver.users.get_users_by_usernames([username])
            if not users:
                click.echo(f"Error: User '{username}' not found.", err=True)
                sys.exit(EXIT_ERROR)
            other_id = users[0]["id"]
            for team in ctx.teams:
                channels = ctx.driver.channels.get_channels_for_user(ctx.user_id, team.id)
                for ch in channels:
                    if ch["type"] == "D" and other_id in ch["name"]:
                        return ch
            click.echo(f"Error: No DM channel found with @{username}.", err=True)
            sys.exit(EXIT_ERROR)
        except SystemExit:
            raise
        except Exception as e:
            click.echo(f"Error: Could not find DM channel with @{username}: {e}", err=True)
            sys.exit(EXIT_ERROR)

    # 26-char alphanumeric -> direct ID
    if re.match(r"^[a-z0-9]{26}$", channel_arg):
        try:
            return ctx.driver.channels.get_channel(channel_arg)
        except Exception:
            click.echo(f"Error: Channel ID '{channel_arg}' not found.", err=True)
            sys.exit(EXIT_ERROR)

    # Channel name -> try each team (suppress driver's stderr on 404s)
    for team in ctx.teams:
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                return ctx.driver.channels.get_channel_by_name(team.id, channel_arg)
        except Exception:
            continue

    click.echo(f"Error: Channel '{channel_arg}' not found in any team.", err=True)
    sys.exit(EXIT_ERROR)


def fetch_post_silent(driver, post_id: str) -> Optional[dict]:
    """Fetch a post by ID, suppressing driver stderr on errors."""
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            return driver.posts.get_post(post_id)
    except Exception:
        return None


def search_mentions(ctx: MMContext, since_ms: Optional[int] = None,
                    limit: int = 30) -> list[tuple[dict, str]]:
    """Search for @-mentions across all teams. Returns [(post, team_name)] deduped."""
    all_posts = []
    for team in ctx.teams:
        terms = f"@{ctx.username}"
        if since_ms:
            since_date = datetime.fromtimestamp(since_ms / 1000, tz=timezone.utc)
            terms += f" after:{since_date.strftime('%Y-%m-%d')}"
        result = ctx.driver.posts.search_for_team_posts(
            team.id, {"terms": terms, "is_or_search": False}
        )
        for pid in result.get("order", []):
            post = result.get("posts", {}).get(pid)
            if post:
                all_posts.append((post, team.display_name))

    all_posts.sort(key=lambda pt: pt[0].get("create_at", 0), reverse=True)
    seen = set()
    deduped = []
    for p, t in all_posts:
        if p["id"] not in seen:
            seen.add(p["id"])
            deduped.append((p, t))
    return deduped[:limit]


def get_channels_and_members(ctx: MMContext) -> list[tuple[dict, dict, str]]:
    """Fetch all channels + membership info across teams.

    Returns [(channel, member, team_display_name)] deduped by channel ID.
    """
    results = []
    seen = set()
    for team in ctx.teams:
        channels_raw = ctx.driver.channels.get_channels_for_user(ctx.user_id, team.id)
        members_raw = ctx.driver.channels.get_channel_members_for_user(ctx.user_id, team.id)
        member_map = {m["channel_id"]: m for m in members_raw}
        for ch in channels_raw:
            if ch["id"] in seen:
                continue
            seen.add(ch["id"])
            member = member_map.get(ch["id"])
            if member:
                results.append((ch, member, team.display_name))
    return results


def compute_unreads(channels_members: list[tuple[dict, dict, str]],
                    resolver: Resolver,
                    include_muted: bool = False) -> list[dict]:
    """Compute unread channels from channel+member data."""
    unreads = []
    for ch, member, team_name in channels_members:
        if not include_muted:
            notify = member.get("notify_props", {})
            if notify.get("mark_unread") == "mention":
                continue

        total_root = ch.get("total_msg_count_root")
        seen_root = member.get("msg_count_root")
        if total_root is not None and seen_root is not None:
            unread_count = max(0, total_root - seen_root)
            mention_count = member.get("mention_count_root", 0) or 0
        else:
            total = ch.get("total_msg_count", 0) or 0
            seen = member.get("msg_count", 0) or 0
            unread_count = max(0, total - seen)
            mention_count = member.get("mention_count", 0) or 0

        if unread_count == 0 and mention_count == 0:
            continue

        info = resolver.format_channel(ch)
        unreads.append({
            "channel_id": ch["id"],
            "channel": info["name"],
            "display_name": info["display_name"],
            "type": info["type"],
            "unread": unread_count,
            "mentions": mention_count,
            "team_name": team_name,
            "team_id": ch.get("team_id", ""),
            "last_post_at": ch.get("last_post_at", 0),
        })

    unreads.sort(key=lambda u: (-u["mentions"], -u["unread"]))
    return unreads


def fetch_root_context(ctx: MMContext, posts: list[dict],
                       user_map: dict, authors: dict) -> dict[str, dict]:
    """Fetch root post context for reply posts. Returns {root_id: context_dict}.

    Mutates user_map and authors in place when new users are discovered.
    """
    root_ids = {p.get("root_id") for p in posts if p.get("root_id")}
    root_context: dict[str, dict] = {}
    for rid in root_ids:
        root_post = fetch_post_silent(ctx.driver, rid)
        if not root_post:
            continue
        root_uid = root_post.get("user_id", "")
        if root_uid not in user_map:
            extra = Resolver(ctx.driver, ctx.user_id).resolve_users([root_uid])
            user_map.update(extra)
            authors.update({u: f"@{info['username']}" for u, info in extra.items()})
        root_context[rid] = {
            "author": authors.get(root_uid, "unknown"),
            "message": root_post.get("message", "")[:200],
            "created_at": _iso_ts(root_post.get("create_at", 0)),
        }
    return root_context


def resolve_authors(resolver: Resolver, posts: list[dict]) -> tuple[dict, dict]:
    """Batch-resolve authors for a list of posts. Returns (user_map, authors_dict)."""
    author_ids = list({p["user_id"] for p in posts})
    user_map = resolver.resolve_users(author_ids) if author_ids else {}
    authors = {uid: f"@{info['username']}" for uid, info in user_map.items()}
    return user_map, authors
