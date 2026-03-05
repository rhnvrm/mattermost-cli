"""--since argument parsing: relative, absolute, named, and raw timestamps."""

import re
import time
from datetime import datetime, timedelta, timezone


def parse_since(value: str) -> int:
    """Parse a --since value into Unix timestamp in milliseconds.

    Supports:
      Relative:  1h, 30m, 2d, 1w
      Named:     today, yesterday
      Absolute:  2026-03-05, 2026-03-05T14:30
      Raw ms:    1741171200000 (13+ digits, pass through)
      Raw sec:   @1741171200 (@ prefix, multiply by 1000)

    Returns Unix timestamp in milliseconds.
    """
    value = value.strip()

    # Raw Unix ms (13+ digit number)
    if re.match(r"^\d{13,}$", value):
        return int(value)

    # Raw Unix seconds with @ prefix
    if value.startswith("@") and re.match(r"^@\d+$", value):
        return int(value[1:]) * 1000

    # Relative: 1h, 30m, 2d, 1w
    match = re.match(r"^(\d+)([mhdw])$", value)
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        delta = {
            "m": timedelta(minutes=amount),
            "h": timedelta(hours=amount),
            "d": timedelta(days=amount),
            "w": timedelta(weeks=amount),
        }[unit]
        ts = datetime.now(timezone.utc) - delta
        return int(ts.timestamp() * 1000)

    # Named
    now = datetime.now(timezone.utc)
    if value == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return int(start.timestamp() * 1000)
    if value == "yesterday":
        start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return int(start.timestamp() * 1000)

    # Absolute datetime: 2026-03-05T14:30
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except ValueError:
        pass

    # Absolute date: 2026-03-05
    try:
        dt = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except ValueError:
        pass

    raise ValueError(
        f"Cannot parse --since value: '{value}'\n"
        "Expected: 1h, 30m, 2d, today, yesterday, 2026-03-05, "
        "2026-03-05T14:30, 1741171200000, or @1741171200"
    )
