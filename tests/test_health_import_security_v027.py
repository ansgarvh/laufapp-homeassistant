import io
import sqlite3
import zipfile
from datetime import date

from defusedxml.common import EntitiesForbidden

import health_import as health
import health_import_hardening_v027 as hardening


def test_hardened_zip_rejects_extreme_compression_ratio(tmp_path):
    path = tmp_path / "bomb.zip"
    # Highly repetitive XML compresses to a tiny archive and models a classic
    # decompression-amplification payload without allocating a huge fixture.
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("apple_health_export/export.xml", b"<HealthData>" + b"A" * (2 * 1024 * 1024) + b"</HealthData>")
    try:
        hardening.hardened_open_xml(path)
        assert False, "extreme compression ratio must be rejected"
    except ValueError as exc:
        assert "stark komprimiert" in str(exc)


def test_hardened_zip_rejects_ambiguous_export_xml(tmp_path):
    path = tmp_path / "ambiguous.zip"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as z:
        z.writestr("a/export.xml", "<HealthData/>")
        z.writestr("b/export.xml", "<HealthData/>")
    try:
        hardening.hardened_open_xml(path)
        assert False, "multiple export.xml files must be rejected"
    except ValueError as exc:
        assert "genau eine export.xml" in str(exc)


def test_defused_parser_rejects_entity_expansion():
    hardening.install()
    malicious = io.BytesIO(
        b'<!DOCTYPE x [<!ENTITY boom "expanded">]><HealthData><Record value="&boom;"/></HealthData>'
    )
    try:
        list(health.ET.iterparse(malicious, events=("end",)))
        assert False, "XML entities must be rejected"
    except EntitiesForbidden:
        pass


def test_hardened_route_rejects_excessive_point_count(monkeypatch):
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(
        """
        CREATE TABLE runs(id INTEGER PRIMARY KEY,started_at TEXT,ended_at TEXT,duration_s REAL,elevation_m REAL);
        CREATE TABLE gps_points(id INTEGER PRIMARY KEY AUTOINCREMENT,run_id INTEGER,sampled_at TEXT,latitude REAL,longitude REAL,elevation_m REAL,sequence INTEGER,source TEXT,UNIQUE(run_id,source,sequence));
        INSERT INTO runs(id,started_at,ended_at,duration_s) VALUES(1,'2026-08-30T08:00:00+00:00','2026-08-30T08:30:00+00:00',1800);
        """
    )
    gpx = b'''<?xml version="1.0"?><gpx><trk><trkseg>
    <trkpt lat="50.0" lon="6.0"><time>2026-08-30T08:00:01Z</time></trkpt>
    <trkpt lat="50.1" lon="6.1"><time>2026-08-30T08:00:02Z</time></trkpt>
    <trkpt lat="50.2" lon="6.2"><time>2026-08-30T08:00:03Z</time></trkpt>
    </trkseg></trk></gpx>'''
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED) as z:
        z.writestr("workout-route.gpx", gpx)
    buf.seek(0)
    monkeypatch.setattr(hardening, "MAX_GPX_POINTS_PER_ROUTE", 2)
    with zipfile.ZipFile(buf) as z:
        try:
            hardening.hardened_import_routes(c, z, date(2026, 1, 1))
            assert False, "route point limit must be enforced"
        except ValueError as exc:
            assert "viele Punkte" in str(exc)


def test_hardened_route_rejects_invalid_coordinates():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(
        """
        CREATE TABLE runs(id INTEGER PRIMARY KEY,started_at TEXT,ended_at TEXT,duration_s REAL,elevation_m REAL);
        CREATE TABLE gps_points(id INTEGER PRIMARY KEY AUTOINCREMENT,run_id INTEGER,sampled_at TEXT,latitude REAL,longitude REAL,elevation_m REAL,sequence INTEGER,source TEXT,UNIQUE(run_id,source,sequence));
        INSERT INTO runs(id,started_at,ended_at,duration_s) VALUES(1,'2026-08-30T08:00:00+00:00','2026-08-30T08:30:00+00:00',1800);
        """
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED) as z:
        z.writestr(
            "workout-route.gpx",
            '<gpx><trk><trkseg><trkpt lat="120" lon="6"><time>2026-08-30T08:00:01Z</time></trkpt></trkseg></trk></gpx>',
        )
    buf.seek(0)
    with zipfile.ZipFile(buf) as z:
        try:
            hardening.hardened_import_routes(c, z, date(2026, 1, 1))
            assert False, "invalid GPS coordinate must be rejected"
        except ValueError as exc:
            assert "GPS-Koordinaten" in str(exc)
