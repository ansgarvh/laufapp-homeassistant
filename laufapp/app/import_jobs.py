from __future__ import annotations

import json
import os
import threading
import traceback
import uuid
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from db import data_dir, db_conn, rows
from health_import import import_apple_health
from training import predict_all, mark_plan_stale


_DIAGNOSTIC_LOCK = threading.Lock()


def _status_dir() -> Path:
    p = data_dir() / "import_status"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _imports_dir() -> Path:
    p = data_dir() / "imports"
    p.mkdir(parents=True, exist_ok=True)
    return p


def import_storage_path(job_uuid: str, suffix: str) -> Path:
    safe_suffix = suffix if suffix in {".zip", ".xml"} else ".zip"
    return _imports_dir() / f"apple-health-{job_uuid}{safe_suffix}"


def _status_path(job_uuid: str) -> Path:
    return _status_dir() / f"{job_uuid}.json"


def _diagnostic_path(job_uuid: str) -> Path:
    return _status_dir() / f"{job_uuid}.diagnostics.jsonl"


def _write_live_status(job_uuid: str, payload: dict[str, Any]) -> None:
    path = _status_path(job_uuid)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _read_live_status(job_uuid: str) -> dict[str, Any]:
    try:
        return json.loads(_status_path(job_uuid).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _clear_live_status(job_uuid: str) -> None:
    _status_path(job_uuid).unlink(missing_ok=True)


def _append_diagnostic(job_uuid: str, event: str, **payload: Any) -> None:
    """Append a persistent diagnostic event without ever breaking an import."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **payload,
    }
    try:
        line = json.dumps(entry, ensure_ascii=False, default=str) + "\n"
        with _DIAGNOSTIC_LOCK:
            with _diagnostic_path(job_uuid).open("a", encoding="utf-8") as fh:
                fh.write(line)
    except (OSError, TypeError, ValueError):
        # Diagnostics must remain strictly side-effect-only. The health import
        # must never fail because its diagnostic file cannot be written.
        pass


def _read_diagnostics(job_uuid: str, limit: int = 200) -> list[dict[str, Any]]:
    try:
        with _diagnostic_path(job_uuid).open("r", encoding="utf-8") as fh:
            tail = deque(fh, maxlen=max(1, min(500, int(limit))))
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in tail:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            out.append(item)
    return out


def create_import_job(original_name: str, source_path: Path, file_size: int) -> dict[str, Any]:
    job_uuid = str(uuid.uuid4())
    # Source file is written to a temporary UUID by the API first and renamed to
    # this final job UUID before calling here.
    with db_conn() as c:
        cur = c.execute(
            "INSERT INTO import_jobs(job_uuid,import_type,original_name,source_path,file_size,status,phase,progress) "
            "VALUES(?,?,?,?,?,'queued','Upload abgeschlossen',1)",
            (job_uuid, "apple_health", original_name, str(source_path), file_size),
        )
        job_id = int(cur.lastrowid)
    payload = {
        "id": job_id,
        "job_uuid": job_uuid,
        "status": "queued",
        "phase": "Upload abgeschlossen",
        "progress": 1.0,
    }
    _write_live_status(job_uuid, payload)
    _append_diagnostic(
        job_uuid,
        "queued",
        job_id=job_id,
        phase="Upload abgeschlossen",
        progress=1.0,
        original_name=original_name,
        file_size=file_size,
        replace_existing=False,
    )
    return payload


def create_import_job_with_uuid(job_uuid: str, original_name: str, source_path: Path, file_size: int, replace_existing: bool = False) -> dict[str, Any]:
    with db_conn() as c:
        cur = c.execute(
            "INSERT INTO import_jobs(job_uuid,import_type,original_name,source_path,file_size,status,phase,progress,replace_existing) "
            "VALUES(?,?,?,?,?,'queued','Upload abgeschlossen',1,?)",
            (job_uuid, "apple_health", original_name, str(source_path), file_size, int(replace_existing)),
        )
        job_id = int(cur.lastrowid)
    payload = {
        "id": job_id,
        "job_uuid": job_uuid,
        "status": "queued",
        "phase": "Upload abgeschlossen",
        "progress": 1.0,
        "replace_existing": replace_existing,
    }
    _write_live_status(job_uuid, payload)
    _append_diagnostic(
        job_uuid,
        "queued",
        job_id=job_id,
        phase="Upload abgeschlossen",
        progress=1.0,
        original_name=original_name,
        file_size=file_size,
        replace_existing=bool(replace_existing),
    )
    return payload


def _snapshot(c, source: str) -> None:
    for p in predict_all(c):
        ex = c.execute(
            "SELECT id FROM prediction_history WHERE race_distance_km=? AND source=? AND substr(created_at,1,10)=?",
            (p["distance_km"], source, date.today().isoformat()),
        ).fetchone()
        args = (p["predicted_seconds"], p["low_seconds"], p["high_seconds"], p["confidence"])
        if ex:
            c.execute(
                "UPDATE prediction_history SET predicted_seconds=?,low_seconds=?,high_seconds=?,confidence=?,created_at=CURRENT_TIMESTAMP WHERE id=?",
                (*args, ex["id"]),
            )
        else:
            c.execute(
                "INSERT INTO prediction_history(race_distance_km,predicted_seconds,low_seconds,high_seconds,confidence,source) VALUES(?,?,?,?,?,?)",
                (p["distance_km"], *args, source),
            )


def _job_dict(r) -> dict[str, Any]:
    d = dict(r)
    try:
        d["result"] = json.loads(d.pop("result_json"))
    except Exception:
        d["result"] = {}
    live = _read_live_status(d["job_uuid"])
    if d["status"] in {"queued", "processing"} and live:
        for k in ("status", "phase", "progress", "detail"):
            if k in live:
                d[k] = live[k]
    d["progress"] = max(0.0, min(1.0, float(d.get("progress") or 0)))
    return d


def get_job(job_id: int) -> dict[str, Any] | None:
    with db_conn() as c:
        r = c.execute("SELECT * FROM import_jobs WHERE id=?", (job_id,)).fetchone()
        return _job_dict(r) if r else None


def latest_job() -> dict[str, Any] | None:
    with db_conn() as c:
        r = c.execute("SELECT * FROM import_jobs ORDER BY id DESC LIMIT 1").fetchone()
        return _job_dict(r) if r else None


def list_jobs(limit: int = 20) -> list[dict[str, Any]]:
    with db_conn() as c:
        rr = c.execute("SELECT * FROM import_jobs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [_job_dict(r) for r in rr]


def job_diagnostics(job_id: int, limit: int = 200) -> dict[str, Any]:
    with db_conn() as c:
        r = c.execute(
            "SELECT id,job_uuid,status,phase,progress,error_text,created_at,started_at,finished_at,updated_at "
            "FROM import_jobs WHERE id=?",
            (job_id,),
        ).fetchone()
    if not r:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Import nicht gefunden.")
    d = dict(r)
    d["events"] = _read_diagnostics(d["job_uuid"], limit)
    return d


def _process_job(job_id: int) -> None:
    job_uuid: str | None = None
    last_state: dict[str, Any] = {"phase": "Start", "progress": 0.0, "detail": {}}
    try:
        with db_conn() as c:
            row = c.execute("SELECT * FROM import_jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                return
            source_path = Path(row["source_path"] or "")
            job_uuid = row["job_uuid"]
            if not source_path.is_file():
                c.execute(
                    "UPDATE import_jobs SET status='failed',phase='Fehler',progress=0,error_text=?,updated_at=CURRENT_TIMESTAMP,finished_at=CURRENT_TIMESTAMP WHERE id=?",
                    ("Importdatei fehlt; bitte den Export erneut hochladen.", job_id),
                )
                _append_diagnostic(
                    job_uuid,
                    "failed",
                    job_id=job_id,
                    phase="Dateiprüfung",
                    progress=0.0,
                    error_type="FileNotFoundError",
                    error="Importdatei fehlt; bitte den Export erneut hochladen.",
                )
                _clear_live_status(job_uuid)
                return
            c.execute(
                "UPDATE import_jobs SET status='processing',phase='Entpacken',progress=.02,error_text=NULL,started_at=COALESCE(started_at,CURRENT_TIMESTAMP),updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (job_id,),
            )

        last_state = {"phase": "Entpacken", "progress": 0.02, "detail": {}}
        _append_diagnostic(job_uuid, "started", job_id=job_id, **last_state)
        diagnostic_phase: str | None = None
        diagnostic_bucket = -1

        def report(phase: str, progress: float, detail: dict[str, Any]) -> None:
            nonlocal diagnostic_phase, diagnostic_bucket, last_state
            bounded = round(max(0.0, min(0.97, progress)), 4)
            last_state = {"phase": phase, "progress": bounded, "detail": detail}
            _write_live_status(
                job_uuid,
                {
                    "status": "processing",
                    "phase": phase,
                    "progress": bounded,
                    "detail": detail,
                },
            )
            # Persist phase changes plus 5 %-progress buckets. This keeps even a
            # multi-hour import diagnosable without producing an unbounded log.
            bucket = int(bounded * 20)
            if phase != diagnostic_phase or bucket > diagnostic_bucket:
                _append_diagnostic(
                    job_uuid,
                    "progress",
                    job_id=job_id,
                    phase=phase,
                    progress=bounded,
                    detail=detail,
                )
                diagnostic_phase = phase
                diagnostic_bucket = bucket

        # One DB transaction for the actual health data: a malformed/failed import
        # rolls back rather than leaving a half-imported dataset. Live progress is
        # written to a small status file so it remains visible without committing
        # partial health records.
        with db_conn() as c:
            replace_existing = bool(row["replace_existing"])
            preserved = []
            if replace_existing:
                preserved = [dict(r) for r in c.execute(
                    "SELECT r.id,r.external_id,r.rpe,r.shoe_id,r.notes,"
                    "(SELECT group_concat(id) FROM workouts WHERE linked_run_id=r.id) linked_workouts "
                    "FROM runs r WHERE r.source='apple_health' AND r.external_id IS NOT NULL"
                )]
                # Apple samples/routes may be attached to a conservatively
                # enriched manual run, so clear them by provenance as well.
                c.execute("DELETE FROM run_samples WHERE source='apple_health'")
                c.execute("DELETE FROM gps_points WHERE source='apple_health'")
                c.execute("DELETE FROM health_metrics WHERE source='apple_health'")
                c.execute("DELETE FROM runs WHERE source='apple_health'")
                c.execute("DELETE FROM prediction_history WHERE source='apple_health_import'")
            result = import_apple_health(c, source_path, 24, progress=report)
            if replace_existing:
                for old in preserved:
                    c.execute(
                        "UPDATE runs SET rpe=?,shoe_id=?,notes=? WHERE external_id=?",
                        (old["rpe"], old["shoe_id"], old["notes"], old["external_id"]),
                    )
                    replacement = c.execute("SELECT id FROM runs WHERE external_id=?", (old["external_id"],)).fetchone()
                    if replacement and old["linked_workouts"]:
                        ids = [int(x) for x in old["linked_workouts"].split(",")]
                        c.executemany("UPDATE workouts SET linked_run_id=? WHERE id=?", ((replacement["id"], wid) for wid in ids))
            result["import_mode"] = "replace" if replace_existing else "deduplicate"
            report("Prognosen", 0.97, {"runs_added": result.get("runs_added", 0)})
            _snapshot(c, "apple_health_import")
            result["predictions"] = predict_all(c)
            if result.get("runs_added", 0):
                mark_plan_stale(c, "Neue Apple-Health-Läufe verfügbar")
        with db_conn() as c:
            c.execute(
                "UPDATE import_jobs SET status='completed',phase='Fertig',progress=1,result_json=?,error_text=NULL,updated_at=CURRENT_TIMESTAMP,finished_at=CURRENT_TIMESTAMP,source_path=NULL WHERE id=?",
                (json.dumps(result, ensure_ascii=False), job_id),
            )
        _append_diagnostic(
            job_uuid,
            "completed",
            job_id=job_id,
            phase="Fertig",
            progress=1.0,
            summary={
                "runs_added": result.get("runs_added", 0),
                "metrics_added": result.get("metrics_added", 0),
                "samples_added": result.get("samples_added", 0),
                "gps_points_added": result.get("gps_points_added", 0),
                "import_mode": result.get("import_mode"),
            },
        )
        source_path.unlink(missing_ok=True)
        _clear_live_status(job_uuid)
    except Exception as exc:
        trace = traceback.format_exc()
        message = str(exc)[:4000] or exc.__class__.__name__
        print(
            f"APPLE_HEALTH_IMPORT_FAILED job_id={job_id} job_uuid={job_uuid or 'unknown'} "
            f"phase={last_state.get('phase', 'unknown')}\n{trace}",
            flush=True,
        )
        if job_uuid:
            _append_diagnostic(
                job_uuid,
                "failed",
                job_id=job_id,
                phase=last_state.get("phase", "unknown"),
                progress=last_state.get("progress", 0.0),
                detail=last_state.get("detail", {}),
                error_type=exc.__class__.__name__,
                error=message,
                traceback=trace,
            )
        try:
            with db_conn() as c:
                c.execute(
                    "UPDATE import_jobs SET status='failed',phase='Fehler',progress=0,error_text=?,updated_at=CURRENT_TIMESTAMP,finished_at=CURRENT_TIMESTAMP WHERE id=?",
                    (message, job_id),
                )
        except Exception:
            print(
                f"APPLE_HEALTH_IMPORT_STATUS_UPDATE_FAILED job_id={job_id}\n{traceback.format_exc()}",
                flush=True,
            )
        if job_uuid:
            _clear_live_status(job_uuid)
    finally:
        MANAGER.finished(job_id)


class ImportManager:
    def __init__(self) -> None:
        self._executor: ThreadPoolExecutor | None = None
        self._active: set[int] = set()
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            if self._executor is None:
                self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="health-import")
        # Any processing job interrupted by an app update/restart is safe to
        # retry: the health-data transaction would have rolled back and all
        # inserts are deduplicated.
        with db_conn() as c:
            interrupted = [
                (int(r["id"]), r["job_uuid"])
                for r in c.execute(
                    "SELECT id,job_uuid FROM import_jobs WHERE status='processing' AND source_path IS NOT NULL ORDER BY id"
                ).fetchall()
            ]
            c.execute(
                "UPDATE import_jobs SET status='queued',phase='Wird fortgesetzt',progress=0,updated_at=CURRENT_TIMESTAMP "
                "WHERE status='processing' AND source_path IS NOT NULL"
            )
            pending = [int(r["id"]) for r in c.execute("SELECT id FROM import_jobs WHERE status='queued' AND source_path IS NOT NULL ORDER BY id").fetchall()]
        for interrupted_id, interrupted_uuid in interrupted:
            _append_diagnostic(
                interrupted_uuid,
                "resumed_after_restart",
                job_id=interrupted_id,
                phase="Wird fortgesetzt",
                progress=0.0,
            )
        for job_id in pending:
            self.submit(job_id)

    def submit(self, job_id: int) -> None:
        with self._lock:
            if job_id in self._active:
                return
            if self._executor is None:
                self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="health-import")
            self._active.add(job_id)
            executor = self._executor
        executor.submit(_process_job, job_id)

    def finished(self, job_id: int) -> None:
        with self._lock:
            self._active.discard(job_id)

    def stop(self) -> None:
        with self._lock:
            executor = self._executor
            self._executor = None
        if executor:
            executor.shutdown(wait=False, cancel_futures=False)


MANAGER = ImportManager()


def retry_job(job_id: int) -> dict[str, Any]:
    with db_conn() as c:
        row = c.execute("SELECT * FROM import_jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            raise KeyError("Import nicht gefunden.")
        if row["status"] != "failed":
            raise ValueError("Nur fehlgeschlagene Importe können erneut gestartet werden.")
        if not row["source_path"] or not Path(row["source_path"]).is_file():
            raise ValueError("Die Importdatei ist nicht mehr vorhanden. Bitte erneut hochladen.")
        c.execute(
            "UPDATE import_jobs SET status='queued',phase='Wird erneut gestartet',progress=0,error_text=NULL,finished_at=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (job_id,),
        )
        job_uuid = row["job_uuid"]
    _append_diagnostic(
        job_uuid,
        "retry_requested",
        job_id=job_id,
        phase="Wird erneut gestartet",
        progress=0.0,
    )
    MANAGER.submit(job_id)
    return get_job(job_id) or {}
