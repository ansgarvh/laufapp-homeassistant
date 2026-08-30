from __future__ import annotations

import zipfile
from datetime import datetime, timezone
from pathlib import Path

from defusedxml import ElementTree as DefusedET
from defusedxml.common import DefusedXmlException

import health_import as health

MAX_ZIP_ENTRIES = 20_000
MAX_COMPRESSION_RATIO = 250.0
MAX_TOTAL_GPX_BYTES = 2 * 1024**3
MAX_GPX_FILE_BYTES = 256 * 1024**2
MAX_GPX_POINTS_PER_ROUTE = 250_000

_original_open_xml = health.open_xml


def _ratio(info: zipfile.ZipInfo) -> float:
    if info.file_size <= 0:
        return 1.0
    if info.compress_size <= 0:
        return float("inf")
    return info.file_size / info.compress_size


def hardened_open_xml(path: Path):
    if not zipfile.is_zipfile(path):
        return _original_open_xml(path)
    z = zipfile.ZipFile(path)
    try:
        infos = z.infolist()
        if len(infos) > MAX_ZIP_ENTRIES:
            raise ValueError("Der Apple-Health-ZIP enthält ungewöhnlich viele Dateien.")
        if any(info.flag_bits & 0x1 for info in infos):
            raise ValueError("Verschlüsselte Dateien im Apple-Health-ZIP werden nicht akzeptiert.")
        exports = [info for info in infos if info.filename.lower().endswith("export.xml")]
        if len(exports) != 1:
            raise ValueError("Der Apple-Health-ZIP muss genau eine export.xml enthalten.")
        export = exports[0]
        if export.file_size > 8 * 1024**3:
            raise ValueError("Die entpackte export.xml ist größer als 8 GB.")
        if _ratio(export) > MAX_COMPRESSION_RATIO:
            raise ValueError("Die export.xml ist ungewöhnlich stark komprimiert; Import aus Sicherheitsgründen abgebrochen.")
        gpx_infos = [info for info in infos if info.filename.lower().endswith(".gpx")]
        if sum(info.file_size for info in gpx_infos) > MAX_TOTAL_GPX_BYTES:
            raise ValueError("Die GPX-Routendaten im Health-Export sind ungewöhnlich groß.")
        for info in gpx_infos:
            if info.file_size > MAX_GPX_FILE_BYTES:
                raise ValueError("Eine GPX-Route im Health-Export ist ungewöhnlich groß.")
            if _ratio(info) > MAX_COMPRESSION_RATIO:
                raise ValueError("Eine GPX-Route ist ungewöhnlich stark komprimiert; Import aus Sicherheitsgründen abgebrochen.")
        return z.open(export), z, int(export.file_size)
    except Exception:
        z.close()
        raise


def hardened_import_routes(c, z, cutoff, progress=None):
    if z is None:
        return {"routes_seen": 0, "routes_attached": 0, "routes_unmatched": 0, "gps_points_added": 0}
    route_names = [
        n for n in z.namelist()
        if n.lower().endswith(".gpx") and ("route" in n.lower() or "workout" in n.lower())
    ]
    added = attached = unmatched = 0
    for idx, name in enumerate(route_names):
        if progress:
            progress("Routen", 0.86 + 0.08 * (idx / max(1, len(route_names))), {"routes_seen": idx})
        points = []
        try:
            with z.open(name) as raw:
                for point in health._iter_gpx_points(raw):
                    if len(points) >= MAX_GPX_POINTS_PER_ROUTE:
                        raise ValueError("Eine GPX-Route enthält ungewöhnlich viele Punkte.")
                    seq, timestamp, lat, lon, elevation = point
                    if not (-90 <= float(lat) <= 90 and -180 <= float(lon) <= 180):
                        raise ValueError("Ungültige GPS-Koordinaten im Apple-Health-Export.")
                    if elevation is not None and not (-1000 <= float(elevation) <= 12000):
                        raise ValueError("Ungültige GPS-Höhe im Apple-Health-Export.")
                    points.append((seq, timestamp, lat, lon, elevation))
        except (DefusedXmlException, health.ET.ParseError):
            unmatched += 1
            continue
        if not points:
            continue
        ts = health.epoch(points[0][1])
        if ts is None or datetime.fromtimestamp(ts, timezone.utc).date() < cutoff:
            continue
        run_id = health._find_run_for_timestamp(c, ts, cutoff)
        if not run_id:
            unmatched += 1
            continue
        attached += 1
        elevations = []
        for seq, timestamp, lat, lon, elevation in points:
            sampled = health.iso(timestamp)
            cur = c.execute(
                "INSERT OR IGNORE INTO gps_points(run_id,sampled_at,latitude,longitude,elevation_m,sequence,source) VALUES(?,?,?,?,?,?,'apple_health')",
                (run_id, sampled, lat, lon, elevation, seq),
            )
            added += int(bool(cur.rowcount))
            if elevation is not None:
                elevations.append(float(elevation))
        if elevations:
            gain = sum(max(0.0, b - a) for a, b in zip(elevations, elevations[1:]))
            c.execute("UPDATE runs SET elevation_m=COALESCE(elevation_m,?) WHERE id=?", (round(gain, 1), run_id))
    return {"routes_seen": len(route_names), "routes_attached": attached, "routes_unmatched": unmatched, "gps_points_added": added}


def install() -> None:
    # Replace the parser object used by both the top-level export.xml iterator
    # and the GPX helper. defusedxml preserves the iterparse API while forbidding
    # entity expansion and external references by default.
    health.ET = DefusedET
    health.open_xml = hardened_open_xml
    health.import_routes = hardened_import_routes
