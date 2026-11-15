"""MIRAGE v1.2 signal engine adapted from Trading Intelligence PRO.

The strategy model is kept exchange-agnostic; market input is Binance USD-M
closed kline data. Order sizing and execution remain in trading.py / app.py.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any

TIMEFRAMES = {
    "15m": ("SCALPING", "breakout"),
    "1h": ("INTRADAY", "ema_pullback"),
    "4h": ("SWING", "trend_following"),
    "1d": ("POSITION", "trend_following"),
}
TIMEFRAME_MS = {"15m": 900_000, "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}
DUPLICATE_COOLDOWN_MINUTES = {"15m": 60, "1h": 240, "4h": 960, "1d": 5760}
ATR_STOP_MULTIPLIER = 1.8


def _ema(values: list[float], period: int) -> list[float]:
    if period <= 0 or len(values) < period:
        return []
    alpha = 2.0 / (period + 1)
    out = [sum(values[:period]) / period]
    for value in values[period:]:
        out.append(out[-1] + alpha * (value - out[-1]))
    return out


def _rsi(values: list[float], period: int = 14) -> float | None:
    if period <= 0 or len(values) <= period:
        return None
    changes = [values[i] - values[i - 1] for i in range(1, len(values))]
    gains = [max(x, 0.0) for x in changes]
    losses = [max(-x, 0.0) for x in changes]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(changes)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def _atr(candles: list[dict[str, float]], period: int = 14) -> float | None:
    if period <= 0 or len(candles) <= period:
        return None
    ranges = []
    for i in range(1, len(candles)):
        current, previous = candles[i], candles[i - 1]
        high, low = current["high"], current["low"]
        previous_close = previous["close"]
        ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
    if len(ranges) < period:
        return None
    value = sum(ranges[:period]) / period
    for item in ranges[period:]:
        value = (value * (period - 1) + item) / period
    return value


def _macd(values: list[float]) -> dict[str, float] | None:
    if len(values) < 35:
        return None
    fast, slow = _ema(values, 12), _ema(values, 26)
    if not fast or not slow:
        return None
    series = [fast[14 + i] - slow[i] for i in range(len(slow))]
    signal = _ema(series, 9)
    if not signal:
        return None
    line, signal_line = series[-1], signal[-1]
    return {"macd": line, "signal": signal_line, "histogram": line - signal_line}


def _adx(candles: list[dict[str, float]], period: int = 14) -> dict[str, float] | None:
    if period <= 0 or len(candles) < period * 2 + 1:
        return None
    plus_dm, minus_dm, true_ranges = [], [], []
    for i in range(1, len(candles)):
        cur, prev = candles[i], candles[i - 1]
        up = cur["high"] - prev["high"]
        down = prev["low"] - cur["low"]
        plus_dm.append(up if up > down and up > 0 else 0.0)
        minus_dm.append(down if down > up and down > 0 else 0.0)
        true_ranges.append(max(cur["high"] - cur["low"], abs(cur["high"] - prev["close"]), abs(cur["low"] - prev["close"])))
    tr, plus, minus = sum(true_ranges[:period]), sum(plus_dm[:period]), sum(minus_dm[:period])
    dx_values, plus_di, minus_di = [], 0.0, 0.0
    for i in range(period, len(true_ranges)):
        tr = tr - tr / period + true_ranges[i]
        plus = plus - plus / period + plus_dm[i]
        minus = minus - minus / period + minus_dm[i]
        if tr <= 0:
            dx_values.append(0.0)
            continue
        plus_di, minus_di = 100.0 * plus / tr, 100.0 * minus / tr
        denom = plus_di + minus_di
        dx_values.append(100.0 * abs(plus_di - minus_di) / denom if denom > 0 else 0.0)
    if len(dx_values) < period:
        return None
    adx_value = sum(dx_values[:period]) / period
    for value in dx_values[period:]:
        adx_value = (adx_value * (period - 1) + value) / period
    return {"adx": adx_value, "plus_di": plus_di, "minus_di": minus_di}


def _volume_ratio(candles: list[dict[str, float]], period: int = 20) -> float | None:
    if len(candles) < period + 1:
        return None
    previous = [x["volume"] for x in candles[-period - 1:-1]]
    average = sum(previous) / len(previous)
    return candles[-1]["volume"] / average if average > 0 else None


def _bollinger(values: list[float], period: int = 20, deviations: float = 2.0) -> dict[str, float] | None:
    if len(values) < period:
        return None
    window = values[-period:]
    middle = sum(window) / period
    variance = sum((v - middle) ** 2 for v in window) / period
    deviation = variance ** 0.5
    return {"upper": middle + deviations * deviation, "middle": middle,
            "lower": middle - deviations * deviation,
            "width": 4.0 * deviation / middle if middle else 0.0}


def _indicator_pack(candles: list[dict[str, float]]) -> dict[str, Any]:
    closes = [x["close"] for x in candles]
    e20, e50 = _ema(closes, 20), _ema(closes, 50)
    return {
        "ema20": e20[-1] if e20 else None,
        "ema50": e50[-1] if e50 else None,
        "ema20_previous": e20[-2] if len(e20) > 1 else None,
        "ema50_previous": e50[-2] if len(e50) > 1 else None,
        "rsi": _rsi(closes),
        "macd": _macd(closes),
        "atr": _atr(candles),
        "adx": _adx(candles),
        "bollinger": _bollinger(closes),
        "volume_ratio": _volume_ratio(candles),
    }


def _closed_rows(rows: list[list[Any]], timeframe: str, now_ms: int | None = None) -> list[dict[str, float]]:
    duration = TIMEFRAME_MS[timeframe]
    now_ms = now_ms or int(time.time() * 1000)
    out = []
    for row in rows:
        if len(row) < 7:
            continue
        # Binance kline close time (index 6) is inclusive; ignore the still-forming bar.
        if int(row[6]) >= now_ms:
            continue
        out.append({"timestamp": float(row[0]), "open": float(row[1]), "high": float(row[2]),
                    "low": float(row[3]), "close": float(row[4]), "volume": float(row[5])})
    return out


def analyze_strategy(candles: list[dict[str, float]], strategy: str) -> dict[str, Any] | None:
    if len(candles) < 100:
        return None
    indicators = _indicator_pack(candles)
    price = candles[-1]["close"]
    e20, e50 = indicators["ema20"], indicators["ema50"]
    rsi, macd, atr, adx_data = indicators["rsi"], indicators["macd"], indicators["atr"], indicators["adx"]
    volume_ratio = indicators["volume_ratio"]
    if any(x is None for x in (e20, e50, rsi, macd, atr, adx_data)) or price <= 0 or atr <= 0:
        return None
    adx_value, histogram = adx_data["adx"], macd["histogram"]
    bullish, bearish = e20 > e50, e20 < e50
    direction, score, reasons = "NEUTRAL", 50.0, []

    if strategy == "trend_following":
        if adx_value < 18:
            return None
        if bullish and price > e20 and histogram > 0 and 52 <= rsi <= 72:
            direction, score = "BUY", 82 + min(8, (adx_value - 18) * 0.35)
            reasons = ["EMA20 выше EMA50", "Цена выше EMA20", "MACD momentum положительный", "RSI подтверждает импульс", "ADX подтверждает силу тренда"]
        elif bearish and price < e20 and histogram < 0 and 28 <= rsi <= 48:
            direction, score = "SELL", 18 - min(8, (adx_value - 18) * 0.35)
            reasons = ["EMA20 ниже EMA50", "Цена ниже EMA20", "MACD momentum отрицательный", "RSI подтверждает слабость", "ADX подтверждает силу тренда"]

    elif strategy == "ema_pullback":
        previous_ema20 = indicators["ema20_previous"]
        previous_close = candles[-2]["close"]
        if previous_ema20 is None or adx_value < 16:
            return None
        if bullish and previous_close <= previous_ema20 and price > e20 and histogram > 0 and 48 <= rsi <= 68:
            direction, score = "BUY", 83 + min(7, (adx_value - 16) * 0.3)
            reasons = ["Старший тренд бычий", "Откат к EMA20 и возврат выше", "MACD momentum развернулся вверх", "RSI подтверждает восстановление"]
        elif bearish and previous_close >= previous_ema20 and price < e20 and histogram < 0 and 32 <= rsi <= 52:
            direction, score = "SELL", 17 - min(7, (adx_value - 16) * 0.3)
            reasons = ["Старший тренд медвежий", "Откат к EMA20 и отбой вниз", "MACD momentum развернулся вниз", "RSI подтверждает слабость"]

    elif strategy == "breakout":
        if adx_value < 18 or volume_ratio is None:
            return None
        previous = candles[-21:-1]
        range_high = max(x["high"] for x in previous)
        range_low = min(x["low"] for x in previous)
        if price > range_high and bullish and histogram > 0 and volume_ratio >= 1.2 and 50 <= rsi <= 75:
            direction, score = "BUY", 84 + min(6, (volume_ratio - 1.2) * 5)
            reasons = ["Закрытие выше максимума 20 свечей", "Объём выше среднего", "EMA подтверждает рост", "MACD momentum положительный"]
        elif price < range_low and bearish and histogram < 0 and volume_ratio >= 1.2 and 25 <= rsi <= 50:
            direction, score = "SELL", 16 - min(6, (volume_ratio - 1.2) * 5)
            reasons = ["Закрытие ниже минимума 20 свечей", "Объём выше среднего", "EMA подтверждает снижение", "MACD momentum отрицательный"]
    else:
        raise ValueError(f"Unknown strategy model: {strategy}")

    if direction == "NEUTRAL":
        return None
    strength = score if direction == "BUY" else 100.0 - score
    grade = "S" if strength >= 90 else "A" if strength >= 80 else "B" if strength >= 70 else "C"

    # Original Trading Intelligence PRO independent quality gate.
    plus_di, minus_di = adx_data["plus_di"], adx_data["minus_di"]
    di_ok = plus_di > minus_di if direction == "BUY" else minus_di > plus_di
    ema_slope = indicators["ema20_previous"]
    slope_ok = (e20 > ema_slope) if direction == "BUY" else (e20 < ema_slope)
    minimum_volume = 1.2 if strategy == "breakout" else 0.75
    volume_ok = volume_ratio is not None and volume_ratio >= minimum_volume
    gate = {"passed": bool(di_ok and slope_ok and volume_ok),
            "checks": {"directional_movement": bool(di_ok), "ema_slope": bool(slope_ok), "volume_participation": bool(volume_ok)},
            "minimum_volume_ratio": minimum_volume,
            "rejection_reasons": [label for ok, label in ((di_ok, "DI не подтверждает направление"), (slope_ok, "Наклон EMA20 не подтверждает направление"), (volume_ok, "Недостаточное участие объёма")) if not ok]}
    indicators["quality_gate"] = gate
    indicators["bollinger"] = indicators.get("bollinger")
    if strength < 80 or grade not in {"S", "A"} or not gate["passed"]:
        return None

    risk_distance = atr * ATR_STOP_MULTIPLIER
    if risk_distance <= 0:
        return None
    if direction == "BUY":
        stop = price - risk_distance
        tps = [price + risk_distance, price + risk_distance * 1.5, price + risk_distance * 2.0]
        side = "LONG"
    else:
        stop = price + risk_distance
        tps = [price - risk_distance, price - risk_distance * 1.5, price - risk_distance * 2.0]
        side = "SHORT"
    if min([stop, *tps]) <= 0:
        return None
    return {"direction": direction, "side": side, "score": int(round(strength)), "grade": grade,
            "entry": price, "stop": stop, "tps": tps, "reasons": reasons,
            "indicators": indicators, "created_at": int(time.time())}


_EXCHANGE_CACHE: dict[str, Any] = {"loaded_at": 0.0, "allowed": set()}
_EXCHANGE_LOCK = asyncio.Lock()


async def _load_exchange_filters(api) -> set[str]:
    async with _EXCHANGE_LOCK:
        now = time.time()
        if _EXCHANGE_CACHE["allowed"] and now - _EXCHANGE_CACHE["loaded_at"] < 21_600:
            return set(_EXCHANGE_CACHE["allowed"])
        info = await api.get("/fapi/v1/exchangeInfo")
        allowed: set[str] = set()
        filters_map: dict[str, dict[str, float]] = {}
        for item in info.get("symbols", []):
            symbol = str(item.get("symbol", "")).upper()
            if not (item.get("status") == "TRADING" and item.get("contractType") == "PERPETUAL"
                    and item.get("quoteAsset") == "USDT" and symbol.endswith("USDT")):
                continue
            allowed.add(symbol)
            filters = {f.get("filterType"): f for f in item.get("filters", [])}
            lot = filters.get("LOT_SIZE", {})
            price = filters.get("PRICE_FILTER", {})
            notional = filters.get("MIN_NOTIONAL", filters.get("NOTIONAL", {}))
            filters_map[symbol] = {"step_size": float(lot.get("stepSize", 0.001)),
                                   "min_qty": float(lot.get("minQty", 0.001)),
                                   "min_notional": float(notional.get("notional", notional.get("minNotional", 5))),
                                   "tick_size": float(price.get("tickSize", 0.01))}
        if not allowed:
            raise RuntimeError("Binance exchangeInfo returned no active USDT perpetual contracts")
        api.symbol_filters.update(filters_map)
        _EXCHANGE_CACHE["allowed"] = allowed
        _EXCHANGE_CACHE["loaded_at"] = now
        return set(allowed)


def _to_int(value, default=0):
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return default


async def scan_market(api, symbols_limit: int = 10, *, ticker_cache: dict[str, dict] | None = None):
    """Scan the most active USDT perpetuals from the live 24h WebSocket cache.

    Intentionally does not call /fapi/v1/ticker/24hr REST: that endpoint was
    repeatedly returning HTTP 418 and being hammered by the old refresh loop.
    """
    allowed = await _load_exchange_filters(api)
    live = ticker_cache or {}
    ranked = [(symbol, row) for symbol, row in live.items() if symbol in allowed]
    ranked.sort(key=lambda item: float(item[1].get("quote_volume", 0) or 0), reverse=True)
    symbols = [symbol for symbol, _ in ranked[:max(1, min(30, int(symbols_limit)))]]
    if not symbols:
        await asyncio.sleep(2.5)
        live = ticker_cache or {}
        ranked = [(symbol, row) for symbol, row in live.items() if symbol in allowed]
        ranked.sort(key=lambda item: float(item[1].get("quote_volume", 0) or 0), reverse=True)
        symbols = [symbol for symbol, _ in ranked[:max(1, min(30, int(symbols_limit)))]]
    if not symbols:
        raise RuntimeError("WAITING_FOR_TICKER_STREAM: Binance 24h WebSocket universe has not arrived yet")

    jobs = []
    for symbol in symbols:
        for interval, (strategy_name, model) in TIMEFRAMES.items():
            async def one(sym=symbol, tf=interval, strat=strategy_name, model_name=model):
                try:
                    rows = await api.klines(sym, tf, 200)
                    candles = _closed_rows(rows, tf)
                    result = analyze_strategy(candles, model)
                    if not result:
                        return None
                    return {"symbol": sym, "side": result["side"], "strategy": strat, "interval": tf,
                            "score": result["score"], "grade": result["grade"], "entry": result["entry"],
                            "stop": result["stop"], "tps": result["tps"], "created_at": result["created_at"],
                            "indicators": result["indicators"], "reasons": result["reasons"]}
                except Exception:
                    return None
            jobs.append(one())
    results = await asyncio.gather(*jobs)
    return [item for item in results if item is not None and item["score"] >= 80 and item["grade"] in {"S", "A"}]
