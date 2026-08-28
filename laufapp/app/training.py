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
    return {'volume':get_setting(c,'training_volume_profile','steady'),'difficulty':get_setting(c,'training_difficulty','balanced'),'baseline':max(8,min(160,float(get_setting(c,'baseline_weekly_km',40)))),'max_long':max(8,min(50,float(get_setting(c,'max_long_run_km',32 if dist>=40 else 24)))),'max_share':max(.30,min(.60,float(get_setting(c,'max_long_run_share',.45))))}

def _zones(c,race):
    dist=float(race['distance_km']);goal=float(race['goal_seconds'])/dist;p5=predict_distance(c,5);p10=predict_distance(c,10);phm=predict_distance(c,21.0975)
    threshold=(p10['predicted_seconds']/10) if p10 else goal-(18 if dist>=20 else 5)
    if phm and dist>=40:threshold=phm['predicted_seconds']/21.0975
    interval=(p5['predicted_seconds']/5) if p5 else max(180,threshold-20)
    return {'easy':(goal+(55 if dist>=20 else 45),goal+(95 if dist>=20 else 80)),'goal':(goal-5,goal+5),'threshold':(threshold-5,threshold+5),'interval':(interval-4,interval+4)}

def _weekly_target(c,race,ws):
    prefs=_prefs(c,float(race['distance_km']));recent=[v for v in weekly_volume(c,4,ws) if v>0];base=sum(recent)/len(recent) if recent else prefs['baseline'];days=(date.fromisoformat(race['race_date'])-ws).days
    if days<=6:return max(14,base*.45),'race'
    if days<=13:return max(18,base*.65),'taper'
    if days<=20:return max(24,base*.82),'taper'
    if ws.isocalendar().week%4==0:return max(20,base*.86),'deload'
    growth={'gradual':1.03,'steady':1.055,'progressive':1.075}.get(prefs['volume'],1.055);ceiling=82 if float(race['distance_km'])>=40 else 66 if float(race['distance_km'])>=20 else 54
    return max(20,min(ceiling,base*growth)),'build'

def _templates(c,dist,phase,total):
    prefs=_prefs(c,dist);diff=prefs['difficulty']
    if phase=='race':
        rem=max(10,total-dist)
        return [('easy','Locker + Strides',min(8,rem*.42),'easy','2–3/10','Frische erhalten','Locker laufen, danach 4 × 20 s lockere Steigerungen.'),('raceprep','Race-Pace Aktivierung',min(7,rem*.34),'goal','5–6/10','Wettkampfgefühl aktivieren','Kurzes Einlaufen, 3 × 1 km in Zielpace mit viel lockerer Pause, auslaufen.'),('easy','Shakeout',max(4,rem*.24),'easy','1–2/10','Beine locker halten','Sehr locker; nur wenn du dich frisch fühlst.'),('race','Wettkampf',dist,'goal','wettkampfspezifisch','Zielwettkampf','Pacing kontrolliert eröffnen und den im Training erprobten Fueling-Plan umsetzen.')]
    cap=min(32 if dist>=40 else 24 if dist>=20 else 18 if dist>=10 else 15,prefs['max_long']);long_km=min(cap,max(12 if dist>=20 else 9,total*min(.38 if dist>=20 else .32,prefs['max_share'])))
    qfrac={'comfortable':.18,'balanced':.22,'challenging':.25}.get(diff,.22);quality=max(7,total*qfrac);easy1=max(5,total*.20);easy2=max(5,total-long_km-quality-easy1)
    if phase=='deload':qt='Kontrollierter Tempolauf';qd='2 km einlaufen, 20–25 min kontrolliert zügig, locker auslaufen. Kein All-out.';qz='threshold';qr='6–7/10'
    elif dist>=20:
        reps={'comfortable':3,'balanced':4,'challenging':5}.get(diff,4);qt='Schwellenintervalle';qd=f'2 km einlaufen, {reps} × 2 km kontrolliert an der Schwelle, 2 min Trabpause, locker auslaufen.';qz='threshold';qr={'comfortable':'6–7/10','balanced':'7–8/10','challenging':'8/10'}.get(diff,'7–8/10')
    else:
        reps={'comfortable':5,'balanced':6,'challenging':7}.get(diff,6);qt=f'{reps} × 1 km';qd=f'2 km einlaufen, {reps} × 1 km kontrolliert schnell, 2 min Trabpause, auslaufen.';qz='interval';qr='7–8/10'
    ld='Reduzierter Longrun. Intensität niedrig halten; Ziel ist Frische.' if phase=='taper' else ('Ruhiger Longrun. Fueling und Trinken wie im Wettkampf testen.' if dist>=20 else 'Ruhiger langer Lauf in entspannter Intensität.')
    return [('easy','Easy Run',easy1,'easy','2–3/10','Aerobe Basis','Locker und gesprächsfähig laufen. Bei Hitze, Hügeln oder Müdigkeit hat RPE Vorrang vor Pace.'),('quality',qt,quality,qz,qr,'Schwelle & Laufökonomie',qd),('easy','Easy Run',easy2,'easy','2–3/10','Umfang ohne hohe Ermüdung','Locker laufen. Pace nicht erzwingen.'),('long','Long Run',long_km,'easy','3–4/10','Ausdauer & Ermüdungsresistenz',ld)]

def _wdict(r):
    d=dict(r);d['details']=json.loads(d.pop('details_json','{}'));d['pace_text']=None
    if d.get('pace_low_s_per_km') and d.get('pace_high_s_per_km'):d['pace_text']=f"{pace_text(d['pace_low_s_per_km']).replace('/km','')}–{pace_text(d['pace_high_s_per_km'])}"
    return d

def generate_week(c,ws:date|None=None,force=False):
    ws=week_start_for(ws or date.today());key=ws.isoformat()
    existing=c.execute("SELECT * FROM workouts WHERE week_start=? ORDER BY scheduled_date",(key,)).fetchall()
    native=c.execute("SELECT * FROM workouts WHERE origin_week_start=? ORDER BY scheduled_date",(key,)).fetchall()
    # A workout moved in from a neighbouring week must not prevent creation of the
    # four native sessions of this week. origin_week_start keeps that distinction.
    if native and not force:return [_wdict(r) for r in existing]
    race=current_race(c)
    if not race:return [_wdict(r) for r in existing]
    if force and native:
        # Never destroy completed/skipped sessions or an explicit cross-week move.
        if any(r['status']!='planned' or r['week_start']!=key for r in native):return [_wdict(r) for r in existing]
        c.execute("DELETE FROM workouts WHERE origin_week_start=?",(key,));c.execute("DELETE FROM plan_reviews WHERE week_start=?",(key,))
    days=sorted(set(int(x) for x in get_setting(c,'training_days',[1,3,4,6]) if 0<=int(x)<=6));days=days if len(days)==4 else [1,3,4,6]
    total,phase=_weekly_target(c,race,ws);zones=_zones(c,race);templates=_templates(c,float(race['distance_km']),phase,total);dates=[ws+timedelta(days=d) for d in days];race_date=date.fromisoformat(race['race_date'])
    if phase=='race' and ws<=race_date<=ws+timedelta(days=6):dates=sorted([d for d in dates if d<race_date])[-3:]+[race_date]
    for scheduled,t in zip(dates,templates):
        typ,title,km,zone,rpe,purpose,instructions=t;low,high=zones.get(zone,(None,None));details={'purpose':purpose,'instructions':instructions,'phase':phase,'week_target_km':round(total,1),'rpe_target':rpe,'evidence_note':'Planheuristik: überwiegend lockerer Umfang, getrennte Belastungsspitzen, konservative Progression und Wettkampfspezifität. RPE darf bei Hitze, Höhenprofil oder ungewöhnlicher Müdigkeit Pace-Vorgaben übersteuern.'}
        c.execute("INSERT INTO workouts(week_start,origin_week_start,scheduled_date,workout_type,title,distance_km,pace_low_s_per_km,pace_high_s_per_km,details_json,status) VALUES(?,?,?,?,?,?,?,?,?, 'planned')",(key,key,scheduled.isoformat(),typ,title,round(km,1),low,high,json.dumps(details,ensure_ascii=False)))
    return [_wdict(r) for r in c.execute("SELECT * FROM workouts WHERE week_start=? ORDER BY scheduled_date",(ws.isoformat(),)).fetchall()]

def move_workout(c,wid:int,new:date):
    r=c.execute("SELECT * FROM workouts WHERE id=?",(wid,)).fetchone()
    if not r:raise KeyError('Workout nicht gefunden')
    if r['status']!='planned':raise ValueError('Nur geplante, noch offene Einheiten können verschoben werden.')
    old=date.fromisoformat(r['scheduled_date'])
    if abs((week_start_for(new)-week_start_for(old)).days)>7:raise ValueError('Ein Training kann höchstens in die vorherige oder nächste Woche verschoben werden.')
    if c.execute("SELECT id FROM workouts WHERE id!=? AND scheduled_date=? AND status='planned'",(wid,new.isoformat())).fetchone():raise ValueError('Auf diesem Tag liegt bereits eine geplante Laufeinheit.')
    warnings=[];hard={'quality','long','race','raceprep'}
    if r['workout_type'] in hard:
        for o in c.execute("SELECT * FROM workouts WHERE id!=? AND scheduled_date BETWEEN ? AND ?",(wid,(new-timedelta(days=1)).isoformat(),(new+timedelta(days=1)).isoformat())).fetchall():
            if o['workout_type'] in hard:warnings.append('Zwei belastende Einheiten liegen nun direkt nebeneinander. Prüfe Erholung und Wochenstruktur.');break
    new_ws=week_start_for(new);c.execute("UPDATE workouts SET scheduled_date=?,week_start=? WHERE id=?",(new.isoformat(),new_ws.isoformat(),wid));c.execute("DELETE FROM plan_reviews WHERE week_start IN (?,?)",(r['week_start'],new_ws.isoformat()))
    return {'workout':_wdict(c.execute("SELECT * FROM workouts WHERE id=?",(wid,)).fetchone()),'warnings':warnings}

def auto_match_run(c,run_id):
    r=c.execute("SELECT * FROM runs WHERE id=?",(run_id,)).fetchone()
    if not r:return None
    day=parse_dt(r['started_at']).date().isoformat();cands=c.execute("SELECT * FROM workouts WHERE scheduled_date=? AND status='planned'",(day,)).fetchall()
    if not cands:return None
    w=min(cands,key=lambda x:abs(float(x['distance_km'])-float(r['distance_km'])));c.execute("UPDATE workouts SET status='completed',linked_run_id=? WHERE id=?",(run_id,w['id']));return int(w['id'])

def guardrails(c,workouts):
    planned=sum(float(w['distance_km']) for w in workouts);long_km=sum(float(w['distance_km']) for w in workouts if w['workout_type'] in {'long','race'});share=long_km/planned if planned else 0;cap=float(get_setting(c,'max_long_run_share',.45));alerts=[]
    if share>cap+.015 and not any(w['workout_type']=='race' for w in workouts):alerts.append({'level':'warn','text':f'Longrun-Anteil {share:.0%} liegt über deinem Guardrail von {cap:.0%}.'})
    hard_dates=sorted(date.fromisoformat(w['scheduled_date']) for w in workouts if w['workout_type'] in {'quality','long','raceprep','race'})
    if any((b-a).days<=1 for a,b in zip(hard_dates,hard_dates[1:])):alerts.append({'level':'warn','text':'Belastende Einheiten liegen an aufeinanderfolgenden Tagen.'})
    skipped=sum(w['status']=='skipped' for w in workouts)
    if skipped>=2:alerts.append({'level':'info','text':'Mehrere Einheiten sind ausgefallen; eine adaptive Wochenprüfung ist sinnvoll.'})
    low=sum(float(w['distance_km']) for w in workouts if w['workout_type'] in {'easy','long'})/planned if planned else 0
    return {'long_run_share':round(share,3),'long_run_share_cap':round(cap,3),'low_intensity_distance_share':round(low,3),'hard_sessions':sum(w['workout_type'] in {'quality','raceprep','race'} for w in workouts),'skipped_sessions':skipped,'alerts':alerts,'needs_review':bool(alerts)}

def week_summary(c,ws):
    workouts=generate_week(c,ws);planned=sum(float(w['distance_km']) for w in workouts);completed=sum(float(w['distance_km']) for w in workouts if w['status']=='completed');actual=float(c.execute("SELECT COALESCE(SUM(distance_km),0) km FROM runs WHERE started_at>=? AND started_at<?",(ws.isoformat(),(ws+timedelta(days=7)).isoformat())).fetchone()['km'] or 0)
    return {'week_start':ws.isoformat(),'week_end':(ws+timedelta(days=6)).isoformat(),'workouts':workouts,'planned_km':round(planned,1),'completed_planned_km':round(completed,1),'actual_km':round(actual,1),'guardrails':guardrails(c,workouts)}

def dashboard(c):
    race=current_race(c);today=date.today();week=week_summary(c,week_start_for(today)) if race else {'workouts':[],'planned_km':0,'actual_km':0};n=next((w for w in week['workouts'] if w['status']=='planned' and w['scheduled_date']>=today.isoformat()),None)
    if not n and race:n=next((w for w in week_summary(c,week_start_for(today)+timedelta(days=7))['workouts'] if w['status']=='planned'),None)
    return {'today':today.isoformat(),'race':dict(race) if race else None,'assessment':goal_assessment(c,race) if race else None,'next_workout':n,'week':week,'profile':performance_profile(c,race),'pending_suggestions':c.execute("SELECT COUNT(*) n FROM suggestions WHERE status='pending'").fetchone()['n']}
