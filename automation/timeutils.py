from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_TIMEZONE = "Asia/Shanghai"
NANOSECOND_FRACTION_RE = re.compile(
    r"(?P<microseconds>\.\d{6})\d+(?=(?:Z|[+-]\d{2}:\d{2})?$)"
)


def get_timezone(name: str = DEFAULT_TIMEZONE) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"unknown timezone: {name}") from exc


def parse_display_datetime(
    value: str, timezone: str = DEFAULT_TIMEZONE
) -> datetime:
    normalized = NANOSECOND_FRACTION_RE.sub(r"\g<microseconds>", value.strip())
    parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(get_timezone(timezone))
    return parsed
