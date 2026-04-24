from __future__ import annotations

from datetime import date

import pytest

from shushu import alerts


def _today(y, m, d):
    return date(y, m, d)


def test_classify_none_returns_ok():
    assert alerts.classify(None, today=_today(2026, 4, 24)) == "ok"


def test_classify_far_future_returns_ok():
    assert alerts.classify(date(2027, 1, 1), today=_today(2026, 4, 24)) == "ok"


def test_classify_within_30_days_returns_alerting():
    assert alerts.classify(date(2026, 5, 10), today=_today(2026, 4, 24)) == "alerting"


def test_classify_today_returns_alerting():
    assert alerts.classify(date(2026, 4, 24), today=_today(2026, 4, 24)) == "alerting"


def test_classify_past_returns_expired():
    assert alerts.classify(date(2026, 4, 23), today=_today(2026, 4, 24)) == "expired"


@pytest.mark.parametrize("s", ["2026-04-24", "2099-12-31"])
def test_parse_date_accepts_iso(s):
    assert alerts.parse_date(s) is not None


def test_parse_date_rejects_malformed():
    with pytest.raises(ValueError):
        alerts.parse_date("2026-13-40")


def test_parse_date_accepts_none_and_empty():
    assert alerts.parse_date(None) is None
    assert alerts.parse_date("") is None
