---
title: Authentication
description: Login methods and token storage
---

# Authentication

## Methods

### Password + MFA

The most common method. Works with SSO servers that accept password login.

```bash
mm login
```

Prompts for:
1. **Server URL** -- e.g. `https://chat.example.com`
2. **Username** -- your Mattermost username
3. **Password** -- your password
4. **MFA token** -- if MFA is enabled on your account

On success, a session token is created and stored locally. Your password is never written to disk.

Session tokens expire based on server configuration (typically 30 days of inactivity). When it expires, run `mm login` again.

### Personal Access Token

If your Mattermost admin has enabled personal access tokens:

```bash
mm login --token mmtok_abc123...
```

Prompts for the server URL only. The token is stored and used directly.

PATs don't expire unless revoked, making them better for automated use.

## Token storage

Credentials are stored at:

```
~/.config/mm/config.json
```

The directory is created with 0700 permissions, the file with 0600.

Contents:

```json
{
  "url": "https://chat.example.com",
  "auth_method": "password",
  "token": "session-token-here"
}
```

Only the session token is stored. For PAT auth, `auth_method` is `"token"`.

## Environment variables

Environment variables override the config file. Useful for CI, containers, or agent environments.

| Variable | Description |
|----------|-------------|
| `MATTERMOST_URL` | Server URL (overrides config) |
| `MATTERMOST_TOKEN` | Auth token (overrides config) |
| `MATTERMOST_TEAM` | Filter to one team (like `--team`) |
| `MM_CONFIG_PATH` | Custom config file path |

Example:

```bash
export MATTERMOST_URL=https://chat.example.com
export MATTERMOST_TOKEN=mmtok_abc123...
mm whoami
```

## Verify authentication

```bash
mm whoami
```

If auth is valid, returns your user info and teams. If the token has expired:

```
Error: Session expired. Run 'mm login' to re-authenticate.
```

## Logout

Revoke the session and clear stored credentials:

```bash
mm logout
```
