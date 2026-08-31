(() => {
  'use strict';

  const screen = document.getElementById('screen');
  const modalRoot = document.getElementById('modal-root');
  const toastNode = document.getElementById('toast');
  let activeWorkoutId = null;
  let raceRenderBusy = false;

  const baseUrl = () => new URL('.', document.baseURI);
  const apiPath = path => new URL(path.replace(/^\//, ''), baseUrl()).toString();
  const esc = s => String(s ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const fmt1 = n => Number(n || 0).toLocaleString('de-DE', {minimumFractionDigits:1, maximumFractionDigits:1});
  const dateObj = s => { const [y,m,d] = String(s).slice(0,10).split('-').map(Number); return new Date(Date.UTC(y,m-1,d)); };
  const niceDate = s => dateObj(s).toLocaleDateString('de-DE', {day:'2-digit',month:'short',year:'numeric',timeZone:'UTC'});
  const secondsText = v => { let s=Math.round(Number(v)||0),h=Math.floor(s/3600),m=Math.floor((s%3600)/60),x=s%60; return h?`${h}:${String(m).padStart(2,'0')}:${String(x).padStart(2,'0')}`:`${m}:${String(x).padStart(2,'0')}`; };
  const durationFromInput = v => { const p=String(v||'').trim().split(':').map(Number); if(p.some(Number.isNaN)||p.length<2||p.length>3)return null; return p.length===2?p[0]*60+p[1]:p[0]*3600+p[1]*60+p[2]; };
  const distName = d => Math.abs(d-5)<.2?'5 km':Math.abs(d-10)<.2?'10 km':Math.abs(d-21.0975)<.3?'Halbmarathon':Math.abs(d-42.195)<.4?'Marathon':`${fmt1(d)} km`;

  async function api(path, options={}) {
    const init={...options,headers:{...(options.headers||{})}};
    if(options.body && typeof options.body!=='string' && !(options.body instanceof FormData)){
      init.headers['Content-Type']='application/json'; init.body=JSON.stringify(options.body);
    }
    const res=await fetch(apiPath(path),init);
    let data=null; try{data=await res.json();}catch{}
    if(!res.ok){
      const detail=data?.detail;
      const msg=typeof detail==='string'?detail:Array.isArray(detail)?detail.map(x=>x.msg||String(x)).join(' · '):detail?JSON.stringify(detail):`Fehler ${res.status}`;
      throw new Error(msg);
    }
    return data;
  }

  function toast(message,error=false){
    if(!toastNode)return;
    toastNode.textContent=message;
    toastNode.className=`toast show${error?' error':''}`;
    clearTimeout(toast._t);
    toast._t=setTimeout(()=>toastNode.className='toast',3000);
  }

  function closeModal(){ modalRoot.innerHTML=''; }
  function modal(title,body,onReady){
    modalRoot.innerHTML=`<div class="modal-backdrop"><section class="modal" role="dialog" aria-modal="true" aria-label="${esc(title)}"><div class="modal-head"><h2>${esc(title)}</h2><button class="close" type="button" aria-label="Schließen">×</button></div>${body}</section></div>`;
    const modalEl=modalRoot.querySelector('.modal');
    modalRoot.querySelector('.close')?.addEventListener('click',closeModal);
    modalRoot.querySelector('.modal-backdrop')?.addEventListener('click',e=>{if(e.target===e.currentTarget)closeModal()});
    onReady?.(modalEl);
  }

  function refreshSettingsView(){
    const b=document.querySelector('#bottom-nav [data-view="settings"]');
    if(b)b.click();
  }

  function raceCard(r){
    const rec=r.recommendation;
    const recommendation=rec
      ? `Laufapp-Empfehlung: <strong>${esc(rec.predicted_time)}</strong>${rec.range_text?` · Bereich ${esc(rec.range_text)}`:''}`
      : 'Laufapp-Empfehlung: noch nicht genügend Leistungsdaten';
    const past=dateObj(r.race_date)<dateObj(new Date().toISOString().slice(0,10));
    return `<article class="card v020-race-card ${past?'is-past':''}" data-race-id="${r.id}">
      <div class="v020-race-head"><div><span class="v020-race-badge ${String(r.priority||'A').toLowerCase()}">${esc(r.priority)}-Rennen</span>${r.is_focus?'<span class="pill good">Planfokus</span>':''}</div><strong>${esc(r.name)}</strong></div>
      <div class="v020-race-meta"><span>${niceDate(r.race_date)}</span><span>${esc(distName(Number(r.distance_km)))}</span><span>Ziel ${esc(secondsText(r.goal_seconds))}</span></div>
      <div class="v020-race-rec">${recommendation}</div>
      <div class="button-row"><button class="button" data-race-edit="${r.id}" type="button">Bearbeiten</button><button class="button danger" data-race-delete="${r.id}" type="button">Löschen</button></div>
    </article>`;
  }

  async function renderRaces(){
    if(raceRenderBusy || !screen || screen.querySelector('#v020-races'))return;
    const title=screen.querySelector('.page-head h1')?.textContent?.trim();
    if(title!=='Einstellungen')return;
    raceRenderBusy=true;
    try{
      const races=await api('api/v2/races');
      const section=document.createElement('section');
      section.id='v020-races'; section.className='section';
      section.innerHTML=`<div class="section-head"><h2>Rennen</h2><button class="link" id="v020-add-race" type="button">Rennen hinzufügen</button></div>
        <div class="v020-race-help"><strong>A-Rennen</strong> steuern Periodisierung, Peak und Taper. Das jeweils nächste A-Rennen steuert nur die Wochen bis zu seinem Termin; danach übernimmt das folgende A-Rennen. <strong>B-Rennen</strong> ersetzen nur den Longrun ihrer Rennwoche. <strong>C-Rennen</strong> dienen als Trainingswettkampf und ersetzen eine passende Qualitäts- bzw. lange Einheit. Vergangene Trainingstage werden beim Ändern des Rennkalenders nie neu berechnet.</div>
        <div class="v020-race-list">${races.length?races.map(raceCard).join(''):'<article class="card empty"><p>Noch kein Rennen hinterlegt.</p></article>'}</div>`;
      const firstSection=screen.querySelector('section');
      if(firstSection?.nextSibling) firstSection.parentNode.insertBefore(section,firstSection.nextSibling); else screen.appendChild(section);
      section.querySelector('#v020-add-race')?.addEventListener('click',()=>openRaceModal());
      section.querySelectorAll('[data-race-edit]').forEach(b=>b.addEventListener('click',()=>openRaceModal(races.find(r=>r.id===Number(b.dataset.raceEdit)))));
      section.querySelectorAll('[data-race-delete]').forEach(b=>b.addEventListener('click',async()=>{
        const race=races.find(r=>r.id===Number(b.dataset.raceDelete));
        if(!race||!confirm(`Wettkampf „${race.name}“ wirklich löschen?`))return;
        try{await api(`api/v2/races/${race.id}`,{method:'DELETE'});toast('Wettkampf gelöscht.');refreshSettingsView();}catch(e){toast(e.message,true)}
      }));
    }catch(e){toast(`Rennen konnten nicht geladen werden: ${e.message}`,true)}
    finally{raceRenderBusy=false;}
  }

  function raceTypeHelp(priority){
    if(priority==='A')return 'A-Rennen: Primäres Saisonziel. Das chronologisch nächste A-Rennen steuert nur die Planung bis zu seinem Termin. Nach einem A-Marathon folgt automatisch eine Erholungs-/Wiedereinstiegsphase, bevor das nächste A-Rennen übernimmt.';
    if(priority==='B')return 'B-Rennen: Sekundäres Rennen. Ersetzt ausschließlich den Longrun in seiner Rennwoche; kein zusätzlicher Taper und keine Änderung der vorherigen Wochen.';
    return 'C-Rennen: Trainingswettkampf. Ersetzt in seiner Woche eine passende Qualitäts- oder bei längerer Distanz die lange Einheit. Keine Änderung der vorherigen Wochen und kein eigener Taper.';
  }

  function openRaceModal(race=null){
    const tomorrow=new Date(); tomorrow.setDate(tomorrow.getDate()+1); const min=tomorrow.toISOString().slice(0,10);
    const defaultDate=race?.race_date||(()=>{const d=new Date();d.setDate(d.getDate()+30);return d.toISOString().slice(0,10)})();
    const priority=race?.priority||'A';
    modal(race?'Rennen bearbeiten':'Rennen hinzufügen',`<form class="form-grid" id="v020-race-form">
      <div class="grid2"><label class="field"><span>Wettkampf</span><input class="input" name="name" value="${esc(race?.name||'')}" required maxlength="120"></label><label class="field"><span>Datum</span><input class="input" type="date" name="date" value="${esc(defaultDate)}" min="${min}" required></label></div>
      <div class="grid2"><label class="field"><span>Distanz</span><div class="input-unit"><input class="input" type="number" name="distance" value="${race?.distance_km??42.195}" min="1.01" max="100" step="0.001" required><span>km</span></div></label><label class="field"><span>Typ</span><select class="select" name="priority"><option value="A" ${priority==='A'?'selected':''}>A-Rennen</option><option value="B" ${priority==='B'?'selected':''}>B-Rennen</option><option value="C" ${priority==='C'?'selected':''}>C-Rennen</option></select></label></div>
      <label class="field"><span>Zielzeit (hh:mm:ss)</span><input class="input" name="goal" value="${esc(secondsText(race?.goal_seconds||12600))}" required pattern="[0-9:]+"><small class="v020-goal-rec" id="v020-goal-rec">Laufapp-Empfehlung wird geladen …</small><button class="link v020-adopt-rec" id="v020-adopt-rec" type="button" hidden>Empfehlung übernehmen</button></label>
      <div class="v020-race-type-help" id="v020-race-type-help">${esc(raceTypeHelp(priority))}</div>
      <button class="button primary" type="submit">${race?'Rennen speichern':'Rennen hinzufügen'}</button>
    </form>`,m=>{
      const form=m.querySelector('#v020-race-form'),rec=m.querySelector('#v020-goal-rec'),adopt=m.querySelector('#v020-adopt-rec'),help=m.querySelector('#v020-race-type-help');
      let recommendation=null,timer=null;
      const loadRecommendation=async()=>{
        clearTimeout(timer);timer=setTimeout(async()=>{
          const distance=Number(form.distance.value);if(!distance||distance<=1)return;
          try{const r=await api(`api/v2/races/recommendation?distance_km=${encodeURIComponent(distance)}`);recommendation=r.available?r:null;rec.innerHTML=recommendation?`Laufapp-Empfehlung aktuell: <strong>${esc(r.predicted_time)}</strong>${r.range_text?` · Bereich ${esc(r.range_text)}`:''}`:'Laufapp-Empfehlung: noch nicht genügend Leistungsdaten';adopt.hidden=!recommendation;}catch{rec.textContent='Laufapp-Empfehlung aktuell nicht verfügbar';adopt.hidden=true;}
        },120);
      };
      form.distance.addEventListener('input',loadRecommendation);
      form.priority.addEventListener('change',()=>help.textContent=raceTypeHelp(form.priority.value));
      adopt.addEventListener('click',()=>{if(recommendation)form.goal.value=secondsText(recommendation.predicted_seconds)});
      loadRecommendation();
      form.addEventListener('submit',async e=>{
        e.preventDefault();const goal=durationFromInput(form.goal.value);if(!goal)return toast('Bitte eine gültige Zielzeit eingeben.',true);
        const payload={name:form.name.value.trim(),distance_km:Number(form.distance.value),race_date:form.date.value,goal_seconds:goal,priority:form.priority.value};
        try{await api(race?`api/v2/races/${race.id}`:'api/v2/races',{method:race?'PUT':'POST',body:payload});closeModal();toast(race?'Rennen aktualisiert · Zukunftsplan ab heute neu ausgerichtet.':'Rennen hinzugefügt · Zukunftsplan ab heute neu ausgerichtet.');refreshSettingsView();}catch(err){toast(err.message,true)}
      });
    });
  }

  function enhanceMore(){
    if(screen.querySelector('.page-head h1')?.textContent?.trim()!=='Mehr')return;
    const old=document.getElementById('add-race');
    if(old)old.style.display='none';
    if(old?.parentElement && !document.getElementById('v020-manage-races')){
      const b=document.createElement('button');b.className='button';b.type='button';b.id='v020-manage-races';b.textContent='Rennen unter Einstellungen';b.addEventListener('click',()=>document.querySelector('#bottom-nav [data-view="settings"]')?.click());old.parentElement.prepend(b);
    }
  }

  async function enhanceWorkoutModal(id){
    const modalEl=modalRoot.querySelector('.modal');if(!modalEl||modalEl.querySelector('[data-v020-shoe]'))return;
    try{
      const info=await api(`api/v2/workouts/${id}/run-info`);
      if(info.workout?.status!=='completed')return;
      const row=modalEl.querySelector('.button-row');if(!row)return;
      const b=document.createElement('button');b.className='button';b.type='button';b.dataset.v020Shoe='1';b.textContent=info.run?.shoe_model?'Schuh ändern':'Schuh zuordnen';
      b.addEventListener('click',()=>openShoeModal(id));row.appendChild(b);
      if(info.run?.shoe_model){const p=document.createElement('div');p.className='v020-linked-shoe';p.textContent=`Schuh: ${[info.run.shoe_brand,info.run.shoe_model,info.run.shoe_nickname].filter(Boolean).join(' · ')}`;row.parentElement.insertBefore(p,row);}
    }catch{}
  }

  async function openShoeModal(workoutId){
    try{
      const [info,shoes]=await Promise.all([api(`api/v2/workouts/${workoutId}/run-info`),api('api/shoes')]);
      const current=Number(info.run?.shoe_id||info.single_same_day_candidate?.shoe_id||0);
      modal('Schuh zuordnen',`<form class="form-grid" id="v020-shoe-form"><p class="form-note">Die Kilometer des verknüpften absolvierten Laufs werden dem ausgewählten Schuh zugerechnet.</p><label class="field"><span>Schuh</span><select class="select" name="shoe"><option value="">Kein Schuh</option>${shoes.filter(s=>!s.archived).map(s=>`<option value="${s.id}" ${current===Number(s.id)?'selected':''}>${esc([s.brand,s.model,s.nickname].filter(Boolean).join(' · '))} · ${fmt1(s.total_km)} km</option>`).join('')}</select></label><button class="button primary" type="submit">Zuordnung speichern</button></form>`,m=>m.querySelector('form').addEventListener('submit',async e=>{e.preventDefault();const val=e.currentTarget.shoe.value;try{await api(`api/v2/workouts/${workoutId}/shoe`,{method:'PATCH',body:{shoe_id:val?Number(val):null}});closeModal();toast('Schuhzuordnung gespeichert. Die Schuhkilometer wurden aktualisiert.');}catch(err){toast(err.message,true)}}));
    }catch(e){toast(e.message,true)}
  }

  document.addEventListener('click',e=>{
    const menu=e.target.closest?.('[data-workout-menu]');
    if(menu){activeWorkoutId=Number(menu.dataset.workoutMenu);setTimeout(()=>enhanceWorkoutModal(activeWorkoutId),40);}
  },true);

  const observer=new MutationObserver(()=>{renderRaces();enhanceMore();});
  observer.observe(screen,{childList:true,subtree:true});
  renderRaces();enhanceMore();
})();
