"""MIRAGE v1.1.1 entry-safety overlay.

This thin layer imports the established v1.1 runtime and adds a hard PHANTOM
entry gate. It deliberately leaves the original trading calculations, Funding
logic, WebSocket handlers, and open-position manager untouched.
"""
from __future__ import annotations

import time

from fastapi import Depends

import app as core
import app_v11 as v11
from mirage_v11_fixes import entry_gate_failures

app = core.app


def _base_phantom_status(user, db) -> dict:
    """Use the same per-account PHANTOM state that the dashboard displays."""
    status = v11.phantom_v11(user=user, db=db)
    now = time.time()
    failures = entry_gate_failures(
        core.ws_state,
        bool(core.market.status.ok),
        float(core.market.status.checked_at or 0),
        now,
    )
    # Preserve the v1.1 per-account open-position quote check as part of the
    # entry decision. A stale position quote keeps that account in PROTECTIVE.
    stale_position_checks = [
        check for check in status.get("checks", [])
        if check.get("name") == "Open-position quotes" and not check.get("ok", False)
    ]
    can_open = status.get("state") == "ACTIVE" and not failures and not stale_position_checks
    reasons = list(failures)
    reasons.extend(
        f"{check.get('name', 'PHANTOM check')}: {check.get('detail', 'not healthy')}"
        for check in stale_position_checks
    )
    if not can_open and not reasons:
        reasons.append("PHANTOM is not ACTIVE")

    status["state"] = "ACTIVE" if can_open else "PROTECTIVE"
    status["new_entries_allowed"] = can_open
    status["entry_block_reasons"] = reasons
    status.setdefault("checks", []).append({
        "name": "New paper entries",
        "ok": can_open,
        "detail": "Allowed: REST and both live WebSocket feeds are healthy"
        if can_open else "Blocked: " + "; ".join(reasons),
    })
    return status


# Wrap the v1.1 open_trade patch rather than replacing its fee/risk/position
# sizing behavior. The underlying RLock is re-entrant, so both guards are safe.
_previous_open_trade = core.open_trade


def open_trade_v111(db, user, plan, quote_data, settings):
    with v11.OPEN_TRADE_LOCK:
        status = _base_phantom_status(user, db)
        if not status["new_entries_allowed"]:
            reasons = "; ".join(status["entry_block_reasons"])
            raise ValueError(f"PHANTOM PROTECTIVE: new entries are disabled. {reasons}")
        return _previous_open_trade(db, user, plan, quote_data, settings)


core.open_trade = open_trade_v111


def phantom_v111(user=Depends(core.auth_user), db=Depends(core.db_dependency)):
    return _base_phantom_status(user, db)


def health_v111():
    result = v11.health_v11()
    now = time.time()
    failures = entry_gate_failures(
        core.ws_state,
        bool(core.market.status.ok),
        float(core.market.status.checked_at or 0),
        now,
    )
    result["version"] = "1.1.1"
    result["entry_feed_gate"] = {
        "allowed": not failures,
        "block_reasons": failures,
        "policy": "REST fallback may manage existing positions but cannot authorize new entries",
    }
    return result


v11._replace_endpoint("/api/phantom", "GET", phantom_v111)
v11._replace_endpoint("/api/health", "GET", health_v111)


if __name__ == "__main__":
    import os
    import uvicorn

    uvicorn.run(
        "app_v111:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        workers=1,
        reload=core.APP_ENV == "development",
    )
