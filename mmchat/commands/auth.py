"""Authentication commands: login, logout, whoami."""

import json
import sys
from typing import Optional

import click
from mattermostdriver.exceptions import NoAccessTokenProvided

from ..cli import get_context, main, pass_state
from ..client import EXIT_ERROR, create_driver, login
from ..config import clear_config, save_config


@main.command()
@click.option("--url", prompt=False, default=None, help="Mattermost server URL.")
@click.option("--token", "pat", default=None, help="Personal Access Token (skips password flow).")
@click.option("--user", "login_id", default=None, help="Username or email (non-interactive).")
@click.option("--password", default=None, help="Password (non-interactive).")
def login_cmd(url, pat, login_id, password):
    """Authenticate with Mattermost and store session token."""
    if not url:
        url = click.prompt("Mattermost URL")

    if not url.startswith("http"):
        url = f"https://{url}"

    if pat:
        _login_with_pat(url, pat)
        return

    if not login_id:
        login_id = click.prompt("Username or email")
    if not password:
        password = click.prompt("Password", hide_input=True)

    mfa_token = click.prompt("MFA code (press Enter to skip)", default="", show_default=False)
    mfa_token = mfa_token.strip() or None

    _login_with_password(url, login_id, password, mfa_token)


login_cmd.name = "login"


def _login_with_pat(url: str, pat: str) -> None:
    """Validate PAT and save config."""
    driver = create_driver(url, pat)
    try:
        login(driver)
    except NoAccessTokenProvided:
        click.echo("Error: Invalid Personal Access Token.", err=True)
        sys.exit(EXIT_ERROR)
    except ConnectionError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(EXIT_ERROR)

    _show_teams(driver)
    path = save_config(url=url, auth_method="token", token=pat)
    click.echo(f"Logged in as @{driver.client.username} (PAT)")
    click.echo(f"Config saved to {path}")


def _login_with_password(
    url: str,
    login_id: str,
    password: str,
    mfa_token: Optional[str] = None,
) -> None:
    """Login with password (+MFA), save session token."""
    # IMPORTANT: debug=False always during password login.
    # The driver logs passwords when debug=True.
    driver = create_driver(url, token="", login_id=login_id, password=password, mfa_token=mfa_token)

    try:
        login(driver)
    except NoAccessTokenProvided as e:
        err_msg = str(e).lower()
        if "mfa" in err_msg and mfa_token is None:
            click.echo("MFA is required for this account.")
            mfa_code = click.prompt("MFA code")
            driver = create_driver(
                url, token="", login_id=login_id, password=password, mfa_token=mfa_code.strip()
            )
            try:
                login(driver)
            except NoAccessTokenProvided:
                click.echo("Error: Invalid credentials or MFA code.", err=True)
                sys.exit(EXIT_ERROR)
        else:
            click.echo("Error: Invalid username or password.", err=True)
            sys.exit(EXIT_ERROR)
    except ConnectionError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(EXIT_ERROR)

    session_token = driver.client.token
    _show_teams(driver)
    path = save_config(url=url, auth_method="password", token=session_token)
    click.echo(f"Logged in as @{driver.client.username}")
    click.echo(f"Config saved to {path}")


def _show_teams(driver) -> None:
    """Show teams the user belongs to."""
    teams = driver.teams.get_user_teams(driver.client.userid)
    if not teams:
        click.echo("Warning: You don't belong to any teams.")
        return
    if len(teams) == 1:
        click.echo(f"Team: {teams[0]['display_name']} ({teams[0]['name']})")
    else:
        click.echo("Teams:")
        for t in teams:
            click.echo(f"  - {t['display_name']} ({t['name']})")
        click.echo("Use --team <name> to filter commands to a specific team.")


@main.command()
@pass_state
def whoami(state):
    """Show current user info and validate auth."""
    ctx = get_context(state)
    u = ctx.driver.users.get_user(ctx.user_id)

    if not state.human:
        click.echo(
            json.dumps(
                {
                    "user_id": u["id"],
                    "username": u["username"],
                    "display_name": f"{u.get('first_name', '')} {u.get('last_name', '')}".strip(),
                    "email": u.get("email", ""),
                    "teams": [{"id": t.id, "name": t.name, "display_name": t.display_name} for t in ctx.teams],
                },
                indent=2,
            )
        )
        return

    display_name = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()
    click.echo(f"Username:     @{u['username']}")
    if display_name:
        click.echo(f"Display name: {display_name}")
    if u.get("email"):
        click.echo(f"Email:        {u['email']}")
    click.echo(f"User ID:      {u['id']}")
    click.echo(f"Teams:")
    for t in ctx.teams:
        click.echo(f"  - {t.display_name} ({t.name})")


@main.command()
def logout():
    """Revoke session and clear stored credentials."""
    from ..config import load_config

    config = load_config()
    if config.get("url") and config.get("token"):
        try:
            driver = create_driver(config["url"], config["token"])
            driver.login()
            driver.logout()
        except Exception:
            pass

    clear_config()
    click.echo("Logged out. Stored credentials cleared.")
