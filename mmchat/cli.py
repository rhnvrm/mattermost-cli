"""Click CLI - main group and all commands."""

import contextlib
import io
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

import click
from mattermostdriver.exceptions import NoAccessTokenProvided

from . import __version__
from .client import (
    EXIT_AUTH_EXPIRED,
    EXIT_ERROR,
    MMContext,
    create_driver,
    ensure_auth,
    login,
)
from .config import ConfigError, clear_config, get_credentials, save_config
from .formatters import (
    format_channels_json,
    format_channels_md,
    format_post_md,
    format_posts_json,
    format_posts_md,
    format_unread_json,
    format_unread_md,
)
from .resolve import Resolver
from .time_utils import parse_since


class State:
    """Global CLI state passed via click context."""

    def __init__(self):
        self.human: bool = False
        self.team: Optional[str] = None
        self.debug: bool = False


pass_state = click.make_pass_decorator(State, ensure=True)


@click.group()
@click.option("--human", is_flag=True, help="Human-readable markdown output (default is JSON).")
@click.option("--team", default=None, help="Filter to a specific team.")
@click.option("--debug", is_flag=True, help="Enable debug output.")
@click.version_option(version=__version__, prog_name="mm")
@click.pass_context
def main(ctx, human, team, debug):
    """mm - Mattermost CLI. Output is JSON by default."""
    ctx.ensure_object(State)
    ctx.obj.human = human
    ctx.obj.team = team
    ctx.obj.debug = debug


def get_context(state: State) -> MMContext:
    """Load credentials and return an authenticated MMContext."""
    try:
        creds = get_credentials()
    except ConfigError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(EXIT_ERROR)

    team = state.team or creds.get("team")
    return ensure_auth(creds["url"], creds["token"], team)


# -- Auth commands --


@main.command()
@click.option("--url", prompt=False, default=None, help="Mattermost server URL.")
@click.option("--token", "pat", default=None, help="Personal Access Token (skips password flow).")
@click.option("--user", "login_id", default=None, help="Username or email (non-interactive).")
@click.option("--password", default=None, help="Password (non-interactive).")
def login_cmd(url, pat, login_id, password):
    """Authenticate with Mattermost and store session token."""
    # Prompt for URL if not given
    if not url:
        url = click.prompt("Mattermost URL")

    # Normalize URL
    if not url.startswith("http"):
        url = f"https://{url}"

    # PAT flow
    if pat:
        _login_with_pat(url, pat)
        return

    # Password flow
    if not login_id:
        login_id = click.prompt("Username or email")
    if not password:
        password = click.prompt("Password", hide_input=True)

    # MFA - prompt upfront (optional, press Enter to skip)
    mfa_token = click.prompt("MFA code (press Enter to skip)", default="", show_default=False)
    mfa_token = mfa_token.strip() or None

    _login_with_password(url, login_id, password, mfa_token)


# Register with the name 'login' (can't name the function 'login' - conflicts with client.login)
login_cmd.name = "login"


def _login_with_pat(url: str, pat: str) -> None:
    """Validate PAT and save config."""
    driver = create_driver(url, pat)
    try:
        login(driver)
    except NoAccessTokenProvided:
        click.echo("Error: Invalid Personal Access Token.", err=True)
        sys.exit(EXIT_ERROR)
    except ConnectionError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(EXIT_ERROR)

    # Show teams the user belongs to
    _show_teams(driver)

    path = save_config(url=url, auth_method="token", token=pat)
    click.echo(f"Logged in as @{driver.client.username} (PAT)")
    click.echo(f"Config saved to {path}")


def _login_with_password(
    url: str,
    login_id: str,
    password: str,
    mfa_token: Optional[str] = None,
) -> None:
    """Login with password (+MFA), save session token."""
    # IMPORTANT: debug=False always during password login.
    # The driver logs passwords when debug=True.
    driver = create_driver(url, token="", login_id=login_id, password=password, mfa_token=mfa_token)

    try:
        login(driver)
    except NoAccessTokenProvided as e:
        # Check if MFA is required but wasn't provided
        err_msg = str(e).lower()
        if "mfa" in err_msg and mfa_token is None:
            click.echo("MFA is required for this account.")
            mfa_code = click.prompt("MFA code")
            # Must create a fresh driver with mfa_token set
            driver = create_driver(
                url, token="", login_id=login_id, password=password, mfa_token=mfa_code.strip()
            )
            try:
                login(driver)
            except NoAccessTokenProvided:
                click.echo("Error: Invalid credentials or MFA code.", err=True)
                sys.exit(EXIT_ERROR)
        else:
            click.echo("Error: Invalid username or password.", err=True)
            sys.exit(EXIT_ERROR)
    except ConnectionError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(EXIT_ERROR)

    # Session token is now on driver.client.token
    session_token = driver.client.token

    # Show teams the user belongs to
    _show_teams(driver)

    path = save_config(url=url, auth_method="password", token=session_token)
    click.echo(f"Logged in as @{driver.client.username}")
    click.echo(f"Config saved to {path}")


def _show_teams(driver) -> None:
    """Show teams the user belongs to. No selection needed - commands read all teams."""
    teams = driver.teams.get_user_teams(driver.client.userid)
    if not teams:
        click.echo("Warning: You don't belong to any teams.")
        return
    if len(teams) == 1:
        click.echo(f"Team: {teams[0]['display_name']} ({teams[0]['name']})")
    else:
        click.echo("Teams:")
        for t in teams:
            click.echo(f"  - {t['display_name']} ({t['name']})")
        click.echo("Use --team <name> to filter commands to a specific team.")


@main.command()
@pass_state
def whoami(state):
    """Show current user info and validate auth."""
    ctx = get_context(state)

    user = ctx.driver.users.get_user(ctx.user_id)

    if not state.human:
        click.echo(
            json.dumps(
                {
                    "user_id": user["id"],
                    "username": user["username"],
                    "display_name": f"{user.get('first_name', '')} {user.get('last_name', '')}".strip(),
                    "email": user.get("email", ""),
                    "teams": [{"id": t.id, "name": t.name, "display_name": t.display_name} for t in ctx.teams],
                },
                indent=2,
            )
        )
        return

    display_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
    click.echo(f"Username:     @{user['username']}")
    if display_name:
        click.echo(f"Display name: {display_name}")
    if user.get("email"):
        click.echo(f"Email:        {user['email']}")
    click.echo(f"User ID:      {user['id']}")
    click.echo(f"Teams:")
    for t in ctx.teams:
        click.echo(f"  - {t.display_name} ({t.name})")


@main.command()
def logout():
    """Revoke session and clear stored credentials."""
    from .config import load_config

    config = load_config()
    if config.get("url") and config.get("token"):
        # Try to revoke server-side session
        try:
            driver = create_driver(config["url"], config["token"])
            driver.login()
            driver.logout()
        except Exception:
            # Token might already be expired - that's fine
            pass

    clear_config()
    click.echo("Logged out. Stored credentials cleared.")


# -- Data commands --


@main.command()
@click.option("--type", "ch_type", type=click.Choice(["public", "private", "dm", "group"]), help="Filter by channel type.")
@pass_state
def channels(state, ch_type):
    """List channels you belong to."""
    ctx = get_context(state)
    resolver = Resolver(ctx.driver, ctx.user_id)

    type_filter = {"public": "O", "private": "P", "dm": "D", "group": "G"}.get(ch_type)

    all_channels = []
    for team in ctx.teams:
        raw = ctx.driver.channels.get_channels_for_user(ctx.user_id, team.id)
        for ch in raw:
            info = resolver.format_channel(ch)
            info["team_name"] = team.display_name
            info["team_id"] = team.id
            if type_filter and ch["type"] != type_filter:
                continue
            all_channels.append(info)

    # Sort: type order (O, P, G, D) then name
    type_order = {"O": 0, "P": 1, "G": 2, "D": 3}
    all_channels.sort(key=lambda c: (type_order.get(c["type"], 9), c["display_name"].lower()))

    # Deduplicate (channels can appear in multiple teams for cross-team channels)
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

    unreads = []
    for team in ctx.teams:
        # 2 API calls per team instead of N per channel
        channels_raw = ctx.driver.channels.get_channels_for_user(ctx.user_id, team.id)
        members_raw = ctx.driver.channels.get_channel_members_for_user(ctx.user_id, team.id)

        # Build member lookup: channel_id -> member
        member_map = {m["channel_id"]: m for m in members_raw}

        for ch in channels_raw:
            member = member_map.get(ch["id"])
            if not member:
                continue

            # Skip muted channels unless --include-muted
            if not include_muted:
                notify = member.get("notify_props", {})
                if notify.get("mark_unread") == "mention":
                    continue

            # Use root counts (matches CRT-enabled UI) with fallback to total
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
                "team_name": team.display_name,
                "team_id": team.id,
                "last_post_at": ch.get("last_post_at", 0),
            })

    # Sort: mentions desc, then unread desc
    unreads.sort(key=lambda u: (-u["mentions"], -u["unread"]))

    # Deduplicate
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


def _enrich_posts(
    posts: list[dict],
    authors: dict[str, str],
    resolver: Resolver,
    team_by_post: dict[str, str],
) -> list[dict]:
    """Build enriched post dicts for JSON output (shared by mentions + search)."""
    from .formatters import _iso_ts

    enriched = []
    for p in posts:
        uid = p.get("user_id", "")
        ch = resolver.resolve_channel(p.get("channel_id", ""))
        root_id = p.get("root_id", "")
        file_ids = p.get("file_ids") or []
        entry = {
            "id": p["id"],
            "thread_id": root_id if root_id else p["id"],
            "is_reply": bool(root_id),
            "author": authors.get(uid, "unknown"),
            "message": p.get("message", ""),
            "created_at": _iso_ts(p.get("create_at", 0)),
            "channel": ch["display_name"],
            "channel_id": p.get("channel_id", ""),
            "team": team_by_post.get(p["id"], ""),
            "file_count": len(file_ids),
        }
        if not root_id and p.get("reply_count"):
            entry["reply_count"] = p["reply_count"]
        if file_ids and p.get("metadata", {}).get("files"):
            entry["files"] = [
                {"name": f.get("name", ""), "size": f.get("size", 0)}
                for f in p["metadata"]["files"]
            ]
        enriched.append(entry)
    return enriched


def _resolve_channel(ctx: MMContext, resolver: Resolver, channel_arg: str) -> dict:
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
            # Search existing channels for the DM (read-only - no channel creation)
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


@main.command()
@click.argument("channel")
@click.option("--since", "since", default=None, help="Show messages since (1h, 2d, today, 2026-03-05).")
@click.option("--limit", "limit", default=30, type=int, show_default=True, help="Max messages (max 200).")
@pass_state
def messages(state, channel, since, limit):
    """Read messages from a channel.

    CHANNEL can be a channel name, @username (for DMs), or a channel ID.
    """
    ctx = get_context(state)
    resolver = Resolver(ctx.driver, ctx.user_id)

    ch = _resolve_channel(ctx, resolver, channel)
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

    # Build post list in order (newest first from API, reverse for display)
    posts = [posts_map[pid] for pid in order if pid in posts_map]
    posts.reverse()  # chronological order

    # Apply limit (API might return more with 'since' param)
    posts = posts[:limit]

    # Resolve all authors in batch
    author_ids = list({p["user_id"] for p in posts})
    user_map = resolver.resolve_users(author_ids)
    authors = {uid: f"@{info['username']}" for uid, info in user_map.items()}

    if not state.human:
        click.echo(format_posts_json(posts, authors, ch_info["display_name"]))
    else:
        click.echo(format_posts_md(posts, authors, ch_info["display_name"]))


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
    # API returns newest-first, sort chronologically
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

    # Resolve authors
    author_ids = list({p["user_id"] for p in posts})
    user_map = resolver.resolve_users(author_ids)
    authors = {uid: f"@{info['username']}" for uid, info in user_map.items()}

    # Resolve channel name for context
    if posts:
        ch_info = resolver.resolve_channel(posts[0].get("channel_id", ""))
        ch_name = ch_info["display_name"]
    else:
        ch_name = None

    if not state.human:
        click.echo(format_posts_json(posts, authors, ch_name))
    else:
        click.echo(format_posts_md(posts, authors, ch_name))


@main.command()
@click.option("--since", "since", default="1d", show_default=True, help="Show mentions since (1h, 2d, today, 0 for all).")
@click.option("--limit", "limit", default=30, type=int, show_default=True, help="Max results.")
@pass_state
def mentions(state, since, limit):
    """Show recent posts that mention you. Defaults to last 24h."""
    ctx = get_context(state)
    resolver = Resolver(ctx.driver, ctx.user_id)

    all_posts = []
    for team in ctx.teams:
        terms = f"@{ctx.username}"
        if since and since != "0":
            try:
                since_ms = parse_since(since)
                since_date = datetime.fromtimestamp(since_ms / 1000, tz=timezone.utc)
                terms += f" after:{since_date.strftime('%Y-%m-%d')}"
            except ValueError as e:
                click.echo(f"Error: {e}", err=True)
                sys.exit(EXIT_ERROR)

        result = ctx.driver.posts.search_for_team_posts(team.id, {"terms": terms, "is_or_search": False})
        order = result.get("order", [])
        posts_map = result.get("posts", {})

        for pid in order:
            if pid in posts_map:
                all_posts.append((posts_map[pid], team.display_name))

    # Sort by create_at desc, deduplicate (same post can appear in multiple teams)
    all_posts.sort(key=lambda pt: pt[0].get("create_at", 0), reverse=True)
    seen_ids = set()
    deduped = []
    for p, t in all_posts:
        if p["id"] not in seen_ids:
            seen_ids.add(p["id"])
            deduped.append((p, t))
    deduped = deduped[:limit]

    posts_only = [p for p, _ in deduped]
    team_by_post = {p["id"]: t for p, t in deduped}

    # Resolve authors and channels
    author_ids = list({p["user_id"] for p in posts_only})
    user_map = resolver.resolve_users(author_ids)
    authors = {uid: f"@{info['username']}" for uid, info in user_map.items()}

    for p in posts_only:
        resolver.resolve_channel(p.get("channel_id", ""))

    if not state.human:
        click.echo(json.dumps(_enrich_posts(posts_only, authors, resolver, team_by_post), indent=2))
    else:
        # Group by channel
        by_channel = defaultdict(list)
        for p in posts_only:
            ch = resolver.resolve_channel(p.get("channel_id", ""))
            by_channel[ch["display_name"]].append(p)

        lines = []
        for ch_name, posts in by_channel.items():
            lines.append(f"## #{ch_name}\n")
            for p in posts:
                author = authors.get(p.get("user_id", ""), "unknown")
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

    # Sort by create_at desc, deduplicate
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

    # Resolve
    author_ids = list({p["user_id"] for p in posts_only})
    user_map = resolver.resolve_users(author_ids)
    authors = {uid: f"@{info['username']}" for uid, info in user_map.items()}

    for p in posts_only:
        resolver.resolve_channel(p.get("channel_id", ""))

    if not state.human:
        click.echo(json.dumps(_enrich_posts(posts_only, authors, resolver, team_by_post), indent=2))
    else:
        lines = []
        for p in posts_only:
            author = authors.get(p.get("user_id", ""), "unknown")
            ch = resolver.resolve_channel(p.get("channel_id", ""))
            lines.append(format_post_md(p, author, ch["display_name"]))
            lines.append("")
        click.echo("\n".join(lines).rstrip() if lines else "No results found.")
