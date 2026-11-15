"""MIRAGE v1.1 runtime overlay.

Keep the established app.py, market.py, trading.py and frontend intact while
replacing the unsafe market-data wiring, Funding timestamp handling, stale
quote gates, login brute-force protection, dashboard safety, and PHANTOM health.
Run this module (not app:app) through the updated Procfile/Dockerfile.
"""
from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from collections import defaultdict, deque
from typing import Any

import websockets
from fastapi import Depends, HTTPException, Request
from starlette.responses import JSONResponse

import app as core
from mirage_v11_fixes import (
    epoch_ms,
    funding_start_ms,
    is_usdm_payload,
    merge_quote_parts,
    quote_is_fresh,
    recent_failures_exceeded,
    relevant_quote_message,
    unpack_stream_message,
)

app = core.app
PARTIAL_QUOTES: dict[str, dict[str, Any]] = {}
LOGIN_FAILURES: dict[str, deque[float]] = defaultdict(deque)
LOGIN_LIMIT = 10
LOGIN_WINDOW_SECONDS = 15 * 60
OPEN_TRADE_LOCK = threading.RLock()
FUNDING_CHECK_CACHE: dict[int, float] = {}

# v1.1 uses two category-specific Binance connections. Do not use the old
# BINANCE_FUTURES_WS_URL combined endpoint from v1.0.
MARKET_WS_URL = os.getenv(
    "BINANCE_FUTURES_MARKET_WS_URL",
    "wss://fstream.binance.com/market/stream?streams=!markPrice@arr@1s/!ticker@arr",
)
PUBLIC_WS_URL = os.getenv(
    "BINANCE_FUTURES_PUBLIC_WS_URL",
    "wss://fstream.binance.com/public/stream?streams=!bookTicker",
)


def _refresh_ws_aggregate() -> None:
    now = time.time()
    public_ok = bool(core.ws_state.get("public_connected")) and now - float(core.ws_state.get("public_last_message", 0)) <= 12
    market_ok = bool(core.ws_state.get("market_connected")) and now - float(core.ws_state.get("market_last_message", 0)) <= 12
    core.ws_state["connected"] = public_ok and market_ok
    core.ws_state["last_message"] = int(max(
        float(core.ws_state.get("public_last_message", 0)),
        float(core.ws_state.get("market_last_message", 0)),
    ))
    if core.ws_state["connected"]:
        core.ws_state["last_error"] = ""
    elif not public_ok and not market_ok:
        core.ws_state["last_error"] = "Public book and market mark streams are not both healthy"
    elif not public_ok:
        core.ws_state["last_error"] = "Public book stream is unavailable or stale"
    else:
        core.ws_state["last_error"] = "Market mark stream is unavailable or stale"


def _handle_market_payload(payload: dict[str, Any], channel: str) -> None:
    event = str(payload.get("e", ""))
    symbol = str(payload.get("s", "")).upper()
    now = time.time()

    if event == "24hrTicker" and symbol.endswith("USDT") and is_usdm_payload(payload):
        core.ticker_cache[symbol] = {
            "change_pct": float(payload.get("P", 0) or 0),
            "quote_volume": float(payload.get("q", 0) or 0),
            "last_price": float(payload.get("c", 0) or 0),
        }
        return

    if not symbol or not is_usdm_payload(payload):
        return
    existing = core.market_cache.get(symbol)
    merged = merge_quote_parts(PARTIAL_QUOTES, symbol, channel, payload, now, existing=existing)
    if merged is not None:
        # Preserve informational fields already obtained from REST/mark stream.
        if existing:
            for key in ("last_funding_rate", "next_funding_time", "time", "stale"):
                if key in existing:
                    merged.setdefault(key, existing[key])
        if event == "markPriceUpdate":
            merged["last_funding_rate"] = float(payload.get("r", 0) or 0)
            merged["next_funding_time"] = int(payload.get("T", 0) or 0)
            merged["time"] = int(payload.get("E", 0) or 0)
        elif event == "bookTicker":
            merged["time"] = int(payload.get("T", payload.get("E", 0)) or 0)
        merged.pop("stale", None)
        core.market_cache[symbol] = merged
        if core.market_event:
            core.market_event.set()


async def _feed_loop(channel: str, url: str) -> None:
    connected_key = f"{channel}_connected"
    last_key = f"{channel}_last_message"
    error_key = f"{channel}_last_error"
    while True:
        try:
            async with websockets.connect(
                url,
                ping_interval=180,
                ping_timeout=600,
                close_timeout=8,
                max_size=8 * 1024 * 1024,
                open_timeout=12,
            ) as ws:
                core.ws_state[connected_key] = True
                core.ws_state[error_key] = ""
                _refresh_ws_aggregate()
                async for raw in ws:
                    try:
                        payloads = unpack_stream_message(raw)
                        now = time.time()
                        health_message_seen = False
                        for payload in payloads:
                            if channel == "market":
                                if payload.get("e") in {"markPriceUpdate", "24hrTicker"}:
                                    _handle_market_payload(payload, channel)
                            elif payload.get("e") == "bookTicker":
                                _handle_market_payload(payload, channel)
                            if relevant_quote_message(channel, payload):
                                health_message_seen = True
                        # 24h ticker traffic must not mask a stalled Mark Price feed.
                        if health_message_seen:
                            core.ws_state[last_key] = now
                        _refresh_ws_aggregate()
                    except Exception as exc:
                        core.ws_state[error_key] = f"Invalid {channel} message: {str(exc)[:140]}"
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            core.ws_state[error_key] = str(exc)[:180]
            await asyncio.sleep(5)
        finally:
            core.ws_state[connected_key] = False
            _refresh_ws_aggregate()


async def websocket_market_loop_v11() -> None:
    """Run the Public and Market feeds independently with automatic reconnects."""
    await asyncio.gather(
        _feed_loop("market", MARKET_WS_URL),
        _feed_loop("public", PUBLIC_WS_URL),
    )


# Patch the module global used by app.py's already-registered lifespan function.
core.websocket_market_loop = websocket_market_loop_v11


# Strictly require independently fresh book and mark timestamps.
def get_quote_from_cache_v11(symbol: str):
    quote_data = core.market_cache.get(symbol)
    if not quote_is_fresh(quote_data, time.time(), max_age=5.0):
        raise HTTPException(
            503,
            f"Fresh Bid/Ask and Mark Price for {symbol} are not both available; entry blocked",
        )
    quote = core.Quote(
        float(quote_data["bid"]),
        float(quote_data["ask"]),
        float(quote_data["mark"]),
        int(quote_data.get("time", 0)),
    )
    try:
        quote.validate()
    except ValueError as exc:
        raise HTTPException(503, str(exc)) from exc
    return quote


core.get_quote_from_cache = get_quote_from_cache_v11


# Serialize open requests and reject another same-side position for the same
# user/symbol, regardless of the strategy label.
_original_open_trade = core.open_trade


def open_trade_v11(db, user, plan, quote_data, settings):
    with OPEN_TRADE_LOCK:
        symbol = str(plan.get("symbol", "")).upper()
        side = str(plan.get("side", "")).upper()
        cached = core.market_cache.get(symbol)
        if not quote_is_fresh(cached, time.time(), max_age=5.0):
            raise ValueError("Bid/Ask or Mark Price is stale or incomplete; entry blocked")
        duplicate = db.scalar(
            core.select(core.Trade.id).where(
                core.Trade.user_id == user.id,
                core.Trade.symbol == symbol,
                core.Trade.side == side,
                core.Trade.status == "OPEN",
            ).limit(1)
        )
        if duplicate:
            raise ValueError(f"An open {side} position for {symbol} already exists in this account")
        trade = _original_open_trade(db, user, plan, quote_data, settings)
        # v1.0 set this checkpoint in seconds. v1.1 persists it in milliseconds.
        trade.last_funding_time = epoch_ms(trade.opened_at)
        db.commit()
        db.refresh(trade)
        return trade


core.open_trade = open_trade_v11


async def apply_funding_v11(db, trade, user, now_ms: int) -> None:
    """Fetch all missing funding records using millisecond timestamps.

    Funding is booked only from Binance's historical funding records. If the
    API is unavailable or a record is malformed, the checkpoint is not moved.
    """
    if trade.status != "OPEN":
        return
    now = time.time()
    if now - FUNDING_CHECK_CACHE.get(trade.id, 0) < 60:
        return
    FUNDING_CHECK_CACHE[trade.id] = now

    # Normalize checkpoints already stored by v1.0 (seconds) before querying.
    last_ms = epoch_ms(trade.last_funding_time)
    if trade.last_funding_time and last_ms != trade.last_funding_time:
        trade.last_funding_time = last_ms
    start_ms = funding_start_ms(trade.last_funding_time, trade.opened_at)
    if start_ms > now_ms:
        return

    rows: list[dict[str, Any]] = []
    cursor = start_ms
    try:
        # Binance returns records in ascending order; paginate if the outage
        # exceeded the endpoint's 1,000-record page size.
        for _ in range(20):
            page = await core.market.get(
                "/fapi/v1/fundingRate",
                {"symbol": trade.symbol, "startTime": cursor, "endTime": now_ms, "limit": 1000},
            )
            if not isinstance(page, list):
                raise ValueError("Funding history response is not a list")
            if not page:
                break
            rows.extend(page)
            if len(page) < 1000:
                break
            last_page_ms = max(int(item["fundingTime"]) for item in page)
            next_cursor = last_page_ms + 1
            if next_cursor <= cursor:
                raise ValueError("Funding history pagination did not advance")
            cursor = next_cursor
            if cursor > now_ms:
                break

        prepared: list[tuple[int, float, float]] = []
        for row in rows:
            funding_time = int(row["fundingTime"])
            rate = float(row["fundingRate"])
            mark = float(row["markPrice"])
            if funding_time <= last_ms or funding_time > now_ms:
                continue
            if not (math_is_finite(rate) and math_is_finite(mark) and mark > 0):
                raise ValueError("Funding record contains an invalid rate or mark price")
            prepared.append((funding_time, rate, mark))
        prepared.sort(key=lambda item: item[0])

        for funding_time, rate, mark in prepared:
            # No fills occur while the server is down; the persisted remaining
            # quantity is therefore the best available paper-position amount.
            debit = core.funding_cost(trade.side, trade.remaining_qty * mark, rate)
            pnl = -debit
            user.balance += pnl
            trade.funding_pnl += pnl
            trade.last_funding_time = funding_time
            core.add_audit(
                db,
                "FUNDING",
                "INFO",
                f"{trade.symbol} funding {rate * 100:.5f}% => {pnl:+.4f} USDT",
                user.id,
            )
    except Exception as exc:
        core.add_audit(
            db,
            "FUNDING",
            "WARNING",
            f"Funding history unavailable for {trade.symbol}; checkpoint retained: {str(exc)[:110]}",
            user.id,
        )
        return


# app.py's manager calls this module global dynamically.
core.apply_funding = apply_funding_v11
core.funding_check_cache = FUNDING_CHECK_CACHE


def math_is_finite(value: float) -> bool:
    try:
        return value == value and abs(value) != float("inf")
    except Exception:
        return False


# Account-specific dashboard with defensive quote reads (no KeyError when
# one stream has arrived but the other has not yet produced a complete quote).
def dashboard_v11(user=Depends(core.auth_user), db=Depends(core.db_dependency)):
    positions = core.active_trades(db, user.id)
    unrealized = 0.0
    notional = 0.0
    open_risk = 0.0
    settings = core.get_settings(db, user.id)
    for trade in positions:
        quote = core.market_cache.get(trade.symbol)
        if quote_is_fresh(quote, time.time(), max_age=5.0):
            close_price = quote["bid"] if trade.side == "LONG" else quote["ask"]
            unrealized += core.gross_pnl(trade.side, trade.entry_price, close_price, trade.remaining_qty)
            unrealized -= core.fee(trade.remaining_qty * close_price, float(settings["taker_fee"]))
            notional += trade.remaining_qty * quote["mark"]
        open_risk += trade.risk_amount * (trade.remaining_qty / trade.initial_qty)

    closed = db.scalars(
        core.select(core.Trade).where(
            core.Trade.user_id == user.id,
            core.Trade.status == "CLOSED",
        )
    ).all()
    net_closed = [
        trade.gross_realized - trade.entry_fee - trade.exit_fee_total + trade.funding_pnl
        for trade in closed
    ]
    return {
        "balance": user.balance,
        "equity": user.balance + unrealized,
        "unrealized_pnl": unrealized,
        "open_positions": len(positions),
        "open_notional": notional,
        "open_risk": open_risk,
        "total_closed": len(closed),
        "realized_net": sum(net_closed),
        "market": core.market.status.__dict__,
        "engine": {**core.engine_state, "websocket": core.ws_state},
        "recent_signals": [
            core.signal_public(row)
            for row in db.scalars(core.select(core.Signal).order_by(core.desc(core.Signal.created_at)).limit(5)).all()
        ],
    }


def health_v11():
    _refresh_ws_aggregate()
    return {
        "ok": True,
        "app": "MIRAGE",
        "version": "1.1.0",
        "server_region": core.SERVER_REGION,
        "market": core.market.status.__dict__,
        "engine": {**core.engine_state, "websocket": core.ws_state},
        "server_time": int(time.time()),
        "paper_only": True,
        "real_orders_enabled": False,
        "websocket_feeds": {
            "market": {"connected": core.ws_state.get("market_connected", False),
                       "last_message": core.ws_state.get("market_last_message", 0),
                       "last_error": core.ws_state.get("market_last_error", "")},
            "public": {"connected": core.ws_state.get("public_connected", False),
                       "last_message": core.ws_state.get("public_last_message", 0),
                       "last_error": core.ws_state.get("public_last_error", "")},
        },
    }


def phantom_v11(user=Depends(core.auth_user), db=Depends(core.db_dependency)):
    _refresh_ws_aggregate()
    now = time.time()
    events = db.scalars(
        core.select(core.AuditEvent)
        .where((core.AuditEvent.user_id == user.id) | (core.AuditEvent.user_id == None))
        .order_by(core.desc(core.AuditEvent.created_at))
        .limit(40)
    ).all()
    positions = core.active_trades(db, user.id)
    stale_symbols = sorted({t.symbol for t in positions if not quote_is_fresh(core.market_cache.get(t.symbol), now, 5.0)})
    public_ok = bool(core.ws_state.get("public_connected")) and now - float(core.ws_state.get("public_last_message", 0)) <= 12
    market_ok = bool(core.ws_state.get("market_connected")) and now - float(core.ws_state.get("market_last_message", 0)) <= 12
    state = "ACTIVE" if core.market.status.ok and public_ok and market_ok and not stale_symbols else "PROTECTIVE"
    return {
        "state": state,
        "checks": [
            {"name": "REST market data", "ok": bool(core.market.status.ok),
             "detail": core.market.status.message},
            {"name": "Market Mark Price stream", "ok": market_ok,
             "detail": core.ws_state.get("market_last_error") or f"Last message {core.ws_state.get('market_last_message', 0)}"},
            {"name": "Public Bid/Ask stream", "ok": public_ok,
             "detail": core.ws_state.get("public_last_error") or f"Last message {core.ws_state.get('public_last_message', 0)}"},
            {"name": "Open-position quotes", "ok": not stale_symbols,
             "detail": "All open-position quotes fresh" if not stale_symbols else "Stale/incomplete: " + ", ".join(stale_symbols)},
            {"name": "Paper-only execution", "ok": True,
             "detail": "No exchange order endpoints are implemented"},
            {"name": "Per-account risk gate", "ok": True,
             "detail": "Per-user balance, margin and risk checks remain enabled"},
            {"name": "Duplicate position guard", "ok": True,
             "detail": "Duplicate same-side symbol positions are rejected"},
        ],
        "events": [
            {"category": e.category, "severity": e.severity, "message": e.message, "created_at": e.created_at}
            for e in events
        ],
    }


# Replace the old endpoints rather than leaving duplicate routes active.
def _replace_endpoint(path: str, method: str, endpoint) -> None:
    kept = []
    for route in app.router.routes:
        methods = getattr(route, "methods", set()) or set()
        if getattr(route, "path", None) == path and method in methods:
            continue
        kept.append(route)
    app.router.routes = kept
    app.add_api_route(path, endpoint, methods=[method], include_in_schema=True)


_replace_endpoint("/api/dashboard", "GET", dashboard_v11)
_replace_endpoint("/api/health", "GET", health_v11)
_replace_endpoint("/api/phantom", "GET", phantom_v11)


class LoginRateLimitMiddleware:
    """Block repeated failed login attempts without penalizing successful logins."""
    def __init__(self, asgi_app):
        self.app = asgi_app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or scope.get("path") != "/api/auth/login" or scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return
        client = scope.get("client") or ("unknown", 0)
        key = str(client[0])
        now = time.monotonic()
        queue = LOGIN_FAILURES[key]
        while queue and now - queue[0] >= LOGIN_WINDOW_SECONDS:
            queue.popleft()
        if recent_failures_exceeded(list(queue), now, LOGIN_WINDOW_SECONDS, LOGIN_LIMIT):
            body = json.dumps({"detail": "Too many failed login attempts. Try again later."}).encode()
            await send({"type": "http.response.start", "status": 429,
                        "headers": [(b"content-type", b"application/json"),
                                    (b"content-length", str(len(body)).encode()),
                                    (b"retry-after", str(LOGIN_WINDOW_SECONDS).encode())]})
            await send({"type": "http.response.body", "body": body})
            return

        async def wrapped_send(message):
            if message.get("type") == "http.response.start" and message.get("status") == 401:
                queue.append(time.monotonic())
            await send(message)

        await self.app(scope, receive, wrapped_send)


app.add_middleware(LoginRateLimitMiddleware)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app_v11:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")),
                workers=1, reload=core.APP_ENV == "development")
