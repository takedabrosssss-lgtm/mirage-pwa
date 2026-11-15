"""MIRAGE v1.2.1 database compatibility and transaction recovery patch."""
from __future__ import annotations

import logging
import app as core
from sqlalchemy import BigInteger

LOG = logging.getLogger("mirage.dbfix.v121")

# Binance fundingTime is Unix milliseconds (~1.8e12). PostgreSQL INTEGER is
# signed 32-bit and cannot store it. Change SQLAlchemy's bind type as well as
# the existing PostgreSQL column, so generated SQL uses BIGINT casts.
_trade_column = core.Trade.__table__.c.last_funding_time
_trade_column.type = BigInteger()

if core.engine.dialect.name == "postgresql":
    with core.engine.begin() as conn:
        conn.exec_driver_sql(
            "ALTER TABLE trades "
            "ALTER COLUMN last_funding_time TYPE BIGINT "
            "USING last_funding_time::BIGINT"
        )
    LOG.warning("MIRAGE v1.2.1: trades.last_funding_time migrated to BIGINT")
else:
    LOG.info(
        "MIRAGE v1.2.1: SQLAlchemy funding timestamp bind type set to BIGINT "
        "(SQLite INTEGER storage is already 64-bit)"
    )

# A failed trade commit must not leave the shared scan Session unusable.
# The caller can then record the rejection/audit event in a clean transaction.
_previous_open_trade = core.open_trade

def _rollback_safe_open_trade(db, user, plan, quote_data, settings):
    try:
        return _previous_open_trade(db, user, plan, quote_data, settings)
    except Exception:
        try:
            db.rollback()
        except Exception:
            LOG.exception("MIRAGE v1.2.1: rollback failed after paper trade error")
        raise

core.open_trade = _rollback_safe_open_trade
