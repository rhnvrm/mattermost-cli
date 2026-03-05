"""Tests for --since parsing."""

import time

import pytest

from mmchat.time_utils import parse_since


class TestRelative:
    def test_hours(self):
        result = parse_since("1h")
        now_ms = int(time.time() * 1000)
        # Should be roughly 1 hour ago (within 5 seconds tolerance)
        expected = now_ms - 3600 * 1000
        assert abs(result - expected) < 5000

    def test_minutes(self):
        result = parse_since("30m")
        now_ms = int(time.time() * 1000)
        expected = now_ms - 30 * 60 * 1000
        assert abs(result - expected) < 5000

    def test_days(self):
        result = parse_since("2d")
        now_ms = int(time.time() * 1000)
        expected = now_ms - 2 * 86400 * 1000
        assert abs(result - expected) < 5000

    def test_weeks(self):
        result = parse_since("1w")
        now_ms = int(time.time() * 1000)
        expected = now_ms - 7 * 86400 * 1000
        assert abs(result - expected) < 5000


class TestNamed:
    def test_today(self):
        result = parse_since("today")
        now_ms = int(time.time() * 1000)
        # Should be start of today (before now, at most 24h ago)
        assert result <= now_ms
        assert result > now_ms - 86400 * 1000

    def test_yesterday(self):
        result = parse_since("yesterday")
        now_ms = int(time.time() * 1000)
        assert result <= now_ms
        assert result > now_ms - 2 * 86400 * 1000


class TestAbsolute:
    def test_date(self):
        result = parse_since("2026-03-05")
        # Should be a valid timestamp for 2026-03-05 start of day (UTC)
        from datetime import datetime, timezone

        expected = int(datetime(2026, 3, 5, tzinfo=timezone.utc).timestamp() * 1000)
        assert result == expected

    def test_datetime(self):
        result = parse_since("2026-03-05T14:30")
        from datetime import datetime, timezone

        expected = int(datetime(2026, 3, 5, 14, 30, tzinfo=timezone.utc).timestamp() * 1000)
        assert result == expected


class TestRawTimestamps:
    def test_raw_ms(self):
        result = parse_since("1741171200000")
        assert result == 1741171200000

    def test_raw_seconds_with_prefix(self):
        result = parse_since("@1741171200")
        assert result == 1741171200000


class TestInvalid:
    def test_garbage(self):
        with pytest.raises(ValueError):
            parse_since("garbage")

    def test_empty(self):
        with pytest.raises(ValueError):
            parse_since("")

    def test_negative(self):
        with pytest.raises(ValueError):
            parse_since("-1h")
