from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any, Dict, Iterable

from .config import ScheduleConfig


@dataclass(frozen=True)
class ScheduleDecision:
    full_scan_due: bool
    reply_poll_due: bool
    full_scan_interval_minutes: int
    reply_poll_interval_minutes: int


def _parse_clock(value: str) -> time:
    return datetime.strptime(value, "%H:%M").time()


def _due(last_value: str | None, now: datetime, minutes: int) -> bool:
    if not last_value:
        return True
    try:
        last = datetime.fromisoformat(last_value)
    except ValueError:
        return True
    if last.tzinfo is None and now.tzinfo is not None:
        last = last.replace(tzinfo=now.tzinfo)
    return now - last >= timedelta(minutes=minutes)


def full_scan_interval(now: datetime, config: ScheduleConfig) -> int:
    active = _parse_clock(config.active_start) <= now.time() < _parse_clock(
        config.active_end
    )
    weekday = now.weekday() < 5
    if weekday and active:
        return config.weekday_active_minutes
    if weekday:
        return config.weekday_quiet_minutes
    if active:
        return config.weekend_active_minutes
    return config.weekend_quiet_minutes


def awaiting_fast_reply(
    batches: Iterable[Dict[str, Any]], now: datetime, config: ScheduleConfig
) -> bool:
    for batch in batches:
        if batch.get("status") != "awaiting_review":
            continue
        dispatched_at = batch.get("dispatched_at")
        if not dispatched_at:
            continue
        try:
            dispatched = datetime.fromisoformat(dispatched_at)
        except ValueError:
            continue
        if dispatched.tzinfo is None and now.tzinfo is not None:
            dispatched = dispatched.replace(tzinfo=now.tzinfo)
        if now - dispatched < timedelta(hours=config.reply_fast_hours):
            return True
    return False


def decide(
    runtime: Dict[str, Any],
    batches: Iterable[Dict[str, Any]],
    now: datetime,
    config: ScheduleConfig,
) -> ScheduleDecision:
    scan_minutes = full_scan_interval(now, config)
    reply_minutes = (
        config.reply_fast_minutes
        if awaiting_fast_reply(batches, now, config)
        else scan_minutes
    )
    return ScheduleDecision(
        full_scan_due=_due(runtime.get("last_full_scan_at"), now, scan_minutes),
        reply_poll_due=_due(runtime.get("last_reply_poll_at"), now, reply_minutes),
        full_scan_interval_minutes=scan_minutes,
        reply_poll_interval_minutes=reply_minutes,
    )
