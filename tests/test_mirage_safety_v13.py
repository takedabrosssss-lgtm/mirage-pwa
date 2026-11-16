from datetime import datetime, timedelta, timezone

import pytest

from mirage_safety_helpers_v13 import (
    choose_mark_trigger,
    market_lot_values,
    parse_retry_after,
    reserve_fee_adjusted_margin,
    scan_coverage_complete,
)


def test_retry_after_supports_seconds_and_http_date():
    assert parse_retry_after("120") == pytest.approx(120)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    future = (now + timedelta(seconds=90)).strftime("%a, %d %b %Y %H:%M:%S GMT")
    assert parse_retry_after(future, now=now) == pytest.approx(90)


def test_invalid_retry_after_returns_none():
    assert parse_retry_after(None) is None
    assert parse_retry_after("not-a-date") is None


def test_incomplete_scanner_coverage_fails_closed():
    assert scan_coverage_complete(40, 40, 0)
    assert not scan_coverage_complete(40, 39, 1)
    assert not scan_coverage_complete(0, 0, 0)


def test_mark_trigger_stop_wins_when_stop_and_target_both_touched():
    assert choose_mark_trigger("LONG", 95, [105, 110, 115], 90, 94, 106) == "SL"
    assert choose_mark_trigger("SHORT", 105, [95, 90, 85], 110, 94, 106) == "SL"


def test_liquidation_has_priority_over_stop_and_target():
    assert choose_mark_trigger("LONG", 95, [105, 110, 115], 92, 91, 106) == "LIQUIDATION"


def test_market_lot_size_preferred_for_market_fills():
    filters = {
        "LOT_SIZE": {"stepSize": "0.01", "minQty": "0.01"},
        "MARKET_LOT_SIZE": {"stepSize": "0.1", "minQty": "0.2"},
    }
    assert market_lot_values(filters) == (0.1, 0.2)


def test_lot_size_fallback_when_market_filter_is_zero():
    filters = {
        "LOT_SIZE": {"stepSize": "0.01", "minQty": "0.02"},
        "MARKET_LOT_SIZE": {"stepSize": "0", "minQty": "0"},
    }
    assert market_lot_values(filters) == (0.01, 0.02)


def test_entry_fee_is_reserved_alongside_margin():
    free = 100.0
    adjusted = reserve_fee_adjusted_margin(free, leverage=8, fee_rate=0.0005)
    assert adjusted < free
    # margin + entry fee for the capped notional cannot exceed free balance
    notional = adjusted * 8
    assert adjusted + notional * 0.0005 <= free + 1e-12
