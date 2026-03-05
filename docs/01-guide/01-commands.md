---
title: Commands
description: Complete command reference
---

# Commands

All commands output JSON by default. Add `--human` before any command for markdown output. Add `--team <name>` to filter to a specific team.

## mm overview

Get oriented in one call. Returns mentions, unread channels, and recently active channels.

```bash
mm overview                   # Last 6 hours (default)
mm overview --since 1d        # Last 24 hours
mm overview --since 0         # No time filter
```

This is the best starting point - it replaces separate calls to `mm mentions`, `mm unread`, and `mm channels --since`.

## mm messages

Read messages from a channel.

```bash
mm messages general                   # By channel name
mm messages @alice                    # DM with a user
mm messages abc123def456...           # By channel ID (for group DMs)
mm messages general --limit 10        # Last 10 messages
mm messages general --since 2h        # Messages from last 2 hours
mm messages general --since today     # Messages from today
mm messages general --threads         # Thread index view
```

The `--threads` flag groups messages by thread and shows root message + reply count + last reply. Useful for busy channels where flat messages are hard to follow.

For group DMs, use the `ref` field from `mm overview` or `mm channels` since group DM display names aren't addressable.

## mm thread

Read a thread by any post ID in that thread.

```bash
mm thread abc123def456...             # Root + last 9 replies (default)
mm thread abc123def456... --limit 0   # Full thread
mm thread abc123def456... --limit 5   # Root + last 4 replies
mm thread abc123def456... --since 1h  # Root + replies from last hour
```

The root message is always included regardless of `--limit` or `--since` so you have context.

The post ID can be any post in the thread (root or reply). The CLI resolves it to the full thread automatically.

## mm mentions

Show posts that @mention you. Reply-mentions include a `root` field with the original message being replied to.

```bash
mm mentions                   # Last 24 hours (default)
mm mentions --since 2h        # Last 2 hours
mm mentions --since 0         # All time
mm mentions --limit 10        # Max 10 results
```

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

## mm channel

Show info about a single channel.

```bash
mm channel general
mm channel @alice              # DM info
```

Returns purpose, header, member count, pinned post count, last post time, and creation date.

## mm channels

List all channels you belong to.

```bash
mm channels                     # All channels
mm channels --type public       # Only public channels
mm channels --type dm           # Only DMs
mm channels --type group        # Only group DMs
mm channels --since 6h          # Channels with recent activity
```

Each entry includes a `ref` field for use with `mm messages`.

## mm unread

Show channels with unread messages. Muted channels are hidden by default.

```bash
mm unread
mm unread --include-muted
```

Returns channels sorted by mention count (descending), then unread count.

## mm pinned

Show pinned posts in a channel.

```bash
mm pinned general
mm pinned general --limit 5
```

Pinned posts are the channel's institutional memory - decisions, links, and important context.

## mm members

List members of a channel with online status.

```bash
mm members general
```

Sorted by status (online first). Shows username, display name, position, and status.

## mm user

Show user profile and status.

```bash
mm user @alice
mm user alice                  # @ prefix is optional
```

Returns name, position, email, status (online/away/offline/dnd), and timezone.

## mm login

Authenticate with your Mattermost server.

```bash
mm login --url https://chat.example.com                # Interactive: password + MFA
mm login --url https://chat.example.com --token <pat>  # Personal Access Token
```

Password login prompts for username, password, and (if enabled) MFA token. The session token is stored - your password is never written to disk.

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

## Global options

These go before the command name:

```bash
mm --human mentions             # Markdown output
mm --team Engineering unread    # Filter to one team
mm --debug messages general     # Debug logging
mm --version                    # Show version
```
