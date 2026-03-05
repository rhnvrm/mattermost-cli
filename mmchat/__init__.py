"""mattermost-cli - Mattermost CLI for humans and agents."""

try:
    from importlib.metadata import version
    __version__ = version("mattermost-cli")
except Exception:
    __version__ = "0.0.0-dev"
