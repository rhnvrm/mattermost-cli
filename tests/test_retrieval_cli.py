"""Exercise the real CLI and driver against a local, synthetic Mattermost API."""

import json
import inspect
import subprocess
import sys
import threading
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pytest
from click.testing import CliRunner

from mmchat.cli import main


def post(number, channel="channel1"):
    return {"id": f"p{number:025d}", "channel_id": channel, "user_id": "alice",
            "create_at": 1700000000000 + number, "message": f"message {number}", "root_id": ""}


def post_list(posts):
    return {"order": [p["id"] for p in posts], "posts": {p["id"]: p for p in posts}}


@pytest.fixture
def api(monkeypatch, tmp_path):
    class API:
        posts = [post(i) for i in range(1250, 0, -1)]
        teams = [{"id": "team1", "name": "test", "display_name": "Test"}]
        requests = []
        counts = Counter()
        failures = {}
        fail_after = {}
        team_posts = {}
        repeat = False
        search_page_size = 60
        message_page_size = 200
        delays = {}
        omit_users = False
        malformed_page = False
        overlap = False
        dm = False
        inaccessible = False
        first_inaccessible_post_time = 0
        database_search = False

        def response(self, method, path, query, body):
            self.requests.append((method, path, query, body))
            self.counts[path] += 1
            if path in self.delays:
                time.sleep(self.delays[path])
            failure = self.failures.get(path)
            if failure and self.counts[path] <= failure[0]:
                return failure[1], {"message": "synthetic failure"}
            later_failure = self.fail_after.get(path)
            if later_failure and self.counts[path] > later_failure[0]:
                return later_failure[1], {"message": "synthetic later failure"}
            if path == "/users/me":
                return 200, {"id": "me", "username": "me"}
            if path == "/users/me/teams":
                return 200, self.teams
            if path in ("/users/ids", "/users/usernames"):
                if self.omit_users and path == "/users/ids":
                    return 200, []
                return 200, [{"id": "alice", "username": "alice"}]
            if path == "/users/username/alice":
                return 200, {"id": "alice", "username": "alice"}
            if path == "/users/alice/status":
                return 200, {"status": "online"}
            if path == "/users/status/ids":
                return 200, [{"user_id": "alice", "status": "online"}]
            if path == "/users/alice":
                return 200, {"id": "alice", "username": "alice"}
            if path.endswith("/channels/name/general") or path == "/channels/channel1":
                return 200, {"id": "channel1", "name": "general", "display_name": "General", "type": "O"}
            if path == "/channels/channel1/posts":
                size = min(int(query.get("per_page", [60])[0]), self.message_page_size)
                posts = self.posts
                if "before" in query and not self.repeat:
                    boundary = next(p["create_at"] for p in posts if p["id"] == query["before"][0])
                    posts = [p for p in posts if p["create_at"] < boundary]
                page = 0 if self.repeat else int(query.get("page", [0])[0])
                result = post_list(posts[page * size:(page + 1) * size])
                result["first_inaccessible_post_time"] = self.first_inaccessible_post_time
                return 200, result
            if path.endswith("/posts/search"):
                page = 0 if self.repeat else body.get("page", 0)
                size = min(body.get("per_page", 60), self.search_page_size)
                if self.malformed_page and page == 1:
                    return 200, {"order": ["missing"], "posts": {}}
                start = max(0, page * size - (10 * page if self.overlap else 0))
                posts = self.team_posts.get(path.split("/")[2], self.posts)
                after = next((term[6:] for term in body["terms"].split() if term.startswith("after:")), None)
                if after:
                    cutoff = datetime.strptime(after, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1)
                    posts = [p for p in posts if p["create_at"] >= int(cutoff.timestamp() * 1000)]
                if self.database_search:
                    return 200, post_list(posts[:100] if page == 0 else [])
                return 200, post_list(posts[start:start + size])
            if path == "/channels/channel1/pinned":
                return 200, post_list(self.posts[:20])
            if path == "/channels/channel1/stats":
                return 200, {"member_count": 1}
            if path == "/channels/channel1/members":
                return 200, ([{"user_id": "alice"}] if int(query.get("page", [0])[0]) == 0 else [])
            if path.endswith("/thread"):
                return 200, post_list(list(reversed(self.posts[-5:])))
            if path.startswith("/posts/"):
                found = next((p for p in self.posts if p["id"] == path.rsplit("/", 1)[1]), None)
                return (200, found) if found else (404, {"message": "missing"})
            if path.startswith("/users/me/teams/") and path.endswith("/channels"):
                if self.dm:
                    return 200, [{"id": "channel1", "name": "me__alice", "display_name": "", "type": "D"}]
                return 200, [{"id": "channel1", "name": "general", "display_name": "General", "type": "O",
                              "total_msg_count": 5, "last_post_at": 1700000001250}]
            if path.endswith("/channels/members"):
                return 200, [{"channel_id": "channel1", "msg_count": 0}]
            return 404, {"message": "unknown fixture endpoint"}

    state = API()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.respond()

        def do_POST(self):
            self.respond()

        def respond(self):
            parsed = urlparse(self.path)
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or "null")
            status, data = state.response(self.command, parsed.path.removeprefix("/api/v4"),
                                          parse_qs(parsed.query), body)
            if isinstance(data, dict) and "posts" in data:
                data["first_inaccessible_post_time"] = state.first_inaccessible_post_time
            payload = json.dumps(data).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            if state.inaccessible and parsed.path.endswith("/posts"):
                self.send_header("Has-Inaccessible-Posts", "true")
            self.end_headers()
            try:
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    monkeypatch.setenv("MATTERMOST_URL", f"http://127.0.0.1:{server.server_port}")
    monkeypatch.setenv("MATTERMOST_TOKEN", "synthetic-test-token")
    monkeypatch.setenv("MM_CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.delenv("MATTERMOST_TEAM", raising=False)
    yield state
    server.shutdown()
    server.server_close()
    thread.join()


def invoke(*args):
    # Click <8.2 requires opting out of stderr mixing explicitly.
    options = {"mix_stderr": False} if "mix_stderr" in inspect.signature(CliRunner).parameters else {}
    return CliRunner(**options).invoke(main, args)


def coverage(result):
    return json.loads(result.stderr.strip().splitlines()[-1])["coverage"]


def test_messages_fetch_more_than_one_page(api):
    result = invoke("messages", "general", "--limit", "1250")
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert len(data) == 1250
    assert [p["id"] for p in data] == [post(i)["id"] for i in range(1, 1251)]
    report = coverage(result)
    assert report["conversations_checked"] == 1
    assert report["pages_fetched"] >= 7
    assert report["complete"] is True


def test_search_obeys_limit_despite_short_server_pages(api):
    result = invoke("search", "message", "--limit", "200")
    assert result.exit_code == 0, result.output
    assert len(json.loads(result.stdout)) == 200
    assert api.counts["/teams/team1/posts/search"] == 4
    assert coverage(result)["sources"][0]["stop_reason"] == "limit"


def test_all_messages_and_since_boundary(api):
    result = invoke("messages", "general", "--limit", "0", "--since", "1700000001000")
    assert result.exit_code == 0, result.output
    assert len(json.loads(result.stdout)) == 251
    queries = [query for _, path, query, _ in api.requests if path.endswith("/posts")]
    assert all("since" not in query for query in queries)
    assert coverage(result)["sources"][0]["stop_reason"] == "since"


def test_stalled_pagination_is_incomplete(api):
    api.repeat = True
    result = invoke("search", "message", "--limit", "200")
    assert result.exit_code != 0
    assert len(json.loads(result.stdout)) == 60
    assert coverage(result)["complete"] is False
    assert coverage(result)["failures"][0]["error"] == "PaginationStalled"


def test_defaults_remain_bounded(api):
    result = invoke("messages", "general")
    assert result.exit_code == 0
    assert len(json.loads(result.stdout)) == 30
    assert json.loads(result.stdout)[0]["id"] == post(1221)["id"]
    assert coverage(result)["sources"][0]["stop_reason"] == "limit"
    assert coverage(result)["scope"]["limit"] == 30


def test_messages_continue_after_short_pages(api):
    api.message_page_size = 60
    result = invoke("messages", "general", "--limit", "200")
    assert result.exit_code == 0
    assert len(json.loads(result.stdout)) == 200
    assert api.counts["/channels/channel1/posts"] == 4


def test_unlimited_search_deduplicates_teams_and_overlapping_pages(api):
    api.teams = api.teams + [{"id": "team2", "name": "other", "display_name": "Other"}]
    api.overlap = True
    result = invoke("search", "message", "--limit", "0")
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert [p["id"] for p in data] == [post(i)["id"] for i in range(1250, 0, -1)]
    assert coverage(result)["teams_checked"] == 2
    assert all(s["stop_reason"] == "exhausted" for s in coverage(result)["sources"])


def test_malformed_page_retains_previous_results(api):
    api.malformed_page = True
    result = invoke("search", "message", "--limit", "200")
    assert result.exit_code == 4
    assert len(json.loads(result.stdout)) == 60
    assert coverage(result)["failures"][0]["error"] == "InvalidPostList"


def test_mentions_filters_exact_time_and_keeps_root_context(api):
    api.posts = [post(i) for i in range(1250, 0, -1)]
    api.posts[0]["root_id"] = post(1)["id"]
    result = invoke("mentions", "--since", "1700000001000", "--limit", "0")
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert len(data) == 251
    assert data[0]["root"]["message"] == "message 1"
    assert coverage(result)["scope"]["since_ms"] == 1700000001000


def test_missing_root_context_is_reported(api):
    api.posts = [dict(post(1250), root_id="missing-root")]
    result = invoke("mentions", "--since", "0")
    assert result.exit_code == 4
    assert len(json.loads(result.stdout)) == 1
    assert coverage(result)["failures"][0]["error"] == "ResourceNotFound"


def test_failed_batch_lookup_can_recover(api):
    api.failures["/users/ids"] = (99, 400)
    result = invoke("messages", "general")
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)[0]["author"] == "@alice"
    assert coverage(result)["failures"] == []
    assert api.counts["/users/ids"] == 1


def test_omitted_batch_users_are_looked_up(api):
    api.omit_users = True
    result = invoke("messages", "general")
    assert result.exit_code == 0
    assert json.loads(result.stdout)[0]["author"] == "@alice"
    assert api.counts["/users/alice"] == 1


def test_failed_author_lookup_keeps_posts_but_marks_incomplete(api):
    api.failures["/users/ids"] = (99, 400)
    api.failures["/users/alice"] = (99, 403)
    result = invoke("messages", "general")
    assert result.exit_code == 4
    assert len(json.loads(result.stdout)) == 30
    assert coverage(result)["complete"] is False


@pytest.mark.parametrize("command", ["channels", "unread", "overview"])
def test_channel_inventory_failure_preserves_other_sections(api, command):
    api.teams = api.teams + [{"id": "team2", "name": "other", "display_name": "Other"}]
    api.failures["/users/me/teams/team2/channels"] = (99, 403)
    args = [command] + (["--since", "0"] if command == "overview" else [])
    result = invoke(*args)
    assert result.exit_code == 4, result.output
    data = json.loads(result.stdout)
    assert data["unread"] if command == "overview" else len(data) == 1
    assert coverage(result)["teams_checked"] == 2
    assert coverage(result)["conversations_checked"] == 1


def test_dm_lookup_uses_only_existing_channels(api):
    api.dm = True
    result = invoke("messages", "@alice")
    assert result.exit_code == 0, result.output
    assert len(json.loads(result.stdout)) == 30
    assert all(method == "GET" or path in ("/users/usernames", "/users/ids")
               for method, path, _, _ in api.requests)


def test_expected_channel_miss_is_not_a_failure(api):
    api.teams = api.teams + [{"id": "team2", "name": "other", "display_name": "Other"}]
    api.failures["/teams/team1/channels/name/general"] = (99, 404)
    result = invoke("messages", "general")
    assert result.exit_code == 0, result.output
    assert coverage(result)["failures"] == []


def test_thread_limit_one_keeps_only_root(api):
    result = invoke("thread", post(1)["id"], "--limit", "1")
    assert result.exit_code == 0
    assert [p["id"] for p in json.loads(result.stdout)] == [post(1)["id"]]
    assert coverage(result)["sources"][0]["stop_reason"] == "limit"


@pytest.mark.parametrize("args", [("channel", "general"), ("user", "alice"),
                                  ("members", "general"), ("pinned", "general")])
def test_related_read_commands_report_coverage(api, args):
    result = invoke(*args)
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)
    assert coverage(result)["complete"] is True


def test_human_output_has_human_coverage(api):
    result = invoke("--human", "messages", "general", "--limit", "1")
    assert result.exit_code == 0
    assert "message 1250" in result.stdout
    assert "Coverage: complete" in result.stderr
    assert "limit 1" in result.stderr


def test_cli_subprocess_keeps_streams_separate(api):
    result = subprocess.run([sys.executable, "-c", "from mmchat.cli import main; main()",
                             "search", "message", "--limit", "200"],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert len(json.loads(result.stdout)) == 200
    assert json.loads(result.stderr)["coverage"]["complete"] is True


def test_request_timeout_is_bounded_and_retried(api, monkeypatch):
    from mmchat import client
    monkeypatch.setattr(client, "REQUEST_TIMEOUT", 0.02)
    monkeypatch.setattr(client, "retry_delay", lambda *args: 0)
    api.delays["/channels/channel1/posts"] = 0.1
    result = invoke("messages", "general")
    assert result.exit_code == 4
    assert json.loads(result.stdout) == []
    assert api.counts["/channels/channel1/posts"] == 3
    assert coverage(result)["retries"] == 2
    assert coverage(result)["failures"][0]["error"] == "ReadTimeout"


@pytest.mark.parametrize("status", [400, 401, 403, 404, 501])
def test_permanent_errors_are_not_retried(api, status):
    api.failures["/channels/channel1/posts"] = (99, status)
    result = invoke("messages", "general")
    assert result.exit_code == 4
    assert api.counts["/channels/channel1/posts"] == 1


def test_retryable_status_respects_attempt_budget(api):
    api.failures["/channels/channel1/posts"] = (99, 429)
    result = invoke("messages", "general")
    assert result.exit_code == 4
    assert api.counts["/channels/channel1/posts"] == 3
    assert coverage(result)["failures"][0]["status"] == 429


def test_login_post_is_never_retried(api):
    from mmchat.client import create_driver
    import os
    driver = create_driver(os.environ["MATTERMOST_URL"], "", login_id="test", password="synthetic")
    api.failures["/users/login"] = (99, 503)
    with pytest.raises(Exception):
        driver.login()
    assert api.counts["/users/login"] == 1


def test_negative_limit_is_rejected_before_network(api):
    result = invoke("messages", "general", "--limit", "-1")
    assert result.exit_code != 0
    assert api.requests == []


def test_later_page_failure_preserves_earlier_page(api):
    api.fail_after["/teams/team1/posts/search"] = (1, 503)
    result = invoke("search", "message", "--limit", "200")
    assert result.exit_code == 4
    assert len(json.loads(result.stdout)) == 60
    assert api.counts["/teams/team1/posts/search"] == 4
    assert coverage(result)["pages_fetched"] == 1
    assert coverage(result)["sources"][0]["stop_reason"] == "failure"


def test_search_merges_global_newest_results(api):
    api.teams = api.teams + [{"id": "team2", "name": "other", "display_name": "Other"}]
    api.team_posts = {"team1": [post(i) for i in range(200, 0, -2)],
                      "team2": [post(i) for i in range(199, 0, -2)]}
    result = invoke("search", "message", "--limit", "100")
    assert result.exit_code == 0
    assert [p["id"] for p in json.loads(result.stdout)] == [post(i)["id"] for i in range(200, 100, -1)]


def test_subprocess_failure_is_one_safe_json_report(api):
    api.failures["/channels/channel1/posts"] = (99, 403)
    result = subprocess.run([sys.executable, "-c", "from mmchat.cli import main; main()",
                             "messages", "general"], capture_output=True, text=True, timeout=10)
    assert result.returncode == 4
    assert json.loads(result.stdout) == []
    assert json.loads(result.stderr)["coverage"]["complete"] is False
    assert "synthetic failure" not in result.stderr
    assert "synthetic-test-token" not in result.stderr


def test_server_withheld_posts_are_reported(api):
    api.inaccessible = True
    result = invoke("messages", "general")
    assert result.exit_code == 4
    assert len(json.loads(result.stdout)) == 30
    assert coverage(result)["failures"][0]["error"] == "PermissionError"


def test_transient_failure_is_retried(api):
    api.failures["/channels/channel1/posts"] = (1, 503)
    result = invoke("messages", "general")
    assert result.exit_code == 0, result.output
    assert len(json.loads(result.stdout)) == 30
    assert api.counts["/channels/channel1/posts"] == 2
    assert coverage(result)["failures"] == []


def test_failed_team_retains_other_results(api):
    api.teams = api.teams + [{"id": "team2", "name": "other", "display_name": "Other"}]
    api.failures["/teams/team2/posts/search"] = (99, 503)
    result = invoke("search", "message", "--limit", "200")
    assert result.exit_code != 0
    assert len(json.loads(result.stdout)) == 200
    assert api.counts["/teams/team2/posts/search"] == 3
    assert coverage(result)["complete"] is False
