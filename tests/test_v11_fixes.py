import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mirage_v11_fixes import (
    entry_gate_failures,
    epoch_ms,
    funding_start_ms,
    is_usdm_payload,
    merge_quote_parts,
    quote_is_fresh,
    recent_failures_exceeded,
    relevant_quote_message,
    unpack_stream_message,
)


def test_epoch_ms_accepts_legacy_seconds_and_binance_ms():
    assert epoch_ms(1_700_000_000) == 1_700_000_000_000
    assert epoch_ms(1_700_000_000_123) == 1_700_000_000_123


def test_funding_start_uses_ms_and_is_exclusive_of_checkpoint():
    assert funding_start_ms(1_700_000_010, 1_700_000_000) == 1_700_000_010_001
    assert funding_start_ms(1_700_000_010_000, 1_700_000_000) == 1_700_000_010_001
    assert funding_start_ms(0, 1_700_000_000) == 1_700_000_000_000


def test_quote_requires_both_feed_timestamps_not_generic_received_at():
    now = 1000.0
    incomplete = {"bid": 99, "ask": 101, "mark": 100, "received_at": now}
    assert not quote_is_fresh(incomplete, now)


def test_quote_rejects_one_stale_feed_even_if_other_is_new():
    q = {"bid": 99, "ask": 101, "mark": 100,
         "book_received_at": 999.8, "mark_received_at": 990.0}
    assert not quote_is_fresh(q, 1000.0, max_age=5)


def test_quote_accepts_complete_fresh_data_and_rejects_crossed_book():
    q = {"bid": 99, "ask": 101, "mark": 100,
         "book_received_at": 998.0, "mark_received_at": 999.0}
    assert quote_is_fresh(q, 1000.0)
    q["ask"] = 98
    assert not quote_is_fresh(q, 1000.0)


def test_market_and_public_streams_must_both_arrive_before_quote_published():
    parts = {}
    mark = {"e": "markPriceUpdate", "s": "BTCUSDT", "p": "100", "r": "0.001", "T": 2000, "st": 1}
    book = {"e": "bookTicker", "s": "BTCUSDT", "b": "99.9", "a": "100.1", "st": 1}
    assert merge_quote_parts(parts, "BTCUSDT", "market", mark, 1000.0) is None
    merged = merge_quote_parts(parts, "BTCUSDT", "public", book, 1000.1)
    assert merged is not None
    assert merged["bid"] == pytest.approx(99.9)
    assert merged["ask"] == pytest.approx(100.1)
    assert merged["mark"] == pytest.approx(100)


def test_stale_mark_is_not_reused_when_new_book_arrives():
    parts = {}
    mark = {"e": "markPriceUpdate", "s": "BTCUSDT", "p": "100"}
    book = {"e": "bookTicker", "s": "BTCUSDT", "b": "99.9", "a": "100.1"}
    merge_quote_parts(parts, "BTCUSDT", "market", mark, 1000.0)
    assert merge_quote_parts(parts, "BTCUSDT", "public", book, 1006.0) is None


def test_combined_and_raw_messages_are_normalized():
    assert unpack_stream_message('{"stream":"!markPrice@arr@1s","data":[{"e":"markPriceUpdate"}]}') == [{"e": "markPriceUpdate"}]
    assert unpack_stream_message('{"e":"bookTicker","s":"BTCUSDT"}') == [{"e": "bookTicker", "s": "BTCUSDT"}]
    assert unpack_stream_message('[{"e":"markPriceUpdate"},{"e":"markPriceUpdate"}]') == [
        {"e": "markPriceUpdate"}, {"e": "markPriceUpdate"}
    ]


def test_market_payload_filter_rejects_coin_m_and_non_usdt_symbols():
    assert is_usdm_payload({"s": "BTCUSDT", "st": 1})
    assert is_usdm_payload({"s": "ETHUSDT"})
    assert not is_usdm_payload({"s": "BTCUSD_PERP", "st": 2})
    assert not is_usdm_payload({"s": "BTCUSDC", "st": 1})


def test_login_failure_window_expires_old_attempts():
    stamps = [1.0, 2.0, 3.0]
    assert recent_failures_exceeded(stamps, now=4.0, window=10.0, limit=3)
    assert not recent_failures_exceeded(stamps, now=20.0, window=10.0, limit=3)
    assert stamps == []


def test_ticker_updates_do_not_mask_stalled_mark_price_feed():
    assert not relevant_quote_message("market", {"e": "24hrTicker", "s": "BTCUSDT"})
    assert relevant_quote_message("market", {"e": "markPriceUpdate", "s": "BTCUSDT"})
    assert relevant_quote_message("public", {"e": "bookTicker", "s": "BTCUSDT"})
    assert not relevant_quote_message("public", {"e": "depthUpdate", "s": "BTCUSDT"})


def healthy_state(now=1000.0):
    return {
        "market_connected": True,
        "market_last_message": now - 1,
        "public_connected": True,
        "public_last_message": now - 1,
    }


def test_entry_gate_allows_only_fresh_rest_and_both_live_feeds():
    assert entry_gate_failures(healthy_state(), True, 990.0, 1000.0) == []


def test_entry_gate_blocks_when_rest_fallback_is_available_but_websockets_are_down():
    state = healthy_state()
    state["market_connected"] = False
    state["public_connected"] = False
    failures = entry_gate_failures(state, True, 990.0, 1000.0)
    assert any("Mark Price WebSocket is disconnected" in item for item in failures)
    assert any("Bid/Ask WebSocket is disconnected" in item for item in failures)


def test_entry_gate_blocks_one_stale_websocket_even_if_other_is_healthy():
    state = healthy_state()
    state["market_last_message"] = 980.0
    failures = entry_gate_failures(state, True, 990.0, 1000.0)
    assert any("Mark Price WebSocket is stale" in item for item in failures)
    assert not any("Bid/Ask WebSocket" in item for item in failures)


def test_entry_gate_blocks_unavailable_or_old_rest_market_status():
    assert entry_gate_failures(healthy_state(), False, 990.0, 1000.0)
    assert any("older than 15 minutes" in item for item in
               entry_gate_failures(healthy_state(), True, 1.0, 1000.0))


def test_entry_gate_rejects_future_feed_timestamps():
    state = healthy_state(now=1000.0)
    state["public_last_message"] = 2000.0
    assert any("Bid/Ask WebSocket is stale" in item for item in
               entry_gate_failures(state, True, 990.0, 1000.0))
