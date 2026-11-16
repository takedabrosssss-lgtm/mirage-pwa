"""Pure helpers for MIRAGE v1.3 safety tests."""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Iterable


def parse_retry_after(value: str | None, now: datetime | None = None) -> float | None:
    if not value:
        return None
    try:
        return max(1.0, float(value))
    except (TypeError, ValueError):
        pass
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        return max(1.0, (parsed - current).total_seconds())
    except Exception:
        return None


def scan_coverage_complete(attempted: int, succeeded: int, failed: int) -> bool:
    return attempted > 0 and failed == 0 and succeeded == attempted


def choose_mark_trigger(
    side: str,
    stop: float,
    targets: Iterable[float],
    liquidation: float,
    low: float,
    high: float,
) -> str | None:
    """Return conservative priority: liquidation, SL, then TP."""
    side = side.upper()
    if side == "LONG":
        if low <= liquidation:
            return "LIQUIDATION"
        if low <= stop:
            return "SL"
        if any(high >= target for target in targets):
            return "TP"
    elif side == "SHORT":
        if high >= liquidation:
            return "LIQUIDATION"
        if high >= stop:
            return "SL"
        if any(low <= target for target in targets):
            return "TP"
    else:
        raise ValueError("side must be LONG or SHORT")
    return None


def reserve_fee_adjusted_margin(
    free_balance: float, leverage: int, fee_rate: float
) -> float:
    if free_balance < 0 or leverage < 1 or fee_rate < 0:
        raise ValueError("invalid margin reservation inputs")
    return free_balance / (1.0 + leverage * fee_rate)


def market_lot_values(filters: dict) -> tuple[float, float]:
    market_lot = filters.get("MARKET_LOT_SIZE") or {}
    normal_lot = filters.get("LOT_SIZE") or {}
    candidate = market_lot if float(market_lot.get("stepSize", 0) or 0) > 0 else normal_lot
    return (
        float(candidate.get("stepSize", 0.001) or 0.001),
        float(candidate.get("minQty", 0.001) or 0.001),
    )
