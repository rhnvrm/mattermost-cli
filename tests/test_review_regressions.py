"""Regressions from review of the bounded retrieval contract."""

from datetime import datetime, timedelta, timezone
import json

import pytest

from tests.test_retrieval_cli import api, coverage, invoke, post


@pytest.mark.parametrize("args", [("search", "message", "--limit", "200"),
                                  ("mentions", "--since", "0", "--limit", "0")])
def test_database_search_cap_is_not_exhaustion(api, args):
    api.database_search = True
    result = invoke(*args)
    assert result.exit_code == 4, result.output
    assert len(json.loads(result.stdout)) == 100
    report = coverage(result)
    assert report["complete"] is False
    assert report["sources"][0]["stop_reason"] == "unsupported_pagination"


@pytest.mark.parametrize("count,tied", [(202, 2), (402, 402)])
def test_messages_keep_equal_timestamp_posts_across_pages(api, count, tied):
    api.posts = [post(i) for i in range(count, 0, -1)]
    start = 199 if tied == 2 else 0
    for p in api.posts[start:start + tied]:
        p["create_at"] = api.posts[start]["create_at"]
    result = invoke("messages", "general", "--limit", "0")
    assert result.exit_code == 0, result.output
    assert {p["id"] for p in json.loads(result.stdout)} == {p["id"] for p in api.posts}
    assert len(json.loads(result.stdout)) == count
    assert coverage(result)["complete"] is True


@pytest.mark.parametrize("args", [("messages", "general"), ("search", "message"),
                                  ("thread", post(1)["id"])])
def test_json_inaccessible_history_is_incomplete(api, args):
    api.first_inaccessible_post_time = 1700000000000
    result = invoke(*args)
    assert result.exit_code == 4, result.output
    assert json.loads(result.stdout)
    assert coverage(result)["complete"] is False


def test_paged_search_with_exactly_100_matches_is_exhausted(api):
    api.posts = api.posts[:100]
    api.search_page_size = 200
    result = invoke("search", "message", "--limit", "200")
    assert result.exit_code == 0, result.stderr
    assert len(json.loads(result.stdout)) == 100
    assert coverage(result)["sources"][0]["stop_reason"] == "exhausted"
    assert coverage(result)["sources"][0]["pages_fetched"] == 3
    assert api.counts["/teams/team1/posts/search"] == 3


@pytest.mark.parametrize("limit,expected", [(30, 30), (100, 100)])
def test_database_search_with_satisfied_limit_succeeds(api, limit, expected):
    api.database_search = True
    result = invoke("search", "message", "--limit", str(limit))
    assert result.exit_code == 0, result.stderr
    assert len(json.loads(result.stdout)) == expected
    assert coverage(result)["sources"][0]["stop_reason"] == "limit"


def test_database_search_below_cap_can_be_exhausted(api):
    api.database_search = True
    api.posts = api.posts[:99]
    result = invoke("search", "message", "--limit", "0")
    assert result.exit_code == 0, result.stderr
    assert len(json.loads(result.stdout)) == 99
    assert coverage(result)["sources"][0]["stop_reason"] == "exhausted"


def test_search_pagination_probe_failure_keeps_results(api):
    api.database_search = True
    api.fail_after["/teams/team1/posts/search"] = (2, 403)
    result = invoke("search", "message", "--limit", "200")
    assert result.exit_code == 4
    assert len(json.loads(result.stdout)) == 100
    assert coverage(result)["sources"][0]["stop_reason"] == "failure"


def test_dm_lookup_continues_after_failed_team(api):
    api.dm = True
    api.teams = api.teams + [{"id": "team2", "name": "other", "display_name": "Other"}]
    api.failures["/users/me/teams/team1/channels"] = (99, 403)
    result = invoke("messages", "@alice")
    assert result.exit_code == 4
    assert len(json.loads(result.stdout)) == 30
    assert api.counts["/users/me/teams/team2/channels"] == 1


def test_initial_auth_transport_failure_is_setup_error(api):
    api.failures["/users/me"] = (99, 403)
    result = invoke("messages", "general")
    assert result.exit_code == 1
    assert coverage(result)["complete"] is False


@pytest.mark.parametrize("args,path", [
    (("messages", "a" * 26), "/channels/" + "a" * 26),
    (("messages", "@alice"), "/users/usernames"),
    (("user", "alice"), "/users/username/alice"),
])
def test_lookup_transport_failure_uses_incomplete_exit(api, args, path):
    api.failures[path] = (99, 503)
    result = invoke(*args)
    assert result.exit_code == 4, result.output
    assert coverage(result)["complete"] is False


def test_named_channel_lookup_continues_after_failed_team(api):
    api.teams = api.teams + [{"id": "team2", "name": "other", "display_name": "Other"}]
    api.failures["/teams/team1/channels/name/general"] = (99, 403)
    result = invoke("messages", "general")
    assert api.counts["/teams/team2/channels/name/general"] == 1
    assert result.exit_code == 4
    assert len(json.loads(result.stdout)) == 30
    assert coverage(result)["complete"] is False


@pytest.mark.parametrize("command", ["mentions", "overview"])
def test_mentions_today_includes_today_with_server_date_semantics(api, command):
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    api.posts = [dict(post(3), create_at=int((today + timedelta(hours=2)).timestamp() * 1000)),
                 dict(post(2), create_at=int(today.timestamp() * 1000)),
                 dict(post(1), create_at=int((today - timedelta(milliseconds=1)).timestamp() * 1000))]
    result = invoke(command, "--since", "today")
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    entries = data["mentions"] if command == "overview" else data
    assert len(entries) == 2
    assert {p["message"] for p in entries} == {"message 3", "message 2"}


def test_initial_expired_auth_keeps_exit_two(api):
    api.failures["/users/me"] = (99, 401)
    result = invoke("messages", "general")
    assert result.exit_code == 2
    assert coverage(result)["complete"] is False


def test_setup_error_keeps_exit_one(api):
    result = invoke("--team", "missing-team", "messages", "general")
    assert result.exit_code == 1
    assert coverage(result)["complete"] is False
