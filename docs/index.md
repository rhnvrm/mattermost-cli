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
```

## What it does

```bash
mm overview                       # Mentions + unread + active channels
mm messages general               # Read channel messages
mm messages general --threads     # Thread index (root + reply count)
mm messages @alice                # Read DMs with a user
mm thread abc123def456...         # Read a thread
mm search "deployment issue"      # Search across all teams
mm mentions                       # Posts that @mention you
mm channel general                # Channel info, members, pinned count
mm user @alice                    # Profile, status, timezone
mm pinned general                 # Pinned posts
mm members general                # Channel members with online status
mm channels --since 6h            # Recently active channels
mm unread                         # Channels with unread messages
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
  "is_bot": true,
  "bot_name": "alertmatter",
  "reactions": {"+1": 3, "white_check_mark": 1}
}
```

ISO 8601 timestamps, human-readable type labels, thread IDs on every post, bot detection, reaction counts, and file metadata included.

## Agent-tuned defaults

Commands are tuned for running without flags first, then refining with `--help`:

- `mm overview` returns mentions, unreads, and active channels in a single call
- `mm mentions` includes root message context on replies (so you know what "this" refers to)
- `mm thread` returns root + last 9 replies (not the entire thread)
- `mm unread` includes a `ref` field you can pass directly to `mm messages`
- `mm messages --threads` groups by thread instead of showing flat messages
- Bot posts automatically extract alert text from webhook attachments

## Agent skill

Install as a coding agent skill:

```bash
npx skills add rhnvrm/mattermost-cli
```

## Learn more

- [Quickstart](quickstart/) - Install, authenticate, first commands
- **Guide**
  - [Commands](guide/commands/) - All commands with examples
  - [JSON Output](guide/json-output/) - Output format reference
  - [Authentication](guide/authentication/) - Login methods and token storage
  - [Tips](guide/tips/) - Filtering, searching, and workflow patterns
