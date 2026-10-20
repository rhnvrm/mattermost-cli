"""Pagination independent of the HTTP transport and command rendering."""

from typing import Callable, Optional

from .coverage import Coverage


PAGE_SIZE = 200
MAX_PAGES = 1000


class InvalidPostList(ValueError):
    pass


class PaginationStalled(ValueError):
    pass


class PageLimitReached(ValueError):
    pass


class UnsupportedSearchPagination(ValueError):
    pass


def ordered_posts(result: dict) -> list[dict]:
    """Validate a post-list response rather than silently dropping missing posts."""
    if not isinstance(result, dict) or not isinstance(result.get("order"), list) or not isinstance(result.get("posts"), dict):
        raise InvalidPostList("Invalid post list")
    try:
        posts = [result["posts"][pid] for pid in result["order"]]
    except (KeyError, TypeError) as error:
        raise InvalidPostList("Missing ordered post") from error
    if any(not isinstance(p, dict) or not isinstance(p.get("id"), str) or not p["id"]
           or type(p.get("create_at")) is not int
           for p in posts):
        raise InvalidPostList("Invalid post")
    if any(post["id"] != pid for pid, post in zip(result["order"], posts)):
        raise InvalidPostList("Post ID mismatch")
    return posts


def collect_posts(fetch: Callable, report: Coverage, source: dict, *,
                  limit: int = 0, since_ms: Optional[int] = None,
                  confirm_exhaustion: Optional[Callable[[], None]] = None) -> list[dict]:
    """Walk newest-first pages, retaining partial results on failure.

    Short pages are not proof of exhaustion: servers may clamp per_page.
    """
    posts = {}
    for page in range(MAX_PAGES):
        try:
            response = fetch(page)
            source["pages_fetched"] += 1
            batch = ordered_posts(response)
            if not batch:
                if confirm_exhaustion:
                    confirm_exhaustion()
                source["stop_reason"] = "exhausted"
                break
            new = [post for post in batch if post["id"] not in posts]
            if not new:
                raise PaginationStalled("Pagination made no progress")
            for post in new:
                posts[post["id"]] = post
            eligible = [p for p in posts.values() if since_ms is None or p["create_at"] >= since_ms]
            if limit and len(eligible) >= limit:
                source["stop_reason"] = "limit"
                break
            if since_ms is not None and any(p["create_at"] < since_ms for p in batch):
                source["stop_reason"] = "since"
                break
        except Exception as error:
            report.fail(f"{source['kind']}:{source['id']}", error)
            if isinstance(error, UnsupportedSearchPagination):
                source["stop_reason"] = "unsupported_pagination"
            else:
                source["stop_reason"] = "stalled" if isinstance(error, PaginationStalled) else "failure"
            break
    else:
        report.fail(f"{source['kind']}:{source['id']}", PageLimitReached("Page safety limit reached"))
        source["stop_reason"] = "page_limit"
    result = sorted((p for p in posts.values() if since_ms is None or p["create_at"] >= since_ms),
                    key=lambda p: (p["create_at"], p["id"]), reverse=True)
    if limit:
        result = result[:limit]
    source["returned"] = len(result)
    return result
