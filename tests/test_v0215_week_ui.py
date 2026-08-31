from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _week_render_source():
    js = (ROOT / "laufapp/app/static/app.js").read_text(encoding="utf-8")
    start = js.index("async function renderWeek")
    end = js.index("function openPlanRefresh", start)
    return js[start:end]


def test_week_navigation_toolbar_is_directly_above_day_strip():
    source = _week_render_source()
    summary = source.index('class="week-summary"')
    toolbar = source.index('class="week-toolbar week-toolbar-days"')
    days = source.index('class="day-strip"')
    assert summary < toolbar < days
    assert 'id="prev-week"' in source
    assert 'id="next-week"' in source
    assert 'id="current-week"' in source


def test_completed_marker_is_rendered_from_workout_status_not_text_scraping():
    js = (ROOT / "laufapp/app/static/app.js").read_text(encoding="utf-8")
    css = (ROOT / "laufapp/app/static/assets/v0215.css").read_text(encoding="utf-8")
    index = (ROOT / "laufapp/app/static/index.html").read_text(encoding="utf-8")
    assert "status=w.status==='completed'?'completed'" in js
    assert 'class="week-workout status-${status}"' in js
    assert 'class="week-status-mark"' in js
    assert 'aria-label="Absolviert"' in js
    assert '>✓</span>' in js
    assert '.week-status-mark' in css
    assert 'background:var(--goodSoft)' in css
    assert 'color:var(--good)' in css
    assert 'assets/v0215.css?v=0.2.15' in index
    assert 'assets/v0214.js?v=0.2.14' not in index


def test_current_week_link_does_not_shift_next_arrow_off_date_row():
    css = (ROOT / "laufapp/app/static/assets/v0215.css").read_text(encoding="utf-8")
    assert 'grid-template-columns:44px minmax(0,1fr) 44px' in css
    assert '.week-toolbar-days .current-week' in css
    assert 'position:absolute' in css
