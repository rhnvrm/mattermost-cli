# Agent Instructions

Instructions for AI agents working on this repository.

## Overview

mattermost-cli is a Mattermost CLI for humans and agents. JSON output by default for agent consumption, `--human` flag for markdown. Published to PyPI as `mattermost-cli`, CLI command is `mm`.

## Architecture

```
mmchat/
  cli.py         # Click commands - all 8 commands, State object, argument resolution
  client.py      # Driver wrapper - URL parsing, auth, MMContext, Team dataclass
  config.py      # Token storage at ~/.config/mm/config.json (0600 perms)
  resolve.py     # User/channel ID resolution with in-memory caching (Resolver class)
  formatters.py  # JSON (default) and markdown output formatting
  time_utils.py  # --since argument parsing (relative, named, absolute, raw epoch)
tests/
  test_time_utils.py  # Pure function tests
  test_config.py      # File I/O with tmp_path fixtures
  test_client.py      # URL parsing, formatter output shapes
```

## Key design decisions

**Read-only**: No write operations to Mattermost. The `_resolve_channel` function scans existing channels for DMs instead of using `create_direct_message_channel` (which is a write op).

**JSON-first output**: Default output is JSON for agent consumption. `--human` flag switches to markdown tables. All formatters have both `format_*_json` and `format_*_md` variants.

**Agent-tuned defaults**: Commands are tuned for an agent running them bare (no flags), then using `--help` to refine:
- `mm thread` defaults to `--limit 10` (root + last 9 replies), not full thread
- `mm mentions` defaults to `--since 1d`, not all time
- `mm messages` defaults to `--limit 30`

**Cross-team by default**: All data commands iterate all user teams and deduplicate results. `--team` narrows to one.

**No passwords on disk**: Only session tokens are stored. Password+MFA login creates a session token and stores that. Config file has 0600 permissions, directory 0700.

## Dependencies

- `mattermostdriver` (7.3.2) - wraps Mattermost REST API v4. The driver takes separate scheme/host/port options, NOT a full URL. `client.py:create_driver()` handles URL parsing.
- `click` (8.0+) - CLI framework
- `httpx` - HTTP client (used by mattermostdriver internally, also imported for ConnectError handling)

## Testing

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

Tests cover pure logic only (config, time parsing, URL parsing, formatters). API-dependent commands are tested manually against a live instance.

When adding tests: use `tmp_path` and `monkeypatch` for isolation. Don't mock the driver - test pure functions that don't need it.

## Common patterns

**Adding a new CLI command**: 
1. Add the function in `cli.py` with `@main.command()` and `@pass_state`
2. Use `get_context(state)` to get authenticated `MMContext`
3. Create `Resolver(ctx.driver, ctx.user_id)` if you need name resolution
4. Output with `format_*_json` / `format_*_md` based on `state.human`

**JSON output fields for posts**: Every post includes `thread_id` (root_id if reply, own id if root), `is_reply`, `reply_count` (on root posts only), `created_at` (ISO 8601), `file_count`, and `files` (with name/size when available). These fields exist specifically for agent triage workflows.

**The `ref` field**: `mm unread` and `mm channels` JSON output includes a `ref` field - the exact string to pass to `mm messages <ref>`. For named channels this is the channel name (e.g. `gtt`), for DMs/group DMs it's the channel_id (since their display names like "karan, rhnvrm, shravan.bk" aren't addressable). Always use `ref`, never `channel` or `channel_id` directly.

**Resolver caching**: `Resolver` caches user and channel lookups per session. Use `resolve_users()` for batch resolution (one API call for all uncached IDs). Call `format_channel()` (public method) for channel info - not `_resolve_dm_name` directly.

## Gotchas

- The mattermostdriver logs passwords when `debug=True`. `create_driver()` always sets `debug=False`.
- DM channel names are `{uid1}__{uid2}` (double underscore). Group DMs are hashes.
- `get_channels_for_user` returns raw API channel dicts. The `type` field is a single letter: O/P/D/G. Formatters map these to "Public"/"Private"/"DM"/"Group DM".
- Thread API returns posts newest-first. Must sort by `create_at` for chronological display.
- The `--since` filter on `mm thread` keeps the root post regardless of age (for context), then filters replies by time.
- `reply_count` comes from the Mattermost API post object - only present on root posts that have replies.
- File metadata (`name`, `size`) is in `post["metadata"]["files"]` - only present when the API returns it (depends on post age and server config).
- `mm mentions` uses Mattermost search API with `@username after:YYYY-MM-DD` syntax. The `--since 0` disables the date filter.

## Publishing

```bash
# Build
python -m build

# Upload to PyPI
twine upload dist/*

# Users install with
uvx mmchat
# or
pip install mmchat
```

The PyPI package name is `mattermost-cli`. The CLI command is `mm`.
