"""Pure pagination and retry-policy checks; no driver doubles."""

import pytest

from mmchat.client import create_driver, is_read_request, retry_delay
from mmchat.coverage import Coverage
from mmchat.retrieval import collect_posts, ordered_posts, InvalidPostList
from tests.test_retrieval_cli import post, post_list


def test_page_budget_retains_partial_results(monkeypatch):
    monkeypatch.setattr("mmchat.retrieval.MAX_PAGES", 2)
    report = Coverage("test")
    source = report.source("search", "team", 0)
    posts = collect_posts(lambda page: post_list([post(10 - page)]), report, source)
    assert [p["id"] for p in posts] == [post(10)["id"], post(9)["id"]]
    assert source["stop_reason"] == "page_limit"
    assert source["pages_fetched"] == 2
    assert report.as_dict()["complete"] is False
    assert report.failures[0]["error"] == "PageLimitReached"


def test_page_stall_retains_partial_results():
    report = Coverage("test")
    source = report.source("messages", "channel", 0)
    posts = collect_posts(lambda page: post_list([post(10)]), report, source)
    assert len(posts) == 1
    assert source["stop_reason"] == "stalled"
    assert source["pages_fetched"] == 2


def test_time_boundary_includes_equal_timestamps():
    report = Coverage("test")
    source = report.source("messages", "channel", 0)
    posts = collect_posts(lambda page: post_list([post(3), post(2), post(1)]), report, source,
                          since_ms=1700000000002)
    assert [p["id"] for p in posts] == [post(3)["id"], post(2)["id"]]
    assert source["stop_reason"] == "since"


@pytest.mark.parametrize("data", [{}, {"order": ["missing"], "posts": {}},
                                  {"order": ["wrong-id"], "posts": {"wrong-id": post(1)}}])
def test_malformed_post_lists_are_rejected(data):
    with pytest.raises(InvalidPostList):
        ordered_posts(data)


@pytest.mark.parametrize("attempt,header,expected", [(0, None, 0.5), (1, None, 1),
    (0, "3", 3), (0, "9999", 5), (0, "invalid", 0.5), (0, "-1", 0.5),
    (0, "Tue, 20 Oct 2099 12:00:00 GMT", 5)])
def test_retry_wait_is_bounded(attempt, header, expected):
    assert retry_delay(attempt, header) == expected


@pytest.mark.parametrize("method,path,expected", [("GET", "/posts/p", True),
    ("post", "/teams/t/posts/search", True), ("post", "/users/ids", True),
    ("post", "/users/login", False), ("post", "/channels/direct", False),
    ("post", "/posts", False), ("delete", "/posts/p", False)])
def test_retry_allowlist_excludes_writes(method, path, expected):
    assert is_read_request(method, path) is expected


def test_driver_has_explicit_timeout():
    driver = create_driver("http://localhost:8065", "synthetic")
    assert driver.options["request_timeout"] == 15
    assert driver.options["debug"] is False
