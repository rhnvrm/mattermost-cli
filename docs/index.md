---
title: mattermost-cli
description: Mattermost CLI for humans and agents
---

# mattermost-cli

A CLI for Mattermost that outputs JSON by default, designed for both human use and agent automation. Runs against any Mattermost server with personal access tokens or password+MFA auth.

## Install

```bash
# Run directly (no install)
uvx --from mattermost-cli mm --help

# Or install globally
pip install mattermost-cli
mm --help
```

## What it does

```bash
mm login                          # Authenticate (password+MFA or token)
mm unread                         # Channels with unread messages
mm mentions                       # Posts that @mention you (last 24h)
mm messages general               # Read channel messages
mm messages @knadh                # Read DMs with a user
mm thread abc123def456...         # Read a thread by post ID
mm search "deployment issue"      # Search across all teams
mm channels                       # List all your channels
```

Every command outputs JSON by default. Add `--human` for markdown.

## JSON-first

Default output is structured JSON with fields designed for programmatic consumption:

```json
{
  "id": "abc123...",
  "thread_id": "def456...",
  "is_reply": true,
  "author": "@alice",
  "message": "Can you check this?",
  "created_at": "2026-03-05T06:52:30Z",
  "channel": "engineering",
  "reply_count": 12,
  "file_count": 1,
  "files": [{"name": "screenshot.png", "size": 66657}]
}
```

ISO 8601 timestamps, human-readable type labels, thread IDs on every post, file metadata included.

## Agent-tuned defaults

Commands are tuned for running without flags first, then refining with `--help`:

- `mm mentions` defaults to last 24 hours (not all time)
- `mm thread` returns root + last 9 replies (not the entire thread)
- `mm unread` includes a `ref` field you can pass directly to `mm messages`

## Learn more

- [Quickstart](quickstart/) -- Install, authenticate, first commands
- **Guide**
  - [Commands](guide/commands/) -- All commands with examples
  - [JSON Output](guide/json-output/) -- Output format reference
  - [Authentication](guide/authentication/) -- Login methods and token storage
  - [Tips](guide/tips/) -- Filtering, searching, and workflow patterns
