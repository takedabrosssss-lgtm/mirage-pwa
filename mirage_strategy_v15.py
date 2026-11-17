"""MIRAGE v1.5 hybrid signal engine.

Five independent setup models share one quality/risk gate. The engine uses only
closed USD-M candles, confirms direction on higher timeframes, and emits the
same signal schema expected by the existing v1.4 paper-trading runtime.
A score is a rule-based quality index, never a win-probability estimate.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

import mirage_strategy_v12 as base
import mirage_runtime_v12 as runtime
import app as core

# Keep all existing user-facing strategy groups so saved account preferences
# and /api/settings validation remain backward compatible.
MODEL_SCHEDULE: dict[str, tuple[str, str, tuple[str, ...]]] = {
    # timeframe: (existing user strategy group, model, higher-TF confirmations)
    "15m": ("SCALPING", "breakout", ("4h", "1d")),
    "30m": ("SCALPING", "mean_reversion", ("4h", "1d")),
    "1h": ("INTRADAY", "ema_pullback", ("4h", "1d")),
    "4h": ("SWING", "trend_following", ("1d", "1w")),
    "1d": ("POSITION", "momentum", ("1w",)),
}

MODEL_LABELS = {
    "breakout": "Breakout Intelligence",
    "mean_reversion": "Mean Reversion",
    "ema_pullback": "Trend Pullback",
    "trend_following": "Trend Following",
    "momentum": "Momentum Intelligence",
}

# The old helpers own indicator calculations and kline-close filtering. Extend
# their interval map rather than forking that behavior into another code path.
base.TIMEFRAME_MS.update({"30m": 1_800_000, "1w": 604_800_000})
base.DUPLICATE_COOLDOWN_MINUTES.update({"30m": 120, "1w": 10_080})
base.TIMEFRAMES.update({
    "15m": ("SCALPING", "breakout"),
    "30m": ("SCALPING", "mean_reversion"),
    "1h": ("INTRADAY", "ema_pullback"),
    "4h": ("SWING", "trend_following"),
    "1d": ("POSITION", "momentum"),
})


def _safe_num(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
        return result if result == result and abs(result) != float("inf") else default
    except (TypeError, ValueError):
        return default


def _regime(ind: dict[str, Any], price: float) -> str:
    adx = _safe_num((ind.get("adx") or {}).get("adx"))
    atr = _safe_num(ind.get("atr"))
    width = _safe_num((ind.get("bollinger") or {}).get("width"))
    volume = _safe_num(ind.get("volume_ratio"))
    atr_pct = atr / price * 100 if price > 0 else 0.0
    if atr_pct >= 4.5:
        return "EXTREME_VOLATILITY"
    if width < 0.0025:
        return "QUIET"
    if adx >= 23:
        return "TREND"
    if adx <= 18 and width >= 0.003:
        return "RANGE"
    if volume >= 1.6 or atr_pct >= 2.2:
        return "EXPANSION"
    return "TRANSITION"


def _bias(candles: list[dict[str, float]]) -> str:
    if len(candles) < 100:
        return "NEUTRAL"
    ind = base._indicator_pack(candles)
    adx_data = ind.get("adx") or {}
    e20, e50 = ind.get("ema20"), ind.get("ema50")
    adx = _safe_num(adx_data.get("adx"))
    plus = _safe_num(adx_data.get("plus_di"))
    minus = _safe_num(adx_data.get("minus_di"))
    if e20 is None or e50 is None or adx < 18:
        return "NEUTRAL"
    if e20 > e50 and plus > minus:
        return "LONG"
    if e20 < e50 and minus > plus:
        return "SHORT"
    return "NEUTRAL"


def _mtf_confirmation(direction: str, contexts: dict[str, list[dict[str, float]]], *, mean_reversion: bool) -> tuple[bool, dict[str, str]]:
    biases = {tf: _bias(rows) for tf, rows in contexts.items()}
    decisive = [bias for bias in biases.values() if bias != "NEUTRAL"]
    if mean_reversion:
        # In a range, neutral higher timeframes are acceptable; a fade is
        # rejected only when a confirmed higher-timeframe trend points against it.
        return bool(biases) and all(bias in ("NEUTRAL", direction) for bias in biases.values()), biases
    if not decisive:
        return False, biases
    return len(decisive) == len(biases) and all(bias == direction for bias in decisive), biases


def _macd_previous(candles: list[dict[str, float]]) -> dict[str, float] | None:
    return base._macd([row["close"] for row in candles[:-1]]) if len(candles) > 36 else None


def analyze_strategy_v15(
    candles: list[dict[str, float]],
    strategy: str,
    higher_context: dict[str, list[dict[str, float]]] | None = None,
) -> dict[str, Any] | None:
    """Return a fully qualified signal or None; never emits a soft/weak entry."""
    if len(candles) < 120:
        return None
    if strategy not in MODEL_LABELS:
        raise ValueError(f"Unknown MIRAGE v1.5 model: {strategy}")

    ind = base._indicator_pack(candles)
    price = _safe_num(candles[-1].get("close"))
    if price <= 0 or any(ind.get(key) is None for key in ("ema20", "ema50", "rsi", "macd", "atr", "adx", "bollinger")):
        return None

    e20, e50 = float(ind["ema20"]), float(ind["ema50"])
    e20_prev = ind.get("ema20_previous")
    e50_prev = ind.get("ema50_previous")
    rsi = float(ind["rsi"])
    macd = ind["macd"]
    previous_macd = _macd_previous(candles)
    hist = float(macd["histogram"])
    previous_hist = float(previous_macd["histogram"]) if previous_macd else hist
    adx_data = ind["adx"]
    adx = float(adx_data["adx"])
    plus_di = float(adx_data["plus_di"])
    minus_di = float(adx_data["minus_di"])
    di_gap = abs(plus_di - minus_di)
    atr = float(ind["atr"])
    volume_ratio = _safe_num(ind.get("volume_ratio"))
    bands = ind["bollinger"]
    regime = _regime(ind, price)
    if regime in {"EXTREME_VOLATILITY", "QUIET"}:
        return None

    bullish = e20 > e50 and (e20_prev is None or e20 > e20_prev)
    bearish = e20 < e50 and (e20_prev is None or e20 < e20_prev)
    direction = ""
    trigger_reasons: list[str] = []
    mean_reversion = strategy == "mean_reversion"
    previous = candles[-2]
    previous_close = float(previous["close"])
    recent = candles[-21:-1]
    recent_high = max(float(row["high"]) for row in recent)
    recent_low = min(float(row["low"]) for row in recent)
    candle_range = max(1e-12, float(candles[-1]["high"]) - float(candles[-1]["low"]))
    body_ratio = abs(price - float(candles[-1]["open"])) / candle_range
    extension_atr = abs(price - e20) / atr

    # Five different entry hypotheses. All triggers use the last fully closed bar.
    if strategy == "breakout":
        if (regime in {"TREND", "EXPANSION"} and adx >= 20 and volume_ratio >= 1.35
                and price > recent_high and bullish and hist > 0 and 53 <= rsi <= 73
                and body_ratio >= 0.45 and extension_atr <= 2.0):
            direction = "LONG"
            trigger_reasons = ["Break above the 20-bar range", "Participation confirmed by volume", "Momentum and trend aligned"]
        elif (regime in {"TREND", "EXPANSION"} and adx >= 20 and volume_ratio >= 1.35
                and price < recent_low and bearish and hist < 0 and 27 <= rsi <= 47
                and body_ratio >= 0.45 and extension_atr <= 2.0):
            direction = "SHORT"
            trigger_reasons = ["Break below the 20-bar range", "Participation confirmed by volume", "Momentum and trend aligned"]

    elif strategy == "ema_pullback":
        touched = min(float(row["low"]) for row in candles[-4:]) <= e20 + atr * 0.25
        rejected = max(float(row["high"]) for row in candles[-4:]) >= e20 - atr * 0.25
        if (regime == "TREND" and adx >= 21 and bullish and touched and price > e20
                and hist > 0 and hist >= previous_hist and 50 <= rsi <= 68
                and extension_atr <= 1.15):
            direction = "LONG"
            trigger_reasons = ["Pullback tested the EMA20 area", "Closed candle reclaimed EMA20", "Momentum resumed with the trend"]
        elif (regime == "TREND" and adx >= 21 and bearish and rejected and price < e20
                and hist < 0 and hist <= previous_hist and 32 <= rsi <= 50
                and extension_atr <= 1.15):
            direction = "SHORT"
            trigger_reasons = ["Pullback tested the EMA20 area", "Closed candle rejected EMA20", "Momentum resumed to the downside"]

    elif strategy == "momentum":
        roc = (price / float(candles[-7]["close"]) - 1.0) * 100 if float(candles[-7]["close"]) > 0 else 0.0
        if (regime in {"TREND", "EXPANSION"} and adx >= 24 and bullish and price > e20
                and hist > 0 and hist > previous_hist and volume_ratio >= 1.15
                and 55 <= rsi <= 72 and roc >= 0.8 and extension_atr <= 1.8):
            direction = "LONG"
            trigger_reasons = ["Positive multi-bar price acceleration", "MACD histogram expanding", "Volume confirms momentum"]
        elif (regime in {"TREND", "EXPANSION"} and adx >= 24 and bearish and price < e20
                and hist < 0 and hist < previous_hist and volume_ratio >= 1.15
                and 28 <= rsi <= 45 and roc <= -0.8 and extension_atr <= 1.8):
            direction = "SHORT"
            trigger_reasons = ["Negative multi-bar price acceleration", "MACD histogram expanding downward", "Volume confirms momentum"]

    elif strategy == "trend_following":
        if (regime == "TREND" and adx >= 23 and bullish and price > e20 and hist > 0
                and 52 <= rsi <= 70 and extension_atr <= 1.8):
            direction = "LONG"
            trigger_reasons = ["EMA20 / EMA50 trend structure aligned", "Price holds above EMA20", "ADX and MACD confirm trend strength"]
        elif (regime == "TREND" and adx >= 23 and bearish and price < e20 and hist < 0
                and 30 <= rsi <= 48 and extension_atr <= 1.8):
            direction = "SHORT"
            trigger_reasons = ["EMA20 / EMA50 trend structure aligned", "Price holds below EMA20", "ADX and MACD confirm trend strength"]

    elif strategy == "mean_reversion":
        lower = float(bands["lower"])
        upper = float(bands["upper"])
        if (regime == "RANGE" and adx <= 18 and float(candles[-1]["low"]) <= lower
                and price > lower and rsi <= 38 and hist > previous_hist and volume_ratio >= 0.8):
            direction = "LONG"
            trigger_reasons = ["Lower Bollinger band rejection", "RSI shows stretched downside", "MACD momentum begins to recover"]
        elif (regime == "RANGE" and adx <= 18 and float(candles[-1]["high"]) >= upper
                and price < upper and rsi >= 62 and hist < previous_hist and volume_ratio >= 0.8):
            direction = "SHORT"
            trigger_reasons = ["Upper Bollinger band rejection", "RSI shows stretched upside", "MACD momentum begins to fade"]

    if not direction:
        return None

    contexts = higher_context or {}
    mtf_ok, mtf_biases = _mtf_confirmation(direction, contexts, mean_reversion=mean_reversion)
    if not mtf_ok:
        return None

    di_ok = plus_di > minus_di and di_gap >= 5 if direction == "LONG" else minus_di > plus_di and di_gap >= 5
    if mean_reversion:
        trend_ok = regime == "RANGE" and adx <= 18
        min_volume = 0.8
        min_adx = 0.0
        extension_limit = 2.4
    elif strategy == "breakout":
        trend_ok = regime in {"TREND", "EXPANSION"}
        min_volume = 1.35
        min_adx = 20.0
        extension_limit = 2.0
    elif strategy == "ema_pullback":
        trend_ok = regime == "TREND"
        min_volume = 1.0
        min_adx = 21.0
        extension_limit = 1.15
    elif strategy == "momentum":
        trend_ok = regime in {"TREND", "EXPANSION"}
        min_volume = 1.15
        min_adx = 24.0
        extension_limit = 1.8
    else:
        trend_ok = regime == "TREND"
        min_volume = 1.0
        min_adx = 23.0
        extension_limit = 1.8

    volume_ok = volume_ratio >= min_volume
    adx_ok = adx >= min_adx
    extension_ok = extension_atr <= extension_limit
    bollinger_ok = float(bands.get("width", 0)) >= 0.0025
    # Reject doji-like breakouts and very thin candles on all non-reversion models.
    candle_ok = body_ratio >= (0.25 if mean_reversion else 0.35)
    checks = {
        "higher_timeframe_alignment": bool(mtf_ok),
        "market_regime_fit": bool(trend_ok),
        "directional_movement": bool(di_ok),
        "trend_strength": bool(adx_ok),
        "volume_participation": bool(volume_ok),
        "not_overextended": bool(extension_ok),
        "volatility_present": bool(bollinger_ok),
        "closed_candle_quality": bool(candle_ok),
    }
    if not all(checks.values()):
        return None

    # Transparent additive confluence score; not a probability or expected return.
    score = 68.0
    score += 7.0  # all required higher-timeframe checks passed
    score += min(6.0, max(0.0, (adx - min_adx) * 0.28))
    score += min(5.0, max(0.0, (di_gap - 5.0) * 0.30))
    score += min(4.0, max(0.0, (volume_ratio - min_volume) * 3.0))
    score += 3.0 if trend_ok else 0.0
    score += 3.0 if body_ratio >= 0.55 else 1.0
    score += 2.0 if (e20 > e50 if direction == "LONG" else e20 < e50) else 0.0
    # Dynamic mode requires a little more confluence in transitional/volatile expansions.
    minimum_score = 88 if regime == "EXPANSION" else 86
    score = min(100.0, score)
    strength = int(round(score))
    if strength < minimum_score:
        return None
    grade = "S" if strength >= 92 else "A"

    risk_distance = atr * 1.8
    if risk_distance <= 0:
        return None
    if direction == "LONG":
        stop = price - risk_distance
        targets = [price + risk_distance, price + risk_distance * 1.5, price + risk_distance * 2.0]
        side = "LONG"
    else:
        stop = price + risk_distance
        targets = [price - risk_distance, price - risk_distance * 1.5, price - risk_distance * 2.0]
        side = "SHORT"
    if min([stop, *targets]) <= 0:
        return None

    labels = [f"Higher timeframe: {tf} {bias}" for tf, bias in mtf_biases.items()]
    indicators = dict(ind)
    indicators["strategy_model"] = strategy
    indicators["strategy_label"] = MODEL_LABELS[strategy]
    indicators["market_regime"] = regime
    indicators["higher_timeframe_bias"] = mtf_biases
    indicators["score_is_probability"] = False
    indicators["quality_gate"] = {
        "passed": True,
        "checks": checks,
        "minimum_score": minimum_score,
        "minimum_volume_ratio": min_volume,
        "minimum_adx": min_adx,
        "directional_gap": round(di_gap, 3),
        "extension_atr": round(extension_atr, 3),
        "regime": regime,
        "rejection_reasons": [],
    }
    reasons = [MODEL_LABELS[strategy], *trigger_reasons, *labels[:2]]
    return {
        "direction": direction,
        "side": side,
        "score": strength,
        "grade": grade,
        "entry": price,
        "stop": stop,
        "tps": targets,
        "reasons": reasons,
        "indicators": indicators,
        "created_at": int(time.time()),
        "candle_open_time": int(candles[-1]["timestamp"]),
    }


async def scan_market_v15(api, symbols_limit: int = 10, *, ticker_cache: dict[str, dict] | None = None):
    """Fetch each symbol/timeframe once, then evaluate five independent models."""
    allowed = await base._load_exchange_filters(api)
    live = ticker_cache or {}
    ranked = [(symbol, row) for symbol, row in live.items() if symbol in allowed]
    ranked.sort(key=lambda item: _safe_num(item[1].get("quote_volume")), reverse=True)
    symbols = [symbol for symbol, _ in ranked[:max(1, min(30, int(symbols_limit)))]]
    if not symbols:
        await asyncio.sleep(2.0)
        ranked = [(symbol, row) for symbol, row in (ticker_cache or {}).items() if symbol in allowed]
        ranked.sort(key=lambda item: _safe_num(item[1].get("quote_volume")), reverse=True)
        symbols = [symbol for symbol, _ in ranked[:max(1, min(30, int(symbols_limit)))]]
    if not symbols:
        raise RuntimeError("WAITING_FOR_TICKER_STREAM: Binance 24h WebSocket ticker universe has not arrived yet")

    intervals = ("15m", "30m", "1h", "4h", "1d", "1w")

    async def fetch_symbol(symbol: str):
        rows_by_tf: dict[str, list[dict[str, float]]] = {}
        jobs = [api.klines(symbol, tf, 200) for tf in intervals]
        responses = await asyncio.gather(*jobs, return_exceptions=True)
        for tf, rows in zip(intervals, responses):
            if isinstance(rows, Exception):
                continue
            try:
                closed = base._closed_rows(rows, tf)
                if len(closed) >= 120:
                    rows_by_tf[tf] = closed
            except Exception:
                continue
        return symbol, rows_by_tf

    fetched = await asyncio.gather(*(fetch_symbol(symbol) for symbol in symbols))
    results: list[dict[str, Any]] = []
    for symbol, rows_by_tf in fetched:
        for tf, (group, model, context_tfs) in MODEL_SCHEDULE.items():
            candles = rows_by_tf.get(tf)
            contexts = {key: rows_by_tf[key] for key in context_tfs if key in rows_by_tf}
            if not candles or len(contexts) != len(context_tfs):
                continue
            try:
                result = analyze_strategy_v15(candles, model, contexts)
            except Exception:
                continue
            if not result:
                continue
            indicators = dict(result["indicators"])
            indicators["strategy_reasons"] = result["reasons"]
            indicators["signal_candle_time"] = int(result.get("candle_open_time", 0) or 0)
            results.append({
                "symbol": symbol,
                "side": result["side"],
                "strategy": group,
                "interval": tf,
                "score": result["score"],
                "grade": result["grade"],
                "entry": result["entry"],
                "stop": result["stop"],
                "tps": result["tps"],
                "created_at": result["created_at"],
                "candle_open_time": result["candle_open_time"],
                "indicators": indicators,
                "reasons": result["reasons"],
            })
    return results


from fastapi import Depends, HTTPException


async def analyze_v15_endpoint(
    symbol: str, interval: str = "1h", user=Depends(core.auth_user)
):
    """Manual analysis endpoint using the exact same MTF model as the scanner."""
    symbol = str(symbol or "").upper()
    if not symbol.endswith("USDT") or interval not in MODEL_SCHEDULE:
        raise HTTPException(400, "Use a USDT perpetual and one of 15m, 30m, 1h, 4h, 1d")
    if not core.market.status.ok:
        raise HTTPException(503, "Binance USD-M Futures market data is unavailable from this server")
    group, model, context_tfs = MODEL_SCHEDULE[interval]
    try:
        requested = (interval, *context_tfs)
        responses = await asyncio.gather(
            *(core.market.klines(symbol, tf, 200) for tf in requested),
            return_exceptions=True,
        )
        if any(isinstance(item, Exception) for item in responses):
            raise HTTPException(503, "Higher-timeframe market data is unavailable; analysis is blocked")
        candles = base._closed_rows(responses[0], interval)
        contexts = {tf: base._closed_rows(rows, tf) for tf, rows in zip(context_tfs, responses[1:])}
        if len(candles) < 120 or any(len(rows) < 120 for rows in contexts.values()):
            raise HTTPException(503, "Not enough closed candles for multi-timeframe confirmation")
        result = analyze_strategy_v15(candles, model, contexts)
        if not result:
            raise HTTPException(422, "No qualified setup after regime, quality and higher-timeframe checks")
        ind = result["indicators"]
        return {
            "symbol": symbol, "side": result["side"], "strategy": group, "interval": interval,
            "strategy_model": model, "strategy_label": MODEL_LABELS[model],
            "score": result["score"], "grade": result["grade"], "entry": result["entry"],
            "stop": result["stop"], "tps": result["tps"], "atr": ind["atr"],
            "rsi": ind["rsi"], "ema20": ind["ema20"], "ema50": ind["ema50"],
            "volume_ratio": ind["volume_ratio"], "adx": ind["adx"], "macd": ind["macd"],
            "bollinger": ind["bollinger"], "market_regime": ind["market_regime"],
            "higher_timeframe_bias": ind["higher_timeframe_bias"],
            "quality_gate": ind["quality_gate"], "eligible": True, "reasons": result["reasons"],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, f"Analysis failed: {str(exc)[:140]}") from exc


# Replace only signal generation and the manual analysis endpoint captured by
# the existing runtime. The paper executor and its safety wrappers are intact.
runtime.analyze_strategy = analyze_strategy_v15
runtime.scan_market = scan_market_v15
kept_routes = []
for route in core.app.router.routes:
    methods = getattr(route, "methods", set()) or set()
    if getattr(route, "path", None) == "/api/analyze" and "GET" in methods:
        continue
    kept_routes.append(route)
core.app.router.routes = kept_routes
core.app.add_api_route(
    "/api/analyze", analyze_v15_endpoint, methods=["GET"], include_in_schema=True
)
core.app.version = "1.5.0"
core.engine_state["strategy_engine"] = "MIRAGE v1.5 Hybrid Intelligence Engine"

# Correct the health payload version and expose the active strategy catalogue.
_previous_health = next(
    route.endpoint for route in core.app.router.routes
    if getattr(route, "path", None) == "/api/health"
    and "GET" in (getattr(route, "methods", set()) or set())
)


def health_v15():
    payload = _previous_health()
    payload["version"] = "1.5.0"
    payload["signal_intelligence"] = {
        "engine": "HYBRID",
        "models": list(MODEL_LABELS.values()),
        "schedule": {tf: {"group": group, "model": model, "higher_timeframes": list(contexts)}
                     for tf, (group, model, contexts) in MODEL_SCHEDULE.items()},
        "minimum_quality_score": 86,
        "score_is_win_probability": False,
        "closed_candles_only": True,
        "paper_only": True,
    }
    return payload


import app_v11 as v11  # noqa: E402
v11._replace_endpoint("/api/health", "GET", health_v15)
