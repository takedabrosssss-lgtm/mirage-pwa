"""MIRAGE v1.2 runtime integration: automatic paper entries + scanner hardening.

Loads the Trading Intelligence PRO signal model on USD-M futures feeds while
preserving the PWA's futures-only, PHANTOM-gated execution engine.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx
from fastapi import Depends, HTTPException

import app as core
import app_v11 as v11
from mirage_strategy_v12 import TIMEFRAMES, analyze_strategy, scan_market
from mirage_v11_fixes import entry_gate_failures, quote_is_fresh

LOG = logging.getLogger("mirage.runtime.v12")
core.DEFAULT_SETTINGS["auto_trade"] = True
core.app.version = "1.2.0"

# The earlier release repeatedly called this full-market REST endpoint after
# errors. A 24h ticker WebSocket is now the primary market-universe source.
_ORIGINAL_GET = core.market.get


def _retry_after_seconds(response) -> float | None:
    raw = response.headers.get("Retry-After")
    if not raw:
        return None
    try:
        return max(1.0, float(raw))
    except ValueError:
        try:
            dt = parsedate_to_datetime(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return max(1.0, (dt - datetime.now(timezone.utc)).total_seconds())
        except Exception:
            return None


async def guarded_market_get(path: str, params: dict | None = None):
    now = time.time()
    if path == "/fapi/v1/ticker/24hr":
        until = float(getattr(core.market, "_v12_ticker_backoff_until", 0.0))
        if now < until:
            # Return last known REST copy when one exists; do not hit Binance.
            cached = getattr(core.market, "_v12_ticker_rest_cache", None)
            if cached:
                return cached
            raise RuntimeError(f"Binance 24h REST ticker cooldown active for {int(until-now)}s")
    try:
        result = await _ORIGINAL_GET(path, params)
        if path == "/fapi/v1/ticker/24hr":
            core.market._v12_ticker_rest_cache = result
            core.market._v12_ticker_backoff_until = 0.0
            core.market._v12_ticker_backoff_hits = 0
        return result
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status in (418, 429):
            hits = int(getattr(core.market, "_v12_ticker_backoff_hits", 0)) + 1
            core.market._v12_ticker_backoff_hits = hits
            retry_after = _retry_after_seconds(exc.response)
            delay = retry_after if retry_after is not None else min(900.0, 30.0 * (2 ** min(hits - 1, 5)))
            core.market._v12_ticker_backoff_until = time.time() + delay
            LOG.warning("Binance HTTP %s: REST cooldown %.0fs (Retry-After=%s)", status, delay, retry_after)
        raise


core.market.get = guarded_market_get

# Mark WebSocket merged quotes explicitly. REST fallback quotes can still be
# used to manage existing paper positions but must never authorize a new entry.
_ORIGINAL_WS_HANDLER = v11._handle_market_payload


def tagged_ws_handler(payload, channel: str) -> None:
    _ORIGINAL_WS_HANDLER(payload, channel)
    event = str(payload.get("e", ""))
    symbol = str(payload.get("s", "")).upper()
    is_quote_event = (channel == "market" and event == "markPriceUpdate") or (channel == "public" and event == "bookTicker")
    if is_quote_event and symbol:
        q = core.market_cache.get(symbol)
        if q and quote_is_fresh(q, time.time(), max_age=5.0):
            q["source"] = "WEBSOCKET"


v11._handle_market_payload = tagged_ws_handler

_REST_QUOTE_NEXT: dict[str, float] = {}


async def refresh_market_quotes_v12() -> None:
    """Refresh quotes without polling /ticker/24hr; cap per-symbol REST fallback."""
    symbols: set[str] = set()
    with core.DBLocal() as db:
        for trade in db.scalars(core.select(core.Trade).where(core.Trade.status == "OPEN")).all():
            symbols.add(trade.symbol)

    top = sorted(core.ticker_cache.items(), key=lambda item: float(item[1].get("quote_volume", 0) or 0), reverse=True)
    symbols.update(symbol for symbol, _ in top[:16])
    symbols.update(list(core.market_cache.keys())[:8])

    now = time.time()
    async def refresh_one(symbol: str) -> None:
        cached = core.market_cache.get(symbol, {})
        book_age = now - float(cached.get("book_received_at", 0) or 0)
        mark_age = now - float(cached.get("mark_received_at", 0) or 0)
        if 0 <= book_age < 4 and 0 <= mark_age < 4:
            return
        if now < _REST_QUOTE_NEXT.get(symbol, 0):
            return
        _REST_QUOTE_NEXT[symbol] = now + 8.0
        try:
            data = await core.market.book_mark(symbol)
            fetched = time.time()
            data.update({"received_at": fetched, "book_received_at": fetched,
                         "mark_received_at": fetched, "source": "REST_FALLBACK"})
            core.market_cache[symbol] = data
            if core.market_event:
                core.market_event.set()
        except Exception as exc:
            if symbol in core.market_cache:
                core.market_cache[symbol]["stale"] = True
            LOG.debug("REST quote fallback failed for %s: %s", symbol, str(exc)[:120])

    await asyncio.gather(*(refresh_one(symbol) for symbol in list(symbols)[:24]))


core.refresh_market_quotes = refresh_market_quotes_v12


# Enforce feed provenance at both manual and automatic entry points. v1.1.1's
# PHANTOM guard remains nested underneath this additional check.
def get_quote_from_cache_v12(symbol: str):
    quote_data = core.market_cache.get(symbol)
    if not quote_is_fresh(quote_data, time.time(), max_age=5.0):
        raise HTTPException(503, f"Fresh Bid/Ask and Mark Price for {symbol} are unavailable; entry blocked")
    # This quote reader is also used by the manual close endpoint. Fresh REST
    # fallback is acceptable for exits; open_trade_v12 separately enforces
    # WebSocket provenance before any new position can be created.
    quote = core.Quote(float(quote_data["bid"]), float(quote_data["ask"]), float(quote_data["mark"]), int(quote_data.get("time", 0)))
    quote.validate()
    return quote


core.get_quote_from_cache = get_quote_from_cache_v12
_PREVIOUS_OPEN_TRADE = core.open_trade


def open_trade_v12(db, user, plan, quote_data, settings):
    symbol = str(plan.get("symbol", "")).upper()
    side = str(plan.get("side", "")).upper()
    cached = core.market_cache.get(symbol)
    if not quote_is_fresh(cached, time.time(), max_age=5.0) or cached.get("source") != "WEBSOCKET":
        raise ValueError("PHANTOM: fresh WebSocket Bid/Ask and Mark Price required; entry blocked")

    # Match the Telegram bot's one-symbol-per-account rule. Opposite-side
    # positions on the same contract are blocked instead of silently hedged.
    if any(position.symbol == symbol for position in core.active_trades(db, user.id)):
        raise ValueError(f"An open {symbol} position already exists in this account")

    # The original paper engine refuses to chase a signal after price has
    # moved more than half of its stop distance from the signal reference.
    # Scanner-originated plans carry `entry`; manual requests may not.
    reference_entry = plan.get("entry")
    if reference_entry is not None:
        quote = core.Quote(float(quote_data["bid"]), float(quote_data["ask"]),
                           float(quote_data["mark"]), int(quote_data.get("time", 0)))
        live_entry = core.entry_fill(side, quote, float(settings.get("slippage_bps", 0)))
        stop = float(plan["stop"])
        distance = abs(float(reference_entry) - stop)
        targets = [float(value) for value in plan.get("targets", [])]
        if distance <= 0 or abs(live_entry - float(reference_entry)) > distance * 0.5:
            raise ValueError("Signal expired: live entry moved more than 0.5R from the setup")
        if len(targets) != 3:
            raise ValueError("Signal must contain all three Take Profit levels")
        if side == "LONG" and not (stop < live_entry < targets[-1]):
            raise ValueError("Signal is no longer valid at the live LONG entry price")
        if side == "SHORT" and not (stop > live_entry > targets[-1]):
            raise ValueError("Signal is no longer valid at the live SHORT entry price")

    return _PREVIOUS_OPEN_TRADE(db, user, plan, quote_data, settings)


core.open_trade = open_trade_v12


async def run_scan_v12() -> None:
    """Original Telegram strategy model with futures-native paper execution."""
    if not core.market.status.ok:
        core.engine_state["scanner"] = "BLOCKED"
        core.engine_state["last_error"] = "Binance USD-M REST market-data check is unavailable"
        return
    try:
        candidates = await scan_market(
            core.market,
            int(__import__("os").getenv("SCAN_UNIVERSE_SIZE", "10")),
            ticker_cache=core.ticker_cache,
        )
        now = int(time.time())
        opened_total = 0
        saved_total = 0
        with core.DBLocal() as db:
            users = db.scalars(core.select(core.User)).all()
            for item in candidates:
                cooldown = int({"15m": 60, "1h": 240, "4h": 960, "1d": 5760}.get(item["interval"], 60) * 60)
                existing_signal = db.scalar(
                    core.select(core.Signal).where(
                        core.Signal.symbol == item["symbol"],
                        core.Signal.interval == item["interval"],
                        core.Signal.side == item["side"],
                        core.Signal.grade == item["grade"],
                        core.Signal.created_at > now - cooldown,
                    ).order_by(core.desc(core.Signal.created_at)).limit(1)
                )
                # Cooldown deduplicates the signal feed, not the execution
                # retry. If the signal was saved while a quote was stale, a
                # later scan may still enter it when a fresh live quote arrives.
                if existing_signal is None:
                    indicators = dict(item.get("indicators") or {})
                    indicators["strategy_reasons"] = item.get("reasons", [])
                    signal = core.Signal(
                        symbol=item["symbol"], side=item["side"], strategy=item["strategy"],
                        interval=item["interval"], score=item["score"], grade=item["grade"],
                        entry=item["entry"], stop=item["stop"], targets_json=json.dumps(item["tps"]),
                        indicators_json=json.dumps(indicators), created_at=item["created_at"], state="ACTIVE",
                    )
                    db.add(signal)
                    db.flush()
                    saved_total += 1

                # The user's previous Telegram workflow was autonomous. Each
                # MIRAGE login now gets its own independent automatic paper book.
                for user in users:
                    settings = core.get_settings(db, user.id)
                    if not settings.get("auto_trade", True) or item["strategy"] not in settings.get("strategies", []):
                        continue
                    duplicate = db.scalar(core.select(core.Trade.id).where(
                        core.Trade.user_id == user.id,
                        core.Trade.symbol == item["symbol"],
                        core.Trade.side == item["side"],
                        core.Trade.status == "OPEN",
                    ).limit(1))
                    recently_traded = db.scalar(core.select(core.Trade.id).where(
                        core.Trade.user_id == user.id,
                        core.Trade.symbol == item["symbol"],
                        core.Trade.side == item["side"],
                        core.Trade.strategy == item["strategy"],
                        core.Trade.opened_at > now - cooldown,
                    ).limit(1))
                    if duplicate or recently_traded:
                        continue
                    q = core.market_cache.get(item["symbol"])
                    if not quote_is_fresh(q, time.time(), max_age=5.0) or q.get("source") != "WEBSOCKET":
                        core.add_audit(db, "PHANTOM", "WARNING", f"Auto entry blocked {item['symbol']}: live WebSocket quote is not fresh", user.id)
                        continue
                    try:
                        core.open_trade(db, user, {
                            "symbol": item["symbol"], "side": item["side"], "strategy": item["strategy"],
                            "interval": item["interval"], "score": item["score"], "entry": item["entry"],
                            "stop": item["stop"], "targets": item["tps"],
                        }, q, settings)
                        opened_total += 1
                    except Exception as exc:
                        core.add_audit(db, "PHANTOM", "WARNING", f"Auto entry blocked {item['symbol']}: {str(exc)[:130]}", user.id)
                db.commit()

        core.last_scan = now
        core.engine_state["last_scan"] = now
        core.engine_state["scanner"] = "ACTIVE"
        core.engine_state["last_error"] = ""
        core.engine_state["strategy_engine"] = "Trading Intelligence PRO rules · USD-M Futures"
        core.engine_state["scan_candidates"] = len(candidates)
        core.engine_state["signals_saved"] = saved_total
        core.engine_state["auto_positions_opened"] = opened_total
        LOG.info("Scan complete: candidates=%s saved=%s auto_paper_positions=%s", len(candidates), saved_total, opened_total)
    except Exception as exc:
        message = str(exc)[:220]
        if "WAITING_FOR_TICKER_STREAM" in message:
            core.engine_state["scanner"] = "WAITING_FOR_TICKERS"
            core.engine_state["last_error"] = "Waiting for Binance 24h WebSocket ticker stream"
        else:
            core.engine_state["scanner"] = "DEGRADED"
            core.engine_state["last_error"] = message
            with core.DBLocal() as db:
                core.add_audit(db, "MARKET", "ERROR", f"Scanner failed: {message}")
                db.commit()
        LOG.exception("MIRAGE v1.2 scan cycle failed")


core.run_scan = run_scan_v12


async def analyze_v12(symbol: str, interval: str = "1h", user=Depends(core.auth_user)):
    symbol = symbol.upper()
    if not symbol.endswith("USDT") or interval not in TIMEFRAMES:
        raise HTTPException(400, "Use a USDT perpetual and one of 15m, 1h, 4h, 1d")
    if not core.market.status.ok:
        raise HTTPException(503, "Binance USD-M Futures market data is unavailable from this server")
    try:
        rows = await core.market.klines(symbol, interval, 200)
        from mirage_strategy_v12 import _closed_rows
        candles = _closed_rows(rows, interval)
        strategy, model = TIMEFRAMES[interval]
        result = analyze_strategy(candles, model)
        if not result:
            raise HTTPException(422, "No qualified S/A setup on this timeframe. No position will be opened.")
        return {
            "symbol": symbol, "side": result["side"], "strategy": strategy, "interval": interval,
            "score": result["score"], "grade": result["grade"], "entry": result["entry"],
            "stop": result["stop"], "tps": result["tps"], "atr": result["indicators"]["atr"],
            "rsi": result["indicators"]["rsi"], "ema20": result["indicators"]["ema20"],
            "ema50": result["indicators"]["ema50"], "volume_ratio": result["indicators"]["volume_ratio"],
            "adx": result["indicators"]["adx"], "macd": result["indicators"]["macd"],
            "bollinger": result["indicators"]["bollinger"], "eligible": True,
            "reasons": result["reasons"],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, f"Analysis failed: {str(exc)[:140]}") from exc


# Replace the simpler placeholder analyzer with the same model used by the scanner.
kept = []
for route in core.app.router.routes:
    methods = getattr(route, "methods", set()) or set()
    if getattr(route, "path", None) == "/api/analyze" and "GET" in methods:
        continue
    kept.append(route)
core.app.router.routes = kept
core.app.add_api_route("/api/analyze", analyze_v12, methods=["GET"], include_in_schema=True)


# One-time migration: accounts were bootstrapped with auto_trade=false in v1.0.
# Turn on autonomous Paper Trading once for all four private accounts, then
# respect any future user changes to this switch.
def apply_auto_trade_default_migration() -> None:
    with core.engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS mirage_runtime_migrations (migration_key VARCHAR(120) PRIMARY KEY, applied_at BIGINT NOT NULL)"
        )
        exists = conn.exec_driver_sql(
            "SELECT migration_key FROM mirage_runtime_migrations WHERE migration_key = 'v12_auto_paper_default'"
        ).first()
    if exists:
        return
    with core.DBLocal() as db:
        rows = db.scalars(core.select(core.UserSettings)).all()
        for row in rows:
            try:
                payload = json.loads(row.payload or "{}")
            except Exception:
                payload = {}
            payload["auto_trade"] = True
            payload.setdefault("strategies", ["SCALPING", "INTRADAY", "SWING", "POSITION"])
            row.payload = json.dumps(payload)
            core.add_audit(db, "AUTO_PAPER", "INFO", "Autonomous Paper Trading enabled by MIRAGE v1.2 upgrade", row.user_id)
        db.commit()
    with core.engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO mirage_runtime_migrations (migration_key, applied_at) VALUES ('v12_auto_paper_default', %s)" % int(time.time())
        )
    LOG.warning("MIRAGE v1.2 one-time automatic Paper Trading migration applied")


apply_auto_trade_default_migration()
core.engine_state["strategy_engine"] = "Trading Intelligence PRO rules · USD-M Futures"


def health_v12():
    """Expose the actual v1.2 strategy/scanner runtime and fail-closed entry gate."""
    result = v11.health_v11()
    now = time.time()
    failures = entry_gate_failures(
        core.ws_state,
        bool(core.market.status.ok),
        float(core.market.status.checked_at or 0),
        now,
    )
    result["version"] = "1.2.0"
    result["engine"] = {**core.engine_state, "websocket": core.ws_state}
    result["strategy_engine"] = "Trading Intelligence PRO rules · Binance USD-M Futures"
    result["entry_feed_gate"] = {
        "allowed": not failures,
        "block_reasons": failures,
        "policy": "Both live WebSocket feeds and a fresh REST health check are required for new entries",
    }
    result["automatic_paper_trading"] = {
        "default_enabled": True,
        "real_orders_enabled": False,
    }
    return result


_kept_health_routes = []
for _route in core.app.router.routes:
    _methods = getattr(_route, "methods", set()) or set()
    if getattr(_route, "path", None) == "/api/health" and "GET" in _methods:
        continue
    _kept_health_routes.append(_route)
core.app.router.routes = _kept_health_routes
core.app.add_api_route("/api/health", health_v12, methods=["GET"], include_in_schema=True)
