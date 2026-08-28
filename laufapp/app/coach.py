from __future__ import annotations
import base64, json, os, re, sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from db import get_setting
from training import current_race, dashboard, predict_all, weekly_volume, week_start_for, week_summary

RATES={'gpt-5.6-luna':(.20,1.20),'gpt-5.6-terra':(2,12),'gpt-5.6-sol':(4,20),'gpt-5.6':(4,20)}
WEB_SEARCH_EUR=.01

def _options():
    p=Path(os.environ.get('LAUFAPP_OPTIONS_FILE','/data/options.json'))
    if not p.exists():return {}
    try:return json.loads(p.read_text())
    except:return {}
def api_key():
    k=os.environ.get('OPENAI_API_KEY') or _options().get('openai_api_key');return k.strip() if isinstance(k,str) and k.strip() else None
def month_cost(c):
    pref=date.today().strftime('%Y-%m');return float(c.execute("SELECT COALESCE(SUM(estimated_cost_eur),0) v FROM ai_usage WHERE substr(created_at,1,7)=?",(pref,)).fetchone()['v'] or 0)
def config_status(c):return {'configured':bool(api_key()),'coach_model':get_setting(c,'coach_model','gpt-5.6-terra'),'vision_model':get_setting(c,'vision_model','gpt-5.6-luna'),'evidence_search':bool(get_setting(c,'evidence_search',True)),'monthly_budget_eur':float(get_setting(c,'monthly_ai_budget_eur',10)),'month_cost_eur':round(month_cost(c),4)}
def budget_check(c):
    budget=float(get_setting(c,'monthly_ai_budget_eur',10))
    if month_cost(c)>=budget:raise RuntimeError('Das monatliche KI-Budget wurde erreicht. Erhöhe das Limit unter Mehr → KI & Datenschutz.')
def usage(response):
    u=getattr(response,'usage',None);it=int(getattr(u,'input_tokens',0) or 0) if u else 0;ot=int(getattr(u,'output_tokens',0) or 0) if u else 0;ws=sum(getattr(x,'type',None)=='web_search_call' for x in (getattr(response,'output',None) or []));return it,ot,ws
def record_usage(c,kind,model,response):
    it,ot,ws=usage(response);ir,orr=RATES.get(model,(4,20));cost=(it*ir+ot*orr)/1e6+ws*WEB_SEARCH_EUR;c.execute("INSERT INTO ai_usage(usage_kind,model,input_tokens,output_tokens,web_searches,estimated_cost_eur) VALUES(?,?,?,?,?,?)",(kind,model,it,ot,ws,cost))
def sources(response):
    out=[];seen=set()
    for item in getattr(response,'output',None) or []:
        for content in getattr(item,'content',None) or []:
            for ann in getattr(content,'annotations',None) or []:
                u=getattr(ann,'url',None);title=getattr(ann,'title',None) or 'Quelle'
                if u and u not in seen:seen.add(u);out.append({'title':str(title),'url':str(u)})
    return out[:8]
def parse_json(text):
    text=(text or '').strip();text=re.sub(r'^```(?:json)?\s*|\s*```$','',text,flags=re.I)
    try:v=json.loads(text);return v if isinstance(v,dict) else {'reply':str(v)}
    except:pass
    m=re.search(r'\{.*\}',text,re.S)
    if m:
        try:return json.loads(m.group())
        except:pass
    return {'reply':text}
def request(model,input_data,tools=None,effort='medium'):
    try:from openai import OpenAI
    except ImportError as e:raise RuntimeError("Das Python-Paket 'openai' ist nicht installiert.") from e
    kwargs={'model':model,'input':input_data,'reasoning':{'effort':effort}}
    if tools:kwargs['tools']=tools
    return OpenAI(api_key=api_key()).responses.create(**kwargs)

def health_context(c):
    since=(date.today()-timedelta(days=21)).isoformat();rows=c.execute("SELECT metric_type,value FROM health_metrics WHERE start_at>=? ORDER BY start_at",(since,)).fetchall();g={}
    for r in rows:g.setdefault(r['metric_type'],[]).append(float(r['value']))
    return {k:{'latest':round(v[-1],2),'avg_recent':round(sum(v[-7:])/len(v[-7:]),2),'samples':len(v)} for k,v in g.items() if v}
def context(c):
    d=dashboard(c);race=current_race(c);runs=c.execute("SELECT id,started_at,distance_km,duration_s,avg_hr,elevation_m,rpe,notes FROM runs ORDER BY started_at DESC LIMIT 12").fetchall();shoes=c.execute("SELECT s.id,s.brand,s.model,s.nickname,s.start_km+COALESCE(SUM(r.distance_km),0) total_km FROM shoes s LEFT JOIN runs r ON r.shoe_id=s.id WHERE s.archived=0 GROUP BY s.id").fetchall()
    return {'date':date.today().isoformat(),'race':dict(race) if race else None,'goal_assessment':d.get('assessment'),'current_week':d.get('week'),'performance_profile':d.get('profile'),'race_predictions':predict_all(c),'weekly_km_last_8':weekly_volume(c,8),'recent_runs':[dict(r) for r in runs],'health_21d':health_context(c),'shoes':[dict(s) for s in shoes]}

def validate_suggestion(c,raw):
    if not isinstance(raw,dict):return None
    try:wid=int(raw.get('workout_id'));w=c.execute("SELECT * FROM workouts WHERE id=? AND status='planned'",(wid,)).fetchone()
    except:return None
    if not w:return None
    changes=raw.get('changes') or {};safe={}
    if 'distance_km' in changes:
        try:p=float(changes['distance_km']);cur=float(w['distance_km'])
        except:return None
        if not max(3,cur*.5)<=p<=cur*1.1:return None
        safe['distance_km']=round(p,1)
    if 'scheduled_date' in changes:
        try:
            proposed=date.fromisoformat(str(changes['scheduled_date']));old=date.fromisoformat(w['scheduled_date'])
            if abs((week_start_for(proposed)-week_start_for(old)).days)>7:return None
        except:return None
        safe['scheduled_date']=proposed.isoformat()
    if not safe:return None
    return {'title':str(raw.get('title') or 'Plananpassung')[:120],'rationale':str(raw.get('rationale') or 'Adaptive Trainingsanpassung')[:1200],'payload':{'action':'update_workout','workout_id':wid,'changes':safe}}
def add_suggestion(c,sug):
    if not sug:return None
    cur=c.execute("INSERT INTO suggestions(suggestion_type,title,rationale,payload_json) VALUES('plan_change',?,?,?)",(sug['title'],sug['rationale'],json.dumps(sug['payload'],ensure_ascii=False)));return int(cur.lastrowid)

def coach_chat(c,message):
    if not api_key():raise RuntimeError('OpenAI API ist noch nicht konfiguriert. Hinterlege den API-Key in der Home-Assistant-App-Konfiguration.')
    budget_check(c);model=str(get_setting(c,'coach_model','gpt-5.6-terra'));evidence=bool(get_setting(c,'evidence_search',True));ctx=context(c)
    system='''Du bist der evidenzorientierte Laufcoach einer privaten Laufapp. Antworte auf Deutsch, präzise und praktisch. Nutze nur bereitgestellte Messwerte, trenne Daten/Interpretation/Unsicherheit. Bei Trainingsvorschlägen nutze bei aktivierter Websuche bevorzugt mehrere hochwertige wissenschaftliche Quellen (systematische Reviews, Meta-Analysen, peer-reviewte Arbeiten, ACSM, IOC, World Athletics). Du darfst den Plan niemals direkt ändern. Änderungen nur als konservativer Vorschlag; keine abrupten Umfangssprünge oder zwei harte Einheiten direkt hintereinander. Medizinische Diagnosen sind nicht Aufgabe der App. Gib ausschließlich valides JSON zurück: {"reply":"...","suggestion":null} oder {"reply":"...","suggestion":{"title":"...","rationale":"...","workout_id":123,"changes":{"distance_km":8.0,"scheduled_date":"YYYY-MM-DD"}}}.'''
    inp=[{'role':'developer','content':system},{'role':'user','content':f'TRAININGSKONTEXT:\n{json.dumps(ctx,ensure_ascii=False)}\n\nFRAGE:\n{message}'}];resp=request(model,inp,[{'type':'web_search'}] if evidence else None);record_usage(c,'coach_chat',model,resp);parsed=parse_json(getattr(resp,'output_text',''));reply=str(parsed.get('reply') or 'Analyse abgeschlossen.');sug=validate_suggestion(c,parsed.get('suggestion'));sid=add_suggestion(c,sug);src=sources(resp)
    c.execute("INSERT INTO chat_messages(role,text,meta_json) VALUES('user',?, '{}')",(message,));c.execute("INSERT INTO chat_messages(role,text,meta_json) VALUES('assistant',?,?)",(reply,json.dumps({'sources':src,'suggestion_id':sid},ensure_ascii=False)));return {'reply':reply,'sources':src,'suggestion_id':sid,'suggestion':sug}

def extract_run_image(c,image_bytes,mime):
    if not api_key():raise RuntimeError('OpenAI API ist noch nicht konfiguriert.')
    if len(image_bytes)>12*1024*1024:raise RuntimeError('Screenshot ist größer als 12 MB.')
    budget_check(c);model=str(get_setting(c,'vision_model','gpt-5.6-luna'));b64=base64.b64encode(image_bytes).decode();prompt='Lies ausschließlich sichtbare Laufdaten aus diesem Apple-Fitness-/Laufscreenshot. Gib valides JSON: {"distance_km":number|null,"duration_seconds":number|null,"avg_hr":number|null,"elevation_m":number|null,"calories":number|null,"started_at":string|null,"confidence":0..1,"notes":"kurz"}. Nichts erfinden.'
    inp=[{'role':'user','content':[{'type':'input_text','text':prompt},{'type':'input_image','image_url':f'data:{mime};base64,{b64}','detail':'high'}]}];resp=request(model,inp,effort='low');record_usage(c,'vision_extract',model,resp);return parse_json(getattr(resp,'output_text',''))

def analyze_run(c,run_id):
    run=c.execute("SELECT * FROM runs WHERE id=?",(run_id,)).fetchone()
    if not run:raise KeyError('Lauf nicht gefunden.')
    if not api_key():raise RuntimeError('OpenAI API ist noch nicht konfiguriert.')
    budget_check(c);model=str(get_setting(c,'coach_model','gpt-5.6-terra'));evidence=bool(get_setting(c,'evidence_search',True));ctx=context(c)
    system='''Bewerte den angegebenen Lauf im Kontext des Trainingsplans. Berücksichtige Distanz, Pace, Herzfrequenz, RPE, Höhenmeter und Recoverydaten nur soweit vorhanden. Bei echten Trainingsentscheidungen nutze bei verfügbarer Websuche hochwertige Sportwissenschaft. Plan niemals direkt ändern. JSON: {"reply":"...","suggestion":null} oder konservativer update_workout-Vorschlag wie im Coach.'''
    inp=[{'role':'developer','content':system},{'role':'user','content':f'LAUF:\n{json.dumps(dict(run),ensure_ascii=False)}\nKONTEXT:\n{json.dumps(ctx,ensure_ascii=False)}'}];resp=request(model,inp,[{'type':'web_search'}] if evidence else None);record_usage(c,'run_analysis',model,resp);p=parse_json(getattr(resp,'output_text',''));reply=str(p.get('reply') or 'Analyse abgeschlossen.');sug=validate_suggestion(c,p.get('suggestion'));sid=add_suggestion(c,sug);src=sources(resp);c.execute("INSERT INTO chat_messages(role,text,meta_json) VALUES('assistant',?,?)",(reply,json.dumps({'sources':src,'suggestion_id':sid,'run_id':run_id},ensure_ascii=False)));return {'reply':reply,'sources':src,'suggestion_id':sid,'suggestion':sug}

def get_plan_review(c,ws):
    r=c.execute("SELECT * FROM plan_reviews WHERE week_start=?",(ws.isoformat(),)).fetchone()
    if not r:return None
    d=dict(r)
    try:d['sources']=json.loads(d.pop('sources_json'))
    except:d['sources']=[]
    return d

def review_week_plan(c,ws,force=False):
    if (old:=get_plan_review(c,ws)) and not force:return old
    if not api_key():raise RuntimeError('OpenAI API ist noch nicht konfiguriert.')
    budget_check(c);model=str(get_setting(c,'coach_model','gpt-5.6-terra'));evidence=bool(get_setting(c,'evidence_search',True));week=week_summary(c,ws);ctx=context(c)
    system='''Führe einen wissenschaftlichen Qualitätscheck des Lauftrainingsplans durch. Bewerte vier Einheiten im Kontext von Zielwettkampf, jüngstem Umfang und Recovery. Bei Websuche nutze mehrere hochwertige, aktuelle, unabhängige wissenschaftliche Quellen. Prüfe überwiegend niedrige Intensität, Trennung belastender Einheiten, konservative Progression, Wettkampfspezifität und Taper. Ändere nichts selbst. JSON: {"review":"kurz und konkret","suggestion":null} oder mit konservativem update_workout-Vorschlag.'''
    inp=[{'role':'developer','content':system},{'role':'user','content':f'WOCHENPLAN:\n{json.dumps(week,ensure_ascii=False)}\nKONTEXT:\n{json.dumps(ctx,ensure_ascii=False)}'}];resp=request(model,inp,[{'type':'web_search'}] if evidence else None);record_usage(c,'plan_evidence_review',model,resp);p=parse_json(getattr(resp,'output_text',''));text=str(p.get('review') or p.get('reply') or 'Wissenschaftlicher Wochencheck abgeschlossen.');sug=validate_suggestion(c,p.get('suggestion'));sid=add_suggestion(c,sug);src=sources(resp)
    if force:c.execute("DELETE FROM plan_reviews WHERE week_start=?",(ws.isoformat(),))
    c.execute("INSERT INTO plan_reviews(week_start,review_text,sources_json,suggestion_id,model) VALUES(?,?,?,?,?)",(ws.isoformat(),text,json.dumps(src,ensure_ascii=False),sid,model));return get_plan_review(c,ws)
