"""Driver wrapper - auth, URL parsing, team detection."""

import sys
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import httpx
from mattermostdriver import Driver
from mattermostdriver.exceptions import NoAccessTokenProvided


# Exit codes for daemon integration
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_AUTH_EXPIRED = 2
EXIT_RATE_LIMITED = 3


@dataclass
class Team:
    """A Mattermost team."""

    id: str
    name: str
    display_name: str


@dataclass
class MMContext:
    """Authenticated Mattermost context passed to all commands."""

    driver: Driver
    user_id: str
    username: str
    teams: list[Team]  # all teams the user belongs to

    @property
    def team_ids(self) -> list[str]:
        return [t.id for t in self.teams]

    def get_team(self, name: str) -> Optional[Team]:
        for t in self.teams:
            if t.name == name or t.display_name == name:
                return t
        return None


def create_driver(
    url: str,
    token: str,
    login_id: Optional[str] = None,
    password: Optional[str] = None,
    mfa_token: Optional[str] = None,
) -> Driver:
    """Create a Driver instance with proper URL parsing.

    The driver takes separate scheme/host/port options, not a full URL.
    Without parsing, it defaults to port 8065 and connections fail.
    """
    parsed = urlparse(url if "://" in url else f"https://{url}")
    scheme = parsed.scheme or "https"
    hostname = parsed.hostname or url
    port = parsed.port or (443 if scheme == "https" else 80)

    options = {
        "scheme": scheme,
        "url": hostname,
        "port": port,
        "token": token or "",
        "debug": False,
    }
    if login_id:
        options["login_id"] = login_id
    if password:
        options["password"] = password
    if mfa_token:
        options["mfa_token"] = mfa_token

    return Driver(options)


def login(driver: Driver) -> dict:
    """Login and return user info dict.

    Raises:
        NoAccessTokenProvided: on 401 (bad token or expired session)
        httpx.ConnectError: on connection failure
    """
    try:
        result = driver.login()
        return result
    except NoAccessTokenProvided:
        raise
    except httpx.ConnectError as e:
        url = f"{driver.options['scheme']}://{driver.options['url']}:{driver.options['port']}"
        raise ConnectionError(f"Cannot connect to {url}: {e}") from e


def get_teams(driver: Driver, filter_team: Optional[str] = None) -> list[Team]:
    """Get teams the user belongs to. Optionally filter to one.

    By default returns ALL teams. With filter_team, returns only the matching one.
    """
    raw_teams = driver.teams.get_user_teams(driver.client.userid)
    if not raw_teams:
        print("Error: You don't belong to any teams.", file=sys.stderr)
        sys.exit(EXIT_ERROR)

    teams = [Team(id=t["id"], name=t["name"], display_name=t["display_name"]) for t in raw_teams]

    if filter_team:
        matched = [t for t in teams if t.name == filter_team or t.display_name == filter_team]
        if not matched:
            available = ", ".join(t.name for t in teams)
            print(
                f"Error: Team '{filter_team}' not found. Available teams: {available}",
                file=sys.stderr,
            )
            sys.exit(EXIT_ERROR)
        return matched

    return teams


def ensure_auth(
    url: str,
    token: str,
    team_name: Optional[str] = None,
) -> MMContext:
    """Single entry point: create driver, login, get teams, return context.

    By default loads ALL teams. Use team_name (from --team flag) to filter to one.
    Commands iterate ctx.teams for cross-team queries.
    """
    driver = create_driver(url, token)

    try:
        login(driver)
    except NoAccessTokenProvided:
        print(
            "Error: Session expired. Run 'mm login' to re-authenticate.",
            file=sys.stderr,
        )
        sys.exit(EXIT_AUTH_EXPIRED)
    except ConnectionError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(EXIT_ERROR)

    teams = get_teams(driver, team_name)

    return MMContext(
        driver=driver,
        user_id=driver.client.userid,
        username=driver.client.username,
        teams=teams,
    )
