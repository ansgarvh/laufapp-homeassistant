from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

APP_VERSION = "0.1.9"
CURRENT_SCHEMA_VERSION = 4
LEGACY_V012_SCHEMA_VERSION = 1


def data_dir() -> Path:
    p = Path(os.environ.get("LAUFAPP_DATA_DIR", "/data"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def db_path() -> Path:
    return data_dir() / "laufapp.sqlite3"


def transfer_dir() -> Path:
    return Path(os.environ.get("LAUFAPP_TRANSFER_DIR", "/share/laufapp-transfer"))


def transfer_db_path() -> Path:
    return transfer_dir() / "laufapp.sqlite3"


def prepare_repository_transfer(path: Path | None = None) -> dict[str, Any]:
    """Create an integrity-checked one-time bridge for local -> Git repo install.

    Home Assistant uses the repository id as part of an app's persistent /data
    identity, so a local app and the same app from a custom repository do not
    automatically share /data. This snapshot lives only in Home Assistant's
    local /share mount and is consumed by the fresh repository installation.
    """
    source_path = path or db_path()
    if not source_path.is_file():
        raise FileNotFoundError("Laufapp-Datenbank nicht gefunden.")
    tdir = transfer_dir()
    tdir.mkdir(parents=True, exist_ok=True)
    final = transfer_db_path()
    temp = tdir / "laufapp.sqlite3.tmp"
    temp.unlink(missing_ok=True)
    src = connect(source_path)
    dst = sqlite3.connect(temp)
    try:
        src.backup(dst)
        dst.commit()
        if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Transfer-Backup ist nicht konsistent.")
    finally:
        src.close()
        dst.close()
    os.chmod(temp, 0o600)
    os.replace(temp, final)
    meta = {
        "app_version": APP_VERSION,
        "schema_version": CURRENT_SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "size_bytes": final.stat().st_size,
    }
    (tdir / "transfer.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    os.chmod(tdir / "transfer.json", 0o600)
    return meta


def adopt_repository_transfer_if_needed(path: Path | None = None) -> bool:
    """Adopt a prepared transfer only into an otherwise fresh app /data."""
    target = path or db_path()
    transfer = transfer_db_path()
    if target.exists() or not transfer.is_file():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(transfer)
    dest = sqlite3.connect(target)
    try:
        if source.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Vorbereitete Transfer-Datenbank ist beschädigt.")
        source.backup(dest)
        dest.commit()
        if dest.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Übernommene Datenbank ist beschädigt.")
    except Exception:
        dest.close()
        target.unlink(missing_ok=True)
        source.close()
        raise
    else:
        dest.close()
        source.close()
    transfer.unlink(missing_ok=True)
    (transfer_dir() / "transfer.json").unlink(missing_ok=True)
    return True


def connect(path: Path | None = None) -> sqlite3.Connection:
    c = sqlite3.connect(path or db_path(), check_same_thread=False, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=30000")
    return c


@contextmanager
def db_conn(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    c = connect(path)
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def _table_names(c: sqlite3.Connection) -> set[str]:
    return {
        str(r[0])
        for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }


def _detect_schema_version(c: sqlite3.Connection) -> int:
    version = int(c.execute("PRAGMA user_version").fetchone()[0])
    if version:
        return version
    # v0.1.0-v0.1.2 had no explicit schema version. Presence of the settings
    # table uniquely identifies that legacy layout for our migration path.
    if "settings" in _table_names(c):
        return LEGACY_V012_SCHEMA_VERSION
    return 0


def _schema_sql_v2() -> str:
    return '''
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS races(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,distance_km REAL NOT NULL,race_date TEXT NOT NULL,goal_seconds INTEGER NOT NULL,target_source TEXT NOT NULL DEFAULT 'user',active INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS shoes(id INTEGER PRIMARY KEY AUTOINCREMENT,brand TEXT NOT NULL DEFAULT '',model TEXT NOT NULL,nickname TEXT NOT NULL DEFAULT '',start_km REAL NOT NULL DEFAULT 0,archived INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY AUTOINCREMENT,external_id TEXT UNIQUE,started_at TEXT NOT NULL,ended_at TEXT,distance_km REAL NOT NULL,duration_s REAL NOT NULL,avg_hr REAL,elevation_m REAL,calories REAL,source TEXT NOT NULL DEFAULT 'manual',rpe INTEGER,shoe_id INTEGER,notes TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(shoe_id) REFERENCES shoes(id) ON DELETE SET NULL);
    CREATE INDEX IF NOT EXISTS idx_runs_started_at ON runs(started_at);
    CREATE TABLE IF NOT EXISTS health_metrics(id INTEGER PRIMARY KEY AUTOINCREMENT,external_id TEXT UNIQUE,metric_type TEXT NOT NULL,start_at TEXT NOT NULL,end_at TEXT,value REAL NOT NULL,unit TEXT NOT NULL DEFAULT '',source TEXT NOT NULL DEFAULT 'apple_health',created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE INDEX IF NOT EXISTS idx_health_metric_time ON health_metrics(metric_type,start_at);
    CREATE TABLE IF NOT EXISTS workouts(id INTEGER PRIMARY KEY AUTOINCREMENT,week_start TEXT NOT NULL,origin_week_start TEXT NOT NULL,scheduled_date TEXT NOT NULL,workout_type TEXT NOT NULL,title TEXT NOT NULL,distance_km REAL NOT NULL,pace_low_s_per_km REAL,pace_high_s_per_km REAL,details_json TEXT NOT NULL DEFAULT '{}',status TEXT NOT NULL DEFAULT 'planned',linked_run_id INTEGER,manual_override INTEGER NOT NULL DEFAULT 0,modified_by TEXT NOT NULL DEFAULT 'engine',generation_version TEXT,plan_generation_id TEXT,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(linked_run_id) REFERENCES runs(id) ON DELETE SET NULL);
    CREATE INDEX IF NOT EXISTS idx_workouts_week ON workouts(week_start);
    CREATE TABLE IF NOT EXISTS performance_marks(id INTEGER PRIMARY KEY AUTOINCREMENT,distance_km REAL NOT NULL,duration_s REAL NOT NULL,mark_date TEXT NOT NULL,source TEXT NOT NULL DEFAULT 'manual',label TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS prediction_history(id INTEGER PRIMARY KEY AUTOINCREMENT,race_distance_km REAL NOT NULL,predicted_seconds REAL NOT NULL,low_seconds REAL NOT NULL,high_seconds REAL NOT NULL,confidence REAL NOT NULL,source TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS suggestions(id INTEGER PRIMARY KEY AUTOINCREMENT,suggestion_type TEXT NOT NULL,title TEXT NOT NULL,rationale TEXT NOT NULL,payload_json TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,resolved_at TEXT);
    CREATE TABLE IF NOT EXISTS chat_messages(id INTEGER PRIMARY KEY AUTOINCREMENT,role TEXT NOT NULL,text TEXT NOT NULL,meta_json TEXT NOT NULL DEFAULT '{}',created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS ai_usage(id INTEGER PRIMARY KEY AUTOINCREMENT,usage_kind TEXT NOT NULL,model TEXT NOT NULL,input_tokens INTEGER NOT NULL DEFAULT 0,output_tokens INTEGER NOT NULL DEFAULT 0,web_searches INTEGER NOT NULL DEFAULT 0,estimated_cost_eur REAL NOT NULL DEFAULT 0,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS plan_reviews(id INTEGER PRIMARY KEY AUTOINCREMENT,week_start TEXT NOT NULL UNIQUE,review_text TEXT NOT NULL,sources_json TEXT NOT NULL DEFAULT '[]',suggestion_id INTEGER,model TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(suggestion_id) REFERENCES suggestions(id) ON DELETE SET NULL);

    CREATE TABLE IF NOT EXISTS import_jobs(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      job_uuid TEXT NOT NULL UNIQUE,
      import_type TEXT NOT NULL,
      original_name TEXT NOT NULL DEFAULT '',
      source_path TEXT,
      file_size INTEGER NOT NULL DEFAULT 0,
      status TEXT NOT NULL DEFAULT 'queued',
      phase TEXT NOT NULL DEFAULT 'queued',
      progress REAL NOT NULL DEFAULT 0,
      result_json TEXT NOT NULL DEFAULT '{}',
      error_text TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      started_at TEXT,
      finished_at TEXT,
      replace_existing INTEGER NOT NULL DEFAULT 0
    );
    CREATE INDEX IF NOT EXISTS idx_import_jobs_created ON import_jobs(created_at DESC);

    CREATE TABLE IF NOT EXISTS run_samples(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      external_id TEXT NOT NULL UNIQUE,
      run_id INTEGER NOT NULL,
      metric_type TEXT NOT NULL,
      sampled_at TEXT NOT NULL,
      value REAL NOT NULL,
      unit TEXT NOT NULL DEFAULT '',
      source TEXT NOT NULL DEFAULT 'apple_health',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_run_samples_run_metric_time ON run_samples(run_id,metric_type,sampled_at);

    CREATE TABLE IF NOT EXISTS gps_points(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      run_id INTEGER NOT NULL,
      sampled_at TEXT NOT NULL,
      latitude REAL NOT NULL,
      longitude REAL NOT NULL,
      elevation_m REAL,
      sequence INTEGER NOT NULL,
      source TEXT NOT NULL DEFAULT 'apple_health',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE,
      UNIQUE(run_id,source,sequence)
    );
    CREATE INDEX IF NOT EXISTS idx_gps_points_run_seq ON gps_points(run_id,sequence);

    CREATE TABLE IF NOT EXISTS migration_log(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      from_version INTEGER NOT NULL,
      to_version INTEGER NOT NULL,
      app_version TEXT NOT NULL,
      backup_path TEXT,
      migrated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    '''


def _defaults() -> dict[str, Any]:
    return {
        "app_version": APP_VERSION,
        "schema_version": CURRENT_SCHEMA_VERSION,
        "setup_completed": False,
        "training_days": [1, 3, 4, 6],
        "training_volume_profile": "steady",
        "training_difficulty": "balanced",
        "quality_sessions_per_week": 2,
        "max_weekly_km_mode": "auto",
        "baseline_weekly_km": 40.0,
        "max_long_run_km": 35.0,
        "max_long_run_share": 0.45,
        "monthly_ai_budget_eur": 10.0,
        "coach_model": "gpt-5.6-terra",
        "vision_model": "gpt-5.6-luna",
        "evidence_search": True,
        "timezone": "Europe/Berlin",
    }


def _ensure_legacy_compat(c: sqlite3.Connection) -> None:
    """Small idempotent repair for databases created before v0.1.2."""
    if "workouts" not in _table_names(c):
        return
    cols = {r["name"] for r in c.execute("PRAGMA table_info(workouts)").fetchall()}
    if "origin_week_start" not in cols:
        c.execute("ALTER TABLE workouts ADD COLUMN origin_week_start TEXT")
        c.execute(
            "UPDATE workouts SET origin_week_start=week_start WHERE origin_week_start IS NULL"
        )


def _backup_before_migration(
    c: sqlite3.Connection, from_version: int, to_version: int
) -> Path:
    backup_dir = data_dir() / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = backup_dir / f"laufapp-pre-schema{from_version}-to{to_version}-{stamp}.sqlite3"
    target = sqlite3.connect(path)
    try:
        c.backup(target)
        check = target.execute("PRAGMA integrity_check").fetchone()[0]
        if check != "ok":
            raise RuntimeError(f"Migration-Backup ist nicht konsistent: {check}")
        target.commit()
    finally:
        target.close()
    return path


def _apply_migration_1_to_2(c: sqlite3.Connection) -> None:
    # The v2 CREATE statements are idempotent, so applying the target schema is
    # deliberately additive. Existing user data is never dropped or rewritten.
    _ensure_legacy_compat(c)
    c.executescript(_schema_sql_v2())


def _apply_migration_2_to_3(c: sqlite3.Connection) -> None:
    if "replace_existing" not in {r["name"] for r in c.execute("PRAGMA table_info(import_jobs)")}:
        c.execute("ALTER TABLE import_jobs ADD COLUMN replace_existing INTEGER NOT NULL DEFAULT 0")


def _apply_migration_3_to_4(c: sqlite3.Connection) -> None:
    cols={r["name"] for r in c.execute("PRAGMA table_info(workouts)")}
    additions=(("manual_override","INTEGER NOT NULL DEFAULT 0"),("modified_by","TEXT NOT NULL DEFAULT 'engine'"),("generation_version","TEXT"),("plan_generation_id","TEXT"))
    for name,definition in additions:
        if name not in cols:c.execute(f"ALTER TABLE workouts ADD COLUMN {name} {definition}")


def _write_defaults_and_versions(c: sqlite3.Connection) -> None:
    for k, v in _defaults().items():
        c.execute(
            "INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",
            (k, json.dumps(v)),
        )
    # Version markers must follow the installed code, unlike user preferences.
    c.execute(
        "INSERT INTO settings(key,value) VALUES('app_version',?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (json.dumps(APP_VERSION),),
    )
    c.execute(
        "INSERT INTO settings(key,value) VALUES('schema_version',?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (json.dumps(CURRENT_SCHEMA_VERSION),),
    )


def init_db(path: Path | None = None) -> dict[str, Any]:
    """Initialize or migrate the DB without destroying existing health data.

    Returns migration metadata for logging/tests. Any migration is preceded by a
    SQLite online backup. DDL runs transactionally; on failure the app startup
    fails rather than continuing with a partially migrated schema.
    """
    p = path or db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    c = connect(p)
    backup_path: Path | None = None
    from_version = 0
    original_version = 0
    try:
        from_version = _detect_schema_version(c)
        original_version = from_version
        if from_version > CURRENT_SCHEMA_VERSION:
            raise RuntimeError(
                f"Datenbankschema {from_version} ist neuer als diese Laufapp "
                f"(Schema {CURRENT_SCHEMA_VERSION}). Downgrade abgebrochen."
            )

        if from_version == 0:
            c.executescript(_schema_sql_v2())
            _write_defaults_and_versions(c)
            c.execute(f"PRAGMA user_version={CURRENT_SCHEMA_VERSION}")
            c.commit()
            return {
                "from_version": 0,
                "to_version": CURRENT_SCHEMA_VERSION,
                "backup_path": None,
                "created": True,
            }

        if from_version < CURRENT_SCHEMA_VERSION:
            backup_path = _backup_before_migration(
                c, from_version, CURRENT_SCHEMA_VERSION
            )
            c.execute("BEGIN IMMEDIATE")
            migrated_from = from_version
            if from_version == 1:
                _apply_migration_1_to_2(c)
                from_version = 2
            if from_version == 2:
                _apply_migration_2_to_3(c)
                from_version = 3
            if from_version == 3:
                _apply_migration_3_to_4(c)
                from_version = 4
            if from_version != CURRENT_SCHEMA_VERSION:
                raise RuntimeError(f"Kein Migrationspfad ab Schema {from_version}.")
            _write_defaults_and_versions(c)
            c.execute(f"PRAGMA user_version={CURRENT_SCHEMA_VERSION}")
            c.execute(
                "INSERT INTO migration_log(from_version,to_version,app_version,backup_path) "
                "VALUES(?,?,?,?)",
                (
                    migrated_from,
                    CURRENT_SCHEMA_VERSION,
                    APP_VERSION,
                    str(backup_path),
                ),
            )
            c.commit()
        else:
            # Safe/idempotent schema repair. No destructive SQL.
            c.executescript(_schema_sql_v2())
            _apply_migration_2_to_3(c)
            _apply_migration_3_to_4(c)
            _ensure_legacy_compat(c)
            _write_defaults_and_versions(c)
            c.execute(f"PRAGMA user_version={CURRENT_SCHEMA_VERSION}")
            c.commit()

        check = c.execute("PRAGMA integrity_check").fetchone()[0]
        if check != "ok":
            raise RuntimeError(f"SQLite-Integritätsprüfung fehlgeschlagen: {check}")
        return {
            "from_version": original_version,
            "to_version": CURRENT_SCHEMA_VERSION,
            "backup_path": str(backup_path) if backup_path else None,
            "created": False,
        }
    except Exception:
        c.rollback()
        if backup_path and backup_path.is_file():
            # Restore the exact pre-migration database before failing startup.
            # This keeps a failed migration from leaving a partially changed DB.
            source = sqlite3.connect(backup_path)
            try:
                source.backup(c)
                c.commit()
            finally:
                source.close()
        raise
    finally:
        c.close()


def get_setting(c: sqlite3.Connection, key: str, default: Any = None) -> Any:
    r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    if not r:
        return default
    try:
        return json.loads(r["value"])
    except json.JSONDecodeError:
        return r["value"]


def set_setting(c: sqlite3.Connection, key: str, value: Any) -> None:
    c.execute(
        "INSERT INTO settings(key,value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, json.dumps(value)),
    )


def rows(result_rows):
    return [dict(r) for r in result_rows]
