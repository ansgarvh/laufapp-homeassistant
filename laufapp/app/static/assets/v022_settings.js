(() => {
  'use strict';

  const screen=document.getElementById('screen');
  const modalRoot=document.getElementById('modal-root');
  const toastNode=document.getElementById('toast');
  let busy=false;

  const esc=s=>String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const apiPath=path=>new URL(path.replace(/^\//,''),new URL('.',document.baseURI)).toString();
  async function api(path,options={}){
    const init={...options,headers:{...(options.headers||{})}};
    if(options.body&&typeof options.body!=='string'){
      init.headers['Content-Type']='application/json';
      init.body=JSON.stringify(options.body);
    }
    const res=await fetch(apiPath(path),init);
    let data=null;try{data=await res.json()}catch{}
    if(!res.ok){
      const d=data?.detail;
      throw new Error(typeof d==='string'?d:Array.isArray(d)?d.map(x=>x.msg||String(x)).join(' · '):`Fehler ${res.status}`);
    }
    return data;
  }
  function toast(msg,error=false){
    if(!toastNode)return;
    toastNode.textContent=msg;
    toastNode.className=`toast show${error?' error':''}`;
    clearTimeout(toast._v022);
    toast._v022=setTimeout(()=>toastNode.className='toast',3200);
  }
  function closeModal(){modalRoot.innerHTML=''}
  function modal(title,body,onReady){
    modalRoot.innerHTML=`<div class="modal-backdrop"><section class="modal" role="dialog" aria-modal="true" aria-label="${esc(title)}"><div class="modal-head"><h2>${esc(title)}</h2><button class="close" type="button" aria-label="Schließen">×</button></div>${body}</section></div>`;
    const m=modalRoot.querySelector('.modal');
    modalRoot.querySelector('.close')?.addEventListener('click',closeModal);
    modalRoot.querySelector('.modal-backdrop')?.addEventListener('click',e=>{if(e.target===e.currentTarget)closeModal()});
    onReady?.(m);
  }
  const dateObj=s=>{const [y,m,d]=String(s).slice(0,10).split('-').map(Number);return new Date(Date.UTC(y,m-1,d))};
  const niceDate=s=>dateObj(s).toLocaleDateString('de-DE',{day:'2-digit',month:'short',year:'numeric',timeZone:'UTC'});
  const fmt1=n=>Number(n||0).toLocaleString('de-DE',{minimumFractionDigits:1,maximumFractionDigits:1});
  const distName=d=>Math.abs(d-5)<.2?'5 km':Math.abs(d-10)<.2?'10 km':Math.abs(d-21.0975)<.3?'Halbmarathon':Math.abs(d-42.195)<.4?'Marathon':`${fmt1(d)} km`;
  const secondsText=v=>{let s=Math.round(Number(v)||0),h=Math.floor(s/3600),m=Math.floor((s%3600)/60),x=s%60;return h?`${h}:${String(m).padStart(2,'0')}:${String(x).padStart(2,'0')}`:`${m}:${String(x).padStart(2,'0')}`};
  const durationFromInput=v=>{const p=String(v||'').trim().split(':').map(Number);if(p.some(Number.isNaN)||p.length<2||p.length>3)return null;return p.length===2?p[0]*60+p[1]:p[0]*3600+p[1]*60+p[2]};

  const aggressivenessCopy={
    gradual:'Langsamere Progression von Umfang und Belastung. Recovery, Deload und alle Obergrenzen bleiben bindend.',
    steady:'Ausgewogene Progression als Standard. Umfang und spezifische Belastung steigen kontrolliert innerhalb des Trainingsblocks.',
    progressive:'Schnellere Progression bei guter Verträglichkeit. Recovery und harte Wochen-/Longrun-Limits bleiben bindend.'
  };

  async function ensureAggressiveness(settings){
    const form=screen.querySelector('#settings-form');
    if(!form||form.querySelector('[data-v022-aggressiveness]')||form.querySelector('[data-v020-aggressiveness]'))return;
    const current=['gradual','steady','progressive'].includes(settings.training_volume_profile)?settings.training_volume_profile:'steady';
    const field=document.createElement('label');
    field.className='field';field.dataset.v022Aggressiveness='1';
    field.innerHTML=`<span>Planungsaggressivität</span><select class="select" name="v022_aggressiveness" aria-label="Planungsaggressivität"><option value="gradual" ${current==='gradual'?'selected':''}>Konservativ</option><option value="steady" ${current==='steady'?'selected':''}>Moderat</option><option value="progressive" ${current==='progressive'?'selected':''}>Aggressiv</option></select><small>${esc(aggressivenessCopy[current])}</small>`;
    const quality=[...form.querySelectorAll('.field')].find(x=>x.querySelector(':scope > span')?.textContent?.trim()==='Qualitätseinheiten');
    if(quality)quality.before(field);else form.querySelector('button[type="submit"]')?.before(field);
    const select=field.querySelector('select'),note=field.querySelector('small');
    select.addEventListener('change',async()=>{
      const value=select.value;note.textContent=aggressivenessCopy[value]||aggressivenessCopy.steady;select.disabled=true;
      try{
        await api('api/settings',{method:'PATCH',body:{training_volume_profile:value}});
        toast('Planungsaggressivität gespeichert. Plan neu berechnen, um sie anzuwenden.');
      }catch(e){toast(e.message,true);select.value=current;note.textContent=aggressivenessCopy[current]}
      finally{select.disabled=false}
    });
  }

  function raceCard(r){
    const rec=r.recommendation;
    return `<article class="card v020-race-card" data-race-id="${r.id}"><div class="v020-race-head"><div><span class="v020-race-badge ${r.priority==='A'?'a':'b'}">${esc(r.priority)}-Rennen</span>${r.is_focus?'<span class="pill good">Planfokus</span>':''}</div><strong>${esc(r.name)}</strong></div><div class="v020-race-meta"><span>${niceDate(r.race_date)}</span><span>${esc(distName(Number(r.distance_km)))}</span><span>Ziel ${esc(secondsText(r.goal_seconds))}</span></div><div class="v020-race-rec">${rec?`Laufapp-Empfehlung: <strong>${esc(rec.predicted_time)}</strong>${rec.range_text?` · Bereich ${esc(rec.range_text)}`:''}`:'Laufapp-Empfehlung: noch nicht genügend Leistungsdaten'}</div><div class="button-row"><button class="button" data-v022-edit="${r.id}" type="button">Bearbeiten</button><button class="button danger" data-v022-delete="${r.id}" type="button">Löschen</button></div></article>`;
  }

  function raceHelp(priority){
    return priority==='A'
      ? 'A-Rennen steuern Planfokus, Periodisierung und Taper. Das nächste zukünftige A-Rennen ist der aktuelle Fokus.'
      : 'B-Rennen ersetzen nur den Longrun ihrer Rennwoche. Sie lösen keinen eigenen Taper und keine Anpassung der vorherigen Wochen aus.';
  }

  function openRaceModal(race=null){
    const tomorrow=new Date();tomorrow.setDate(tomorrow.getDate()+1);const min=tomorrow.toISOString().slice(0,10);
    const defaultDate=race?.race_date||(()=>{const d=new Date();d.setDate(d.getDate()+30);return d.toISOString().slice(0,10)})();
    const priority=race?.priority||'A';
    modal(race?'Rennen bearbeiten':'Rennen hinzufügen',`<form class="form-grid" id="v022-race-form"><div class="grid2"><label class="field"><span>Wettkampf</span><input class="input" name="name" value="${esc(race?.name||'')}" required maxlength="120"></label><label class="field"><span>Datum</span><input class="input" type="date" name="date" value="${esc(defaultDate)}" min="${min}" required></label></div><div class="grid2"><label class="field"><span>Distanz</span><div class="input-unit"><input class="input" type="number" name="distance" value="${race?.distance_km??42.195}" min="1.01" max="100" step="0.001" required><span>km</span></div></label><label class="field"><span>Typ</span><select class="select" name="priority"><option value="A" ${priority==='A'?'selected':''}>A-Rennen</option><option value="B" ${priority==='B'?'selected':''}>B-Rennen</option></select></label></div><label class="field"><span>Zielzeit (hh:mm:ss)</span><input class="input" name="goal" value="${esc(secondsText(race?.goal_seconds||12600))}" required pattern="[0-9:]+"><small id="v022-rec">Laufapp-Empfehlung wird geladen …</small><button class="link" id="v022-adopt" type="button" hidden>Empfehlung übernehmen</button></label><div class="v020-race-type-help" id="v022-race-help">${esc(raceHelp(priority))}</div><button class="button primary" type="submit">${race?'Rennen speichern':'Rennen hinzufügen'}</button></form>`,m=>{
      const form=m.querySelector('#v022-race-form'),rec=m.querySelector('#v022-rec'),adopt=m.querySelector('#v022-adopt'),help=m.querySelector('#v022-race-help');
      let recommendation=null,timer=null;
      const loadRec=()=>{clearTimeout(timer);timer=setTimeout(async()=>{const distance=Number(form.distance.value);if(!distance||distance<=1)return;try{const r=await api(`api/v2/races/recommendation?distance_km=${encodeURIComponent(distance)}`);recommendation=r.available?r:null;rec.innerHTML=recommendation?`Laufapp-Empfehlung aktuell: <strong>${esc(r.predicted_time)}</strong>${r.range_text?` · Bereich ${esc(r.range_text)}`:''}`:'Laufapp-Empfehlung: noch nicht genügend Leistungsdaten';adopt.hidden=!recommendation}catch{rec.textContent='Laufapp-Empfehlung aktuell nicht verfügbar';adopt.hidden=true}},120)};
      form.distance.addEventListener('input',loadRec);form.priority.addEventListener('change',()=>help.textContent=raceHelp(form.priority.value));adopt.addEventListener('click',()=>{if(recommendation)form.goal.value=secondsText(recommendation.predicted_seconds)});loadRec();
      form.addEventListener('submit',async e=>{e.preventDefault();const goal=durationFromInput(form.goal.value);if(!goal)return toast('Bitte eine gültige Zielzeit eingeben.',true);const payload={name:form.name.value.trim(),distance_km:Number(form.distance.value),race_date:form.date.value,goal_seconds:goal,priority:form.priority.value};try{await api(race?`api/v2/races/${race.id}`:'api/v2/races',{method:race?'PUT':'POST',body:payload});closeModal();toast(race?'Rennen aktualisiert.':'Rennen hinzugefügt.');document.querySelector('#bottom-nav [data-view="settings"]')?.click()}catch(err){toast(err.message,true)}});
    });
  }

  async function ensureRaces(){
    if(screen.querySelector('#v020-races')||screen.querySelector('#v022-races'))return;
    const races=await api('api/v2/races');
    const section=document.createElement('section');section.id='v022-races';section.className='section';
    section.innerHTML=`<div class="section-head"><h2>Rennen</h2><button class="link" id="v022-add-race" type="button">Rennen hinzufügen</button></div><div class="v020-race-help"><strong>A-Rennen</strong> steuern Periodisierung, Peak und Taper. <strong>B-Rennen</strong> ersetzen nur den Longrun ihrer Rennwoche.</div><div class="v020-race-list">${races.length?races.map(raceCard).join(''):'<article class="card empty"><p>Noch kein Rennen hinterlegt.</p></article>'}</div>`;
    const firstSection=screen.querySelector('section');
    if(firstSection?.nextSibling)firstSection.parentNode.insertBefore(section,firstSection.nextSibling);else screen.appendChild(section);
    section.querySelector('#v022-add-race')?.addEventListener('click',()=>openRaceModal());
    section.querySelectorAll('[data-v022-edit]').forEach(b=>b.addEventListener('click',()=>openRaceModal(races.find(r=>r.id===Number(b.dataset.v022Edit)))));
    section.querySelectorAll('[data-v022-delete]').forEach(b=>b.addEventListener('click',async()=>{const race=races.find(r=>r.id===Number(b.dataset.v022Delete));if(!race||!confirm(`Wettkampf „${race.name}“ wirklich löschen?`))return;try{await api(`api/v2/races/${race.id}`,{method:'DELETE'});toast('Wettkampf gelöscht.');document.querySelector('#bottom-nav [data-view="settings"]')?.click()}catch(e){toast(e.message,true)}}));
  }

  async function ensureSettings(){
    if(busy||screen?.querySelector('.page-head h1')?.textContent?.trim()!=='Einstellungen')return;
    busy=true;
    try{const settings=await api('api/settings');await ensureAggressiveness(settings);await ensureRaces()}
    catch(e){toast(`Zusätzliche Einstellungen konnten nicht geladen werden: ${e.message}`,true)}
    finally{busy=false}
  }

  const observer=new MutationObserver(()=>ensureSettings());
  if(screen){observer.observe(screen,{childList:true,subtree:true});ensureSettings();setTimeout(ensureSettings,250);setTimeout(ensureSettings,900);setTimeout(ensureSettings,2200)}
})();
