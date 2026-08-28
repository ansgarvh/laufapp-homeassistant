from __future__ import annotations
import json, math, sqlite3
from datetime import date, datetime, timedelta, timezone
from typing import Any
from db import get_setting

STANDARD_DISTANCES=[5.0,10.0,21.0975,42.195]
LABELS={5.0:'5 km',10.0:'10 km',21.0975:'Halbmarathon',42.195:'Marathon'}

def parse_dt(value:str)->datetime:
    value=value.strip()
    for candidate in (value,value.replace(' +','+')):
        try:
            d=datetime.fromisoformat(candidate)
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError: pass
    for fmt in ('%Y-%m-%d %H:%M:%S %z','%Y-%m-%d %H:%M:%S'):
        try:
            d=datetime.strptime(value,fmt); return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError: pass
    raise ValueError(f'Unbekanntes Datumsformat: {value}')

def week_start_for(d:date)->date:return d-timedelta(days=d.weekday())
def hms(sec:float|None)->str|None:
    if sec is None:return None
    s=max(0,int(round(sec)));h,r=divmod(s,3600);m,s=divmod(r,60);return f'{h}:{m:02d}:{s:02d}' if h else f'{m}:{s:02d}'
def pace_text(sec:float|None)->str|None:
    if not sec or sec<=0:return None
    m,s=divmod(int(round(sec)),60);return f'{m}:{s:02d}/km'
def riegel(t:float,from_km:float,to_km:float,exp:float=1.06)->float:return t*(to_km/from_km)**exp

def weekly_volume(c:sqlite3.Connection,weeks:int=8,ref:date|None=None)->list[float]:
    ref=ref or date.today(); first=week_start_for(ref)-timedelta(days=(weeks-1)*7)
    out=[0.0]*weeks
    for r in c.execute("SELECT started_at,distance_km FROM runs WHERE started_at>=?",(first.isoformat(),)).fetchall():
        try:i=(week_start_for(parse_dt(r['started_at']).date())-first).days//7
        except ValueError:continue
        if 0<=i<weeks:out[i]+=float(r['distance_km'] or 0)
    return [round(x,1) for x in out]

def recent_long_runs(c,weeks=8):
    start=(date.today()-timedelta(days=weeks*7)).isoformat()
    return [float(r['distance_km']) for r in c.execute("SELECT distance_km FROM runs WHERE started_at>=? ORDER BY distance_km DESC LIMIT 8",(start,)).fetchall()]

def consistency(c,weeks=8):
    vols=weekly_volume(c,weeks); return round(sum(1 for v in vols if v>=12)/weeks*100)

def _anchors(c)->list[dict[str,Any]]:
    out=[]; cutoff=(date.today()-timedelta(days=550)).isoformat()
    for r in c.execute("SELECT * FROM performance_marks WHERE mark_date>=? ORDER BY mark_date DESC",(cutoff,)).fetchall():
        out.append({'distance_km':float(r['distance_km']),'duration_s':float(r['duration_s']),'date':r['mark_date'],'source':r['source'],'label':r['label'] or 'Leistungsmarke','quality':1.0})
    cutoff=(date.today()-timedelta(days=210)).isoformat()
    runs=[dict(r) for r in c.execute("SELECT started_at,distance_km,duration_s FROM runs WHERE started_at>=? AND distance_km>=4.5 AND duration_s>0",(cutoff,)).fetchall()]
    for target in STANDARD_DISTANCES:
        eligible=[r for r in runs if .85*target<=float(r['distance_km'])<=1.35*target]
        if eligible:
            b=min(eligible,key=lambda r:float(r['duration_s'])/float(r['distance_km']))
            out.append({'distance_km':float(b['distance_km']),'duration_s':float(b['duration_s']),'date':b['started_at'][:10],'source':'training','label':'Schneller Trainingslauf','quality':.55})
    return out

def predict_distance(c,target:float)->dict[str,Any]|None:
    anchors=_anchors(c)
    if not anchors:return None
    ps=[]
    for a in anchors:
        exp=1.075 if target>=42 and a['distance_km']<20 else 1.06
        pred=riegel(a['duration_s'],a['distance_km'],target,exp)
        extrap=abs(math.log(max(target/a['distance_km'],1e-9),2)); age=max(0,(date.today()-date.fromisoformat(a['date'][:10])).days)
        score=a['quality']*max(.55,1-age/730)/(1+.28*extrap);ps.append({**a,'predicted':pred,'score':score})
    ps.sort(key=lambda x:(-x['score'],x['predicted'])); top=ps[0]['score']; selected=min([p for p in ps if p['score']>=top*.82],key=lambda x:x['predicted'])
    avg=sum(weekly_volume(c,6))/6; longest=max(recent_long_runs(c) or [0]); penalty=1.0;notes=[]
    if target>=40 and selected['distance_km']<35:
        if avg<30:penalty*=1.07;notes.append('geringer jüngster Wochenumfang')
        elif avg<40:penalty*=1.045;notes.append('moderater Wochenumfang')
        elif avg<50:penalty*=1.02
        if longest<24:penalty*=1.045;notes.append('noch wenig lange Läufe')
        elif longest<28:penalty*=1.02
    elif target>=20 and selected['distance_km']<18 and avg<25: penalty*=1.035
    pred=selected['predicted']*penalty; conf=max(.35,min(.96,selected['score']*(.95 if penalty==1 else .88)));unc=.02+(1-conf)*.09
    low,high=pred*(1-unc),pred*(1+unc)
    return {'distance_km':target,'label':LABELS.get(target,f'{target:g} km'),'predicted_seconds':round(pred),'predicted_time':hms(pred),'low_seconds':round(low),'high_seconds':round(high),'range_text':f'{hms(low)}–{hms(high)}','confidence':round(conf,2),'anchor':{k:selected[k] for k in ('distance_km','duration_s','date','source','label')},'notes':notes}

def predict_all(c):return [p for d in STANDARD_DISTANCES if (p:=predict_distance(c,d))]

def current_race(c):return c.execute("SELECT * FROM races WHERE active=1 ORDER BY id DESC LIMIT 1").fetchone()

def goal_assessment(c,race):
    race=dict(race);pred=predict_distance(c,float(race['distance_km']));days=(date.fromisoformat(race['race_date'])-date.today()).days
    if not pred:return {'status':'noch keine Prognose','level':'neutral','message':'Für eine belastbare Prognose fehlen noch Leistungsdaten.','prediction':None,'days_to_race':days}
    goal=float(race['goal_seconds']);cur=float(pred['predicted_seconds']);gap=(cur-goal)/cur-min(.025,max(0,days/7)*.0022)
    if goal>=cur: status,level,msg='realistisch','good','Deine aktuelle Prognose liegt bereits auf oder unter der Zielzeit.'
    elif gap<=.012: status,level,msg='realistisch','good','Das Ziel liegt nahe an der aktuellen Prognose und passt zum verbleibenden Trainingsfenster.'
    elif gap<=.04: status,level,msg='ambitioniert','warn','Das Ziel ist erreichbar, verlangt aber eine klare Leistungsentwicklung und hohe Trainingskonstanz.'
    else: status,level,msg='derzeit unwahrscheinlich','risk','Die aktuelle Leistungsbasis liegt deutlich hinter der Zielzeit. Ein Zwischenziel wäre sinnvoll.'
    return {'status':status,'level':level,'message':msg,'prediction':pred,'days_to_race':days,'goal_gap_seconds':round(cur-goal)}

def performance_profile(c,race=None):
    vols=weekly_volume(c,8);avg=sum(vols)/len(vols);longest=max(recent_long_runs(c) or [0]);dist=float(race['distance_km']) if race else 21.0975
    vt=55 if dist>=40 else 45 if dist>=20 else 35;lt=30 if dist>=40 else 22 if dist>=20 else 16 if dist>=10 else 12
    endurance=min(100,100*avg/max(vt,1));m_end=min(100,50*avg/vt+50*longest/lt)
    p5,p10,phm=predict_distance(c,5),predict_distance(c,10),predict_distance(c,21.0975);speed=threshold=50
    if p5 and p10:
        fade=p10['predicted_seconds']/max(riegel(p5['predicted_seconds'],5,10),1);speed=max(20,min(100,95-max(0,fade-1)*300))
    if p10 and phm:
        fade=phm['predicted_seconds']/max(riegel(p10['predicted_seconds'],10,21.0975),1);threshold=max(20,min(100,95-max(0,fade-1)*300))
    return {'Grundlagenausdauer':round(endurance),'Schwelle':round(threshold),'Speed':round(speed),'Marathon-Ausdauer':round(m_end if dist>=40 else (endurance+threshold)/2),'Trainingskonstanz':consistency(c)}

def _prefs(c,dist):
    long_default=35 if dist>=40 else 26 if dist>=20 else 18 if dist>=10 else 14
    return {'volume':get_setting(c,'training_volume_profile','steady'),'difficulty':get_setting(c,'training_difficulty','balanced'),'baseline':max(8,min(160,float(get_setting(c,'baseline_weekly_km',40)))),'max_long':max(8,min(50,float(get_setting(c,'max_long_run_km',long_default)))),'max_share':max(.30,min(.60,float(get_setting(c,'max_long_run_share',.45)))),'quality':max(1,min(3,int(get_setting(c,'quality_sessions_per_week',2))))}

def established_volume(c,ref:date|None=None):
    """Robust baseline from eight *completed* weeks; the current week is context only."""
    ref=ref or date.today(); current=week_start_for(ref); vols=weekly_volume(c,9,current-timedelta(days=1))[:8]
    active=[v for v in vols if v>=5]
    if len(active)<3:return {'km':None,'trend':'unzureichende Historie','completed_weeks':vols,'current_partial_km':weekly_volume(c,1,ref)[0]}
    ordered=sorted(active); trimmed=ordered[1:-1] if len(ordered)>=5 else ordered
    robust=sum(trimmed)/len(trimmed)
    recent=active[-3:]
    # Three consecutive completed reductions, with the latest below 70% of the
    # older robust level, are treated as detraining rather than a single deload.
    detraining=len(recent)==3 and recent[0]>recent[1]>recent[2] and recent[-1]<robust*.70
    if detraining: robust=.65*sum(recent)/3+.35*robust
    slope=(recent[-1]-recent[0])/max(recent[0],1)
    trend='reduziert' if detraining else 'steigend' if slope>.12 else 'stabil' if slope>=-.12 else 'wechselhaft'
    return {'km':round(robust,1),'trend':trend,'completed_weeks':vols,'current_partial_km':weekly_volume(c,1,ref)[0]}

def long_run_history(c,ref:date|None=None):
    ref=ref or date.today(); start=(ref-timedelta(days=56)).isoformat()
    runs=[(parse_dt(r['started_at']).date(),float(r['distance_km'])) for r in c.execute("SELECT started_at,distance_km FROM runs WHERE started_at>=? ORDER BY started_at",(start,)).fetchall() if float(r['distance_km'] or 0)>=12]
    return {'distances':[x[1] for x in runs],'longest_4w':max((x[1] for x in runs if x[0]>=ref-timedelta(days=28)),default=0),'longest_8w':max((x[1] for x in runs),default=0),'ge20':sum(x[1]>=20 for x in runs),'ge24':sum(x[1]>=24 for x in runs),'ge28':sum(x[1]>=28 for x in runs),'ge30':sum(x[1]>=30 for x in runs)}

def _zones(c,race):
    dist=float(race['distance_km']);goal=float(race['goal_seconds'])/dist;p5=predict_distance(c,5);p10=predict_distance(c,10);phm=predict_distance(c,21.0975)
    threshold=(p10['predicted_seconds']/10) if p10 else goal-(18 if dist>=20 else 5)
    if phm and dist>=40:threshold=phm['predicted_seconds']/21.0975
    interval=(p5['predicted_seconds']/5) if p5 else max(180,threshold-20)
    return {'easy':(goal+(55 if dist>=20 else 45),goal+(95 if dist>=20 else 80)),'goal':(goal-5,goal+5),'threshold':(threshold-5,threshold+5),'interval':(interval-4,interval+4)}

def _phase(race,ws):
    weeks=max(0,(date.fromisoformat(race['race_date'])-ws).days//7)
    if weeks==0:return 'race',weeks
    if weeks<=2:return 'taper',weeks
    if weeks<=5:return 'peak',weeks
    if weeks<=12:return 'specific',weeks
    return 'build',weeks

def _block_recovery(c,ws,phase):
    if phase not in {'build','specific'}:return False
    # Derive block position from race-relative weeks, not calendar week number.
    race=current_race(c); race_ws=week_start_for(date.fromisoformat(race['race_date']))
    sequence=((race_ws-ws).days//7)
    cycle=3 if phase=='specific' else 4
    return sequence%cycle==0

def _weekly_target(c,race,ws):
    prefs=_prefs(c,float(race['distance_km'])); ev=established_volume(c,ws);base=ev['km'] or prefs['baseline'];phase,weeks=_phase(race,ws)
    recovery=_block_recovery(c,ws,phase)
    factor={'gradual':1.01,'steady':1.025,'progressive':1.04}.get(prefs['volume'],1.025)
    if ev['trend']=='reduziert':factor=min(factor,.96)
    if phase=='specific':factor+=.01
    elif phase=='peak':factor+=.015
    elif phase=='taper':factor={2:.72,1:.52}.get(weeks,.45)
    elif phase=='race':factor=.42
    if recovery:factor=.84;phase='recovery'
    ceiling=82 if float(race['distance_km'])>=40 else 66 if float(race['distance_km'])>=20 else 54
    ceiling=max(ceiling,base*1.04) # established athletes are not forced below their history
    target=max(14,min(ceiling,base*factor))
    recommendation=automatic_max_weekly_km(c,race,ws)
    user_cap=float(get_setting(c,'max_weekly_km',recommendation)) if get_setting(c,'max_weekly_km_mode','auto')=='user' else recommendation
    return min(target,user_cap),phase

def automatic_max_weekly_km(c,race=None,ref:date|None=None):
    """History-based hard ceiling: robust completed-week volume times a race/trend factor."""
    race=race or current_race(c);dist=float(race['distance_km']) if race else 21.0975
    ev=established_volume(c,ref);base=ev['km'] or float(get_setting(c,'baseline_weekly_km',40))
    factor=1.10 if dist>=40 else 1.08 if dist>=20 else 1.06
    if ev['trend']=='reduziert':factor*=.95
    return round(max(14,min(180,base*factor)),1)

def _long_run(c,race,ws,phase,total):
    dist=float(race['distance_km']);p=_prefs(c,dist);h=long_run_history(c,ws);recent=h['longest_4w'] or h['longest_8w']; normal=total*min(.38,p['max_share'])
    if dist<40:return min(p['max_long'],24 if dist>=20 else 18,max(9,normal)),'easy','Ruhiger langer Lauf.'
    if phase=='race':return dist,'race','Zielwettkampf.'
    if phase=='taper':return min(p['max_long'],max(14,total*.34)),'taper','Reduzierter Long Run für Frische bei erhaltener Ausdauer.'
    if phase=='recovery':return min(p['max_long'],max(16,recent*.78 if recent else normal*.8)),'recovery','Bewusst reduzierter Long Run nach dem Belastungsblock.'
    safe_history=min(p['max_long'],(recent+3 if recent else normal))
    if phase=='peak' and total>=58 and h['ge28']>=2 and p['max_long']>=30:
        km=min(p['max_long'],35,max(30,min(safe_history,total*.50)));kind='peak'
    elif phase in {'specific','peak'} and h['ge24']>=2:
        km=min(safe_history,max(normal,recent));kind='mp_blocks' if ((date.fromisoformat(race['race_date'])-ws).days//7)%2==0 else 'mp_finish'
    elif recent>=18:
        km=min(safe_history,max(normal,recent));kind='progressive' if phase=='specific' else 'easy'
    else:km=min(safe_history,max(14,normal));kind='easy'
    reasons=f"{round(km):g} km aus {h['longest_8w']:g} km längstem Lauf und {round(total):g} km geplantem Wochenumfang."
    return km,kind,reasons

def _templates(c,race,ws,phase,total):
    dist=float(race['distance_km']);p=_prefs(c,dist);long_km,kind,reason=_long_run(c,race,ws,phase,total)
    hard_long=kind in {'progressive','mp_finish','mp_blocks'}
    idx=((date.fromisoformat(race['race_date'])-ws).days//7)%4
    if hard_long: qt,qd,qz,qr='Kurze Schwellenreize','2 km locker, 4 × 5 min kontrolliert zügig mit 2 min Trabpause, auslaufen.','threshold','6–7/10'
    elif phase in {'specific','peak'} and idx in {0,2}: qt,qd,qz,qr='Marathon-Pace','2 km locker, kontrollierter Abschnitt in Marathonpace, locker auslaufen.','goal','6–7/10'
    elif idx==1:qt,qd,qz,qr='Cruise-Intervalle','2 km locker, 5 × 1,5 km an der Schwelle mit kurzer Trabpause, auslaufen.','threshold','7/10'
    elif idx==2:qt,qd,qz,qr='Kontinuierlicher Tempolauf','2 km locker, 25–35 min kontrolliert an der Schwelle, auslaufen.','threshold','7/10'
    else:qt,qd,qz,qr='Schwellenintervalle','2 km locker, 3 × 3 km kontrolliert an der Schwelle, 2 min Trabpause, auslaufen.','threshold','7–8/10'
    run_days=len(get_setting(c,'training_days',[1,3,4,6]));quality_limit=min(p['quality'],max(1,run_days-2)); hard_budget=max(0,quality_limit-(1 if hard_long else 0))
    if phase=='race':
        easy_count=max(1,run_days-2);easy_km=max(2,(total-dist-5)/easy_count)
        return [('easy','Locker + Strides' if i==0 else 'Shakeout',easy_km,'easy','1–3/10','Frische','Sehr locker; einige kurze Steigerungen nur bei guten Beinen.') for i in range(easy_count)]+[('raceprep','Race-Pace Aktivierung',5,'goal','5/10','Aktivierung','Kurze Zielpace-Reize.'),('race','Wettkampf',dist,'goal','Wettkampf','Zielwettkampf','Kontrolliert eröffnen.')]
    quality=max(5,total*(.14 if hard_long else .18)); remaining=max(0,total-long_km-quality*hard_budget);easy_km=remaining/max(1,run_days-1-hard_budget)
    long_text={'easy':'Ruhig und gesprächsfähig; Fueling üben.','progressive':'Überwiegend locker, den Schluss kontrolliert moderat laufen.','mp_finish':'Überwiegend locker, finalen Abschnitt kontrolliert in Marathonpace.','mp_blocks':'Lockere Abschnitte mit einfachen Marathonpace-Blöcken; nicht schneller.','peak':'Langer, überwiegend lockerer Ausdauerlauf; Fueling vollständig proben.','recovery':'Bewusst locker und reduziert.','taper':'Locker, kurz und frisch beenden.'}.get(kind,'Locker laufen.')
    templates=[]
    for i in range(run_days-1):
        if i<hard_budget:templates.append(('quality',qt if i==0 else 'Kontrollierter Tempolauf',quality,qz,qr,'Qualität ohne Überlastung',qd))
        else:templates.append(('easy','Regenerationslauf' if run_days>=6 and i==run_days-2 else 'Easy Run',max(3,easy_km),'easy','2–3/10','Aerobe Basis','Locker; RPE hat Vorrang.'))
    templates.append(('long','Long Run',long_km,'goal' if hard_long and kind!='progressive' else 'easy','6/10' if hard_long else '3–4/10','Marathon-Ausdauer',long_text+' '+reason))
    # Rounding/minimums must never turn a ceiling into a target violation.
    scale=min(1,total/sum(x[2] for x in templates))
    return [(*x[:2],x[2]*scale,*x[3:]) for x in templates]

def _wdict(r):
    d=dict(r);d['details']=json.loads(d.pop('details_json','{}'));d['pace_text']=None
    if d.get('pace_low_s_per_km') and d.get('pace_high_s_per_km'):d['pace_text']=f"{pace_text(d['pace_low_s_per_km']).replace('/km','')}–{pace_text(d['pace_high_s_per_km'])}"
    return d

def mark_plan_stale(c,reason):
    if c.execute("SELECT 1 FROM workouts WHERE status='planned' AND scheduled_date>=? LIMIT 1",(date.today().isoformat(),)).fetchone():
        from db import set_setting
        set_setting(c,'plan_stale',True);set_setting(c,'plan_stale_reason',reason)

def plan_basis(c,ws,race,total,phase):
    ev=established_volume(c,ws);lh=long_run_history(c,ws);weeks=max(0,(date.fromisoformat(race['race_date'])-ws).days//7)
    return {'established_weekly_km':ev['km'] or _prefs(c,float(race['distance_km']))['baseline'],'trend':ev['trend'],'longest_recent_km':lh['longest_8w'],'phase':phase,'weeks_to_race':weeks,'planned_weekly_km':round(total,1),'current_partial_km':ev['current_partial_km']}

def _cleanup_generated_collisions(c,ws:date)->int:
    """Remove only stale engine rows that collide with protected/user-owned rows.

    v0.1.8 could regenerate a planned engine workout on a date that already held
    a completed, linked or manually changed workout. Those stale duplicates are
    safe to remove because the protected row is authoritative. Ambiguous groups
    containing only generated planned rows are left untouched for investigation.
    """
    start=week_start_for(ws);key=start.isoformat();end=(start+timedelta(days=6)).isoformat();removed=0
    groups={}
    for r in c.execute("SELECT * FROM workouts WHERE scheduled_date BETWEEN ? AND ? ORDER BY id",(key,end)).fetchall():groups.setdefault(r['scheduled_date'],[]).append(r)
    for group in groups.values():
        if len(group)<2:continue
        protected=[r for r in group if r['status']!='planned' or r['linked_run_id'] is not None or int(r['manual_override'] or 0)!=0 or (r['modified_by'] or 'engine')!='engine']
        generated=[r for r in group if r['status']=='planned' and r['linked_run_id'] is None and int(r['manual_override'] or 0)==0 and (r['modified_by'] or 'engine')=='engine']
        if protected and generated:
            c.executemany("DELETE FROM workouts WHERE id=?",[(int(r['id']),) for r in generated]);removed+=len(generated)
    return removed

def _remaining_template_slots(dates,templates,native_rows):
    """Consume one deterministic template slot for every preserved native row."""
    slots=[{'date':d,'template':t,'used':False} for d,t in zip(dates,templates)]
    for r in sorted(native_rows,key=lambda x:int(x['id'])):
        available=[i for i,s in enumerate(slots) if not s['used']]
        if not available:break
        scheduled=str(r['scheduled_date']);typ=str(r['workout_type']);title=str(r['title'])
        chosen=next((i for i in available if slots[i]['date'].isoformat()==scheduled),None)
        if chosen is None:chosen=next((i for i in available if slots[i]['template'][0]==typ and slots[i]['template'][1]==title),None)
        if chosen is None:chosen=next((i for i in available if slots[i]['template'][0]==typ),None)
        if chosen is None:chosen=available[0]
        slots[chosen]['used']=True
    return [(s['date'],s['template']) for s in slots if not s['used']]

def _schedule_remaining_slots(ws,remaining,occupied):
    """Keep configured dates where possible; relocate only true collisions."""
    week_dates=[ws+timedelta(days=i) for i in range(7)];assigned=set();out=[]
    reserved={d.isoformat() for d,_ in remaining if d.isoformat() not in occupied}
    for preferred,t in remaining:
        key=preferred.isoformat()
        if key not in occupied and key not in assigned:
            scheduled=preferred
        else:
            pool=[d for d in week_dates if d.isoformat() not in occupied and d.isoformat() not in assigned and d.isoformat() not in reserved]
            if not pool:pool=[d for d in week_dates if d.isoformat() not in occupied and d.isoformat() not in assigned]
            # Seven configured days plus an incoming manual workout can leave no
            # unique day. Preserve the requested/manual schedule rather than
            # deleting a native session; the guardrails can then surface density.
            scheduled=min(pool,key=lambda d:(abs((d-preferred).days),d.weekday())) if pool else preferred
        assigned.add(scheduled.isoformat());reserved.discard(scheduled.isoformat());out.append((scheduled,t))
    return out

def generate_week(c,ws:date|None=None,force=False):
    ws=week_start_for(ws or date.today());key=ws.isoformat();removed=_cleanup_generated_collisions(c,ws)
    existing=c.execute("SELECT * FROM workouts WHERE week_start=? ORDER BY scheduled_date,id",(key,)).fetchall();native=c.execute("SELECT * FROM workouts WHERE origin_week_start=? ORDER BY scheduled_date,id",(key,)).fetchall()
    # Normal week loads must never silently regenerate after a settings change.
    # The sole exception is self-healing after the v0.1.8 collision cleanup.
    if native and not force and not removed:return [_wdict(r) for r in existing]
    race=current_race(c)
    if not race:return [_wdict(r) for r in existing]
    if force:
        # Only untouched, future, planned generated rows are replaceable.
        c.execute("DELETE FROM workouts WHERE origin_week_start=? AND scheduled_date>=? AND status='planned' AND linked_run_id IS NULL AND COALESCE(manual_override,0)=0",(key,date.today().isoformat()))
        c.execute("DELETE FROM plan_reviews WHERE week_start=?",(key,))
    native_rows=c.execute("SELECT * FROM workouts WHERE origin_week_start=? ORDER BY scheduled_date,id",(key,)).fetchall()
    total,phase=_weekly_target(c,race,ws);zones=_zones(c,race);templates=_templates(c,race,ws,phase,total);days=sorted(set(int(x) for x in get_setting(c,'training_days',[1,3,4,6]) if 0<=int(x)<=6));days=days if 3<=len(days)<=7 else [1,3,4,6];dates=[ws+timedelta(days=d) for d in days]
    remaining_slots=_remaining_template_slots(dates,templates,native_rows)
    visible=c.execute("SELECT * FROM workouts WHERE scheduled_date BETWEEN ? AND ? ORDER BY scheduled_date,id",(key,(ws+timedelta(days=6)).isoformat())).fetchall();occupied={r['scheduled_date'] for r in visible};preserved_km=sum(float(r['distance_km'] or 0) for r in visible)
    candidates=_schedule_remaining_slots(ws,remaining_slots,occupied)
    candidate_km=sum(float(t[2]) for _,t in candidates);remaining_km=max(0.0,total-preserved_km);scale=min(1.0,remaining_km/candidate_km) if candidate_km>0 else 0.0
    generation=datetime.now(timezone.utc).isoformat()
    for scheduled,t in candidates:
        typ,title,km,zone,rpe,purpose,instructions=t;km*=scale
        if km<=0.05:continue
        low,high=zones.get(zone,(None,None));details={'purpose':purpose,'instructions':instructions,'phase':phase,'week_target_km':round(total,1),'rpe_target':rpe,'plan_basis':plan_basis(c,ws,race,total,phase)}
        c.execute("INSERT INTO workouts(week_start,origin_week_start,scheduled_date,workout_type,title,distance_km,pace_low_s_per_km,pace_high_s_per_km,details_json,status,manual_override,modified_by,generation_version,plan_generation_id) VALUES(?,?,?,?,?,?,?,?,?,'planned',0,'engine','0.1.9',?)",(key,key,scheduled.isoformat(),typ,title,round(km,1),low,high,json.dumps(details,ensure_ascii=False),generation))
    if force:
        from db import set_setting
        set_setting(c,'plan_stale',False);set_setting(c,'plan_stale_reason','')
    return [_wdict(r) for r in c.execute("SELECT * FROM workouts WHERE week_start=? ORDER BY scheduled_date,id",(key,)).fetchall()]

def refresh_plan(c,start:date|None=None,weeks=4):
    start=week_start_for(start or date.today());old=[]
    for i in range(weeks):
        ws=start+timedelta(days=7*i);_cleanup_generated_collisions(c,ws);rows0=[_wdict(r) for r in c.execute("SELECT * FROM workouts WHERE week_start=? ORDER BY scheduled_date,id",(ws.isoformat(),))]
        if i==0:old=rows0
        generate_week(c,ws,True)
    new=[_wdict(r) for r in c.execute("SELECT * FROM workouts WHERE week_start=? ORDER BY scheduled_date,id",(start.isoformat(),))]
    def stats(xs):return (round(sum(float(x['distance_km']) for x in xs),1),max([float(x['distance_km']) for x in xs if x['workout_type']=='long'] or [0]),next((x['title'] for x in xs if x['workout_type']=='quality'),None))
    a,b=stats(old),stats(new);diff={}
    if a[0]!=b[0]:diff['volume_km']={'old':a[0],'new':b[0]}
    if a[1]!=b[1]:diff['long_run_km']={'old':a[1],'new':b[1]}
    if a[2]!=b[2]:diff['quality']={'old':a[2],'new':b[2]}
    if len(old)!=len(new):diff['session_count']={'old':len(old),'new':len(new)}
    return {'updated':bool(diff),'diff':diff,'weeks':weeks,'summary_week_start':start.isoformat()}

def move_workout(c,wid:int,new:date):
    r=c.execute("SELECT * FROM workouts WHERE id=?",(wid,)).fetchone()
    if not r:raise KeyError('Workout nicht gefunden')
    if r['status']!='planned':raise ValueError('Nur geplante Einheiten können verschoben werden.')
    old=date.fromisoformat(r['scheduled_date'])
    if new==old:return {'workout':_wdict(r),'warnings':[],'operation':'noop'}
    targets=c.execute("SELECT * FROM workouts WHERE id!=? AND scheduled_date=? ORDER BY id",(wid,new.isoformat())).fetchall()
    if len(targets)>1:raise ValueError('Der Zieltag ist mehrfach belegt. Bitte die Woche zuerst neu laden beziehungsweise bereinigen.')
    target=targets[0] if targets else None
    if target and target['status']!='planned':raise ValueError('Auf eine absolvierte Einheit kann nicht getauscht werden.')
    if target:
        c.execute("UPDATE workouts SET scheduled_date=?,week_start=?,manual_override=1,modified_by='user' WHERE id=?",(old.isoformat(),week_start_for(old).isoformat(),target['id']))
    c.execute("UPDATE workouts SET scheduled_date=?,week_start=?,manual_override=1,modified_by='user' WHERE id=?",(new.isoformat(),week_start_for(new).isoformat(),wid))
    return {'workout':_wdict(c.execute("SELECT * FROM workouts WHERE id=?",(wid,)).fetchone()),'warnings':[],'operation':'swap' if target else 'move'}

def auto_match_run(c,run_id):
    r=c.execute("SELECT * FROM runs WHERE id=?",(run_id,)).fetchone();day=parse_dt(r['started_at']).date().isoformat() if r else '' ;w=c.execute("SELECT * FROM workouts WHERE scheduled_date=? AND status='planned' ORDER BY ABS(distance_km-?) LIMIT 1",(day,float(r['distance_km']) if r else 0)).fetchone()
    if not w:return None
    c.execute("UPDATE workouts SET status='completed',linked_run_id=? WHERE id=?",(run_id,w['id']));return int(w['id'])

def guardrails(c,workouts):
    planned=sum(float(w['distance_km']) for w in workouts);long_km=sum(float(w['distance_km']) for w in workouts if w['workout_type'] in {'long','race'});share=long_km/planned if planned else 0;cap=float(get_setting(c,'max_long_run_share',.45));alerts=[]
    if share>cap+.015 and not any(w['workout_type']=='race' for w in workouts):alerts.append({'level':'info','text':f'Longrun-Anteil {share:.0%} über dem üblichen Guardrail; lockerer Restumfang wurde angepasst.'})
    hard=sum(w['workout_type'] in {'quality','raceprep','race'} or (w['workout_type']=='long' and (w.get('details') or {}).get('rpe_target')=='6/10') for w in workouts)
    return {'long_run_share':round(share,3),'long_run_share_cap':round(cap,3),'low_intensity_distance_share':round(sum(float(w['distance_km']) for w in workouts if w['workout_type'] in {'easy','long'})/planned,3) if planned else 0,'hard_sessions':hard,'skipped_sessions':sum(w['status']=='skipped' for w in workouts),'alerts':alerts,'needs_review':bool(alerts)}

def week_summary(c,ws):
    workouts=generate_week(c,ws);planned=sum(float(w['distance_km']) for w in workouts);race=current_race(c);total,phase=_weekly_target(c,race,ws) if race else (planned,'build');basis=plan_basis(c,ws,race,total,phase) if race else None
    actual=float(c.execute("SELECT COALESCE(SUM(distance_km),0) km FROM runs WHERE started_at>=? AND started_at<?",(ws.isoformat(),(ws+timedelta(days=7)).isoformat())).fetchone()['km'] or 0)
    return {'week_start':ws.isoformat(),'week_end':(ws+timedelta(days=6)).isoformat(),'workouts':workouts,'planned_km':round(planned,1),'completed_planned_km':round(sum(float(w['distance_km']) for w in workouts if w['status']=='completed'),1),'actual_km':round(actual,1),'guardrails':guardrails(c,workouts),'plan_basis':basis,'plan_stale':bool(get_setting(c,'plan_stale',False)),'plan_stale_reason':get_setting(c,'plan_stale_reason','')}

def dashboard(c):
    race=current_race(c);today=date.today();week=week_summary(c,week_start_for(today)) if race else {'workouts':[],'planned_km':0,'actual_km':0};n=next((w for w in week['workouts'] if w['status']=='planned' and w['scheduled_date']>=today.isoformat()),None)
    return {'today':today.isoformat(),'race':dict(race) if race else None,'assessment':goal_assessment(c,race) if race else None,'next_workout':n,'week':week,'profile':performance_profile(c,race),'pending_suggestions':c.execute("SELECT COUNT(*) n FROM suggestions WHERE status='pending'").fetchone()['n']}
