---
title: Commands
description: Complete command reference
---

# Commands

All commands output JSON by default. Add `--human` before any command for markdown output. Add `--team <name>` to filter to a specific team.

## mm login

Authenticate with your Mattermost server.

```bash
mm login                    # Interactive: password + MFA
mm login --token <pat>      # Personal Access Token
```

Password login prompts for server URL, username, password, and (if enabled) MFA token. The session token is stored -- your password is never written to disk.

When the session expires, run `mm login` again.

## mm logout

Revoke the current session and clear stored credentials.

```bash
mm logout
```

## mm whoami

Show current user info and validate that auth is working.

```bash
mm whoami
```

Returns your user ID, username, display name, email, and list of teams.

## mm unread

Show channels with unread messages.

```bash
mm unread
mm unread --team Engineering
```

Returns channels sorted by mention count (descending), then unread count.

Each entry includes:

| Field | Description |
|-------|-------------|
| `channel_id` | Internal channel ID |
| `channel` | Display name |
| `ref` | Use this with `mm messages <ref>` |
| `type` | Public, Private, DM, or Group DM |
| `unread` | Number of unread messages |
| `mentions` | Number of @mentions |
| `team` | Team name |
| `last_post_at` | Timestamp of last post |

The `ref` field is important: for named channels it's the channel name (e.g. `general`), for DMs and group DMs it's the channel ID (since their display names aren't addressable). Always use `ref` when passing a channel to other commands.

## mm mentions

Show posts that @mention you.

```bash
mm mentions                   # Last 24 hours (default)
mm mentions --since 2h        # Last 2 hours
mm mentions --since 0         # All time
mm mentions --limit 10        # Max 10 results
```

Results are grouped by channel in `--human` mode.

## mm messages

Read messages from a channel.

```bash
mm messages general                   # By channel name
mm messages @alice                    # DM with a user
mm messages abc123def456...           # By channel ID (for group DMs)
mm messages general --limit 10        # Last 10 messages
mm messages general --since 2h        # Messages from last 2 hours
mm messages general --since today     # Messages from today
```

For group DMs, use the `ref` field from `mm unread` or `mm channels` since group DM display names (e.g. "alice, bob, carol") aren't addressable.

## mm thread

Read a thread by any post ID in that thread.

```bash
mm thread abc123def456...             # Root + last 9 replies (default)
mm thread abc123def456... --limit 0   # Full thread
mm thread abc123def456... --limit 5   # Root + last 4 replies
mm thread abc123def456... --since 1h  # Root + replies from last hour
```

The root message is always included regardless of `--limit` or `--since` so you have context.

The post ID can be any post in the thread -- root or reply. The CLI resolves it to the full thread automatically.

## mm search

Search messages across all teams.

```bash
mm search "deployment issue"
mm search "deployment issue" --limit 10
mm search "from:alice"                        # Mattermost search modifiers
mm search "in:engineering deployment"         # Search in a specific channel
mm search "before:2026-03-01 incident"        # Date filters
```

Supports all [Mattermost search modifiers](https://docs.mattermost.com/collaborate/search-for-messages.html): `from:`, `in:`, `before:`, `after:`, `on:`, etc.

## mm channels

List all channels you belong to.

```bash
mm channels                     # All channels
mm channels --type public       # Only public channels
mm channels --type dm           # Only DMs
mm channels --type group        # Only group DMs
mm channels --type private      # Only private channels
```

Each entry includes a `ref` field for use with `mm messages`.

## Global options

These go before the command name:

```bash
mm --human mentions             # Markdown output
mm --team Engineering unread    # Filter to one team
mm --debug messages general     # Debug logging
mm --version                    # Show version
```
