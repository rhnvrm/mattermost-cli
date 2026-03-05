"""Click CLI - main group and entry point.

Commands are registered in the commands/ package via imports.
"""

import sys
from typing import Optional

import click

from . import __version__
from .client import EXIT_ERROR, ensure_auth
from .config import ConfigError, get_credentials


class State:
    """Global CLI state passed via click context."""

    def __init__(self):
        self.human: bool = False
        self.team: Optional[str] = None
        self.debug: bool = False


pass_state = click.make_pass_decorator(State, ensure=True)


@click.group()
@click.option("--human", is_flag=True, help="Human-readable markdown output (default is JSON).")
@click.option("--team", default=None, help="Filter to a specific team.")
@click.option("--debug", is_flag=True, help="Enable debug output.")
@click.version_option(version=__version__, prog_name="mm")
@click.pass_context
def main(ctx, human, team, debug):
    """mm - Mattermost CLI. Output is JSON by default."""
    ctx.ensure_object(State)
    ctx.obj.human = human
    ctx.obj.team = team
    ctx.obj.debug = debug


def get_context(state: State):
    """Load credentials and return an authenticated MMContext."""
    try:
        creds = get_credentials()
    except ConfigError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(EXIT_ERROR)

    team = state.team or creds.get("team")
    return ensure_auth(creds["url"], creds["token"], team)


# Import command modules to register them on the main group.
# Each module imports `main` and uses @main.command() decorators.
from .commands import auth, channels, messages, overview, people, search  # noqa: E402, F401
