from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_index_loads_v15_locale_and_visual_layers():
    html = (ROOT / "static/index.html").read_text(encoding="utf-8")
    assert "/static/visual-v15.css?v=16" in html
    assert "/static/i18n-v15.js?v=16" in html
    assert 'lang="ru"' in html


def test_service_worker_precaches_all_v15_shell_assets():
    sw = (ROOT / "static/sw.js").read_text(encoding="utf-8")
    for asset in ("visual-v15.css", "i18n-v15.js", "app.js?v=16", "styles.css?v=16"):
        assert asset in sw
    assert "mirage-shell-v16" in sw


def test_onboarding_is_fullscreen_and_has_three_dimensional_motion():
    css = (ROOT / "static/visual-v15.css").read_text(encoding="utf-8")
    assert ".onboarding-screen" in css and "inset: 0" in css
    assert "perspective: 1000px" in css
    assert "transform-style: preserve-3d" in css
    assert "@keyframes mirage-core-float" in css


def test_i18n_updates_dynamic_market_strategy_cards_and_reuses_saved_locale():
    js = (ROOT / "static/i18n-v15.js").read_text(encoding="utf-8")
    assert "MutationObserver" in js
    assert "setting-language" in js
    assert "Mean Reversion" in js
    assert "localStorage.getItem('mirage-onboarding-v15-migrated')" in js
