---
title: Quickstart
description: Get running in 2 minutes
---

# Quickstart

## Install

```bash
# With uvx (no install needed)
uvx mattermost-cli --help

# Or install with pip
pip install mattermost-cli
```

This gives you the `mm` command.

## Authenticate

**Password + MFA** (most common):

```bash
mm login
```

You'll be prompted for your server URL, username, password, and MFA token. The session token is stored locally -- your password is never saved to disk.

**Personal Access Token** (if your server allows it):

```bash
mm login --token your-pat-here
```

You'll be prompted for the server URL. The token is stored and used for all future requests.

**Verify it works:**

```bash
mm whoami
```

```json
{
  "user_id": "w1gab...",
  "username": "alice",
  "display_name": "Alice Chen",
  "email": "alice@example.com",
  "teams": [
    {"id": "kofs...", "name": "engineering", "display_name": "Engineering"}
  ]
}
```

## First commands

**Check what's unread:**

```bash
mm unread
```

This returns all channels with unread messages, sorted by mention count. Each entry includes a `ref` field -- use it to read messages from that channel.

**See who's mentioning you:**

```bash
mm mentions
```

Returns @mentions from the last 24 hours. Each mention includes `thread_id` so you can fetch the full conversation.

**Read a thread:**

```bash
mm thread abc123def456ghi789jkl012
```

Returns the root message + last 9 replies by default. Use `--limit 0` for the full thread, or `--since 1h` for recent replies only.

**Human-readable output:**

```bash
mm --human mentions
```

```
## #engineering

**@bob** (06:52) [2 replies, files: screenshot.png]
@alice can you review this deployment config?

## #incidents

**@carol** (04:17)
Reminder to check the monitoring dashboard. @alice @dave
```

## Configuration

Credentials are stored at `~/.config/mm/config.json` with 0600 permissions. Only the session token and server URL are saved.

Environment variables override the config file:

| Variable | Description |
|----------|-------------|
| `MATTERMOST_URL` | Server URL |
| `MATTERMOST_TOKEN` | Auth token |
| `MATTERMOST_TEAM` | Filter to one team |
| `MM_CONFIG_PATH` | Custom config file path |

## Next steps

- [Commands](guide/commands/) -- Full reference for all commands
- [JSON Output](guide/json-output/) -- Understand the output format
- [Tips](guide/tips/) -- Filtering, searching, and workflow patterns
