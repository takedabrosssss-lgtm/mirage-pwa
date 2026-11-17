import asyncio
import math
import time
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import mirage_strategy_v12 as base
import mirage_strategy_v15 as v15


def candles_up(count=180):
    rows = []
    for i in range(count):
        close = 100 + 0.02 * i + math.sin(i / 4) * 4 + math.sin(i / 13) * 0.88
        rows.append({
            "timestamp": float(i), "open": close - 0.2,
            "high": close + 1.1, "low": close - 1.1,
            "close": close, "volume": 1500.0,
        })
    return rows


def to_rows(rows, interval, now_ms=None):
    now_ms = now_ms or int(time.time() * 1000)
    duration = base.TIMEFRAME_MS[interval]
    start = now_ms - len(rows) * duration
    result = []
    for i, candle in enumerate(rows):
        opened = start + i * duration
        result.append([
            opened, str(candle["open"]), str(candle["high"]), str(candle["low"]),
            str(candle["close"]), str(candle["volume"]), opened + duration - 1,
            "0", 100, "0", "0", "0",
        ])
    return result


def test_v15_exposes_five_distinct_models_and_five_scan_horizons():
    assert set(v15.MODEL_LABELS) == {
        "breakout", "mean_reversion", "ema_pullback", "trend_following", "momentum"
    }
    assert set(v15.MODEL_SCHEDULE) == {"15m", "30m", "1h", "4h", "1d"}
    assert v15.MODEL_SCHEDULE["30m"][1] == "mean_reversion"
    assert v15.MODEL_SCHEDULE["1d"][1] == "momentum"
    assert base.TIMEFRAME_MS["30m"] == 1_800_000
    assert base.TIMEFRAME_MS["1w"] == 604_800_000


def test_v15_rejects_extreme_volatility_and_quiet_market_regimes():
    extreme = {"adx": {"adx": 30}, "atr": 5.0, "bollinger": {"width": .04}, "volume_ratio": 2}
    quiet = {"adx": {"adx": 12}, "atr": .1, "bollinger": {"width": .001}, "volume_ratio": .8}
    assert v15._regime(extreme, 100) == "EXTREME_VOLATILITY"
    assert v15._regime(quiet, 100) == "QUIET"


def test_higher_timeframe_confirmation_fails_closed_on_missing_or_conflicting_trend(monkeypatch):
    upward = candles_up()
    downward = [
        {**row, "open": row["open"] + (2 * (row["close"] - 100)),
         "close": 200 - row["close"], "high": 201 - row["low"], "low": 199 - row["high"]}
        for row in upward
    ]
    monkeypatch.setattr(v15, "_bias", lambda rows: "LONG" if rows is upward else "SHORT")
    ok, biases = v15._mtf_confirmation("LONG", {"4h": upward, "1d": upward}, mean_reversion=False)
    assert ok is True
    assert set(biases.values()) == {"LONG"}
    ok, _ = v15._mtf_confirmation("LONG", {"4h": upward, "1d": downward}, mean_reversion=False)
    assert ok is False
    ok, _ = v15._mtf_confirmation("LONG", {}, mean_reversion=False)
    assert ok is False


def test_mean_reversion_may_operate_when_higher_timeframes_are_neutral(monkeypatch):
    neutral = candles_up()
    monkeypatch.setattr(v15, "_bias", lambda rows: "NEUTRAL")
    ok, _ = v15._mtf_confirmation("LONG", {"4h": neutral, "1d": neutral}, mean_reversion=True)
    assert ok is True
    monkeypatch.setattr(v15, "_bias", lambda rows: "SHORT")
    ok, _ = v15._mtf_confirmation("LONG", {"4h": neutral}, mean_reversion=True)
    assert ok is False


def test_v15_never_emits_a_signal_without_minimum_history():
    assert v15.analyze_strategy_v15(candles_up(80), "trend_following", {"1d": candles_up()}) is None
    with pytest.raises(ValueError):
        v15.analyze_strategy_v15(candles_up(), "not_a_real_model", {"1d": candles_up()})


def test_scanner_reads_closed_klines_and_does_not_poll_full_rest_ticker():
    class FakeMarket:
        def __init__(self):
            self.symbol_filters = {}
            self.paths = []
            self.intervals = []

        async def get(self, path, params=None):
            self.paths.append(path)
            assert path == "/fapi/v1/exchangeInfo"
            return {"symbols": [{
                "symbol": "BTCUSDT", "status": "TRADING", "contractType": "PERPETUAL",
                "quoteAsset": "USDT", "filters": [
                    {"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.001"},
                    {"filterType": "PRICE_FILTER", "tickSize": "0.1"},
                    {"filterType": "MIN_NOTIONAL", "notional": "5"},
                ],
            }]}

        async def klines(self, symbol, interval, limit=200):
            self.intervals.append(interval)
            return to_rows(candles_up(), interval)

    async def run():
        api = FakeMarket()
        base._EXCHANGE_CACHE["loaded_at"] = 0.0
        base._EXCHANGE_CACHE["allowed"] = set()
        await v15.scan_market_v15(
            api, symbols_limit=10,
            ticker_cache={"BTCUSDT": {"quote_volume": 1_000_000}},
        )
        assert api.paths == ["/fapi/v1/exchangeInfo"]
        assert set(api.intervals) == {"15m", "30m", "1h", "4h", "1d", "1w"}
        assert len(api.intervals) == 6

    asyncio.run(run())
