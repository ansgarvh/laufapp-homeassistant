from __future__ import annotations

import bisect
import calendar
import hashlib
import math
import sqlite3
import zipfile
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Callable

from training import auto_match_run, parse_dt

RUNNING_TYPES = {"HKWorkoutActivityTypeRunning", "HKWorkoutActivityTypeRun"}
METRIC_TYPES = {
    "HKQuantityTypeIdentifierRestingHeartRate": ("resting_hr", "count/min"),
    "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": ("hrv_sdnn", "ms"),
    "HKQuantityTypeIdentifierBodyMass": ("body_mass", "kg"),
    "HKQuantityTypeIdentifierVO2Max": ("vo2max", "mL/min·kg"),
}
# Time-resolved metrics used for detailed run analysis. Apple may aggregate
# samples; we preserve the timestamps and the finest granularity present in the
# export rather than manufacturing higher-frequency data.
RUN_SAMPLE_TYPES = {
    "HKQuantityTypeIdentifierHeartRate": ("heart_rate", "count/min"),
    "HKQuantityTypeIdentifierRunningSpeed": ("running_speed", "m/s"),
    "HKQuantityTypeIdentifierRunningPower": ("running_power", "W"),
    "HKQuantityTypeIdentifierRunningStrideLength": ("stride_length", "m"),
    "HKQuantityTypeIdentifierRunningVerticalOscillation": ("vertical_oscillation", "cm"),
    "HKQuantityTypeIdentifierRunningGroundContactTime": ("ground_contact_time", "ms"),
    "HKQuantityTypeIdentifierStepCount": ("cadence", "spm"),
}
SLEEP_TYPE = "HKCategoryTypeIdentifierSleepAnalysis"
ProgressCallback = Callable[[str, float, dict[str, Any]], None]


def date_cutoff(months: int = 24) -> date:
    t = date.today()
    m = t.year * 12 + t.month - 1 - months
    y, m0 = divmod(m, 12)
    mo = m0 + 1
    d = min(t.day, calendar.monthrange(y, mo)[1])
    return date(y, mo, d)


def f(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def dur(v, u):
    x = f(v)
    if x is None:
        return None
    u = (u or "min").lower()
    return x if u in {"s", "sec", "second", "seconds"} else x * 3600 if u in {"h", "hr", "hour", "hours"} else x * 60


def dist(v, u):
    x = f(v)
    if x is None:
        return None
    u = (u or "km").lower()
    return x * 1.609344 if u in {"mi", "mile", "miles"} else x / 1000 if u in {"m", "meter", "meters"} else x


def iso(v):
    if not v:
        return None
    try:
        return parse_dt(v).isoformat()
    except Exception:
        return v


def epoch(v: str | None) -> float | None:
    if not v:
        return None
    try:
        return parse_dt(v).timestamp()
    except Exception:
        return None


def fp(*parts):
    return hashlib.sha256("|".join("" if p is None else str(p) for p in parts).encode()).hexdigest()


def avg_hr(e):
    for ch in list(e):
        tag = ch.tag.split("}")[-1]
        if tag == "WorkoutStatistics" and ch.attrib.get("type") == "HKQuantityTypeIdentifierHeartRate":
            if (x := f(ch.attrib.get("average"))) is not None:
                return x
    return None


def elev(e):
    for ch in list(e):
        if ch.tag.split("}")[-1] == "WorkoutStatistics" and "Elevation" in ch.attrib.get("type", ""):
            x = f(ch.attrib.get("sum") or ch.attrib.get("average"))
            if x is not None:
                return x * 0.3048 if ch.attrib.get("unit", "m").lower() in {"ft", "feet"} else x
    return None


def _workout_stat(e, type_fragment: str, fields=("sum", "average")):
    """Extract a value and unit from a nested Apple WorkoutStatistics node."""
    for ch in list(e):
        if ch.tag.split("}")[-1] != "WorkoutStatistics" or type_fragment not in ch.attrib.get("type", ""):
            continue
        for field in fields:
            if ch.attrib.get(field) is not None:
                return ch.attrib[field], ch.attrib.get("unit")
    return None, None


def insert_run(c, e, cutoff):
    a = e.attrib
    if a.get("workoutActivityType") not in RUNNING_TYPES:
        return None
    raw = a.get("startDate") or a.get("creationDate")
    if not raw:
        return None
    try:
        sd = parse_dt(raw)
    except Exception:
        return None
    if sd.date() < cutoff:
        return None
    dv, du = a.get("duration"), a.get("durationUnit")
    if dv is None:
        dv, du = _workout_stat(e, "Duration")
    ds = dur(dv, du)
    if ds is None and a.get("endDate"):
        try:
            ds = (parse_dt(a["endDate"]) - sd).total_seconds()
        except Exception:
            pass
    xv, xu = a.get("totalDistance"), a.get("totalDistanceUnit")
    if xv is None:
        xv, xu = _workout_stat(e, "Distance")
    km = dist(xv, xu)
    if ds is None or km is None or ds <= 0 or km <= 0:
        return None
    start = sd.isoformat()
    end = iso(a.get("endDate"))
    external = a.get("uuid") or fp("run", start, end, round(km, 4), round(ds, 2))
    hr = avg_hr(e)
    el = elev(e)
    energy, _energy_unit = _workout_stat(e, "ActiveEnergyBurned")
    cal = f(a.get("totalEnergyBurned") or energy)
    existing = c.execute("SELECT id FROM runs WHERE external_id=?", (external,)).fetchone()
    if existing:
        return ("existing", int(existing["id"]))
    # A run may already have been entered from a screenshot/manual form before
    # the next Apple Health export. Conservatively enrich it instead of creating
    # a duplicate; user-entered shoe/RPE/notes are preserved.
    same_day = c.execute("SELECT * FROM runs WHERE external_id IS NULL AND started_at LIKE ?", (sd.date().isoformat() + "%",)).fetchall()
    for old in same_day:
        try:
            delta = abs((parse_dt(old["started_at"]) - sd).total_seconds())
        except Exception:
            continue
        dist_tol = max(0.05, km * 0.01)
        if delta <= 5400 and abs(float(old["distance_km"]) - km) <= dist_tol and abs(float(old["duration_s"]) - ds) <= 30:
            c.execute(
                "UPDATE runs SET external_id=?,ended_at=COALESCE(ended_at,?),avg_hr=COALESCE(avg_hr,?),elevation_m=COALESCE(elevation_m,?),calories=COALESCE(calories,?),source='apple_health_enriched' WHERE id=?",
                (external, end, hr, el, cal, old["id"]),
            )
            return ("merged", int(old["id"]))
    cur = c.execute(
        "INSERT OR IGNORE INTO runs(external_id,started_at,ended_at,distance_km,duration_s,avg_hr,elevation_m,calories,source) VALUES(?,?,?,?,?,?,?,?, 'apple_health')",
        (external, start, end, km, ds, hr, el, cal),
    )
    if cur.rowcount:
        rid = int(cur.lastrowid)
        auto_match_run(c, rid)
        return ("added", rid)
    return None


def sleep_interval(e, cutoff):
    a = e.attrib
    if a.get("type") != SLEEP_TYPE:
        return None
    val = a.get("value", "")
    if "Asleep" not in val or "Awake" in val:
        return None
    try:
        s, en = parse_dt(a.get("startDate", "")), parse_dt(a.get("endDate", ""))
    except Exception:
        return None
    if en <= s or en.date() < cutoff:
        return None
    return en.date(), s, en


def insert_sleep(c, nights):
    added = 0
    for night, intervals in nights.items():
        merged = []
        for s, e in sorted(intervals):
            if not merged or s > merged[-1][1]:
                merged.append([s, e])
            elif e > merged[-1][1]:
                merged[-1][1] = e
        hours = sum((e - s).total_seconds() for s, e in merged) / 3600
        if not 0 < hours <= 16:
            continue
        cur = c.execute(
            "INSERT OR IGNORE INTO health_metrics(external_id,metric_type,start_at,end_at,value,unit,source) VALUES(?,'sleep_hours',?,?,?,'h','apple_health')",
            (f"apple_health_sleep_{night.isoformat()}", merged[0][0].isoformat(), merged[-1][1].isoformat(), hours),
        )
        added += int(bool(cur.rowcount))
    return added


def insert_metric(c, e, cutoff):
    a = e.attrib
    typ = a.get("type")
    if typ not in METRIC_TYPES:
        return False
    try:
        sd = parse_dt(a.get("startDate") or a.get("creationDate") or "")
    except Exception:
        return False
    if sd.date() < cutoff:
        return False
    metric, canonical = METRIC_TYPES[typ]
    value = f(a.get("value"))
    if value is None:
        return False
    unit = a.get("unit") or canonical
    if metric == "body_mass" and unit.lower() in {"lb", "lbs"}:
        value *= 0.45359237
        unit = "kg"
    start = sd.isoformat()
    end = iso(a.get("endDate"))
    external = a.get("uuid") or fp("metric", typ, start, end, value, unit)
    return bool(
        c.execute(
            "INSERT OR IGNORE INTO health_metrics(external_id,metric_type,start_at,end_at,value,unit,source) VALUES(?,?,?,?,?,?,'apple_health')",
            (external, metric, start, end, value, unit),
        ).rowcount
    )


def _convert_sample(metric: str, value: float, unit: str, start_ts: float, end_ts: float) -> tuple[float, str] | None:
    u = (unit or "").strip().lower()
    if metric == "heart_rate":
        return value, "count/min"
    if metric == "running_speed":
        if u in {"km/hr", "km/h", "kmph"}:
            value /= 3.6
        elif u in {"mi/hr", "mph"}:
            value *= 0.44704
        return value, "m/s"
    if metric == "running_power":
        return value, "W"
    if metric == "stride_length":
        if u in {"cm"}:
            value /= 100
        elif u in {"mm"}:
            value /= 1000
        return value, "m"
    if metric == "vertical_oscillation":
        if u in {"m", "meter", "meters"}:
            value *= 100
        elif u in {"mm"}:
            value /= 10
        return value, "cm"
    if metric == "ground_contact_time":
        if u in {"s", "sec", "second", "seconds"}:
            value *= 1000
        return value, "ms"
    if metric == "cadence":
        seconds = max(0.0, end_ts - start_ts)
        if seconds <= 0:
            return None
        return value / seconds * 60.0, "spm"
    return None


def stage_run_sample(c: sqlite3.Connection, e, cutoff: date) -> bool:
    a = e.attrib
    typ = a.get("type")
    if typ not in RUN_SAMPLE_TYPES:
        return False
    start_ts = epoch(a.get("startDate") or a.get("creationDate"))
    end_ts = epoch(a.get("endDate") or a.get("startDate") or a.get("creationDate"))
    if start_ts is None or end_ts is None:
        return False
    if datetime.fromtimestamp(start_ts, timezone.utc).date() < cutoff:
        return False
    value = f(a.get("value"))
    if value is None or not math.isfinite(value):
        return False
    metric, _canonical = RUN_SAMPLE_TYPES[typ]
    converted = _convert_sample(metric, value, a.get("unit") or "", start_ts, end_ts)
    if converted is None:
        return False
    value, canonical_unit = converted
    c.execute(
        "INSERT INTO import_run_samples(metric_type,start_ts,end_ts,value,unit,external_id) VALUES(?,?,?,?,?,?)",
        (metric, start_ts, end_ts, value, canonical_unit, a.get("uuid") or ""),
    )
    return True


def _run_intervals(c: sqlite3.Connection, cutoff: date):
    rr = c.execute(
        "SELECT id,started_at,ended_at,duration_s FROM runs WHERE started_at>=? ORDER BY started_at",
        (cutoff.isoformat(),),
    ).fetchall()
    intervals = []
    for r in rr:
        s = epoch(r["started_at"])
        e = epoch(r["ended_at"])
        if s is None:
            continue
        if e is None:
            e = s + float(r["duration_s"])
        intervals.append((s, e, int(r["id"])))
    return intervals


def attach_staged_samples(c: sqlite3.Connection, cutoff: date) -> int:
    intervals = _run_intervals(c, cutoff)
    if not intervals:
        return 0
    starts = [x[0] for x in intervals]
    added = 0
    for s in c.execute("SELECT metric_type,start_ts,end_ts,value,unit,external_id FROM import_run_samples ORDER BY start_ts"):
        i = bisect.bisect_right(starts, float(s["start_ts"])) - 1
        if i < 0:
            continue
        run_start, run_end, run_id = intervals[i]
        # Allow a small sensor timestamp tolerance around workout boundaries.
        if float(s["start_ts"]) < run_start - 30 or float(s["start_ts"]) > run_end + 30:
            continue
        sampled = datetime.fromtimestamp(float(s["start_ts"]), timezone.utc).isoformat()
        external = s["external_id"] or fp("run_sample", run_id, s["metric_type"], sampled, round(float(s["value"]), 6), s["unit"])
        cur = c.execute(
            "INSERT OR IGNORE INTO run_samples(external_id,run_id,metric_type,sampled_at,value,unit,source) VALUES(?,?,?,?,?,?,'apple_health')",
            (external, run_id, s["metric_type"], sampled, s["value"], s["unit"]),
        )
        added += int(bool(cur.rowcount))
    return added


def open_xml(path: Path) -> tuple[BinaryIO, zipfile.ZipFile | None, int]:
    if zipfile.is_zipfile(path):
        z = zipfile.ZipFile(path)
        names = [n for n in z.namelist() if n.lower().endswith("export.xml")]
        if not names:
            z.close()
            raise ValueError("Im ZIP wurde keine Apple-Health export.xml gefunden.")
        info = z.getinfo(names[0])
        if info.file_size > 8 * 1024**3:
            z.close()
            raise ValueError("Die entpackte export.xml ist größer als 8 GB.")
        return z.open(info), z, int(info.file_size)
    return open(path, "rb"), None, int(path.stat().st_size)


def _stream_position(stream: BinaryIO) -> int:
    try:
        return int(stream.tell())
    except Exception:
        return 0


def _find_run_for_timestamp(c: sqlite3.Connection, ts: float, cutoff: date) -> int | None:
    for s, e, rid in _run_intervals(c, cutoff):
        if s - 120 <= ts <= e + 120:
            return rid
    return None


def _iter_gpx_points(raw: BinaryIO):
    seq = 0
    for _event, elem in ET.iterparse(raw, events=("end",)):
        if elem.tag.split("}")[-1] != "trkpt":
            continue
        lat = f(elem.attrib.get("lat"))
        lon = f(elem.attrib.get("lon"))
        elevation = None
        timestamp = None
        for ch in list(elem):
            tag = ch.tag.split("}")[-1]
            if tag == "ele":
                elevation = f(ch.text)
            elif tag == "time":
                timestamp = ch.text
        if lat is not None and lon is not None and timestamp:
            yield seq, timestamp, lat, lon, elevation
            seq += 1
        elem.clear()


def import_routes(c: sqlite3.Connection, z: zipfile.ZipFile | None, cutoff: date, progress: ProgressCallback | None = None) -> dict[str, int]:
    if z is None:
        return {"routes_seen": 0, "routes_attached": 0, "routes_unmatched": 0, "gps_points_added": 0}
    route_names = [n for n in z.namelist() if n.lower().endswith(".gpx") and ("route" in n.lower() or "workout" in n.lower())]
    added = attached = unmatched = 0
    for idx, name in enumerate(route_names):
        if progress:
            progress("Routen", 0.86 + 0.08 * (idx / max(1, len(route_names))), {"routes_seen": idx})
        try:
            with z.open(name) as raw:
                points = list(_iter_gpx_points(raw))
        except ET.ParseError:
            unmatched += 1
            continue
        if not points:
            continue
        ts = epoch(points[0][1])
        if ts is None or datetime.fromtimestamp(ts, timezone.utc).date() < cutoff:
            continue
        run_id = _find_run_for_timestamp(c, ts, cutoff)
        if not run_id:
            unmatched += 1
            continue
        attached += 1
        elevations = []
        for seq, timestamp, lat, lon, elevation in points:
            sampled = iso(timestamp)
            cur = c.execute(
                "INSERT OR IGNORE INTO gps_points(run_id,sampled_at,latitude,longitude,elevation_m,sequence,source) VALUES(?,?,?,?,?,?,'apple_health')",
                (run_id, sampled, lat, lon, elevation, seq),
            )
            added += int(bool(cur.rowcount))
            if elevation is not None:
                elevations.append(float(elevation))
        if elevations:
            gain = sum(max(0.0, b - a) for a, b in zip(elevations, elevations[1:]))
            c.execute(
                "UPDATE runs SET elevation_m=COALESCE(elevation_m,?) WHERE id=?",
                (round(gain, 1), run_id),
            )
    return {"routes_seen": len(route_names), "routes_attached": attached, "routes_unmatched": unmatched, "gps_points_added": added}


def import_apple_health(
    c: sqlite3.Connection,
    path: Path,
    months: int = 24,
    progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    cutoff = date_cutoff(months)
    stream, z, total_bytes = open_xml(path)
    runs = merged = existing = metrics = workouts_seen = records_seen = samples_staged = 0
    running_seen = non_running = relevant_records = 0
    rejected: dict[str, int] = {}
    metric_seen = {"resting_hr": 0, "hrv_sdnn": 0, "body_mass": 0, "vo2max": 0}
    metric_added = dict.fromkeys(metric_seen, 0)
    sample_staged_by_type = dict.fromkeys((v[0] for v in RUN_SAMPLE_TYPES.values()), 0)
    earliest = latest = None
    nights: dict[date, list[tuple[datetime, datetime]]] = {}
    # Temporary staging avoids retaining all heart-rate/running-dynamics samples
    # in RAM while still allowing us to associate records with workouts that may
    # appear later in Apple's export.xml.
    c.execute(
        "CREATE TEMP TABLE IF NOT EXISTS import_run_samples(metric_type TEXT,start_ts REAL,end_ts REAL,value REAL,unit TEXT,external_id TEXT)"
    )
    c.execute("DELETE FROM import_run_samples")
    if progress:
        progress("Entpacken", 0.03, {"records_seen": 0, "workouts_seen": 0})
    try:
        for _, e in ET.iterparse(stream, events=("end",)):
            tag = e.tag.split("}")[-1]
            if tag == "Workout":
                workouts_seen += 1
                activity = e.attrib.get("workoutActivityType")
                if activity in RUNNING_TYPES:
                    running_seen += 1
                else:
                    non_running += 1
                result = insert_run(c, e, cutoff)
                runs += int(bool(result and result[0] == "added"))
                merged += int(bool(result and result[0] == "merged"))
                existing += int(bool(result and result[0] == "existing"))
                if activity in RUNNING_TYPES and not result:
                    a = e.attrib
                    reason = "invalid_start_date"
                    try:
                        sd = parse_dt(a.get("startDate") or a.get("creationDate") or "")
                        if sd.date() < cutoff:
                            reason = "before_cutoff"
                        else:
                            dv, du = a.get("duration"), a.get("durationUnit")
                            if dv is None: dv, du = _workout_stat(e, "Duration")
                            ds = dur(dv, du)
                            if ds is None and a.get("endDate"): ds = (parse_dt(a["endDate"]) - sd).total_seconds()
                            xv, xu = a.get("totalDistance"), a.get("totalDistanceUnit")
                            if xv is None: xv, xu = _workout_stat(e, "Distance")
                            km = dist(xv, xu)
                            reason = "missing_distance" if km is None else "missing_duration" if ds is None else "non_positive_distance" if km <= 0 else "non_positive_duration"
                    except Exception:
                        pass
                    rejected[reason] = rejected.get(reason, 0) + 1
                e.clear()
            elif tag == "Record":
                records_seen += 1
                typ = e.attrib.get("type")
                if typ in METRIC_TYPES:
                    metric_seen[METRIC_TYPES[typ][0]] += 1
                sl = sleep_interval(e, cutoff)
                if sl:
                    relevant_records += 1
                    night, s, en = sl
                    nights.setdefault(night, []).append((s, en))
                elif insert_metric(c, e, cutoff):
                    metrics += 1
                    relevant_records += 1
                    metric_added[METRIC_TYPES[typ][0]] += 1
                elif stage_run_sample(c, e, cutoff):
                    samples_staged += 1
                    relevant_records += 1
                    sample_staged_by_type[RUN_SAMPLE_TYPES[typ][0]] += 1
                try:
                    seen_date = parse_dt(e.attrib.get("startDate") or e.attrib.get("creationDate") or "").date()
                    if seen_date >= cutoff and (typ in METRIC_TYPES or typ in RUN_SAMPLE_TYPES or typ == SLEEP_TYPE):
                        earliest = min(earliest, seen_date) if earliest else seen_date
                        latest = max(latest, seen_date) if latest else seen_date
                except Exception:
                    pass
                e.clear()
            if progress and (records_seen + workouts_seen) % 5000 == 0:
                ratio = min(1.0, _stream_position(stream) / max(1, total_bytes))
                progress(
                    "Health-Daten & Workouts",
                    0.06 + ratio * 0.70,
                    {
                        "records_seen": records_seen,
                        "workouts_seen": workouts_seen,
                        "runs_added": runs,
                        "samples_staged": samples_staged,
                    },
                )
        if progress:
            progress("Schlaf", 0.78, {"nights_seen": len(nights)})
        metrics += insert_sleep(c, nights)
        if progress:
            progress("Laufmetriken", 0.82, {"samples_staged": samples_staged})
        samples_added = attach_staged_samples(c, cutoff)
        route_result = import_routes(c, z, cutoff, progress)
        gps_points_added = route_result["gps_points_added"]
    except ET.ParseError as exc:
        raise ValueError(f"Apple-Health-XML konnte nicht gelesen werden: {exc}") from exc
    finally:
        stream.close()
        if z:
            z.close()
    if progress:
        progress("Import abgeschlossen", 0.95, {"runs_added": runs, "metrics_added": metrics})
    outside_period = rejected.get("before_cutoff", 0)
    invalid_reasons = {k: v for k, v in rejected.items() if k != "before_cutoff"}
    invalid_total = sum(invalid_reasons.values())
    rejected_total = sum(rejected.values())
    classification = "success"
    useful_runs = runs or merged or existing
    if ((running_seen and not useful_runs) or (workouts_seen and not running_seen) or
            (samples_staged and not samples_added and not useful_runs) or
            (route_result["routes_seen"] and not route_result["routes_attached"] and not useful_runs)):
        classification = "warning"
    return {
        "runs_added": runs,
        "runs_merged": merged,
        "runs_already_existing": existing,
        "running_workouts_rejected": rejected_total,
        "rejection_reasons": rejected,
        "running_workouts_seen_total": running_seen,
        "running_workouts_in_period": running_seen - outside_period,
        "running_workouts_outside_period": outside_period,
        "running_workouts_invalid": invalid_total,
        "invalid_rejection_reasons": invalid_reasons,
        "metrics_added": metrics,
        "run_samples_added": samples_added,
        "gps_points_added": gps_points_added,
        "workouts_seen": workouts_seen,
        "records_seen": records_seen,
        "relevant_records_seen": relevant_records,
        "running_workouts_seen": running_seen,
        "non_running_workouts_seen": non_running,
        "earliest_relevant_date_seen": earliest.isoformat() if earliest else None,
        "latest_relevant_date_seen": latest.isoformat() if latest else None,
        "metric_records_seen": metric_seen,
        "metric_records_added": metric_added,
        "sleep_intervals_seen": sum(len(v) for v in nights.values()),
        "sleep_nights_seen": len(nights),
        "sleep_nights_added": metrics - sum(metric_added.values()),
        "samples_staged": samples_staged,
        "samples_staged_by_type": sample_staged_by_type,
        **route_result,
        "classification": classification,
        "cutoff_date": cutoff.isoformat(),
        "months": months,
    }
