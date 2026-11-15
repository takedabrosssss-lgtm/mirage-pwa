"""Pure, deterministic USDⓈ-M futures paper-execution helpers.

All prices are USDT per base unit. Long/short PnL is linear, like USDT-margined
perpetual contracts. This module never submits an exchange order.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import floor, isfinite
from typing import Literal, Sequence

Side = Literal["LONG", "SHORT"]


@dataclass(frozen=True)
class Quote:
    bid: float
    ask: float
    mark: float
    timestamp_ms: int = 0

    def validate(self) -> None:
        vals = (self.bid, self.ask, self.mark)
        if not all(isfinite(v) and v > 0 for v in vals):
            raise ValueError("Quote contains invalid prices")
        if self.ask < self.bid:
            raise ValueError("Ask is below bid; crossed/stale quote")

    @property
    def spread_bps(self) -> float:
        mid = (self.bid + self.ask) / 2
        return ((self.ask - self.bid) / mid) * 10_000


@dataclass(frozen=True)
class SizeResult:
    quantity: float
    margin_required: float
    risk_budget: float
    estimated_stop_loss: float


def entry_fill(side: Side, quote: Quote, slippage_bps: float) -> float:
    quote.validate()
    slip = max(0.0, slippage_bps) / 10_000
    return quote.ask * (1 + slip) if side == "LONG" else quote.bid * (1 - slip)


def exit_fill(side: Side, quote: Quote, slippage_bps: float) -> float:
    quote.validate()
    slip = max(0.0, slippage_bps) / 10_000
    return quote.bid * (1 - slip) if side == "LONG" else quote.ask * (1 + slip)


def estimated_stop_exit(side: Side, stop_price: float, spread_bps: float, slippage_bps: float) -> float:
    """Conservative expected stop fill, assuming current spread persists."""
    half_cost = max(0.0, spread_bps) / 20_000 + max(0.0, slippage_bps) / 10_000
    return stop_price * (1 - half_cost) if side == "LONG" else stop_price * (1 + half_cost)


def calculate_position_size(
    *, balance: float, risk_pct: float, entry_price: float, stop_price: float,
    side: Side, leverage: int, free_balance: float, fee_rate: float,
    spread_bps: float, slippage_bps: float, quantity_step: float = 0.000001,
) -> SizeResult:
    """Size from total expected stop loss incl. round-trip fee/spread/slippage.

    Leverage only caps required margin. It does not multiply the risk budget.
    """
    if side not in ("LONG", "SHORT"):
        raise ValueError("Side must be LONG or SHORT")
    if not (0 < risk_pct <= 5):
        raise ValueError("Risk percentage must be in (0, 5]")
    if leverage not in (1, 2, 3, 5, 8):
        raise ValueError("Unsupported leverage")
    if min(balance, entry_price, stop_price, free_balance, quantity_step) <= 0:
        raise ValueError("Balance, prices, free balance and quantity step must be positive")
    if side == "LONG" and stop_price >= entry_price:
        raise ValueError("Long stop must be below entry")
    if side == "SHORT" and stop_price <= entry_price:
        raise ValueError("Short stop must be above entry")
    if fee_rate < 0 or spread_bps < 0 or slippage_bps < 0:
        raise ValueError("Execution costs cannot be negative")

    risk_budget = balance * risk_pct / 100
    stop_fill = estimated_stop_exit(side, stop_price, spread_bps, slippage_bps)
    price_loss_per_unit = (entry_price - stop_fill) if side == "LONG" else (stop_fill - entry_price)
    fee_per_unit = fee_rate * (entry_price + stop_fill)
    risk_per_unit = price_loss_per_unit + fee_per_unit
    if not isfinite(risk_per_unit) or risk_per_unit <= 0:
        raise ValueError("Stop-loss risk calculation is invalid")

    qty_by_risk = risk_budget / risk_per_unit
    qty_by_margin = (free_balance * leverage) / entry_price
    raw_qty = min(qty_by_risk, qty_by_margin)
    qty = floor(raw_qty / quantity_step) * quantity_step
    if qty <= 0:
        raise ValueError("Available balance is too small for minimum quantity")
    margin = qty * entry_price / leverage
    stop_loss = qty * risk_per_unit
    return SizeResult(qty, margin, risk_budget, stop_loss)


def gross_pnl(side: Side, entry_price: float, exit_price: float, quantity: float) -> float:
    direction = 1 if side == "LONG" else -1
    return (exit_price - entry_price) * quantity * direction


def fee(notional: float, fee_rate: float) -> float:
    if notional < 0 or fee_rate < 0:
        raise ValueError("Notional and fee rate must not be negative")
    return notional * fee_rate


def funding_cost(side: Side, notional_at_mark: float, funding_rate: float) -> float:
    """Positive return means debit; negative means funding received.

    Positive Binance funding rate: longs pay shorts. Negative: shorts pay longs.
    """
    if notional_at_mark < 0:
        raise ValueError("Notional cannot be negative")
    direction = 1 if side == "LONG" else -1
    return direction * notional_at_mark * funding_rate


def leverage_for_score(score: int) -> int:
    """Quality-to-leverage mapping, hard capped at 8x."""
    if score >= 92:
        return 8
    if score >= 86:
        return 5
    if score >= 80:
        return 3
    return 0  # signal rejected by the S/A-grade gate


def validate_trade_plan(side: Side, entry: float, stop: float, tps: Sequence[float]) -> None:
    if min(entry, stop, *tps) <= 0:
        raise ValueError("All trade plan prices must be positive")
    if len(tps) != 3:
        raise ValueError("Exactly three take-profit levels are required")
    if side == "LONG":
        if not stop < entry or not (entry < tps[0] < tps[1] < tps[2]):
            raise ValueError("Long plan must satisfy SL < entry < TP1 < TP2 < TP3")
    elif side == "SHORT":
        if not stop > entry or not (entry > tps[0] > tps[1] > tps[2]):
            raise ValueError("Short plan must satisfy SL > entry > TP1 > TP2 > TP3")
    else:
        raise ValueError("Side must be LONG or SHORT")


def resolve_candle_touch(side: Side, stop: float, tp: float, low: float, high: float) -> str | None:
    """Conservative historical candle resolver: stop wins when both are touched."""
    if low > high:
        raise ValueError("Candle low cannot exceed high")
    stop_hit = low <= stop if side == "LONG" else high >= stop
    tp_hit = high >= tp if side == "LONG" else low <= tp
    if stop_hit:
        return "SL"
    if tp_hit:
        return "TP"
    return None


def target_quantity(initial_qty: float, remaining_qty: float, target_index: int) -> float:
    """TP1/TP2/TP3 close 50%/30%/the remainder of original quantity."""
    if target_index not in (0, 1, 2):
        raise ValueError("Target index must be 0, 1, or 2")
    planned = (0.50, 0.30, 1.00)[target_index] * initial_qty
    return min(remaining_qty, planned if target_index < 2 else remaining_qty)


def approximate_liquidation_price(side: Side, entry: float, leverage: int, maintenance_rate: float = 0.005) -> float:
    """Indicative isolated liquidation estimate, not exchange-bracket exact.

    Actual Binance liquidation uses account/position-specific maintenance
    brackets, fees and margin state. The UI must label this approximation.
    """
    if entry <= 0 or leverage < 1 or not (0 <= maintenance_rate < 0.5):
        raise ValueError("Invalid liquidation inputs")
    if side == "LONG":
        return entry * (1 - 1 / leverage) / (1 - maintenance_rate)
    return entry * (1 + 1 / leverage) / (1 + maintenance_rate)


def round_to_step(value: float, step: float, mode: str = "nearest") -> float:
    """Round a price/quantity to an exchange step without binary-float drift."""
    if value <= 0 or step <= 0:
        raise ValueError("Value and step must be positive")
    scaled = value / step
    if mode == "down":
        units = floor(scaled + 1e-12)
    elif mode == "up":
        from math import ceil
        units = ceil(scaled - 1e-12)
    else:
        units = round(scaled)
    return round(units * step, 12)
