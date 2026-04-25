"""Alert-date classification for shushu records.

`alert_at` is a date (no time). We compare against today's UTC date.
Classification categories:
- "ok"        — no alert_at, or alert_at is >30 days in the future
- "alerting"  — alert_at is in the next 30 days (inclusive of today)
- "expired"   — alert_at is in the past

This module is pure: no I/O, no store knowledge.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal

AlertState = Literal["ok", "alerting", "expired"]

ALERT_WINDOW_DAYS = 30


def today_utc() -> date:
    return datetime.now(timezone.utc).date()


def classify(alert_at: date | None, today: date | None = None) -> AlertState:
    if alert_at is None:
        return "ok"
    today = today or today_utc()
    if alert_at < today:
        return "expired"
    if (alert_at - today).days <= ALERT_WINDOW_DAYS:
        return "alerting"
    return "ok"


def parse_date(s: str | None) -> date | None:
    if s is None or s == "":
        return None
    return date.fromisoformat(s)
