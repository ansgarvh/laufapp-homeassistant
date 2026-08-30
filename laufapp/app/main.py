from __future__ import annotations
import calendar, ipaddress, json, os, tempfile, uuid
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Literal
from fastapi import FastAPI, File, HTTPException, Query, UploadFile, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator, model_validator
from db import APP_VERSION, adopt_repository_transfer_if_needed, data_dir, db_conn, get_setting, init_db, prepare_repository_transfer, rows, set_setting
from training import automatic_max_weekly_km, current_race, dashboard, generate_week, goal_assessment, hms, move_workout, parse_dt, predict_all, predict_distance, week_start_for, week_summary, auto_match_run, mark_plan_stale, refresh_plan
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

_HOME_ASSISTANT_INTERNAL_NETWORK=ipaddress.ip_network('172.30.32.0/23')

def _trusted_ingress_request(request: Request) -> bool:
    """Recognize authenticated Ingress only from Home Assistant's internal net."""
    host=request.client.host if request.client else ''
    try: peer=ipaddress.ip_address(host)
    except ValueError:return False
    if peer not in _HOME_ASSISTANT_INTERNAL_NETWORK:return False
    source=request.headers.get('x-hass-source','')
    ingress_path=request.headers.get('x-ingress-path','')
    remote_user=request.headers.get('x-remote-user-id','')
    return ingress_path.startswith('/api/hassio_ingress/') and (source=='core.ingress' or bool(remote_user))

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
        if not 3<=len(x)<=7 or any(i<0 or i>6 for i in x):raise ValueError('Bitte drei bis sieben unterschiedliche Trainingstage auswählen.')
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
    training_days:list[int]|None=None;quality_sessions_per_week:int|None=Field(default=None,ge=1,le=3);max_weekly_km_mode:Literal['auto','user']|None=None;max_weekly_km:float|None=Field(default=None,ge=10,le=180);training_volume_profile:Literal['gradual','steady','progressive']|None=None;training_difficulty:Literal['comfortable','balanced','challenging']|None=None;baseline_weekly_km:float|None=Field(default=None,ge=8,le=160);max_long_run_km:float|None=Field(default=None,ge=8,le=50);max_long_run_share:float|None=Field(default=None,ge=.30,le=.60);monthly_ai_budget_eur:float|None=Field(default=None,ge=.5,le=100);coach_model:Literal['gpt-5.6-luna','gpt-5.6-terra','gpt-5.6-sol']|None=None;vision_model:Literal['gpt-5.6-luna','gpt-5.6-terra']|None=None;evidence_search:bool|None=None
    @field_validator('training_days')
    @classmethod
    def days(cls,v):
        if v is None:return v
        x=sorted(set(v))
        if not 3<=len(x)<=7 or any(i<0 or i>6 for i in x):raise ValueError('Es müssen drei bis sieben unterschiedliche Trainingstage gewählt werden.')
        return x

    @model_validator(mode='after')
    def safe_quality(self):
        if self.training_days is not None and self.quality_sessions_per_week is not None and self.quality_sessions_per_week>len(self.training_days)-2:raise ValueError('Mindestens zwei Lauftage müssen locker beziehungsweise für den Longrun bleiben.')
        if self.max_weekly_km_mode=='user' and self.max_weekly_km is None:raise ValueError('Für einen selbst festgelegten Wochenumfang fehlt der Kilometerwert.')
        return self

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
def settings_dict(c):
    race=current_race(c);dist=float(race['distance_km']) if race else 42.195;long_default=35 if dist>=40 else 26 if dist>=20 else 18 if dist>=10 else 14;recommendation=automatic_max_weekly_km(c,race)
    mode=get_setting(c,'max_weekly_km_mode','auto')
    return {'training_days':get_setting(c,'training_days',[1,3,4,6]),'running_days_per_week':len(get_setting(c,'training_days',[1,3,4,6])),'quality_sessions_per_week':get_setting(c,'quality_sessions_per_week',2),'max_weekly_km_mode':mode,'max_weekly_km':get_setting(c,'max_weekly_km',recommendation) if mode=='user' else recommendation,'recommended_max_weekly_km':recommendation,'training_volume_profile':get_setting(c,'training_volume_profile','steady'),'training_difficulty':get_setting(c,'training_difficulty','balanced'),'baseline_weekly_km':get_setting(c,'baseline_weekly_km',40.0),'max_long_run_km':get_setting(c,'max_long_run_km',long_default),'max_long_run_share':get_setting(c,'max_long_run_share',.45),'monthly_ai_budget_eur':get_setting(c,'monthly_ai_budget_eur',10.0),'coach_model':get_setting(c,'coach_model','gpt-5.6-terra'),'vision_model':get_setting(c,'vision_model','gpt-5.6-luna'),'evidence_search':get_setting(c,'evidence_search',True),'plan_stale':get_setting(c,'plan_stale',False),'plan_stale_reason':get_setting(c,'plan_stale_reason',''),'ai':config_status(c)}
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
    with db_conn() as c:
        if p.race_date<=date.today():raise HTTPException(400,'Das Wettkampfdatum muss in der Zukunft liegen.')
        c.execute("UPDATE races SET active=0")
        cur=c.execute("INSERT INTO races(name,distance_km,race_date,goal_seconds,active) VALUES(?,?,?,?,1)",(p.race_name,p.distance_km,p.race_date.isoformat(),p.goal_seconds))
        set_setting(c,'training_days',p.training_days);set_setting(c,'setup_completed',True);set_setting(c,'active_race_id',cur.lastrowid);set_setting(c,'plan_stale',False);set_setting(c,'plan_stale_reason','');refresh_plan(c,14)
    return {'ok':True}
@app.get('/api/settings')
def api_settings():
    with db_conn() as c:return settings_dict(c)
@app.put('/api/settings')
def api_settings_update(p:SettingsPayload):
    with db_conn() as c:
        before=settings_dict(c)
        raw=p.model_dump(exclude_unset=True)
        if raw.get('max_weekly_km_mode')=='auto':raw['max_weekly_km']=None
        for k,v in raw.items():set_setting(c,k,v)
        after=settings_dict(c)
        planning={'training_days','quality_sessions_per_week','max_weekly_km_mode','max_weekly_km','training_volume_profile','training_difficulty','baseline_weekly_km','max_long_run_km','max_long_run_share'}
        changed=[k for k in planning if before.get(k)!=after.get(k)]
        if changed:mark_plan_stale(c,'Planungseinstellungen geändert: '+', '.join(changed))
        after['changed_planning_fields']=changed
        return after
@app.get('/api/races')
def api_races():
    with db_conn() as c:return rows(c.execute("SELECT * FROM races ORDER BY active DESC,race_date").fetchall())
@app.get('/api/shoes')
def api_shoes():
    with db_conn() as c:return shoe_rows(c)
@app.post('/api/shoes')
def api_shoes_add(p:ShoePayload):
    with db_conn() as c:cur=c.execute("INSERT INTO shoes(brand,model,nickname,start_km) VALUES(?,?,?,?)",(p.brand,p.model,p.nickname,p.start_km));return {'id':cur.lastrowid}
@app.delete('/api/shoes/{shoe_id}')
def api_shoes_delete(shoe_id:int):
    with db_conn() as c:c.execute("UPDATE shoes SET archived=1 WHERE id=?",(shoe_id,));return {'ok':True}
@app.get('/api/runs')
def api_runs(limit:int=Query(default=100,ge=1,le=1000)):
    with db_conn() as c:return rows(c.execute("SELECT * FROM runs ORDER BY started_at DESC LIMIT ?",(limit,)).fetchall())
@app.post('/api/runs')
def api_runs_add(p:RunPayload):
    with db_conn() as c:
        cur=c.execute("INSERT INTO runs(external_id,source,started_at,duration_s,distance_km,avg_hr,elevation_m,calories,rpe,shoe_id,notes) VALUES(NULL,?,?,?,?,?,?,?,?,?,?)",(p.source,p.started_at,p.duration_s,p.distance_km,p.avg_hr,p.elevation_m,p.calories,p.rpe,p.shoe_id,p.notes));auto_match_run(c,cur.lastrowid);snapshot(c,'manual');return {'id':cur.lastrowid}
@app.put('/api/runs/{run_id}')
def api_runs_update(run_id:int,p:RunUpdatePayload):
    with db_conn() as c:
        if not c.execute("SELECT 1 FROM runs WHERE id=?",(run_id,)).fetchone():raise HTTPException(404,'Lauf nicht gefunden.')
        values=p.model_dump(exclude_unset=True)
        if not values:return {'ok':True}
        fields=[];args=[]
        for key in ('rpe','shoe_id','notes'):
            if key in values:fields.append(f"{key}=?");args.append(values[key])
        args.append(run_id);c.execute(f"UPDATE runs SET {','.join(fields)} WHERE id=?",args);return {'ok':True}
@app.post('/api/marks')
def api_mark(p:MarkPayload):
    with db_conn() as c:cur=c.execute("INSERT INTO performance_marks(distance_km,duration_s,mark_date,source,label) VALUES(?,?,?,?,?)",(p.distance_km,p.duration_s,p.mark_date.isoformat(),p.source,p.label));return {'id':cur.lastrowid}
@app.delete('/api/marks/{mark_id}')
def api_mark_delete(mark_id:int):
    with db_conn() as c:c.execute("DELETE FROM performance_marks WHERE id=?",(mark_id,));return {'ok':True}
@app.get('/api/week')
def api_week(start:date|None=None):
    with db_conn() as c:return week_summary(c,start or week_start_for(date.today()))
@app.post('/api/week/refresh')
def api_week_refresh(start:date|None=None,force:bool=False):
    with db_conn() as c:
        if force:return refresh_plan(c,14,start or week_start_for(date.today()))
        return generate_week(c,start or week_start_for(date.today()))
@app.patch('/api/workouts/{workout_id}/move')
def api_move(workout_id:int,p:MovePayload):
    with db_conn() as c:return move_workout(c,workout_id,p.scheduled_date)
@app.patch('/api/workouts/{workout_id}/status')
def api_status(workout_id:int,p:StatusPayload):
    with db_conn() as c:c.execute("UPDATE workouts SET status=?,modified=1 WHERE id=?",(p.status,workout_id));return {'ok':True}
@app.get('/api/progress')
def api_progress():
    with db_conn() as c:return {'predictions':predict_all(c),'health':health_summary(c),'marks':rows(c.execute("SELECT * FROM performance_marks ORDER BY mark_date DESC").fetchall())}
@app.get('/api/progress/volume')
def api_progress_volume(period:Literal['1m','3m','6m','12m','this_year','last_year']='3m'):
    with db_conn() as c:return progress_volume(c,period)
@app.get('/api/dashboard')
def api_dashboard():
    with db_conn() as c:return dashboard(c)
@app.get('/api/run-analysis/{run_id}')
def api_run_analysis(run_id:int):
    with db_conn() as c:
        try:return analyze_run(c,run_id)
        except ValueError as e:raise HTTPException(404,str(e))
@app.get('/api/plan-review')
def api_plan_review():
    with db_conn() as c:return get_plan_review(c)
@app.post('/api/coach/chat')
def api_coach_chat(p:CoachPayload):
    with db_conn() as c:
        try:return coach_chat(c,p.message)
        except (ValueError,RuntimeError) as e:raise HTTPException(400,str(e))
@app.post('/api/coach/review-week')
def api_coach_review():
    with db_conn() as c:
        try:return review_week_plan(c)
        except (ValueError,RuntimeError) as e:raise HTTPException(400,str(e))
@app.post('/api/coach/extract-image')
async def api_extract(file:UploadFile=File(...)):
    tmp=Path(tempfile.mkstemp(prefix='run-',suffix=Path(file.filename or '.png').suffix)[1])
    try:
        tmp.write_bytes(await file.read())
        return extract_run_image(tmp)
    finally:tmp.unlink(missing_ok=True)
@app.post('/api/apple-health/import-jobs',status_code=202)
async def api_health_job(file:UploadFile=File(...),replace_existing:bool=False):
    suffix=Path(file.filename or '').suffix.lower()
    if suffix not in {'.zip','.xml'}:raise HTTPException(400,'Bitte Apple-Health-ZIP oder export.xml hochladen.')
    jid=str(uuid.uuid4());temp=import_storage_path(jid,suffix);size=0
    try:
        with temp.open('wb') as out:
            while True:
                chunk=await file.read(4*1024*1024)
                if not chunk:break
                size+=len(chunk)
                if size>MAX_HEALTH_UPLOAD:raise HTTPException(413,'Apple-Health-Export ist größer als 2 GB.')
                out.write(chunk)
    except Exception:
        temp.unlink(missing_ok=True);raise
    job=create_import_job_with_uuid(jid,file.filename or 'apple-health-export'+suffix,temp,size,replace_existing)
    MANAGER.submit(job['id']);return job
@app.get('/api/apple-health/import-jobs/latest')
def api_health_latest():return latest_job() or {}
@app.get('/api/apple-health/import-jobs')
def api_health_jobs():return list_jobs()
@app.get('/api/apple-health/import-jobs/{job_id}')
def api_health_job_status(job_id:int):
    job=get_job(job_id)
    if not job:raise HTTPException(404,'Import nicht gefunden.')
    return job
@app.post('/api/apple-health/import-jobs/{job_id}/retry')
def api_health_retry(job_id:int):
    try:return retry_job(job_id)
    except KeyError as e:raise HTTPException(404,str(e))
    except ValueError as e:raise HTTPException(409,str(e))
@app.get('/api/transfer/status')
def api_transfer_status():return {'data_dir':str(data_dir()),'ready':True}
@app.post('/api/transfer/export')
def api_transfer_export():return prepare_repository_transfer()
app.mount('/assets',StaticFiles(directory=STATIC),name='assets')
@app.get('/{rest:path}',include_in_schema=False)
def pwa(rest:str):
    path=STATIC/rest
    if rest and path.is_file():return FileResponse(path,headers={'Cache-Control':'no-store, max-age=0'})
    return FileResponse(STATIC/'index.html',headers={'Cache-Control':'no-store, max-age=0'})
