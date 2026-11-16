"""MIRAGE v1.3 safety overlay.

Fail-closed public market-data handling, truthful scanner health, serialized and
per-position paper execution, risk-first position management, and execution
accounting safeguards. No private exchange credentials or order endpoints.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
from fastapi import Depends, HTTPException
from sqlalchemy import select

import app as core
import app_v11 as v11
import mirage_runtime_v12 as runtime
import mirage_strategy_v12 as strategy
from mirage_v11_fixes import quote_is_fresh
from mirage_safety_helpers_v13 import (
    choose_mark_trigger,
    market_lot_values,
    parse_retry_after,
    reserve_fee_adjusted_margin,
    scan_coverage_complete,
)

LOG = logging.getLogger("mirage.safety.v13")
core.app.version = "1.3.0"

# Binance 418/429 is an IP-level cooldown. Apply it to every REST endpoint.
_REST_SEMAPHORE = asyncio.Semaphore(2)
_GLOBAL_BACKOFF_UNTIL = 0.0
_GLOBAL_BACKOFF_HITS = 0
_GLOBAL_BACKOFF_REASON = ""
_ORIGINAL_MARKET_GET = core.market.get


async def _market_get_v13(path: str, params: dict | None = None):
    global _GLOBAL_BACKOFF_UNTIL, _GLOBAL_BACKOFF_HITS, _GLOBAL_BACKOFF_REASON
    now = time.time()
    if now < _GLOBAL_BACKOFF_UNTIL:
        remaining = int(_GLOBAL_BACKOFF_UNTIL - now)
        raise RuntimeError(
            f"Binance global REST cooldown active for {remaining}s; endpoint {path} was not requested"
        )
    async with _REST_SEMAPHORE:
        try:
            result = await _ORIGINAL_MARKET_GET(path, params)
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status in (418, 429):
                _GLOBAL_BACKOFF_HITS += 1
                retry_after = parse_retry_after(exc.response.headers.get("Retry-After"))
                delay = retry_after if retry_after is not None else min(
                    86_400.0, 60.0 * (2 ** min(_GLOBAL_BACKOFF_HITS - 1, 10))
                )
                _GLOBAL_BACKOFF_UNTIL = max(
                    _GLOBAL_BACKOFF_UNTIL, time.time() + delay + 5.0
                )
                _GLOBAL_BACKOFF_REASON = (
                    f"Binance HTTP {status}; Retry-After={retry_after}"
                )
                core.market.status.ok = False
                core.market.status.checked_at = time.time()
                core.market.status.message = (
                    f"{_GLOBAL_BACKOFF_REASON}; all REST requests paused"
                )[:220]
                core.engine_state["scanner"] = "BLOCKED"
                core.engine_state["last_error"] = core.market.status.message
                LOG.error(
                    "Binance HTTP %s: global REST cooldown %.0fs; all endpoints paused",
                    status, delay + 5.0,
                )
            raise
        return result


core.market.get = _market_get_v13


# The health probe checks all data classes required by the scanner/execution.
async def _market_check_v13():
    started = time.perf_counter()
    try:
        await core.market.get("/fapi/v1/time")
        await core.market.get("/fapi/v1/exchangeInfo")
        await core.market.get(
            "/fapi/v1/klines",
            {"symbol": "BTCUSDT", "interval": "1m", "limit": 2},
        )
        await core.market.get(
            "/fapi/v1/premiumIndex", {"symbol": "BTCUSDT"}
        )
        await core.market.get(
            "/fapi/v1/ticker/bookTicker", {"symbol": "BTCUSDT"}
        )
        core.market.status.ok = True
        core.market.status.message = (
            "Binance USD-M REST, Klines, Mark Price and Bid/Ask endpoints reachable"
        )
        core.market.status.latency_ms = int(
            (time.perf_counter() - started) * 1000
        )
    except Exception as exc:
        core.market.status.ok = False
        core.market.status.message = str(exc)[:220] or exc.__class__.__name__
        core.market.status.latency_ms = None
    core.market.status.checked_at = time.time()
    return core.market.status


core.market.check = _market_check_v13


# Exchange filters now prefer MARKET_LOT_SIZE for simulated market fills.
async def _load_exchange_filters_v13(api) -> set[str]:
    async with strategy._EXCHANGE_LOCK:
        now = time.time()
        cached = strategy._EXCHANGE_CACHE
        if cached["allowed"] and now - cached["loaded_at"] < 21_600:
            return set(cached["allowed"])

        info = await api.get("/fapi/v1/exchangeInfo")
        allowed: set[str] = set()
        filters_map: dict[str, dict[str, float]] = {}
        for item in info.get("symbols", []):
            symbol = str(item.get("symbol", "")).upper()
            if not (
                item.get("status") == "TRADING"
                and item.get("contractType") == "PERPETUAL"
                and item.get("quoteAsset") == "USDT"
                and symbol.endswith("USDT")
            ):
                continue
            raw_filters = {
                row.get("filterType"): row
                for row in item.get("filters", [])
            }
            step, min_qty = market_lot_values(raw_filters)
            price = raw_filters.get("PRICE_FILTER", {})
            notional = raw_filters.get("MIN_NOTIONAL", raw_filters.get("NOTIONAL", {}))
            filters_map[symbol] = {
                "step_size": step,
                "min_qty": min_qty,
                "min_notional": float(
                    notional.get("notional", notional.get("minNotional", 5)) or 5
                ),
                "tick_size": float(price.get("tickSize", 0.01) or 0.01),
            }
            allowed.add(symbol)

        if not allowed:
            raise RuntimeError(
                "Binance exchangeInfo returned no active USDT perpetual contracts"
            )
        api.symbol_filters.update(filters_map)
        cached["allowed"] = allowed
        cached["loaded_at"] = now
        return set(allowed)


strategy._load_exchange_filters = _load_exchange_filters_v13


# v1.2 swallowed all individual Kline errors. Discard a scan if any requested
# symbol/timeframe failed or returned an unusably short history.
_SCAN_COUNTS = {"attempted": 0, "succeeded": 0, "failed": 0}
_ORIGINAL_SCAN_MARKET = runtime.scan_market
_ORIGINAL_KLINES = core.market.klines


async def _quality_scan_market(*args, **kwargs):
    _SCAN_COUNTS.update(attempted=0, succeeded=0, failed=0)

    async def tracked_klines(symbol: str, interval: str, limit: int = 120):
        _SCAN_COUNTS["attempted"] += 1
        try:
            rows = await _ORIGINAL_KLINES(symbol, interval, limit)
        except Exception:
            _SCAN_COUNTS["failed"] += 1
            raise
        if not isinstance(rows, list) or len(rows) < 100:
            _SCAN_COUNTS["failed"] += 1
            raise RuntimeError(
                f"Insufficient Kline history for {symbol} {interval}"
            )
        _SCAN_COUNTS["succeeded"] += 1
        return rows

    core.market.klines = tracked_klines
    try:
        candidates = await _ORIGINAL_SCAN_MARKET(*args, **kwargs)
    finally:
        core.market.klines = _ORIGINAL_KLINES

    if not scan_coverage_complete(
        _SCAN_COUNTS["attempted"],
        _SCAN_COUNTS["succeeded"],
        _SCAN_COUNTS["failed"],
    ):
        raise RuntimeError(
            "Scan discarded: incomplete Kline coverage "
            f"({_SCAN_COUNTS['succeeded']}/{_SCAN_COUNTS['attempted']} usable; "
            f"{_SCAN_COUNTS['failed']} failed). No new positions opened."
        )
    return candidates


runtime.scan_market = _quality_scan_market


# Reserve enough free balance for both isolated margin and entry commission.
_ORIGINAL_SIZE_CALCULATOR = core.calculate_position_size


def _calculate_position_size_v13(**kwargs):
    adjusted = reserve_fee_adjusted_margin(
        float(kwargs["free_balance"]),
        int(kwargs["leverage"]),
        float(kwargs["fee_rate"]),
    )
    return _ORIGINAL_SIZE_CALCULATOR(
        **{**kwargs, "free_balance": adjusted}
    )


core.calculate_position_size = _calculate_position_size_v13


# Observe transient Mark Price extremes between manager iterations.
_MARK_EXTREMES: dict[str, dict[str, float]] = {}
_ORIGINAL_WS_HANDLER = v11._handle_market_payload


def math_is_finite(value: float) -> bool:
    return value == value and abs(value) != float("inf")


def _track_mark_extremes(payload: dict[str, Any], channel: str) -> None:
    if channel == "market" and payload.get("e") == "markPriceUpdate":
        symbol = str(payload.get("s", "")).upper()
        try:
            mark = float(payload.get("p"))
            if symbol and math_is_finite(mark) and mark > 0:
                old = _MARK_EXTREMES.get(symbol)
                if old is None:
                    _MARK_EXTREMES[symbol] = {
                        "low": mark, "high": mark, "last": mark,
                        "updated_at": time.time(),
                    }
                else:
                    old["low"] = min(old["low"], mark)
                    old["high"] = max(old["high"], mark)
                    old["last"] = mark
                    old["updated_at"] = time.time()
                if len(_MARK_EXTREMES) > 512:
                    oldest = min(
                        _MARK_EXTREMES,
                        key=lambda item: _MARK_EXTREMES[item]["updated_at"],
                    )
                    _MARK_EXTREMES.pop(oldest, None)
        except (TypeError, ValueError):
            pass
    _ORIGINAL_WS_HANDLER(payload, channel)


v11._handle_market_payload = _track_mark_extremes


def _quote_at_mark(quote: dict, trigger_mark: float) -> dict:
    """Preserve current spread around the Mark Price level that was touched."""
    bid = float(quote["bid"])
    ask = float(quote["ask"])
    midpoint = (bid + ask) / 2.0
    half_spread = max(0.0, (ask - bid) / 2.0)
    ratio = half_spread / midpoint if midpoint > 0 else 0.0
    out = dict(quote)
    out["mark"] = trigger_mark
    out["bid"] = trigger_mark * (1.0 - ratio)
    out["ask"] = trigger_mark * (1.0 + ratio)
    return out


# Serialize new entries and reset accumulated extremes at the entry instant.
_ORIGINAL_OPEN_TRADE = core.open_trade


def _open_trade_v13(db, user, plan, quote_data, settings):
    with v11.OPEN_TRADE_LOCK:
        trade = _ORIGINAL_OPEN_TRADE(db, user, plan, quote_data, settings)
        mark = float(quote_data["mark"])
        _MARK_EXTREMES[trade.symbol] = {
            "low": mark, "high": mark, "last": mark,
            "updated_at": time.time(),
        }
        return trade


core.open_trade = _open_trade_v13


# Risk exits run first. Each position has its own session/transaction, so an
# exception cannot leave the next position in PendingRollbackError.
_STALE_AUDIT_AT: dict[int, float] = {}


async def _manage_open_positions_v13():
    with core.DBLocal() as db:
        trade_ids = list(
            db.scalars(
                select(core.Trade.id).where(core.Trade.status == "OPEN")
            ).all()
        )

    if not trade_ids:
        core.engine_state["positions"] = "ACTIVE"
        return

    # Snapshot and clear before any await; the next cycle will collect new ticks.
    extremes_snapshot = {
        symbol: dict(values) for symbol, values in _MARK_EXTREMES.items()
    }
    _MARK_EXTREMES.clear()

    stale_seen = False
    funding_ids: list[int] = []
    for trade_id in trade_ids:
        with v11.OPEN_TRADE_LOCK:
            with core.DBLocal() as db:
                try:
                    trade = db.scalar(
                        select(core.Trade)
                        .where(
                            core.Trade.id == trade_id,
                            core.Trade.status == "OPEN",
                        )
                        .with_for_update()
                    )
                    if trade is None:
                        continue
                    user = db.get(core.User, trade.user_id)
                    if user is None:
                        db.rollback()
                        continue

                    quote = core.market_cache.get(trade.symbol)
                    if not quote_is_fresh(quote, time.time(), max_age=5.0):
                        stale_seen = True
                        last_audit = _STALE_AUDIT_AT.get(trade.id, 0.0)
                        if time.time() - last_audit >= 60:
                            core.add_audit(
                                db, "PHANTOM", "ERROR",
                                f"Position management paused: fresh Bid/Ask or Mark Price unavailable for {trade.symbol}",
                                user.id,
                            )
                            _STALE_AUDIT_AT[trade.id] = time.time()
                            db.commit()
                        else:
                            db.rollback()
                        continue

                    trigger_kind = None
                    extreme = extremes_snapshot.get(trade.symbol)
                    risk_quote = quote
                    if extreme:
                        targets = json.loads(trade.targets_json)
                        liquidation = core.approximate_liquidation_price(
                            trade.side, trade.entry_price, trade.leverage
                        )
                        trigger_kind = choose_mark_trigger(
                            trade.side,
                            trade.stop_price,
                            targets,
                            liquidation,
                            extreme["low"],
                            extreme["high"],
                        )
                        if trigger_kind in {"LIQUIDATION", "SL"}:
                            trigger = (
                                extreme["low"] if trade.side == "LONG"
                                else extreme["high"]
                            )
                            risk_quote = _quote_at_mark(quote, trigger)
                        elif trigger_kind == "TP":
                            trigger = (
                                extreme["high"] if trade.side == "LONG"
                                else extreme["low"]
                            )
                            risk_quote = _quote_at_mark(quote, trigger)

                    core.process_position(db, trade, user, risk_quote)
                    db.commit()
                    if trade.status == "OPEN":
                        funding_ids.append(trade.id)
                except Exception as exc:
                    db.rollback()
                    try:
                        core.add_audit(
                            db, "PHANTOM", "ERROR",
                            f"Position transaction rolled back for trade {trade_id}: {str(exc)[:120]}",
                        )
                        db.commit()
                    except Exception:
                        db.rollback()
                    LOG.exception(
                        "Position %s management failed; other positions continue",
                        trade_id,
                    )

    # Do not wait for Funding endpoints before checking any position's SL/TP.
    for trade_id in funding_ids:
        with core.DBLocal() as db:
            try:
                trade = db.scalar(
                    select(core.Trade)
                    .where(
                        core.Trade.id == trade_id,
                        core.Trade.status == "OPEN",
                    )
                    .with_for_update()
                )
                if trade is None:
                    continue
                user = db.get(core.User, trade.user_id)
                if user is None:
                    db.rollback()
                    continue
                await core.apply_funding(
                    db, trade, user, int(time.time() * 1000)
                )
                db.commit()
            except Exception as exc:
                db.rollback()
                LOG.warning(
                    "Funding processing failed for trade %s: %s",
                    trade_id, str(exc)[:140],
                )

    core.engine_state["positions"] = (
        "PROTECTIVE_STALE_QUOTES" if stale_seen else "ACTIVE"
    )
    core.engine_state["position_check"] = "Mark Price extremes + risk-first exits"
    core.engine_state["position_downtime_replay"] = (
        "NOT_AVAILABLE: price movement during service downtime is not reconstructed"
    )


core.manage_open_positions = _manage_open_positions_v13


# Serialize manual closes with the automatic manager; PostgreSQL row locking is
# also used to make the OPEN -> CLOSED transition idempotent across sessions.
def _manual_close_v13(
    trade_id: int,
    user=Depends(core.auth_user),
    db=Depends(core.db_dependency),
):
    with v11.OPEN_TRADE_LOCK:
        trade = db.scalar(
            select(core.Trade)
            .where(
                core.Trade.id == trade_id,
                core.Trade.user_id == user.id,
                core.Trade.status == "OPEN",
            )
            .with_for_update()
        )
        if trade is None:
            raise HTTPException(404, "Open paper position not found")
        quote = core.get_quote_from_cache(trade.symbol)
        settings = core.get_settings(db, user.id)
        fill = core.exit_fill(
            trade.side, quote, float(settings["slippage_bps"])
        )
        core.close_position_part(
            db, trade, user, trade.remaining_qty, fill, "MANUAL"
        )
        db.commit()
        db.refresh(trade)
        return core.trade_public(trade)


core.app.router.routes = [
    route for route in core.app.router.routes
    if not (
        getattr(route, "path", None) == "/api/trades/{trade_id}/close"
        and "POST" in (getattr(route, "methods", set()) or set())
    )
]
core.app.add_api_route(
    "/api/trades/{trade_id}/close",
    _manual_close_v13,
    methods=["POST"],
    include_in_schema=True,
)


# Manual exits remain in trade history but are excluded from strategy win-rate
# and profit-factor calculations.
def _analytics_v13(
    user=Depends(core.auth_user),
    db=Depends(core.db_dependency),
):
    import statistics

    all_closed = db.scalars(
        select(core.Trade).where(
            core.Trade.user_id == user.id,
            core.Trade.status == "CLOSED",
        ).order_by(core.Trade.closed_at)
    ).all()
    manual_closed = [
        row for row in all_closed if row.close_reason == "MANUAL"
    ]
    rows = [row for row in all_closed if row.close_reason != "MANUAL"]
    values = [
        row.gross_realized - row.entry_fee - row.exit_fee_total + row.funding_pnl
        for row in rows
    ]
    wins = [value for value in values if value > 0]
    losses = [value for value in values if value < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    equity = 10_000.0
    curve = []
    for value, trade in zip(values, rows):
        equity += value
        curve.append({"time": trade.closed_at, "equity": round(equity, 2)})
    return {
        "closed": len(values),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / len(values) * 100 if values else 0,
        "profit_factor": gross_profit / gross_loss if gross_loss else (
            gross_profit if gross_profit else 0
        ),
        "net_pnl": sum(values),
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "avg_trade": statistics.mean(values) if values else 0,
        "equity_curve": curve,
        "by_strategy": {
            key: round(sum(
                row.gross_realized - row.entry_fee - row.exit_fee_total + row.funding_pnl
                for row in rows if row.strategy == key
            ), 2)
            for key in {row.strategy for row in rows}
        },
        "manual_closes_excluded": len(manual_closed),
    }


core.app.router.routes = [
    route for route in core.app.router.routes
    if not (
        getattr(route, "path", None) == "/api/analytics"
        and "GET" in (getattr(route, "methods", set()) or set())
    )
]
core.app.add_api_route(
    "/api/analytics", _analytics_v13, methods=["GET"], include_in_schema=True
)


def _health_v13():
    result = runtime.health_v12()
    remaining = max(0, int(_GLOBAL_BACKOFF_UNTIL - time.time()))
    result["version"] = "1.3.0"
    result["binance_rest_protection"] = {
        "cooldown_active": remaining > 0,
        "cooldown_remaining_seconds": remaining,
        "reason": _GLOBAL_BACKOFF_REASON,
        "policy": "IP-wide cooldown for every Binance REST endpoint after HTTP 418/429",
    }
    result["scanner_quality"] = dict(_SCAN_COUNTS)
    result["position_safety"] = {
        "risk_checks_before_funding": True,
        "per_position_transactions": True,
        "manual_close_serialized": True,
        "mark_price_extremes_tracked_while_running": True,
        "service_downtime_price_replay": False,
    }
    return result


core.app.router.routes = [
    route for route in core.app.router.routes
    if not (
        getattr(route, "path", None) == "/api/health"
        and "GET" in (getattr(route, "methods", set()) or set())
    )
]
core.app.add_api_route(
    "/api/health", _health_v13, methods=["GET"], include_in_schema=True
)

core.engine_state["safety_engine"] = "MIRAGE v1.3 fail-closed protections"
core.engine_state["scanner"] = "BOOTING"
LOG.warning(
    "MIRAGE v1.3 safety overlay loaded; Paper-only execution remains enforced"
)
