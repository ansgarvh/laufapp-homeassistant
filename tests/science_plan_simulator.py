from __future__ import annotations

import json
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/'laufapp'/'app'
if str(APP) not in sys.path:sys.path.insert(0,str(APP))

import main_v020  # noqa: F401 - activates v0.2 planner wiring
import training as base
import training_v020 as training
from db import connect, init_db, set_setting


def _insert_race(c,race_date:date,goal_seconds:int=3*3600+20*60)->int:
    cur=c.execute("INSERT INTO races(name,distance_km,race_date,goal_seconds,target_source,active) VALUES('Synthetischer Marathon',42.195,?,?,'user',1)",(race_date.isoformat(),goal_seconds));rid=int(cur.lastrowid);set_setting(c,'race_priorities',{str(rid):'A'});return rid


def _seed_baseline(c,start:date,weekly_km:float=60.0):
    days=[1,3,4,6];shares=[.20,.20,.18,.42]
    for week in range(6,0,-1):
        ws=start-timedelta(days=week*7)
        for idx,(dow,share) in enumerate(zip(days,shares)):
            km=round(weekly_km*share,1);stamp=ws+timedelta(days=dow);c.execute("INSERT INTO runs(external_id,started_at,distance_km,duration_s,source,rpe,notes) VALUES(?,?,?,?, 'manual',3,'synthetic baseline')",(f'baseline-{week}-{idx}',f'{stamp.isoformat()}T07:00:00+02:00',km,km*330))


def _complete_week(c,workouts,week_index:int):
    for idx,w in enumerate(workouts):
        if w['workout_type']=='race' and week_index<15:continue
        duration=max(900,float(w['distance_km'])*330);cur=c.execute("INSERT INTO runs(external_id,started_at,distance_km,duration_s,source,rpe,notes) VALUES(?,?,?,?, 'manual',?, 'synthetic simulation')",(f'sim-{week_index}-{idx}',f"{w['scheduled_date']}T07:00:00+02:00",float(w['distance_km']),duration,6 if w['workout_type'] in {'quality','race'} else 3));rid=int(cur.lastrowid);c.execute("UPDATE workouts SET status='completed',linked_run_id=? WHERE id=?",(rid,int(w['id'])));set_setting(c,f'workout_feedback:{rid}',{'schema':1,'run_id':rid,'workout_id':int(w['id']),'date':w['scheduled_date'],'rpe':6 if w['workout_type']=='quality' else 4,'legs':4,'pain':'none','recovery':4})


def build_plan(weekly_km:float=60.0,goal_seconds:int=3*3600+20*60):
    tmp=tempfile.TemporaryDirectory();path=Path(tmp.name)/'science.sqlite3';init_db(path);c=connect(path)
    start=base.week_start_for(date.today())+timedelta(days=7);race_ws=start+timedelta(days=15*7);race_date=race_ws+timedelta(days=6)
    set_setting(c,'training_days',[1,3,4,6]);set_setting(c,'baseline_weekly_km',weekly_km);set_setting(c,'training_volume_profile','steady');set_setting(c,'max_weekly_km_mode','auto');set_setting(c,'max_long_run_km',35.0);set_setting(c,'max_long_run_share',.45);set_setting(c,'quality_sessions_per_week',2);_insert_race(c,race_date,goal_seconds);_seed_baseline(c,start,weekly_km);c.execute("INSERT INTO performance_marks(distance_km,duration_s,mark_date,source,label) VALUES(10,2700,?,'manual','synthetic 10k')",((start-timedelta(days=14)).isoformat(),));c.commit()
    rows=[]
    for i in range(16):
        ws=start+timedelta(days=i*7);workouts=training.generate_week(c,ws,True);summary=training.week_summary(c,ws);long=next((w for w in workouts if w['workout_type'] in {'long','race'}),None);quality=next((w for w in workouts if w['workout_type']=='quality'),None);ld=(long or {}).get('details') or {};qd=(quality or {}).get('details') or {};tid=summary['guardrails'].get('rolling_intensity_distribution') or summary['guardrails'].get('week_intensity_distribution') or {}
        rows.append({'week':i+1,'week_start':ws.isoformat(),'weeks_to_race':15-i,'phase':(summary.get('plan_basis') or {}).get('phase') or ld.get('phase') or qd.get('phase') or 'race','planned_km':round(sum(float(w['distance_km']) for w in workouts),1),'quality':quality['title'] if quality else '—','quality_target':qd.get('physiological_target') or '—','longrun':long['title'] if long else '—','longrun_km':round(float(long['distance_km']),1) if long else 0,'mp_km':round(float(ld.get('mp_km',0) or 0),1),'low_pct':round(float(tid.get('low_pct',0) or 0),1),'moderate_pct':round(float(tid.get('moderate_pct',0) or 0),1),'high_pct':round(float(tid.get('high_pct',0) or 0),1),'readiness':(summary.get('plan_basis') or {}).get('readiness',{}).get('level','green'),'why':str(ld.get('why') or qd.get('why') or '')})
        _complete_week(c,workouts,i);c.commit()
    integrity=c.execute('PRAGMA integrity_check').fetchone()[0];schema=c.execute('PRAGMA user_version').fetchone()[0];c.close();tmp.cleanup();return rows,integrity,schema


def validate_plan(rows):
    assert len(rows)==16
    assert rows[-1]['phase']=='race'
    assert rows[-2]['phase']=='taper' and rows[-3]['phase']=='taper'
    deloads=[r for r in rows if r['phase']=='recovery'];assert len(deloads)>=2
    qualities=[r for r in rows if r['quality']!='—'];assert len(set(r['quality'] for r in qualities))>=5
    for a,b in zip(qualities,qualities[1:]):assert a['quality']!=b['quality'] or a['phase']=='taper'
    specific=[r for r in rows if r['phase']=='specific'];mp=[r for r in specific if r['mp_km']>0];assert 2<=len(mp)<=4
    previous=None
    for r in rows:
        # The load-vector rule controls TRAINING Long Runs. Race day itself is not
        # constrained to be within 1.2 km of the final taper Long Run.
        if previous and r['phase']!='race' and r['mp_km']>previous['mp_km'] and r['mp_km']>0:
            assert r['longrun_km']<=previous['longrun_km']+1.2,(previous,r)
        if previous and r['phase']!='race' and r['longrun_km']>=previous['longrun_km']+1.5:
            assert r['mp_km']<=max(.1,previous['mp_km']),(previous,r)
        previous=r
    stable=[r for r in rows[3:13] if r['low_pct']>0];assert stable and sum(r['low_pct'] for r in stable)/len(stable)>=70
    pre_taper=max(r['planned_km'] for r in rows[:-3]);assert rows[-2]['planned_km']<pre_taper*.8 and rows[-1]['planned_km']<pre_taper
    return True


def markdown(rows):
    lines=['| W | Woche | Phase | km | Qualität | Longrun | MP | 4W niedrig/mod/hoch |','|---:|---|---|---:|---|---|---:|---|']
    for r in rows:lines.append(f"| {r['week']} | {r['week_start']} | {r['phase']} | {r['planned_km']:.1f} | {r['quality']} | {r['longrun']} | {r['mp_km']:.1f} km | {r['low_pct']:.0f}/{r['moderate_pct']:.0f}/{r['high_pct']:.0f}% |")
    return '\n'.join(lines)


if __name__=='__main__':
    plan,integrity,schema=build_plan();validate_plan(plan);assert integrity=='ok' and schema==4;print(markdown(plan))
