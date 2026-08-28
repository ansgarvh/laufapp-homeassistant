from __future__ import annotations
import calendar, json, os, tempfile, uuid
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Literal
from fastapi import FastAPI, File, HTTPException, Query, UploadFile, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from db import APP_VERSION, adopt_repository_transfer_if_needed, data_dir, db_conn, get_setting, init_db, prepare_repository_transfer, rows, set_setting
from training import current_race, dashboard, generate_week, goal_assessment, hms, move_workout, parse_dt, predict_all, predict_distance, week_start_for, week_summary, auto_match_run, mark_plan_stale, refresh_plan
from health_import import import_apple_health
from import_jobs import MANAGER, create_import_job_with_uuid, get_job, import_storage_path, latest_job, list_jobs, retry_job
from coach import analyze_run, coach_chat, config_status, extract_run_image, get_plan_review, month_cost, review_week_plan

@asynccontextmanager
async def lifespan(_app:FastAPI):
    adopted = adopt_repository_transfer_if_needed()
    migration = init_db()
    for name in ("tmp", "imports", "import_status", "backups"):
        (data_dir()/name).mkdir(parents=True,exist_ok=True)
    if adopted:
        print("Laufapp repository transfer adopted into persistent /data.", flush=True)
    if migration.get("backup_path"):
        print(f"Laufapp DB migration backup: {migration['backup_path']}", flush=True)
    MANAGER.start()
    try:
        yield
    finally:
        MANAGER.stop()

app=FastAPI(title='Laufapp',version=APP_VERSION,docs_url=None,redoc_url=None,lifespan=lifespan)

def _trusted_ingress_request(request: Request) -> bool:
    # Home Assistant Core injects these headers for authenticated Ingress requests.
    # Do not rely on request.client here: Uvicorn may replace it with the original
    # remote IP from X-Forwarded-For when proxy headers are enabled.
    source=request.headers.get('x-hass-source','')
    ingress_path=request.headers.get('x-ingress-path','')
    return source=='core.ingress' and ingress_path.startswith('/api/hassio_ingress/')

@app.middleware('http')
async def ingress_only(request:Request, call_next):
    # Production Home Assistant Ingress is the only exposed path. Localhost remains
    # available for the container healthcheck. Tests/dev stay unrestricted unless
    # the Docker image explicitly enables the guard. The app port itself is not
    # published by Home Assistant (config.yaml: 8099/tcp: null).
    if os.environ.get('LAUFAPP_TRUSTED_INGRESS_ONLY') == '1':
        host=(request.client.host if request.client else '')
        local=host in {'172.30.32.2','127.0.0.1','::1'}
        if not local and not _trusted_ingress_request(request):
            from fastapi.responses import JSONResponse
            return JSONResponse({'detail':'Direkter Zugriff ist deaktiviert. Bitte Home Assistant Ingress verwenden.'},status_code=403)
    return await call_next(request)

STATIC=Path(__file__).resolve().parent/'static';MAX_HEALTH_UPLOAD=2*1024**3

class SetupPayload(BaseModel):
    race_name:str=Field(min_length=1,max_length=120);distance_km:float=Field(gt=1,le=100);race_date:date;goal_seconds:int=Field(gt=300,le=24*3600);training_days:list[int]
    @field_validator('training_days')
    @classmethod
    def days(cls,v):
        x=sorted(set(v))
        if len(x)!=4 or any(i<0 or i>6 for i in x):raise ValueError('Genau vier unterschiedliche Trainingstage auswählen.')
        return x
class RacePayload(BaseModel):
    name:str=Field(min_length=1,max_length=120);distance_km:float=Field(gt=1,le=100);race_date:date;goal_seconds:int=Field(gt=300,le=24*3600);active:bool=True
class ShoePayload(BaseModel):
    brand:str=Field(default='',max_length=80);model:str=Field(min_length=1,max_length=120);nickname:str=Field(default='',max_length=80);start_km:float=Field(default=0,ge=0,le=10000)
class RunPayload(BaseModel):
    started_at:str;distance_km:float=Field(gt=.05,le=200);duration_s:float=Field(gt=30,le=48*3600);avg_hr:float|None=Field(default=None,ge=30,le=240);elevation_m:float|None=Field(default=None,ge=-1000,le=20000);calories:float|None=Field(default=None,ge=0,le=50000);rpe:int|None=Field(default=None,ge=1,le=10);shoe_id:int|None=None;notes:str=Field(default='',max_length=3000);source:str=Field(default='manual',max_length=40)
    @field_validator('started_at')
    @classmethod
    def dt(cls,v):parse_dt(v);return v
class RunUpdatePayload(BaseModel):
    rpe:int|None=Field(default=None,ge=1,le=10)
    shoe_id:int|None=None
    notes:str|None=Field(default=None,max_length=3000)
class MarkPayload(BaseModel):
    distance_km:float=Field(gt=.4,le=100);duration_s:float=Field(gt=60,le=24*3600);mark_date:date;source:Literal['manual','race','time_trial']='manual';label:str=Field(default='',max_length=120)
class MovePayload(BaseModel):scheduled_date:date
class StatusPayload(BaseModel):status:Literal['planned','completed','skipped']
class CoachPayload(BaseModel):message:str=Field(min_length=1,max_length=6000)
class SettingsPayload(BaseModel):
    training_days:list[int]|None=None;training_volume_profile:Literal['gradual','steady','progressive']|None=None;training_difficulty:Literal['comfortable','balanced','challenging']|None=None;baseline_weekly_km:float|None=Field(default=None,ge=8,le=160);max_long_run_km:float|None=Field(default=None,ge=8,le=50);max_long_run_share:float|None=Field(default=None,ge=.30,le=.60);monthly_ai_budget_eur:float|None=Field(default=None,ge=.5,le=100);coach_model:Literal['gpt-5.6-luna','gpt-5.6-terra','gpt-5.6-sol']|None=None;vision_model:Literal['gpt-5.6-luna','gpt-5.6-terra']|None=None;evidence_search:bool|None=None
    @field_validator('training_days')
    @classmethod
    def days(cls,v):
        if v is None:return v
        x=sorted(set(v))
        if len(x)!=4 or any(i<0 or i>6 for i in x):raise ValueError('Es müssen genau vier unterschiedliche Trainingstage gewählt werden.')
        return x

def health_summary(c):
    out={}
    for metric in ('resting_hr','hrv_sdnn','sleep_hours','body_mass','vo2max'):
        rr=c.execute("SELECT start_at,value,unit FROM health_metrics WHERE metric_type=? ORDER BY start_at DESC LIMIT 14",(metric,)).fetchall()
        if rr:
            vals=[float(r['value']) for r in rr];out[metric]={'latest':round(vals[0],2),'average':round(sum(vals)/len(vals),2),'unit':rr[0]['unit'],'samples':len(vals)}
    return out

def progress_volume(c, period:str):
    today=date.today()
    if period == 'this_year': cutoff=date(today.year,1,1)
    elif period == 'last_year': cutoff,today=date(today.year-1,1,1),date(today.year-1,12,31)
    else:
        months={'1m':1,'3m':3,'6m':6,'12m':12}[period]
        raw=today.year*12+today.month-1-months; year,month0=divmod(raw,12)
        cutoff=date(year,month0+1,min(today.day,calendar.monthrange(year,month0+1)[1]))
    first=week_start_for(cutoff); last=week_start_for(today)
    buckets={}
    for r in c.execute("SELECT started_at,distance_km FROM runs WHERE substr(started_at,1,10)>=? AND substr(started_at,1,10)<=? ORDER BY started_at",(cutoff.isoformat(),today.isoformat())):
        try: ws=week_start_for(parse_dt(r['started_at']).date()).isoformat()
        except Exception: continue
        b=buckets.setdefault(ws,{'distance_km':0.0,'run_count':0});b['distance_km']+=float(r['distance_km']);b['run_count']+=1
    weeks=[]; cursor=first
    while cursor<=last:
        b=buckets.get(cursor.isoformat(),{'distance_km':0.0,'run_count':0})
        weeks.append({'week_start':cursor.isoformat(),'distance_km':round(b['distance_km'],2),'run_count':b['run_count']});cursor+=timedelta(days=7)
    total=round(sum(x['distance_km'] for x in weeks),2)
    return {'period':period,'cutoff_date':cutoff.isoformat(),'through_date':today.isoformat(),'weeks':weeks,'total_km':total,'average_weekly_km':round(total/len(weeks),2) if weeks else 0,'maximum_weekly_km':max((x['distance_km'] for x in weeks),default=0),'number_of_weeks':len(weeks),'active_weeks':sum(x['run_count']>0 for x in weeks)}
def shoe_rows(c):
    return rows(c.execute("SELECT s.id,s.brand,s.model,s.nickname,s.start_km,s.archived,s.created_at,ROUND(s.start_km+COALESCE(SUM(r.distance_km),0),1) total_km,COUNT(r.id) run_count,MAX(r.started_at) last_run FROM shoes s LEFT JOIN runs r ON r.shoe_id=s.id GROUP BY s.id ORDER BY s.archived,s.created_at DESC").fetchall())
def settings_dict(c):return {'training_days':get_setting(c,'training_days',[1,3,4,6]),'training_volume_profile':get_setting(c,'training_volume_profile','steady'),'training_difficulty':get_setting(c,'training_difficulty','balanced'),'baseline_weekly_km':get_setting(c,'baseline_weekly_km',40.0),'max_long_run_km':get_setting(c,'max_long_run_km',32.0),'max_long_run_share':get_setting(c,'max_long_run_share',.45),'monthly_ai_budget_eur':get_setting(c,'monthly_ai_budget_eur',10.0),'coach_model':get_setting(c,'coach_model','gpt-5.6-terra'),'vision_model':get_setting(c,'vision_model','gpt-5.6-luna'),'evidence_search':get_setting(c,'evidence_search',True),'ai':config_status(c)}
def bootstrap(c):
    active=current_race(c);return {'version':APP_VERSION,'setup_completed':bool(get_setting(c,'setup_completed',False)),'training_days':get_setting(c,'training_days',[1,3,4,6]),'races':rows(c.execute("SELECT * FROM races ORDER BY active DESC,race_date").fetchall()),'active_race':dict(active) if active else None,'shoes':shoe_rows(c),'health':health_summary(c),'ai':config_status(c)}
def snapshot(c,source):
    for p in predict_all(c):
        ex=c.execute("SELECT id FROM prediction_history WHERE race_distance_km=? AND source=? AND substr(created_at,1,10)=?",(p['distance_km'],source,date.today().isoformat())).fetchone()
        args=(p['predicted_seconds'],p['low_seconds'],p['high_seconds'],p['confidence'])
        if ex:c.execute("UPDATE prediction_history SET predicted_seconds=?,low_seconds=?,high_seconds=?,confidence=?,created_at=CURRENT_TIMESTAMP WHERE id=?",(*args,ex['id']))
        else:c.execute("INSERT INTO prediction_history(race_distance_km,predicted_seconds,low_seconds,high_seconds,confidence,source) VALUES(?,?,?,?,?,?)",(p['distance_km'],*args,source))

@app.get('/api/health')
def api_health():return {'ok':True,'version':APP_VERSION}
@app.get('/api/bootstrap')
def api_bootstrap():
    with db_conn() as c:return bootstrap(c)
@app.post('/api/setup')
def api_setup(p:SetupPayload):
    if p.race_date<=date.today():raise HTTPException(400,'Das Wettkampfdatum muss in der Zukunft liegen.')
    with db_conn() as c:
        c.execute("UPDATE races SET active=0");cur=c.execute("INSERT INTO races(name,distance_km,race_date,goal_seconds,target_source,active) VALUES(?,?,?,?, 'user',1)",(p.race_name,p.distance_km,p.race_date.isoformat(),p.goal_seconds));set_setting(c,'training_days',p.training_days);set_setting(c,'setup_completed',True);generate_week(c,week_start_for(date.today()),True);return {'ok':True,'race_id':int(cur.lastrowid),'bootstrap':bootstrap(c)}
@app.get('/api/dashboard')
def api_dashboard():
    with db_conn() as c:
        d=dashboard(c);d['health']=health_summary(c);d['ai']=config_status(c);return d
@app.get('/api/week')
def api_week(start:date|None=Query(default=None)):
    with db_conn() as c:return week_summary(c,week_start_for(start or date.today()))
@app.get('/api/progress/volume')
def api_progress_volume(period:Literal['1m','3m','6m','12m','this_year','last_year']='3m'):
    with db_conn() as c:return progress_volume(c,period)
@app.post('/api/plan/generate')
def api_plan(start:date|None=Query(default=None),force:bool=False):
    with db_conn() as c:
        if not current_race(c):raise HTTPException(400,'Lege zuerst einen aktiven Wettkampf an.')
        return {'workouts':generate_week(c,week_start_for(start or date.today()),force)}
@app.post('/api/plan/refresh')
def api_plan_refresh(start:date|None=Query(default=None),weeks:int=Query(default=4,ge=1,le=12)):
    with db_conn() as c:
        if not current_race(c):raise HTTPException(400,'Lege zuerst einen aktiven Wettkampf an.')
        return refresh_plan(c,start,weeks)

@app.get('/api/plan/review')
def api_review_get(start:date|None=Query(default=None)):
    ws=week_start_for(start or date.today())
    with db_conn() as c:return {'week_start':ws.isoformat(),'review':get_plan_review(c,ws)}
@app.post('/api/plan/review')
def api_review_post(start:date|None=Query(default=None),force:bool=False):
    with db_conn() as c:
        try:return review_week_plan(c,week_start_for(start or date.today()),force)
        except RuntimeError as e:raise HTTPException(400,str(e)) from e
@app.post('/api/workouts/{wid}/move')
def api_move(wid:int,p:MovePayload):
    with db_conn() as c:
        try:return move_workout(c,wid,p.scheduled_date)
        except KeyError as e:raise HTTPException(404,str(e)) from e
        except ValueError as e:raise HTTPException(400,str(e)) from e
@app.post('/api/workouts/{wid}/status')
def api_status(wid:int,p:StatusPayload):
    with db_conn() as c:
        if not c.execute("SELECT id FROM workouts WHERE id=?",(wid,)).fetchone():raise HTTPException(404,'Training nicht gefunden.')
        c.execute("UPDATE workouts SET status=?,manual_override=1,modified_by='user' WHERE id=?",(p.status,wid));return {'ok':True}
@app.get('/api/races')
def api_races():
    with db_conn() as c:return rows(c.execute("SELECT * FROM races ORDER BY active DESC,race_date").fetchall())
@app.post('/api/races')
def api_race_add(p:RacePayload):
    if p.race_date<=date.today():raise HTTPException(400,'Das Wettkampfdatum muss in der Zukunft liegen.')
    with db_conn() as c:
        if p.active:c.execute("UPDATE races SET active=0")
        cur=c.execute("INSERT INTO races(name,distance_km,race_date,goal_seconds,target_source,active) VALUES(?,?,?,?, 'user',?)",(p.name,p.distance_km,p.race_date.isoformat(),p.goal_seconds,int(p.active)))
        if p.active:mark_plan_stale(c,'Aktiver Wettkampf geändert')
        return {'id':int(cur.lastrowid)}
@app.post('/api/races/{rid}/adopt-prediction')
def api_adopt(rid:int):
    with db_conn() as c:
        r=c.execute("SELECT * FROM races WHERE id=?",(rid,)).fetchone()
        if not r:raise HTTPException(404,'Wettkampf nicht gefunden.')
        p=predict_distance(c,float(r['distance_km']))
        if not p:raise HTTPException(400,'Noch keine belastbare Prognose vorhanden.')
        c.execute("UPDATE races SET goal_seconds=?,target_source='prediction' WHERE id=?",(p['predicted_seconds'],rid));mark_plan_stale(c,'Zielzeit oder Prognose geändert');return {'ok':True,'goal_seconds':p['predicted_seconds'],'goal_time':p['predicted_time']}
@app.get('/api/predictions')
def api_predictions():
    with db_conn() as c:
        r=current_race(c);return {'predictions':predict_all(c),'assessment':goal_assessment(c,r) if r else None,'history':rows(c.execute("SELECT * FROM prediction_history ORDER BY created_at DESC LIMIT 120").fetchall())}
@app.post('/api/performance-marks')
def api_mark(p:MarkPayload):
    if p.mark_date>date.today():raise HTTPException(400,'Leistungsdatum darf nicht in der Zukunft liegen.')
    with db_conn() as c:
        cur=c.execute("INSERT INTO performance_marks(distance_km,duration_s,mark_date,source,label) VALUES(?,?,?,?,?)",(p.distance_km,p.duration_s,p.mark_date.isoformat(),p.source,p.label));snapshot(c,'performance_mark');return {'id':int(cur.lastrowid),'predictions':predict_all(c)}
@app.get('/api/performance-marks')
def api_marks():
    with db_conn() as c:return rows(c.execute("SELECT * FROM performance_marks ORDER BY mark_date DESC").fetchall())
@app.get('/api/shoes')
def api_shoes():
    with db_conn() as c:return shoe_rows(c)
@app.post('/api/shoes')
def api_shoe_add(p:ShoePayload):
    with db_conn() as c:
        cur=c.execute("INSERT INTO shoes(brand,model,nickname,start_km) VALUES(?,?,?,?)",(p.brand,p.model,p.nickname,p.start_km));return {'id':int(cur.lastrowid)}
@app.post('/api/shoes/{sid}/archive')
def api_shoe_archive(sid:int):
    with db_conn() as c:c.execute("UPDATE shoes SET archived=1 WHERE id=?",(sid,));return {'ok':True}
@app.get('/api/runs')
def api_runs(limit:int=Query(default=100,ge=1,le=1000)):
    with db_conn() as c:return rows(c.execute("SELECT r.*,s.brand shoe_brand,s.model shoe_model FROM runs r LEFT JOIN shoes s ON s.id=r.shoe_id ORDER BY r.started_at DESC LIMIT ?",(limit,)).fetchall())
@app.patch('/api/runs/{rid}')
def api_run_update(rid:int,p:RunUpdatePayload):
    with db_conn() as c:
        r=c.execute("SELECT * FROM runs WHERE id=?",(rid,)).fetchone()
        if not r:raise HTTPException(404,'Lauf nicht gefunden.')
        vals=p.model_dump(exclude_unset=True);parts=[];args=[]
        if 'shoe_id' in vals and vals['shoe_id'] is not None and not c.execute("SELECT id FROM shoes WHERE id=? AND archived=0",(vals['shoe_id'],)).fetchone():raise HTTPException(400,'Schuh nicht gefunden oder archiviert.')
        for k in ('rpe','shoe_id','notes'):
            if k in vals:parts.append(f"{k}=?");args.append(vals[k])
        if parts:c.execute(f"UPDATE runs SET {','.join(parts)} WHERE id=?",(*args,rid))
        return dict(c.execute("SELECT r.*,s.brand shoe_brand,s.model shoe_model FROM runs r LEFT JOIN shoes s ON s.id=r.shoe_id WHERE r.id=?",(rid,)).fetchone())
@app.post('/api/runs')
def api_run_add(p:RunPayload):
    with db_conn() as c:
        cur=c.execute("INSERT INTO runs(started_at,distance_km,duration_s,avg_hr,elevation_m,calories,rpe,shoe_id,notes,source) VALUES(?,?,?,?,?,?,?,?,?,?)",(p.started_at,p.distance_km,p.duration_s,p.avg_hr,p.elevation_m,p.calories,p.rpe,p.shoe_id,p.notes,p.source));rid=int(cur.lastrowid);wid=auto_match_run(c,rid);snapshot(c,'manual_run');return {'id':rid,'matched_workout_id':wid}
@app.post('/api/apple-health/import-jobs',status_code=202)
async def api_health_import_job(file:UploadFile=File(...), replace_existing:bool=False):
    filename=file.filename or 'apple-health-export.zip'
    lower=filename.lower()
    if not (lower.endswith('.zip') or lower.endswith('.xml')):raise HTTPException(400,'Bitte eine ZIP-Datei oder export.xml auswählen.')
    suffix='.zip' if lower.endswith('.zip') else '.xml'
    job_uuid=str(uuid.uuid4())
    target_path=import_storage_path(job_uuid,suffix)
    size=0
    try:
        with target_path.open('wb') as target:
            while chunk:=await file.read(1024*1024):
                size+=len(chunk)
                if size>MAX_HEALTH_UPLOAD:
                    raise HTTPException(413,'Der Health-Export ist größer als 2 GB.')
                target.write(chunk)
        job=create_import_job_with_uuid(job_uuid,filename,target_path,size,replace_existing)
        MANAGER.submit(int(job['id']))
        return job
    except Exception:
        target_path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

@app.get('/api/apple-health/import-jobs/latest')
def api_health_import_latest():
    return latest_job() or {}

@app.get('/api/apple-health/import-jobs')
def api_health_import_jobs(limit:int=Query(default=10,ge=1,le=100)):
    return list_jobs(limit)

@app.get('/api/apple-health/import-jobs/{job_id}')
def api_health_import_job_status(job_id:int):
    job=get_job(job_id)
    if not job:raise HTTPException(404,'Import nicht gefunden.')
    return job

@app.post('/api/apple-health/import-jobs/{job_id}/retry')
def api_health_import_retry(job_id:int):
    try:return retry_job(job_id)
    except KeyError as e:raise HTTPException(404,str(e)) from e
    except ValueError as e:raise HTTPException(400,str(e)) from e

# Compatibility endpoint for older clients/tests. The UI uses the background-job
# endpoint above, so closing/minimising the browser after upload no longer stops
# processing.
@app.post('/api/apple-health/import')
async def api_health_import(file:UploadFile=File(...)):
    suffix='.zip' if (file.filename or '').lower().endswith('.zip') else '.xml';tmp=data_dir()/'tmp'/f'import-{next(tempfile._get_candidate_names())}{suffix}';size=0
    try:
        with tmp.open('wb') as target:
            while chunk:=await file.read(1024*1024):
                size+=len(chunk)
                if size>MAX_HEALTH_UPLOAD:raise HTTPException(413,'Der Health-Export ist größer als 2 GB.')
                target.write(chunk)
        with db_conn() as c:
            try:r=import_apple_health(c,tmp,24)
            except ValueError as e:raise HTTPException(400,str(e)) from e
            snapshot(c,'apple_health_import');
            if r.get('runs_added',0):mark_plan_stale(c,'Neue Apple-Health-Läufe verfügbar')
            r['health_summary']=health_summary(c);r['predictions']=predict_all(c);return r
    finally:await file.close();tmp.unlink(missing_ok=True)

@app.get('/api/runs/{rid}/details')
def api_run_details(rid:int):
    with db_conn() as c:
        run=c.execute("SELECT * FROM runs WHERE id=?",(rid,)).fetchone()
        if not run:raise HTTPException(404,'Lauf nicht gefunden.')
        samples=rows(c.execute("SELECT metric_type,COUNT(*) samples,ROUND(AVG(value),3) average,ROUND(MIN(value),3) minimum,ROUND(MAX(value),3) maximum,MAX(unit) unit FROM run_samples WHERE run_id=? GROUP BY metric_type ORDER BY metric_type",(rid,)).fetchall())
        gps=c.execute("SELECT COUNT(*) n FROM gps_points WHERE run_id=?",(rid,)).fetchone()['n']
        return {'run':dict(run),'sample_summary':samples,'gps_points':int(gps)}
@app.get('/api/suggestions')
def api_suggestions(status:str='pending'):
    if status not in {'pending','accepted','rejected','all'}:raise HTTPException(400,'Ungültiger Status.')
    with db_conn() as c:
        rr=c.execute("SELECT * FROM suggestions ORDER BY id DESC LIMIT 100").fetchall() if status=='all' else c.execute("SELECT * FROM suggestions WHERE status=? ORDER BY id DESC LIMIT 100",(status,)).fetchall();out=[]
        for r in rr:
            d=dict(r)
            try:d['payload']=json.loads(d.pop('payload_json'))
            except:d['payload']={}
            out.append(d)
        return out
@app.post('/api/suggestions/{sid}/accept')
def api_suggestion_accept(sid:int):
    with db_conn() as c:
        r=c.execute("SELECT * FROM suggestions WHERE id=? AND status='pending'",(sid,)).fetchone()
        if not r:raise HTTPException(404,'Offener Vorschlag nicht gefunden.')
        try:p=json.loads(r['payload_json'])
        except:raise HTTPException(400,'Vorschlag ist beschädigt.')
        if p.get('action')!='update_workout':raise HTTPException(400,'Unbekannter Vorschlagstyp.')
        wid=int(p.get('workout_id',0));w=c.execute("SELECT * FROM workouts WHERE id=? AND status='planned'",(wid,)).fetchone()
        if not w:raise HTTPException(400,'Das betroffene Training ist nicht mehr offen.')
        changes=p.get('changes') or {};warnings=[]
        if 'distance_km' in changes:
            proposed=float(changes['distance_km']);cur=float(w['distance_km'])
            if not max(3,cur*.5)<=proposed<=cur*1.1:raise HTTPException(400,'Distanzänderung verletzt die Sicherheitsgrenzen.')
            c.execute("UPDATE workouts SET distance_km=?,manual_override=1,modified_by='coach' WHERE id=?",(round(proposed,1),wid))
        if 'scheduled_date' in changes:
            try:warnings+=move_workout(c,wid,date.fromisoformat(changes['scheduled_date']))['warnings']
            except (KeyError,ValueError) as e:raise HTTPException(400,str(e)) from e
        c.execute("UPDATE suggestions SET status='accepted',resolved_at=CURRENT_TIMESTAMP WHERE id=?",(sid,));return {'ok':True,'warnings':warnings}
@app.post('/api/suggestions/{sid}/reject')
def api_suggestion_reject(sid:int):
    with db_conn() as c:
        if not c.execute("UPDATE suggestions SET status='rejected',resolved_at=CURRENT_TIMESTAMP WHERE id=? AND status='pending'",(sid,)).rowcount:raise HTTPException(404,'Offener Vorschlag nicht gefunden.')
        return {'ok':True}
@app.get('/api/coach/history')
def api_chat_history(limit:int=40):
    with db_conn() as c:
        out=[]
        for r in reversed(c.execute("SELECT * FROM chat_messages ORDER BY id DESC LIMIT ?",(limit,)).fetchall()):
            d=dict(r)
            try:d['meta']=json.loads(d.pop('meta_json'))
            except:d['meta']={}
            out.append(d)
        return out
@app.post('/api/coach/chat')
def api_chat(p:CoachPayload):
    with db_conn() as c:
        try:return coach_chat(c,p.message)
        except RuntimeError as e:raise HTTPException(400,str(e)) from e
@app.post('/api/coach/extract-run')
async def api_extract(file:UploadFile=File(...)):
    mime=file.content_type or 'image/jpeg'
    if not mime.startswith('image/'):raise HTTPException(400,'Bitte einen Bild-Screenshot auswählen.')
    raw=await file.read(12*1024*1024+1);await file.close()
    with db_conn() as c:
        try:return extract_run_image(c,raw,mime)
        except RuntimeError as e:raise HTTPException(400,str(e)) from e
@app.post('/api/coach/analyze-run/{rid}')
def api_analyze(rid:int):
    with db_conn() as c:
        try:return analyze_run(c,rid)
        except KeyError as e:raise HTTPException(404,str(e)) from e
        except RuntimeError as e:raise HTTPException(400,str(e)) from e
@app.get('/api/settings')
def api_settings():
    with db_conn() as c:return settings_dict(c)
@app.patch('/api/settings')
def api_settings_patch(p:SettingsPayload):
    with db_conn() as c:
        vals=p.model_dump(exclude_none=True)
        for k,v in vals.items():set_setting(c,k,v)
        plan_keys={'training_days','training_volume_profile','training_difficulty','baseline_weekly_km','max_long_run_km','max_long_run_share'}
        if plan_keys.intersection(vals) and current_race(c):mark_plan_stale(c,'Trainingspräferenzen geändert')
        return settings_dict(c)
@app.get('/api/ai-usage')
def api_usage():
    with db_conn() as c:return {'month_cost_eur':round(month_cost(c),4),'items':rows(c.execute("SELECT substr(created_at,1,7) month,usage_kind,ROUND(SUM(estimated_cost_eur),4) cost_eur,SUM(input_tokens) input_tokens,SUM(output_tokens) output_tokens,SUM(web_searches) web_searches FROM ai_usage GROUP BY month,usage_kind ORDER BY month DESC").fetchall())}

@app.post('/api/system/prepare-repository-transfer')
def api_prepare_repository_transfer():
    try:return {'ok':True,'transfer':prepare_repository_transfer()}
    except (FileNotFoundError,RuntimeError,OSError) as e:raise HTTPException(500,str(e)) from e

@app.get('/manifest.webmanifest')
def manifest():return FileResponse(STATIC/'manifest.webmanifest',media_type='application/manifest+json',headers={'Cache-Control':'no-cache'})
@app.get('/sw.js')
def sw():return FileResponse(STATIC/'sw.js',media_type='application/javascript',headers={'Cache-Control':'no-cache'})
@app.get('/apple-touch-icon.png')
def touch():return FileResponse(STATIC/'icon-192.png',media_type='image/png')
app.mount('/assets',StaticFiles(directory=STATIC),name='assets')
@app.get('/')
def root():return FileResponse(STATIC/'index.html',headers={'Cache-Control':'no-cache'})
# Convenience routes for relative asset URLs used by Home Assistant Ingress.
@app.get('/styles.css')
def css():return FileResponse(STATIC/'styles.css',media_type='text/css')
@app.get('/app.js')
def js():return FileResponse(STATIC/'app.js',media_type='application/javascript')
