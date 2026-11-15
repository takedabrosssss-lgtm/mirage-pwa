import math
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from trading import (
    Quote, entry_fill, exit_fill, calculate_position_size, gross_pnl, fee,
    funding_cost, leverage_for_score, validate_trade_plan, resolve_candle_touch,
    target_quantity, approximate_liquidation_price, round_to_step,
)


def test_long_and_short_use_correct_bid_ask_side():
    q = Quote(bid=99.9, ask=100.1, mark=100.0)
    assert entry_fill("LONG", q, 0) == pytest.approx(100.1)
    assert entry_fill("SHORT", q, 0) == pytest.approx(99.9)
    assert exit_fill("LONG", q, 0) == pytest.approx(99.9)
    assert exit_fill("SHORT", q, 0) == pytest.approx(100.1)


def test_slippage_worsens_both_entry_directions():
    q = Quote(bid=99.9, ask=100.1, mark=100.0)
    assert entry_fill("LONG", q, 5) > q.ask
    assert entry_fill("SHORT", q, 5) < q.bid
    assert exit_fill("LONG", q, 5) < q.bid
    assert exit_fill("SHORT", q, 5) > q.ask


def test_leverage_changes_margin_not_risk_budget():
    kwargs = dict(balance=10_000, risk_pct=1, entry_price=100, stop_price=98,
                  side="LONG", free_balance=10_000, fee_rate=.0005,
                  spread_bps=2, slippage_bps=2, quantity_step=.000001)
    at3 = calculate_position_size(**kwargs, leverage=3)
    at8 = calculate_position_size(**kwargs, leverage=8)
    assert at3.quantity == pytest.approx(at8.quantity)
    assert at3.estimated_stop_loss <= 100
    assert at8.margin_required < at3.margin_required


def test_position_size_respects_available_isolated_margin():
    result = calculate_position_size(balance=10_000, risk_pct=1, entry_price=100,
        stop_price=95, side="LONG", leverage=3, free_balance=50,
        fee_rate=.0005, spread_bps=4, slippage_bps=3, quantity_step=.001)
    assert result.margin_required <= 50


def test_fee_is_charged_on_notional_not_margin():
    assert fee(8_000, .0005) == pytest.approx(4.0)


def test_funding_direction_and_sign():
    assert funding_cost("LONG", 10_000, .001) == pytest.approx(10)
    assert funding_cost("SHORT", 10_000, .001) == pytest.approx(-10)
    assert funding_cost("LONG", 10_000, -.001) == pytest.approx(-10)
    assert funding_cost("SHORT", 10_000, -.001) == pytest.approx(10)


def test_pnl_long_short():
    assert gross_pnl("LONG", 100, 110, 2) == pytest.approx(20)
    assert gross_pnl("SHORT", 100, 90, 2) == pytest.approx(20)


def test_dynamic_leverage_and_quality_gate():
    assert leverage_for_score(79) == 0
    assert leverage_for_score(80) == 3
    assert leverage_for_score(86) == 5
    assert leverage_for_score(92) == 8
    assert leverage_for_score(100) <= 8


def test_plan_validation():
    validate_trade_plan("LONG", 100, 95, [105, 110, 115])
    validate_trade_plan("SHORT", 100, 105, [95, 90, 85])
    with pytest.raises(ValueError):
        validate_trade_plan("LONG", 100, 101, [105, 110, 115])


def test_ambiguous_historical_candle_stops_out_first():
    assert resolve_candle_touch("LONG", 95, 105, 94, 106) == "SL"
    assert resolve_candle_touch("SHORT", 105, 95, 94, 106) == "SL"
    assert resolve_candle_touch("LONG", 95, 105, 96, 106) == "TP"


def test_take_profit_partial_sizes_are_50_30_remainder():
    initial, remaining = 10.0, 10.0
    tp1 = target_quantity(initial, remaining, 0)
    remaining -= tp1
    tp2 = target_quantity(initial, remaining, 1)
    remaining -= tp2
    tp3 = target_quantity(initial, remaining, 2)
    assert [tp1, tp2, tp3] == pytest.approx([5, 3, 2])


def test_liquidation_estimate_moves_closer_with_higher_leverage():
    long3 = approximate_liquidation_price("LONG", 100, 3)
    long8 = approximate_liquidation_price("LONG", 100, 8)
    assert long8 > long3
    assert long8 < 100
    assert approximate_liquidation_price("SHORT", 100, 8) > 100


def test_exchange_step_rounding():
    assert round_to_step(1.23456, 0.001, "down") == pytest.approx(1.234)
    assert round_to_step(1.23401, 0.001, "up") == pytest.approx(1.235)
    assert round_to_step(1.23456, 0.001) == pytest.approx(1.235)
