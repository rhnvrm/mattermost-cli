# mattermost-cli

Mattermost CLI for humans and agents.

## Install

```bash
# Run directly (no install)
uvx --from mattermost-cli mm --help

# Or install globally
pip install mattermost-cli
```

## Setup

```bash
# Interactive login (password + MFA)
mm login --url https://chat.example.com

# Or with a Personal Access Token
mm login --url https://chat.example.com --token <your-pat>

# Verify
mm whoami
```

## Usage

```bash
# Get oriented (mentions + unread + active channels in one call)
mm overview

# Read messages
mm messages general
mm messages general --since 1h
mm messages general --threads       # thread index view
mm messages @alice                  # DM with a user

# Threads
mm thread <post-id>                 # root + last 9 replies
mm thread <post-id> --limit 0      # full thread

# Search and mentions
mm search "deployment issue"
mm mentions                         # @-mentions in last 24h

# Channel info
mm channel general                  # purpose, members, pinned count
mm channels --since 6h              # recently active channels
mm unread                           # channels with unread messages
mm pinned general                   # pinned posts
mm members general                  # who's in the channel

# People
mm user @alice                      # profile, status, timezone
```

## JSON Output

All commands output JSON by default. Key fields:

- **`thread_id`** on every post - pass to `mm thread`
- **`ref`** on channel entries - pass to `mm messages`
- **`is_bot`** / **`bot_name`** - webhook/bot posts flagged automatically
- **`root`** on reply-mentions - the original message being replied to
- **`reactions`** - emoji counts like `{"+1": 3}`

Webhook posts automatically extract alert content from Slack-format attachments.

Add `--human` for readable markdown output instead.

## Agent Skill

Install as a coding agent skill:

```bash
npx skills add rhnvrm/mattermost-cli
```

## Options

```
--human    Human-readable markdown output (default is JSON)
--team     Filter to a specific team
--debug    Enable debug output
```

## Auth

Two methods supported:

**Password + MFA** (primary): `mm login` prompts interactively. Session token
is stored locally - password is never saved to disk. When the session expires,
run `mm login` again.

**Personal Access Token** (optional): `mm login --token <pat>`. Requires admin
to enable PATs on the Mattermost server. Tokens don't expire.

Credentials stored at `~/.config/mm/config.json` (token only, 600 permissions).

Environment variables override config: `MATTERMOST_URL`, `MATTERMOST_TOKEN`,
`MATTERMOST_TEAM`.

## License

MIT
