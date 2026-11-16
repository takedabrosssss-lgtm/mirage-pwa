"""MIRAGE v1.4 coordinated release overlay.

Keeps the existing paper-only trading engine and v1.3 PHANTOM protections,
while adding one-shot scan controls, honest realized-equity analytics, and
small operational diagnostics. No real exchange orders or API credentials.
"""
from __future__ import annotations

import asyncio
import statistics
import time
from typing import Any

from fastapi import Depends, HTTPException
from sqlalchemy import select

import app as core
import app_v11 as v11
import mirage_runtime_v12 as runtime
import mirage_safety_v13 as safety

core.app.version = "1.4.0"


def _trade_net(trade: Any) -> float:
    return float(
        trade.gross_realized - trade.entry_fee - trade.exit_fee_total + trade.funding_pnl
    )


def build_analytics_payload(closed_trades: list[Any], initial_capital: float = 10_000.0) -> dict:
    """Build statistics excluding manual exits, but include every exit in equity."""
    all_rows = sorted(closed_trades, key=lambda row: (int(row.closed_at or 0), int(row.id or 0)))
    manual_rows = [row for row in all_rows if row.close_reason == "MANUAL"]
    strategy_rows = [row for row in all_rows if row.close_reason != "MANUAL"]
    strategy_values = [_trade_net(row) for row in strategy_rows]
    all_values = [_trade_net(row) for row in all_rows]
    wins = [value for value in strategy_values if value > 0]
    losses = [value for value in strategy_values if value < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))

    equity = float(initial_capital)
    curve = [{"time": int(all_rows[0].closed_at or 0) if all_rows else 0,
              "equity": round(equity, 2), "kind": "initial"}]
    peak = equity
    max_drawdown = 0.0
    for trade, value in zip(all_rows, all_values):
        equity += value
        peak = max(peak, equity)
        drawdown = (peak - equity) / peak * 100 if peak > 0 else 0.0
        max_drawdown = max(max_drawdown, drawdown)
        curve.append({"time": int(trade.closed_at or 0), "equity": round(equity, 2),
                      "kind": "manual" if trade.close_reason == "MANUAL" else "strategy"})

    return {
        # Strategy performance fields exclude manual exits by design.
        "closed": len(strategy_values),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / len(strategy_values) * 100 if strategy_values else 0.0,
        "profit_factor": gross_profit / gross_loss if gross_loss else (gross_profit if gross_profit else 0.0),
        "avg_trade": statistics.mean(strategy_values) if strategy_values else 0.0,
        "avg_win": statistics.mean(wins) if wins else 0.0,
        "avg_loss": statistics.mean(losses) if losses else 0.0,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        # Realized P&L and equity always reflect actual account balance changes,
        # including a user-initiated manual close.
        "net_pnl": sum(all_values),
        "total_closed": len(all_rows),
        "manual_closes_excluded": len(manual_rows),
        "manual_realized_net": sum(_trade_net(row) for row in manual_rows),
        "max_drawdown_pct": max_drawdown,
        "equity_curve": curve,
        "by_strategy": {
            key: round(sum(_trade_net(row) for row in strategy_rows if row.strategy == key), 2)
            for key in sorted({row.strategy for row in strategy_rows})
        },
    }


async def analytics_v14(user=Depends(core.auth_user), db=Depends(core.db_dependency)):
    rows = db.scalars(
        select(core.Trade).where(
            core.Trade.user_id == user.id,
            core.Trade.status == "CLOSED",
        ).order_by(core.Trade.closed_at, core.Trade.id)
    ).all()
    return build_analytics_payload(rows)


# Serializes the background scanner and one-shot user-triggered scanner.
_SCAN_LOCK = asyncio.Lock()
_LAST_MANUAL_SCAN_AT = 0.0
_ORIGINAL_RUN_SCAN = core.run_scan
_MANUAL_SCAN_MIN_INTERVAL = 30.0


async def run_scan_serialized_v14() -> None:
    if _SCAN_LOCK.locked():
        return
    async with _SCAN_LOCK:
        await _ORIGINAL_RUN_SCAN()


async def manual_scan_v14(user=Depends(core.auth_user)):
    global _LAST_MANUAL_SCAN_AT
    now = time.monotonic()
    if _SCAN_LOCK.locked():
        raise HTTPException(409, "Сканер уже выполняет цикл. Дождитесь его завершения.")
    remaining = _MANUAL_SCAN_MIN_INTERVAL - (now - _LAST_MANUAL_SCAN_AT)
    if remaining > 0:
        raise HTTPException(429, f"Повторный ручной запуск будет доступен через {int(remaining) + 1} сек.")
    async with _SCAN_LOCK:
        _LAST_MANUAL_SCAN_AT = time.monotonic()
        await runtime.run_scan_v12(execute_entries=False)
    return {
        "ok": True,
        "mode": "SCAN_ONLY",
        "scanner": core.engine_state.get("scanner", "UNKNOWN"),
        "candidates": int(core.engine_state.get("scan_candidates", 0) or 0),
        "signals_saved": int(core.engine_state.get("signals_saved", 0) or 0),
        "auto_positions_opened": 0,
        "message": "Ручной запуск обновляет сигналы и не открывает позиции.",
    }


# Swap only these API routes; all existing auth and DB dependencies are retained.
core.app.router.routes = [
    route for route in core.app.router.routes
    if not (
        (getattr(route, "path", None) == "/api/analytics"
         and "GET" in (getattr(route, "methods", set()) or set()))
        or (getattr(route, "path", None) == "/api/scanner/run"
            and "POST" in (getattr(route, "methods", set()) or set()))
    )
]
core.app.add_api_route("/api/analytics", analytics_v14, methods=["GET"], include_in_schema=True)
core.app.add_api_route("/api/scanner/run", manual_scan_v14, methods=["POST"], include_in_schema=True)
core.run_scan = run_scan_serialized_v14
# app.background_loop resolves `run_scan` from app.py's module globals rather
# than looking up core.run_scan dynamically. Replace that exact global binding
# too, otherwise the scheduled scanner would silently bypass the v1.2/v1.4 path.
core.background_loop.__globals__["run_scan"] = run_scan_serialized_v14


# Add the exact currently reserved isolated margin to the dashboard response.
_ORIGINAL_DASHBOARD = v11.dashboard_v11

def dashboard_v14(user=Depends(core.auth_user), db=Depends(core.db_dependency)):
    result = _ORIGINAL_DASHBOARD(user=user, db=db)
    positions = core.active_trades(db, user.id)
    reserved = sum(
        float(t.initial_margin) * (float(t.remaining_qty) / float(t.initial_qty))
        for t in positions if float(t.initial_qty) > 0
    )
    result["reserved_isolated_margin"] = round(reserved, 8)
    result["free_margin"] = round(max(0.0, float(user.balance) - reserved), 8)
    return result

v11._replace_endpoint("/api/dashboard", "GET", dashboard_v14)


_ORIGINAL_HEALTH = safety._health_v13

def health_v14():
    result = _ORIGINAL_HEALTH()
    result["version"] = "1.4.0"
    result["release_v14"] = {
        "manual_scanner": "SCAN_ONLY; serialized with automatic scanner",
        "capacity_queue": "DISABLED; a candle skipped at full capacity cannot be opened later",
        "daily_entry_protection": "1.5% of initial 10,000 USDT daily realized-loss limit",
        "loss_streak_protection": "three consecutive non-manual losses => 6-hour entry cooldown",
        "analytics": "manual exits included in realized P&L/equity, excluded from strategy win-rate",
        "real_orders_enabled": False,
    }
    return result

v11._replace_endpoint("/api/health", "GET", health_v14)

core.engine_state["release"] = "MIRAGE v1.4 coordinated paper-trading release"
