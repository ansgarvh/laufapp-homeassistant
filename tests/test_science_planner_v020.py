from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import main_v020  # noqa: F401 - activates v0.2 runtime wiring before API fixtures
import training as base
import training_v020 as training
from db import connect, init_db, set_setting
from training_adaptation_v020 import adaptation_suggestion, recovery_state
from training_planner_v020 import training_paces

TESTS=Path(__file__).parent
if str(TESTS) not in sys.path:sys.path.insert(0,str(TESTS))
from science_plan_simulator import build_plan, validate_plan  # noqa: E402


def _db(tmp_path:Path,name='science.sqlite3'):
    path=tmp_path/name;init_db(path);return connect(path)


def _race(c,ws:date,weeks:int=12,goal:int=12000):
    rd=ws+timedelta(days=weeks*7+6);cur=c.execute("INSERT INTO races(name,distance_km,race_date,goal_seconds,target_source,active) VALUES('Marathon',42.195,?,?,'user',1)",(rd.isoformat(),goal));rid=int(cur.lastrowid);set_setting(c,'race_priorities',{str(rid):'A'});c.commit();return c.execute('SELECT * FROM races WHERE id=?',(rid,)).fetchone()


def _seed_weekly_runs(c,start:date,weekly:float,weeks:int=6):
    shares=(.22,.20,.18,.40);days=(1,3,4,6)
    for n in range(weeks,0,-1):
        ws=start-timedelta(days=n*7)
        for i,(dow,share) in enumerate(zip(days,shares)):
            km=round(weekly*share,1);d=ws+timedelta(days=dow);c.execute("INSERT INTO runs(external_id,started_at,distance_km,duration_s,source,rpe) VALUES(?,?,?,?, 'manual',3)",(f'hist-{weekly}-{n}-{i}',f'{d.isoformat()}T07:00:00+02:00',km,km*330))
    c.commit()


def _health(c,metric,d,value,idx):
    c.execute("INSERT INTO health_metrics(external_id,metric_type,start_at,end_at,value,unit,source) VALUES(?,?,?,?,?,'','apple_health')",(f'{metric}-{idx}',metric,f'{d.isoformat()}T07:00:00+02:00',f'{d.isoformat()}T07:00:00+02:00',value))


def test_a_b_c_novice_advanced_and_four_day_structure(tmp_path):
    """A/B/C: low volume stays conservative; advanced gets more volume; four days keep E/Q/E/L."""
    start=base.week_start_for(date.today())+timedelta(days=7)
    novice=_db(tmp_path,'novice.sqlite3');set_setting(novice,'training_days',[1,3,4,6]);set_setting(novice,'baseline_weekly_km',25.0);_race(novice,start,12);novice.commit();nw=training.generate_week(novice,start,True)
    assert len(nw)==4
    assert [w['workout_type'] for w in nw]==['easy','quality','easy','long']
    assert sum(float(w['distance_km']) for w in nw)<=35
    assert max(float(w['distance_km']) for w in nw if w['workout_type']=='long')<=16
    novice.close()

    advanced=_db(tmp_path,'advanced.sqlite3');set_setting(advanced,'training_days',[1,3,4,6]);set_setting(advanced,'baseline_weekly_km',75.0);_seed_weekly_runs(advanced,start,75);_race(advanced,start,12);advanced.commit();aw=training.generate_week(advanced,start,True)
    assert len(aw)==4
    assert sum(float(w['distance_km']) for w in aw)>sum(float(w['distance_km']) for w in nw)+20
    assert max(float(w['distance_km']) for w in aw if w['workout_type']=='long')<=35
    advanced.close()


def test_d_e_readiness_combines_personal_trends_and_single_hrv_is_not_red(tmp_path):
    """D/E: personal baseline drives readiness; a single HRV dimension cannot alone force red."""
    ref=date.today();c=_db(tmp_path,'readiness-red.sqlite3')
    idx=0
    for offset in range(40,7,-1):
        d=ref-timedelta(days=offset);idx+=1;_health(c,'hrv_sdnn',d,60,idx);_health(c,'resting_hr',d,50,1000+idx);_health(c,'sleep_hours',d,8.0,2000+idx)
    for offset in range(4,-1,-1):
        d=ref-timedelta(days=offset);idx+=1;_health(c,'hrv_sdnn',d,44,idx);_health(c,'resting_hr',d,57,1000+idx);_health(c,'sleep_hours',d,6.0,2000+idx)
    c.commit();red=recovery_state(c,ref);assert red.level.value=='red';assert {'hrv','resting_hr','sleep'}<=set(red.signals);c.close()

    c=_db(tmp_path,'readiness-hrv.sqlite3');idx=0
    for offset in range(40,7,-1):idx+=1;_health(c,'hrv_sdnn',ref-timedelta(days=offset),60,idx)
    for offset in range(4,-1,-1):idx+=1;_health(c,'hrv_sdnn',ref-timedelta(days=offset),44,idx)
    c.commit();hrv_only=recovery_state(c,ref);assert hrv_only.level.value!='red';c.close()


def test_f_skipped_workout_survives_explicit_replan(tmp_path):
    """F: a skipped/manual history row is never silently deleted by a refresh."""
    c=_db(tmp_path,'skip.sqlite3');start=base.week_start_for(date.today())+timedelta(days=7);set_setting(c,'baseline_weekly_km',55.0);_race(c,start,10);c.commit();workouts=training.generate_week(c,start,True);victim=next(w for w in workouts if w['workout_type']=='quality');c.execute("UPDATE workouts SET status='skipped' WHERE id=?",(victim['id'],));c.commit();training.generate_week(c,start,True);row=c.execute('SELECT status FROM workouts WHERE id=?',(victim['id'],)).fetchone();assert row and row['status']=='skipped';c.close()


def test_g_good_progress_can_create_proposal_but_never_mutates_plan(tmp_path):
    """G: repeatedly well-tolerated training can suggest progression, never auto-apply it."""
    c=_db(tmp_path,'progression.sqlite3');start=base.week_start_for(date.today())+timedelta(days=7);set_setting(c,'baseline_weekly_km',62.0);_race(c,start,10);c.commit();workouts=training.generate_week(c,start,True);hard=next(w for w in workouts if w['workout_type']=='quality');before=float(hard['distance_km'])
    for i in range(1,5):set_setting(c,f'workout_feedback:{900+i}',{'run_id':900+i,'date':(date.today()-timedelta(days=i)).isoformat(),'rpe':6,'legs':4,'pain':'none','recovery':4})
    c.commit();proposal=adaptation_suggestion(c,date.today());after=float(c.execute('SELECT distance_km FROM workouts WHERE id=?',(hard['id'],)).fetchone()['distance_km']);assert after==before;assert proposal['suggestion_id'] is not None;assert proposal['suggestion']['changes']['distance_km']>before;assert c.execute("SELECT status FROM suggestions WHERE id=?",(proposal['suggestion_id'],)).fetchone()['status']=='pending';c.close()


def test_h_i_j_k_longrun_mp_deload_and_taper_across_16_weeks():
    """H/I/J/K plus full 16-week progression checks."""
    rows,integrity,schema=build_plan();assert integrity=='ok' and schema==4;assert validate_plan(rows)
    specific=[r for r in rows if r['phase']=='specific'];assert any(r['mp_km']>0 for r in specific);assert any(r['mp_km']==0 for r in specific)
    assert len([r for r in rows if r['phase']=='recovery'])>=2
    assert [r['phase'] for r in rows[-3:]]==['taper','taper','race']
    assert len({r['quality'] for r in rows if r['quality']!='—'})>=5


def test_l_goal_pace_is_not_used_blindly_when_current_estimate_is_slower(tmp_path):
    """L: current estimated MP caps an unrealistically ambitious user goal."""
    c=_db(tmp_path,'paces.sqlite3');start=base.week_start_for(date.today())+timedelta(days=7);race=_race(c,start,10,goal=3*3600);c.execute("INSERT INTO performance_marks(distance_km,duration_s,mark_date,source,label) VALUES(10,3000,?,'manual','current fitness')",((date.today()-timedelta(days=7)).isoformat(),));c.commit();p=training_paces(c,race);assert p['current_estimated_marathon_pace_s_per_km']>p['goal_marathon_pace_s_per_km'];assert p['training_marathon_pace_s_per_km']>=p['current_estimated_marathon_pace_s_per_km']-.1;c.close()


def test_m_bad_recovery_proposes_reduction_without_silent_change(tmp_path):
    """M: multi-signal bad recovery creates a conservative proposal only."""
    c=_db(tmp_path,'adapt-red.sqlite3');start=base.week_start_for(date.today())+timedelta(days=7);set_setting(c,'baseline_weekly_km',60.0);_race(c,start,10);workouts=training.generate_week(c,start,True);hard=next(w for w in workouts if w['workout_type']=='quality');before=float(hard['distance_km']);ref=date.today();idx=0
    for offset in range(40,7,-1):
        d=ref-timedelta(days=offset);idx+=1;_health(c,'hrv_sdnn',d,60,idx);_health(c,'resting_hr',d,50,1000+idx);_health(c,'sleep_hours',d,8,2000+idx)
    for offset in range(4,-1,-1):
        d=ref-timedelta(days=offset);idx+=1;_health(c,'hrv_sdnn',d,43,idx);_health(c,'resting_hr',d,58,1000+idx);_health(c,'sleep_hours',d,5.8,2000+idx)
    c.commit();proposal=adaptation_suggestion(c,ref);after=float(c.execute('SELECT distance_km FROM workouts WHERE id=?',(hard['id'],)).fetchone()['distance_km']);assert proposal['readiness']['level']=='red';assert proposal['suggestion_id'] is not None;assert proposal['suggestion']['changes']['distance_km']<before;assert after==before;c.close()


def test_subjective_feedback_api_is_persistent_and_exposed(setup_client):
    client=setup_client;week=client.get('/api/week').json();w=week['workouts'][0];run=client.post('/api/runs',json={'started_at':f"{w['scheduled_date']}T08:00:00+02:00",'distance_km':w['distance_km'],'duration_s':3600,'source':'manual'});assert run.status_code==200,run.text
    payload={'rpe':7,'legs':3,'pain':'light','recovery':3};r=client.post(f"/api/v2/workouts/{w['id']}/feedback",json=payload);assert r.status_code==200,r.text
    science=client.get(f"/api/v2/workouts/{w['id']}/science");assert science.status_code==200;assert science.json()['feedback']['rpe']==7;assert science.json()['feedback']['pain']=='light'


def test_science_metadata_is_additive_and_schema_stays_four(tmp_path):
    c=_db(tmp_path,'schema.sqlite3');start=base.week_start_for(date.today())+timedelta(days=7);_race(c,start,10);workouts=training.generate_week(c,start,True);assert c.execute('PRAGMA user_version').fetchone()[0]==4
    quality=next(w for w in workouts if w['workout_type']=='quality');d=quality['details'];assert d['physiological_target'];assert d['variant_key'];assert d['workout_form'];assert d['why'];assert d['load']['score']>0;assert d['rolling_intensity_distribution']['weeks']==4;c.close()
