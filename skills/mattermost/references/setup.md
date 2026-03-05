# Setup Guide

Getting `mm` working from scratch. This covers installation, authentication, and verifying everything works.

## 1. Install the CLI

The CLI is published on PyPI. You don't need to clone anything - `uvx` runs it directly:

```bash
uvx --from mattermost-cli mm --help
```

This downloads and runs `mm` in an isolated environment. If you see the help text, installation works.

To make `mm` available as a persistent command (instead of going through `uvx` each time), install it into a Python environment:

```bash
pip install mattermost-cli
```

Or with pipx for isolated global install:

```bash
pipx install mattermost-cli
```

## 2. Find your Mattermost server URL

You need the base URL of your Mattermost instance. This is what you type in your browser to access chat. For example:

- `https://chat.example.com`
- `https://mattermost.yourcompany.com`

If you're not sure, ask your team or check your browser's address bar when you're logged into Mattermost.

## 3. Authenticate

Two options. Personal Access Token is simpler if your server allows it.

### Option A: Personal Access Token (recommended)

1. Log into Mattermost in your browser
2. Go to **Profile > Security > Personal Access Tokens**
   - If you don't see this option, your admin may have disabled it - use Option B instead
3. Click **Create Token**, give it a name (e.g. "mm-cli"), and copy the token
4. Run:

```bash
mm login --url https://chat.example.com --token YOUR_TOKEN
```

The token never expires unless revoked, so you only do this once.

### Option B: Password + MFA

If your server doesn't allow personal access tokens, or you prefer not to create one:

```bash
mm login --url https://chat.example.com
```

This prompts for username, password, and MFA code (if enabled). It creates a session token that's stored locally. Session tokens can expire, so you may need to re-login occasionally.

### Non-interactive login (for scripts/CI)

```bash
mm login --url https://chat.example.com --user you@example.com --password 'yourpass'
```

## 4. Verify

```bash
mm whoami
```

You should see your username, user ID, and the teams you belong to. If you get an auth error, re-run `mm login`.

## 5. Try it

```bash
# What needs attention?
mm overview

# Read a channel
mm messages general

# Your DMs with someone
mm messages @colleague
```

## Where config is stored

Credentials are saved to `$HOME/.config/mm/config.json`. The file contains your server URL and session token (not your password).

You can also configure via environment variables, which take precedence over the config file:

| Variable | Purpose |
|----------|---------|
| `MATTERMOST_URL` | Server URL |
| `MATTERMOST_TOKEN` | Auth token |
| `MATTERMOST_TEAM` | Default team filter |
| `MM_CONFIG_PATH` | Custom config file path |

## Multiple servers

The config file stores one server at a time. To switch between servers, re-run `mm login` with a different `--url`. If you need to work with multiple servers simultaneously, use environment variables:

```bash
MATTERMOST_URL=https://chat-a.example.com MATTERMOST_TOKEN=abc123 mm overview
MATTERMOST_URL=https://chat-b.example.com MATTERMOST_TOKEN=def456 mm overview
```

## Troubleshooting

**"No credentials found"** - Run `mm login` first.

**"Auth expired"** - Your session token expired. Run `mm login` again. Consider using a Personal Access Token instead (they don't expire).

**"Unable to reach server"** - Check the URL. Make sure you can reach it from where you're running `mm` (VPN, firewall, etc.).

**SSL errors** - If your server uses a self-signed certificate, you may need to set `REQUESTS_CA_BUNDLE` or `SSL_CERT_FILE` to your CA bundle path.
