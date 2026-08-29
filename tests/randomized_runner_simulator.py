from __future__ import annotations

import json
import math
import random
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "laufapp" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import main_v020  # noqa: F401 - activates v0.2 runtime wiring
import training as base
import training_v020 as training
from db import connect, init_db, set_setting
from training_planner_v020 import training_paces


SEEDS = (104729, 130363, 155921, 181081, 205759, 230003, 254729, 279067, 303713)
PROFILE_BANDS = (
    (24.0, 30.0),
    (30.0, 38.0),
    (38.0, 46.0),
    (46.0, 54.0),
    (54.0, 62.0),
    (62.0, 70.0),
    (70.0, 80.0),
    (80.0, 90.0),
    (90.0, 100.0),
)
DAY_PATTERNS = {
    3: [1, 3, 6],
    4: [1, 3, 4, 6],
    5: [0, 1, 3, 4, 6],
    6: [0, 1, 2, 3, 4, 6],
    7: [0, 1, 2, 3, 4, 5, 6],
}


def _insert_race(c, name: str, distance_km: float, race_date: date, goal_seconds: int, priority: str) -> int:
    cur = c.execute(
        "INSERT INTO races(name,distance_km,race_date,goal_seconds,target_source,active) VALUES(?,?,?,?, 'user',1)",
        (name, distance_km, race_date.isoformat(), goal_seconds),
    )
    rid = int(cur.lastrowid)
    priorities = dict(base.get_setting(c, "race_priorities", {}) or {}) if hasattr(base, "get_setting") else {}
    # training_v020 reads the same persistent setting; preserve any existing entries.
    from db import get_setting
    priorities = dict(get_setting(c, "race_priorities", {}) or {})
    priorities[str(rid)] = priority
    set_setting(c, "race_priorities", priorities)
    return rid


def _seed_history(c, start: date, baseline: float, rng: random.Random, scenario: int) -> None:
    values = []
    for n in range(8, 0, -1):
        factor = rng.uniform(0.90, 1.10)
        if scenario == 4 and n in {3, 2, 1}:
            factor = {3: 0.90, 2: 0.77, 1: 0.64}[n]
        values.append((n, max(12.0, baseline * factor)))
    days = (1, 3, 4, 6)
    shares = (0.21, 0.20, 0.18, 0.41)
    for n, weekly in values:
        ws = start - timedelta(days=n * 7)
        for i, (dow, share) in enumerate(zip(days, shares)):
            km = round(weekly * share, 1)
            stamp = ws + timedelta(days=dow)
            c.execute(
                "INSERT INTO runs(external_id,started_at,distance_km,duration_s,source,rpe,notes) VALUES(?,?,?,?, 'manual',3,'randomized baseline')",
                (f"rand-hist-{scenario}-{n}-{i}", f"{stamp.isoformat()}T07:00:00+02:00", km, km * 330),
            )


def _profile(index: int, seed: int) -> dict:
    rng = random.Random(seed)
    lo, hi = PROFILE_BANDS[index]
    baseline = round(rng.uniform(lo, hi), 1)
    run_days = 3 + (index % 5)
    quality = min(run_days - 1, 1 + (index % 3))
    horizon = rng.randint(8, 16)
    ten_k_min = max(34.0, min(68.0, 72.0 - 0.38 * baseline + rng.uniform(-1.8, 1.8)))
    ten_k_seconds = int(round(ten_k_min * 60))
    predicted_marathon = ten_k_seconds * math.pow(42.195 / 10.0, 1.06)
    goal_factor = rng.uniform(0.91, 1.08)
    if index in {1, 6}:
        goal_factor = rng.uniform(0.88, 0.94)  # intentionally ambitious
    goal_seconds = int(round(max(2.65 * 3600, min(5.75 * 3600, predicted_marathon * goal_factor))))
    mode = "auto" if index in {0, 4, 8} else "user"
    if mode == "user":
        if index in {2, 7}:
            weekly_cap = round(max(24.0, baseline * rng.uniform(0.86, 0.95)), 1)
        else:
            weekly_cap = round(baseline * rng.uniform(1.04, 1.18), 1)
    else:
        weekly_cap = None
    long_floor = max(18.0, min(31.0, baseline * 0.34))
    max_long = round(rng.uniform(long_floor, 35.0), 1)
    return {
        "index": index,
        "seed": seed,
        "baseline": baseline,
        "run_days": run_days,
        "quality": quality,
        "horizon": horizon,
        "ten_k_seconds": ten_k_seconds,
        "goal_seconds": goal_seconds,
        "max_mode": mode,
        "weekly_cap": weekly_cap,
        "max_long": max_long,
        "max_share": rng.choice((0.40, 0.45, 0.50)),
        "b_race": index in {2, 5, 8},
    }


def _complete_week(c, workouts: list[dict], scenario: int, week_index: int) -> None:
    for i, w in enumerate(workouts):
        km = float(w["distance_km"])
        typ = str(w["workout_type"])
        rpe = 8 if typ in {"quality", "race"} else 4 if typ == "long" else 3
        duration = max(900.0, km * (315 if typ == "race" else 330))
        cur = c.execute(
            "INSERT INTO runs(external_id,started_at,distance_km,duration_s,source,rpe,notes) VALUES(?,?,?,?, 'manual',?,'randomized simulation')",
            (f"rand-sim-{scenario}-{week_index}-{i}", f"{w['scheduled_date']}T07:00:00+02:00", km, duration, rpe),
        )
        rid = int(cur.lastrowid)
        c.execute("UPDATE workouts SET status='completed',linked_run_id=? WHERE id=?", (rid, int(w["id"])))


def _hard_load_count(workouts: list[dict]) -> int:
    count = 0
    for w in workouts:
        details = w.get("details") or {}
        load = details.get("load") or {}
        high = float(load.get("high_min", 0) or 0)
        lt2 = float(load.get("around_lt2_min", 0) or 0)
        mp = float(load.get("marathon_pace_min", 0) or 0)
        moderate = float(load.get("moderate_min", 0) or 0)
        if w["workout_type"] == "race":
            count += 1
        elif w["workout_type"] == "long" and (mp >= 20 or moderate >= 20):
            count += 1
        elif w["workout_type"] == "quality" and (high >= 10 or lt2 >= 20 or mp >= 20):
            count += 1
    return count


def simulate_scenario(index: int, seed: int) -> dict:
    profile = _profile(index, seed)
    rng = random.Random(seed + 17)
    tmp = tempfile.TemporaryDirectory()
    path = Path(tmp.name) / f"runner-{index}.sqlite3"
    init_db(path)
    c = connect(path)
    start = base.week_start_for(date.today()) + timedelta(days=7)
    race_ws = start + timedelta(days=profile["horizon"] * 7)
    race_date = race_ws + timedelta(days=6)

    set_setting(c, "training_days", DAY_PATTERNS[profile["run_days"]])
    set_setting(c, "baseline_weekly_km", profile["baseline"])
    set_setting(c, "training_volume_profile", rng.choice(("gradual", "steady", "progressive")))
    set_setting(c, "max_weekly_km_mode", profile["max_mode"])
    if profile["weekly_cap"] is not None:
        set_setting(c, "max_weekly_km", profile["weekly_cap"])
    set_setting(c, "max_long_run_km", profile["max_long"])
    set_setting(c, "max_long_run_share", profile["max_share"])
    set_setting(c, "quality_sessions_per_week", profile["quality"])

    _seed_history(c, start, profile["baseline"], rng, index)
    a_id = _insert_race(c, f"A-Marathon {index+1}", 42.195, race_date, profile["goal_seconds"], "A")
    if profile["b_race"]:
        b_week = max(2, min(profile["horizon"] - 3, profile["horizon"] // 2))
        b_distance = rng.choice((5.0, 10.0, 21.0975))
        b_date = start + timedelta(days=b_week * 7 + 5)
        b_goal = int(round(profile["ten_k_seconds"] * math.pow(b_distance / 10.0, 1.05)))
        _insert_race(c, f"B-Test {index+1}", b_distance, b_date, b_goal, "B")
    c.execute(
        "INSERT INTO performance_marks(distance_km,duration_s,mark_date,source,label) VALUES(10,?,?, 'manual','randomized 10k')",
        (profile["ten_k_seconds"], (date.today() - timedelta(days=10)).isoformat()),
    )
    c.commit()

    rows = []
    previous_long = None
    repeated_quality = 0
    last_quality_key = None
    min_rolling_low = 100.0
    max_total = 0.0
    longest_long = 0.0
    quality_variants: set[str] = set()

    for week_index in range(profile["horizon"] + 1):
        ws = start + timedelta(days=week_index * 7)
        race = training.race_for_week(c, ws)
        auto_cap = training.automatic_max_weekly_km(c, race, ws)
        workouts = training.generate_week(c, ws, True)
        assert len(workouts) == profile["run_days"], (profile, week_index, workouts)
        scheduled = [w["scheduled_date"] for w in workouts]
        assert len(scheduled) == len(set(scheduled)), (profile, week_index, scheduled)
        assert all(float(w["distance_km"]) > 0 for w in workouts)

        total = round(sum(float(w["distance_km"]) for w in workouts), 1)
        max_total = max(max_total, total)
        phase = str((workouts[0].get("details") or {}).get("phase") or "")
        b_rows = [w for w in workouts if (w.get("details") or {}).get("race_priority") == "B"]
        a_rows = [w for w in workouts if (w.get("details") or {}).get("race_priority") == "A"]
        long_rows = [w for w in workouts if w["workout_type"] == "long"]

        if phase == "race":
            assert len(a_rows) == 1, (profile, week_index, workouts)
            assert abs(float(a_rows[0]["distance_km"]) - 42.195) < 0.06
            assert a_rows[0]["scheduled_date"] == race_date.isoformat()
        else:
            assert len(long_rows) + len(b_rows) == 1, (profile, week_index, workouts)
            cap = profile["weekly_cap"] if profile["max_mode"] == "user" else auto_cap
            if b_rows:
                d = b_rows[0].get("details") or {}
                allowed_extra = max(0.0, float(b_rows[0]["distance_km"]) - float(d.get("replaced_long_run_km", 0) or 0))
                assert total <= float(cap) + allowed_extra + 1.2, (profile, week_index, total, cap, allowed_extra)
            else:
                assert total <= float(cap) + 1.2, (profile, week_index, total, cap)

        for long in long_rows:
            lkm = float(long["distance_km"])
            longest_long = max(longest_long, lkm)
            assert lkm <= profile["max_long"] + 0.11, (profile, week_index, lkm)
            details = long.get("details") or {}
            mp_km = float(details.get("mp_km", 0) or 0)
            if previous_long is not None:
                if mp_km > previous_long["mp_km"] + 0.8 and mp_km > 0:
                    assert lkm <= previous_long["km"] + 1.3, (profile, previous_long, {"km": lkm, "mp_km": mp_km})
                if lkm >= previous_long["km"] + 1.6:
                    assert mp_km <= previous_long["mp_km"] + 0.2, (profile, previous_long, {"km": lkm, "mp_km": mp_km})
            previous_long = {"km": lkm, "mp_km": mp_km}

        quality_rows = [w for w in workouts if w["workout_type"] == "quality"]
        if quality_rows:
            key = str((quality_rows[0].get("details") or {}).get("variant_key") or quality_rows[0]["title"])
            quality_variants.add(key)
            if key == last_quality_key and phase not in {"recovery", "taper"}:
                repeated_quality += 1
            else:
                repeated_quality = 0
            assert repeated_quality < 2, (profile, week_index, key)
            last_quality_key = key

        hard_count = _hard_load_count(workouts)
        if phase not in {"race"}:
            assert hard_count <= profile["quality"], (profile, week_index, phase, hard_count, [(w["title"], w["workout_type"], (w.get("details") or {}).get("load")) for w in workouts])

        rolling = (workouts[0].get("details") or {}).get("rolling_intensity_distribution") or {}
        low_pct = float(rolling.get("low_pct", 0) or 0)
        if week_index >= 3 and phase not in {"race"} and low_pct > 0:
            min_rolling_low = min(min_rolling_low, low_pct)
            assert low_pct >= 68.0, (profile, week_index, phase, rolling)

        paces = training_paces(c, race)
        if paces["goal_marathon_pace_s_per_km"] < paces["current_estimated_marathon_pace_s_per_km"]:
            assert paces["training_marathon_pace_s_per_km"] >= paces["current_estimated_marathon_pace_s_per_km"] - 0.1

        rows.append({"week": week_index + 1, "phase": phase, "km": total, "hard": hard_count})
        if week_index < profile["horizon"]:
            _complete_week(c, workouts, index, week_index)
            c.commit()

    integrity = c.execute("PRAGMA integrity_check").fetchone()[0]
    schema = int(c.execute("PRAGMA user_version").fetchone()[0])
    c.close()
    tmp.cleanup()
    assert integrity == "ok"
    assert schema == 4
    assert len(quality_variants) >= 3, (profile, quality_variants)

    return {
        **profile,
        "a_race_id": a_id,
        "weeks": len(rows),
        "peak_week_km": round(max_total, 1),
        "longest_long_km": round(longest_long, 1),
        "quality_variants": len(quality_variants),
        "min_rolling_low_pct": round(min_rolling_low if min_rolling_low < 100 else 0, 1),
    }


def run_all() -> list[dict]:
    return [simulate_scenario(i, seed) for i, seed in enumerate(SEEDS)]


def markdown(results: list[dict]) -> str:
    lines = [
        "| # | Seed | Basis km | 10 km | Tage | Q | Max/Woche | Max LR | Wochen | Peak km | Längster LR | Q-Varianten | min. 4W low |",
        "|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        cap = "auto" if r["max_mode"] == "auto" else f"{r['weekly_cap']:.1f}"
        lines.append(
            f"| {r['index']+1} | {r['seed']} | {r['baseline']:.1f} | {r['ten_k_seconds']/60:.1f} min | {r['run_days']} | {r['quality']} | {cap} | {r['max_long']:.1f} | {r['weeks']} | {r['peak_week_km']:.1f} | {r['longest_long_km']:.1f} | {r['quality_variants']} | {r['min_rolling_low_pct']:.1f}% |"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    print(markdown(run_all()))
