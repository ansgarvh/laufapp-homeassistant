import json
import sqlite3
from pathlib import Path


def create_v012_database(path: Path) -> None:
    """Create the exact v0.1.2 DB layout without depending on an old source tree."""
    schema=(Path(__file__).parent/'fixtures'/'v012_schema.sql').read_text(encoding='utf-8')
    c=sqlite3.connect(path)
    try:
        c.executescript(schema)
        defaults={
            'app_version':'0.1.2','setup_completed':True,'training_days':[1,3,4,6],
            'training_volume_profile':'steady','training_difficulty':'balanced',
            'baseline_weekly_km':40.0,'max_long_run_km':32.0,'max_long_run_share':0.45,
            'monthly_ai_budget_eur':10.0,'coach_model':'gpt-5.6-terra',
            'vision_model':'gpt-5.6-luna','evidence_search':True,'timezone':'Europe/Berlin',
        }
        c.executemany(
            "INSERT INTO settings(key,value) VALUES(?,?)",
            [(k,json.dumps(v)) for k,v in defaults.items()],
        )
        c.commit()
    finally:
        c.close()


def test_v012_database_migrates_with_backup_and_keeps_user_data(tmp_path, monkeypatch):
    dbfile=tmp_path/'data'/'laufapp.sqlite3';dbfile.parent.mkdir()
    create_v012_database(dbfile)
    with sqlite3.connect(dbfile) as raw:
        raw.row_factory=sqlite3.Row
        c=raw
        c.execute("INSERT INTO shoes(brand,model,nickname,start_km) VALUES('ASICS','Superblast 2','Daily',123.4)")
        sid=c.execute('SELECT id FROM shoes').fetchone()['id']
        c.execute("INSERT INTO runs(external_id,started_at,ended_at,distance_km,duration_s,avg_hr,elevation_m,source,rpe,shoe_id,notes) VALUES('legacy-run','2026-08-01T08:00:00+02:00','2026-08-01T09:00:00+02:00',12,3600,145,120,'apple_health',4,?,'keep me')",(sid,))
        c.execute("INSERT INTO health_metrics(external_id,metric_type,start_at,end_at,value,unit,source) VALUES('legacy-hrv','hrv_sdnn','2026-08-01T07:00:00+02:00','2026-08-01T07:00:00+02:00',54,'ms','apple_health')")
        c.execute("INSERT INTO performance_marks(distance_km,duration_s,mark_date,source,label) VALUES(10,2580,'2026-07-01','manual','PB')")

    import db
    monkeypatch.setenv('LAUFAPP_DATA_DIR',str(dbfile.parent))
    result=db.init_db(dbfile)
    assert result['from_version']==1 and result['to_version']==4
    backup=Path(result['backup_path']);assert backup.is_file()
    with sqlite3.connect(backup) as bc:
        assert bc.execute("SELECT COUNT(*) FROM runs").fetchone()[0]==1
        assert bc.execute("PRAGMA integrity_check").fetchone()[0]=='ok'
    with db.db_conn(dbfile) as c:
        assert c.execute('PRAGMA user_version').fetchone()[0]==4
        assert c.execute("SELECT COUNT(*) FROM runs WHERE external_id='legacy-run'").fetchone()[0]==1
        run=c.execute("SELECT * FROM runs WHERE external_id='legacy-run'").fetchone()
        assert run['rpe']==4 and run['notes']=='keep me' and run['shoe_id']==sid
        assert c.execute("SELECT value FROM health_metrics WHERE external_id='legacy-hrv'").fetchone()['value']==54
        assert c.execute("SELECT COUNT(*) FROM performance_marks").fetchone()[0]==1
        tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert {'import_jobs','run_samples','gps_points','migration_log'} <= tables
        assert json.loads(c.execute("SELECT value FROM settings WHERE key='app_version'").fetchone()['value'])=='0.1.8'
    # An ordinary second startup is idempotent and does not create another migration backup.
    before=set((dbfile.parent/'backups').glob('*.sqlite3'));second=db.init_db(dbfile);after=set((dbfile.parent/'backups').glob('*.sqlite3'))
    assert second['backup_path'] is None and before==after


def test_repository_transfer_bridge_moves_data_into_fresh_repo_data(tmp_path, monkeypatch):
    import db
    local_data=tmp_path/'local-data';repo_data=tmp_path/'repo-data';share=tmp_path/'share-transfer'
    monkeypatch.setenv('LAUFAPP_DATA_DIR',str(local_data));monkeypatch.setenv('LAUFAPP_TRANSFER_DIR',str(share))
    db.init_db()
    with db.db_conn() as c:
        c.execute("INSERT INTO runs(external_id,started_at,distance_km,duration_s,source,notes) VALUES('transfer-run','2026-08-10T08:00:00+02:00',15,4500,'apple_health','must survive')")
        c.execute("INSERT INTO health_metrics(external_id,metric_type,start_at,value,unit,source) VALUES('transfer-hrv','hrv_sdnn','2026-08-10T07:00:00+02:00',59,'ms','apple_health')")
    meta=db.prepare_repository_transfer();assert meta['size_bytes']>0 and (share/'laufapp.sqlite3').is_file()
    monkeypatch.setenv('LAUFAPP_DATA_DIR',str(repo_data))
    assert db.adopt_repository_transfer_if_needed() is True
    db.init_db()
    with db.db_conn() as c:
        assert c.execute("SELECT notes FROM runs WHERE external_id='transfer-run'").fetchone()['notes']=='must survive'
        assert c.execute("SELECT value FROM health_metrics WHERE external_id='transfer-hrv'").fetchone()['value']==59
    assert not (share/'laufapp.sqlite3').exists()


def test_failed_migration_restores_original_database(tmp_path, monkeypatch):
    dbfile=tmp_path/'data'/'laufapp.sqlite3';dbfile.parent.mkdir()
    create_v012_database(dbfile)
    with sqlite3.connect(dbfile) as c:
        c.execute("INSERT INTO runs(external_id,started_at,distance_km,duration_s,source,notes) VALUES('rollback-run','2026-08-01T08:00:00+02:00',10,3600,'manual','original')")
        c.commit()
    import db
    monkeypatch.setenv('LAUFAPP_DATA_DIR',str(dbfile.parent))
    original=db._apply_migration_1_to_2
    def boom(c):
        original(c)
        c.execute("UPDATE runs SET notes='should rollback'")
        raise RuntimeError('synthetic migration failure')
    monkeypatch.setattr(db,'_apply_migration_1_to_2',boom)
    try:db.init_db(dbfile)
    except RuntimeError as e:assert 'synthetic migration failure' in str(e)
    else:raise AssertionError('migration unexpectedly succeeded')
    # Exact user record survived and the legacy schema version marker is still 0.
    with sqlite3.connect(dbfile) as c:
        assert c.execute("SELECT notes FROM runs WHERE external_id='rollback-run'").fetchone()[0]=='original'
        assert c.execute('PRAGMA user_version').fetchone()[0]==0


def test_repository_transfer_never_overwrites_existing_repo_database(tmp_path, monkeypatch):
    import db
    local_data=tmp_path/'local-data';repo_data=tmp_path/'repo-data';share=tmp_path/'share-transfer'
    monkeypatch.setenv('LAUFAPP_TRANSFER_DIR',str(share))
    monkeypatch.setenv('LAUFAPP_DATA_DIR',str(local_data));db.init_db()
    with db.db_conn() as c:
        c.execute("INSERT INTO runs(external_id,started_at,distance_km,duration_s,source,notes) VALUES('old-local','2026-08-10T08:00:00+02:00',10,3600,'manual','local')")
    db.prepare_repository_transfer()
    monkeypatch.setenv('LAUFAPP_DATA_DIR',str(repo_data));db.init_db()
    with db.db_conn() as c:
        c.execute("INSERT INTO runs(external_id,started_at,distance_km,duration_s,source,notes) VALUES('already-repo','2026-08-11T08:00:00+02:00',11,3700,'manual','repo')")
    assert db.adopt_repository_transfer_if_needed() is False
    with db.db_conn() as c:
        assert c.execute("SELECT COUNT(*) FROM runs WHERE external_id='already-repo'").fetchone()[0]==1
        assert c.execute("SELECT COUNT(*) FROM runs WHERE external_id='old-local'").fetchone()[0]==0
    # Transfer deliberately remains available until a fresh target consumes it.
    assert (share/'laufapp.sqlite3').is_file()
