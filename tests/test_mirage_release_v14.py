from types import SimpleNamespace
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from news import _extract_image, _plain_summary
from mirage_release_v14 import build_analytics_payload


def trade(*, pnl, reason="TP1", when=100, strategy="INTRADAY", trade_id=1):
    return SimpleNamespace(
        id=trade_id,
        closed_at=when,
        close_reason=reason,
        gross_realized=pnl,
        entry_fee=0.5,
        exit_fee_total=0.5,
        funding_pnl=0.0,
        strategy=strategy,
    )


def test_first_close_creates_two_equity_points_and_is_visible():
    payload = build_analytics_payload([trade(pnl=20)], initial_capital=10_000)
    assert payload["total_closed"] == 1
    assert len(payload["equity_curve"]) == 2
    assert payload["equity_curve"][0]["equity"] == 10_000
    assert payload["equity_curve"][1]["equity"] == 10_019


def test_manual_close_affects_equity_and_realized_pnl_but_not_strategy_win_rate():
    payload = build_analytics_payload([
        trade(pnl=20, reason="TP3", when=100, trade_id=1),
        trade(pnl=-10, reason="MANUAL", when=200, trade_id=2),
    ])
    assert payload["total_closed"] == 2
    assert payload["manual_closes_excluded"] == 1
    assert payload["closed"] == 1
    assert payload["wins"] == 1
    assert payload["win_rate"] == 100
    assert payload["net_pnl"] == pytest.approx(8)
    assert payload["equity_curve"][-1]["equity"] == pytest.approx(10_008)


def test_analytics_max_drawdown_uses_all_realized_closes():
    payload = build_analytics_payload([
        trade(pnl=100, when=100, trade_id=1),
        trade(pnl=-50, when=200, trade_id=2),
    ])
    assert payload["max_drawdown_pct"] > 0
    assert payload["equity_curve"][-1]["equity"] == pytest.approx(10_048)


def test_news_image_extractor_accepts_rss_media_image():
    import xml.etree.ElementTree as ET
    item = ET.fromstring(
        '<item xmlns:media="http://search.yahoo.com/mrss/">'
        '<media:thumbnail url="https://cdn.example.com/photo.jpg" />'
        '</item>'
    )
    assert _extract_image(item, "", "https://publisher.example/story") == "https://cdn.example.com/photo.jpg"


def test_news_image_extractor_rejects_javascript_and_non_image_enclosure():
    import xml.etree.ElementTree as ET
    item = ET.fromstring('<item><enclosure url="https://cdn.example.com/file.mp3" type="audio/mpeg" /></item>')
    assert _extract_image(item, '<img src="javascript:alert(1)">', "https://publisher.example/story") is None


def test_news_summary_removes_tags_and_scripts():
    assert _plain_summary('<p>Hello <b>market</b></p><script>bad()</script>') == "Hello market"


def test_v14_routes_are_registered_and_active_settings_allow_ten_positions():
    # Importing the release module exercises app_v111's complete import graph.
    import app_v111  # noqa: F401
    import app
    import mirage_release_v14 as release
    paths = {(getattr(route, "path", None), method)
             for route in app.app.router.routes
             for method in (getattr(route, "methods", set()) or set())}
    assert ("/api/analytics", "GET") in paths
    assert ("/api/scanner/run", "POST") in paths
    # The real Render background loop must call the guarded v1.4 wrapper,
    # not app.py's old local scanner implementation.
    assert app.background_loop.__globals__["run_scan"] is release.run_scan_serialized_v14
    assert app.run_scan is release.run_scan_serialized_v14
    assert app.SettingsBody(max_positions=10).max_positions == 10
    with pytest.raises(Exception):
        app.SettingsBody(max_positions=11)

@pytest.mark.asyncio
async def test_manual_scanner_is_scan_only_and_never_opens_paper_positions(monkeypatch):
    import mirage_release_v14 as release

    calls = []

    async def fake_scan(*, execute_entries=True):
        calls.append(execute_entries)

    monkeypatch.setattr(release.runtime, "run_scan_v12", fake_scan)
    monkeypatch.setattr(release, "_LAST_MANUAL_SCAN_AT", 0.0)
    release.core.engine_state.update({
        "scanner": "ACTIVE", "scan_candidates": 2, "signals_saved": 1,
    })
    result = await release.manual_scan_v14(user=SimpleNamespace(id=1))

    assert calls == [False]
    assert result["mode"] == "SCAN_ONLY"
    assert result["auto_positions_opened"] == 0
