from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_completed_workout_has_green_check_marker_hook():
    js = (ROOT / "laufapp/app/static/assets/v0214.js").read_text()
    css = (ROOT / "laufapp/app/static/assets/v0214.css").read_text()
    assert "status-completed" in js
    assert "absolviert" in js
    assert ".week-workout.status-completed" in css
    assert 'content:"✓"' in css
    assert 'background:var(--goodSoft)' in css
    assert 'color:var(--good)' in css


def test_week_date_range_is_moved_immediately_above_day_strip():
    js = (ROOT / "laufapp/app/static/assets/v0214.js").read_text()
    assert "toolbar?.querySelector('.week-title')" in js
    assert "root.querySelector('.day-strip')" in js
    assert "dayStrip.before(title)" in js
    assert "title.classList.add('week-title-days')" in js
    assert "MutationObserver" in js
