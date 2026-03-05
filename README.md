# mattermost-cli

Mattermost CLI for humans and agents.

## Install

```bash
# via uvx (recommended)
uvx mattermost-cli --help

# or pip
pip install mattermost-cli
```

## Setup

```bash
# Interactive login (password + MFA)
mm login

# Or with a Personal Access Token
mm login --token <your-pat>

# Verify
mm whoami
```

## Usage

```bash
# List channels
mm channels

# Show unread messages
mm unread

# Read messages from a channel
mm messages general
mm messages general --since 1h
mm messages @username          # DM with a user

# Read a thread
mm thread <post-id>

# Search
mm search "deployment issue"
mm mentions
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
