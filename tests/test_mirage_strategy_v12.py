import asyncio
import math
import time
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mirage_strategy_v12 as strategy


def make_trend_candles(count=180, *, volume_spike=True):
    candles = []
    for i in range(count):
        close = 100 + 0.02 * i + math.sin(i / 4) * 5 + math.sin(i / 13) * 1.1
        candles.append({
            "timestamp": float(i),
            "open": close - 0.2,
            "high": close + 1.1,
            "low": close - 1.1,
            "close": close,
            "volume": 1700.0 if volume_spike and i == count - 1 else 1000.0,
        })
    return candles


def to_binance_rows(candles, interval, now_ms=None):
    now_ms = now_ms or int(time.time() * 1000)
    duration = strategy.TIMEFRAME_MS[interval]
    rows = []
    start = now_ms - len(candles) * duration
    for i, candle in enumerate(candles):
        opened = start + i * duration
        rows.append([
            opened,
            str(candle["open"]),
            str(candle["high"]),
            str(candle["low"]),
            str(candle["close"]),
            str(candle["volume"]),
            opened + duration - 1,
            "0", 100, "0", "0", "0",
        ])
    return rows


def test_closed_rows_excludes_the_current_unfinished_kline():
    now_ms = 1_800_000_000_000
    rows = [
        [now_ms - 900_000, "100", "102", "99", "101", "10", now_ms - 1],
        [now_ms, "101", "103", "100", "102", "12", now_ms + 899_999],
    ]
    closed = strategy._closed_rows(rows, "15m", now_ms=now_ms)
    assert len(closed) == 1
    assert closed[0]["close"] == 101.0


def test_indicator_pack_contains_all_telegram_model_features():
    pack = strategy._indicator_pack(make_trend_candles())
    assert pack["ema20"] > pack["ema50"]
    assert pack["ema20_previous"] is not None
    assert 0 <= pack["rsi"] <= 100
    assert pack["macd"]["histogram"] > 0
    assert pack["atr"] > 0
    assert pack["adx"]["adx"] >= 18
    assert pack["adx"]["plus_di"] > pack["adx"]["minus_di"]
    assert pack["bollinger"]["upper"] > pack["bollinger"]["lower"]
    assert pack["volume_ratio"] >= 1.2


def test_original_trend_model_maps_buy_to_futures_long_and_staged_targets():
    candles = make_trend_candles()
    result = strategy.analyze_strategy(candles, "trend_following")
    assert result is not None
    assert result["side"] == "LONG"
    assert result["score"] >= 80
    assert result["grade"] in {"A", "S"}
    risk = result["entry"] - result["stop"]
    assert result["tps"][0] == pytest.approx(result["entry"] + risk)
    assert result["tps"][1] == pytest.approx(result["entry"] + risk * 1.5)
    assert result["tps"][2] == pytest.approx(result["entry"] + risk * 2.0)
    assert result["indicators"]["quality_gate"]["passed"] is True


def test_weak_volume_breakout_is_rejected_by_the_quality_gate():
    candles = make_trend_candles(volume_spike=False)
    candles[-1]["volume"] = 1000.0
    result = strategy.analyze_strategy(candles, "breakout")
    assert result is None


def test_scanner_uses_live_ticker_cache_and_never_calls_full_rest_ticker():
    class FakeBinance:
        def __init__(self):
            self.symbol_filters = {}
            self.paths = []

        async def get(self, path, params=None):
            self.paths.append(path)
            if path != "/fapi/v1/exchangeInfo":
                raise AssertionError(f"Unexpected REST request: {path}")
            return {"symbols": [{
                "symbol": "BTCUSDT", "status": "TRADING", "contractType": "PERPETUAL",
                "quoteAsset": "USDT", "filters": [
                    {"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.001"},
                    {"filterType": "PRICE_FILTER", "tickSize": "0.1"},
                    {"filterType": "MIN_NOTIONAL", "notional": "5"},
                ],
            }]}

        async def klines(self, symbol, interval, limit=200):
            return to_binance_rows(make_trend_candles(), interval)

    async def run():
        api = FakeBinance()
        strategy._EXCHANGE_CACHE["loaded_at"] = 0.0
        strategy._EXCHANGE_CACHE["allowed"] = set()
        found = await strategy.scan_market(
            api, symbols_limit=10,
            ticker_cache={"BTCUSDT": {"quote_volume": 1_500_000, "last_price": 110}},
        )
        assert api.paths == ["/fapi/v1/exchangeInfo"]
        assert api.symbol_filters["BTCUSDT"]["tick_size"] == 0.1
        assert {item["interval"] for item in found} >= {"4h", "1d"}
        assert all(item["symbol"] == "BTCUSDT" and item["side"] in {"LONG", "SHORT"} for item in found)

    asyncio.run(run())
