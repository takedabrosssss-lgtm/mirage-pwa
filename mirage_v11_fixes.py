"""Pure safety helpers for MIRAGE v1.1.

This module is intentionally independent from FastAPI/SQLAlchemy so its
critical timestamp and quote-validation behavior can be tested in isolation.
"""
from __future__ import annotations

import json
import math
from collections.abc import Mapping
from typing import Any


def epoch_ms(value: int | float) -> int:
    """Normalize Unix seconds or milliseconds to milliseconds.

    Binance funding timestamps are milliseconds. MIRAGE v1.0 stored
    opened_at/last_funding_time in seconds, so this accepts both formats.
    """
    number = int(value)
    if number <= 0:
        return 0
    return number * 1000 if number < 1_000_000_000_000 else number


def funding_start_ms(last_funding_time: int | float, opened_at: int | float) -> int:
    """First funding timestamp to request, strictly after the last checkpoint."""
    opened_ms = epoch_ms(opened_at)
    last_ms = epoch_ms(last_funding_time)
    return max(opened_ms, last_ms + 1 if last_ms else opened_ms)


def quote_is_fresh(quote: Mapping[str, Any] | None, now: float, max_age: float = 5.0) -> bool:
    """Require complete prices and independently fresh book and mark feeds."""
    if not isinstance(quote, Mapping):
        return False
    try:
        bid = float(quote["bid"])
        ask = float(quote["ask"])
        mark = float(quote["mark"])
        book_at = float(quote["book_received_at"])
        mark_at = float(quote["mark_received_at"])
    except (KeyError, TypeError, ValueError):
        return False
    if not all(math.isfinite(v) and v > 0 for v in (bid, ask, mark, book_at, mark_at)):
        return False
    if ask < bid:
        return False
    return 0 <= now - book_at <= max_age and 0 <= now - mark_at <= max_age


def is_usdm_payload(payload: Mapping[str, Any]) -> bool:
    """Accept USDT symbols and, when supplied, Binance symbol type 1 (UM)."""
    symbol = str(payload.get("s", "")).upper()
    symbol_type = payload.get("st")
    return symbol.endswith("USDT") and symbol_type in (None, 1, "1")


def relevant_quote_message(channel: str, payload: Mapping[str, Any]) -> bool:
    """Only mark and best-bid/ask events may refresh quote-feed health."""
    event = str(payload.get("e", ""))
    return (channel == "market" and event == "markPriceUpdate") or (channel == "public" and event == "bookTicker")


def unpack_stream_message(raw: str | bytes | Mapping[str, Any] | list[Any]) -> list[dict[str, Any]]:
    """Normalize raw and combined Binance WebSocket messages to payload dicts."""
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    value: Any = json.loads(raw) if isinstance(raw, str) else raw
    if isinstance(value, Mapping) and "data" in value:
        value = value["data"]
    values = value if isinstance(value, list) else [value]
    return [dict(item) for item in values if isinstance(item, Mapping)]


def merge_quote_parts(
    parts: dict[str, dict[str, Any]],
    symbol: str,
    channel: str,
    payload: Mapping[str, Any],
    now: float,
    existing: Mapping[str, Any] | None = None,
    max_age: float = 5.0,
) -> dict[str, Any] | None:
    """Merge the public book and market mark feeds; publish only complete quotes."""
    symbol = symbol.upper()
    part = parts.setdefault(symbol, {})
    if existing:
        for source, target in (("bid", "bid"), ("ask", "ask"), ("mark", "mark"),
                               ("book_received_at", "book_received_at"),
                               ("mark_received_at", "mark_received_at")):
            if target not in part and source in existing:
                part[target] = existing[source]

    event = str(payload.get("e", ""))
    if channel == "public" and event == "bookTicker":
        part["bid"] = payload.get("b")
        part["ask"] = payload.get("a")
        part["book_received_at"] = now
    elif channel == "market" and event == "markPriceUpdate":
        part["mark"] = payload.get("p")
        part["mark_received_at"] = now
    else:
        return None

    try:
        result = {
            "symbol": symbol,
            "bid": float(part["bid"]),
            "ask": float(part["ask"]),
            "mark": float(part["mark"]),
            "book_received_at": float(part["book_received_at"]),
            "mark_received_at": float(part["mark_received_at"]),
            "received_at": now,
        }
    except (KeyError, TypeError, ValueError):
        return None
    return result if quote_is_fresh(result, now, max_age=max_age) else None


def recent_failures_exceeded(timestamps: list[float], now: float, window: float, limit: int) -> bool:
    """Return True when at least `limit` failures remain inside the window."""
    recent = [stamp for stamp in timestamps if 0 <= now - stamp < window]
    timestamps[:] = recent
    return len(recent) >= limit
