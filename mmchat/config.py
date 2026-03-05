"""Credential storage - token only, no passwords on disk."""

import json
import os
from pathlib import Path
from typing import Optional


class ConfigError(Exception):
    """Raised when config is missing or invalid."""

    pass


def _config_path() -> Path:
    """Return config file path. Respects $MM_CONFIG_PATH."""
    if custom := os.environ.get("MM_CONFIG_PATH"):
        return Path(custom)
    return Path.home() / ".config" / "mm" / "config.json"


def load_config() -> dict:
    """Load config from disk. Returns empty dict if not found."""
    path = _config_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        raise ConfigError(f"Failed to read config at {path}: {e}")


def save_config(
    url: str,
    auth_method: str,
    token: str,
    team: Optional[str] = None,
) -> Path:
    """Save config to disk. Creates dir with 700, file with 600 permissions.

    Returns the config file path.
    """
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)

    data = {
        "url": url,
        "auth_method": auth_method,
        "token": token,
    }
    if team:
        data["team"] = team

    path.write_text(json.dumps(data, indent=2) + "\n")
    os.chmod(path, 0o600)
    return path


def get_credentials() -> dict:
    """Get credentials with env var override.

    Precedence: env vars > config file > error.
    Returns dict with at least 'url' and 'token' keys.
    """
    url = os.environ.get("MATTERMOST_URL")
    token = os.environ.get("MATTERMOST_TOKEN")
    team = os.environ.get("MATTERMOST_TEAM")

    if url and token:
        creds = {"url": url, "token": token, "auth_method": "env"}
        if team:
            creds["team"] = team
        return creds

    config = load_config()
    if config.get("url") and config.get("token"):
        # Env vars can partially override
        if url:
            config["url"] = url
        if token:
            config["token"] = token
        if team:
            config["team"] = team
        return config

    raise ConfigError(
        "Not authenticated. Run 'mm login' to set up credentials.\n"
        "Or set MATTERMOST_URL and MATTERMOST_TOKEN environment variables."
    )


def clear_config() -> None:
    """Delete config file."""
    path = _config_path()
    if path.exists():
        path.unlink()
