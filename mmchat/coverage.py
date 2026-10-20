"""Per-command retrieval accounting, kept separate from stdout data."""

from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
from typing import Optional

import click

from .formatters import format_coverage_json, format_coverage_md


EXIT_INCOMPLETE = 4
current_coverage: ContextVar[Optional["Coverage"]] = ContextVar("coverage", default=None)


@dataclass
class Coverage:
    command: str
    scope: dict = field(default_factory=dict)
    teams: set = field(default_factory=set)
    conversations: set = field(default_factory=set)
    pages_fetched: int = 0
    requests_attempted: int = 0
    retries: int = 0
    sources: list = field(default_factory=list)
    failures: list = field(default_factory=list)
    _errors: list = field(default_factory=list, repr=False)
    retrieval_started: bool = False

    def fail(self, operation: str, error: BaseException) -> None:
        if any(existing is error for existing in self._errors):
            return
        self._errors.append(error)
        response = getattr(error, "response", None)
        self.failures.append({"operation": operation, "error": type(error).__name__,
                              "status": getattr(response, "status_code", None)})

    def recovered(self, error: Exception) -> None:
        for index, existing in enumerate(self._errors):
            if existing is error:
                self._errors.pop(index)
                self.failures.pop(index)
                return

    def source(self, kind: str, identifier: str, limit: int = 0) -> dict:
        source = {"kind": kind, "id": identifier, "limit": limit,
                  "pages_fetched": 0, "returned": 0, "stop_reason": "pending"}
        self.sources.append(source)
        return source

    def as_dict(self) -> dict:
        return {"command": self.command, "scope": self.scope,
                "complete": not self.failures, "teams_checked": len(self.teams),
                "conversations_checked": len(self.conversations),
                "pages_fetched": self.pages_fetched,
                "requests_attempted": self.requests_attempted, "retries": self.retries,
                "sources": self.sources, "failures": self.failures}


def retrieval_command(function):
    """Give every retrieval command one report, including early failures."""
    @wraps(function)
    def wrapped(state, *args, **kwargs):
        report = Coverage(function.__name__, {key: value for key, value in kwargs.items()
                                              if key in ("limit", "since", "ch_type", "include_muted")})
        report.scope["team"] = state.team
        token = current_coverage.set(report)
        try:
            try:
                result = function(state, *args, **kwargs)
            except SystemExit as error:
                if error.code and report.retrieval_started and report.failures:
                    if not state.human:
                        click.echo("{}" if function.__name__ in ("overview", "channel", "user") else "[]")
                    raise SystemExit(EXIT_INCOMPLETE) from None
                if error.code and not report.failures:
                    report.fail("command", error)
                raise
            except KeyboardInterrupt as error:
                report.fail("command", error)
                raise
            except Exception as error:
                report.fail("command", error)
                if not state.human:
                    click.echo("{}" if function.__name__ in ("overview", "channel", "user") else "[]")
                raise SystemExit(EXIT_INCOMPLETE if report.retrieval_started else 1) from None
            if report.failures:
                raise SystemExit(EXIT_INCOMPLETE)
            return result
        finally:
            for source in report.sources:
                if source["stop_reason"] == "pending":
                    source["stop_reason"] = "failure"
            current_coverage.reset(token)
            formatter = format_coverage_md if state.human else format_coverage_json
            click.echo(formatter(report.as_dict()), err=True)
    return wrapped
