(() => {
  'use strict';

  const screen=document.getElementById('screen');
  const modalRoot=document.getElementById('modal-root');
  const toastNode=document.getElementById('toast');
  const targetLabels={
    aerobic_base:'Aerobe Basis',threshold:'Schwelle / LT2',vo2max:'VO₂max',economy:'Laufökonomie',
    marathon_specific:'Marathon-spezifisch',aerobic_progression:'Aerobe Progression',hills:'Hügel / Kraftausdauer',
    recovery:'Erholung',race:'Wettkampf'
  };
  const formLabels={
    threshold_intervals:'Schwellenintervalle',cruise_intervals:'Cruise Intervals',tempo:'Tempodauerlauf',pyramid:'Pyramide',
    vo2_intervals:'VO₂max-Intervalle',short_intervals:'Kurze Intervalle',hills:'Bergintervalle',fartlek:'Fartlek',
    progression:'Progressionslauf',marathon_pace:'Marathonpace-Blöcke',long_easy:'Easy Longrun',
    long_progression:'Progressiver Longrun',long_mp_blocks:'Longrun mit MP-Blöcken',long_fast_finish:'Longrun Fast Finish',
    long_deload:'Reduzierter Longrun',race_prep:'Race Prep',race:'Wettkampf',easy:'Easy Run'
  };
  const esc=s=>String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const apiPath=path=>new URL(path.replace(/^\//,''),new URL('.',document.baseURI)).toString();
  async function api(path,options={}){
    const init={...options,headers:{...(options.headers||{})}};
    if(options.body&&typeof options.body!=='string'){init.headers['Content-Type']='application/json';init.body=JSON.stringify(options.body)}
    const res=await fetch(apiPath(path),init);let data=null;try{data=await res.json()}catch{}
    if(!res.ok){const d=data?.detail;throw new Error(typeof d==='string'?d:`Fehler ${res.status}`)}return data;
  }
  function toast(message,error=false){if(!toastNode)return;toastNode.textContent=message;toastNode.className=`toast show${error?' error':''}`;clearTimeout(toast._scienceTimer);toast._scienceTimer=setTimeout(()=>toastNode.className='toast',3200)}
  function closeModal(){modalRoot.innerHTML=''}
  function modal(title,body,onReady){
    modalRoot.innerHTML=`<div class="modal-backdrop"><section class="modal" role="dialog" aria-modal="true" aria-label="${esc(title)}"><div class="modal-head"><h2>${esc(title)}</h2><button class="close" type="button" aria-label="Schließen">×</button></div>${body}</section></div>`;
    modalRoot.querySelector('.close')?.addEventListener('click',closeModal);modalRoot.querySelector('.modal-backdrop')?.addEventListener('click',e=>{if(e.target===e.currentTarget)closeModal()});onReady?.(modalRoot.querySelector('.modal'));
  }
  const paceText=s=>{const n=Math.round(Number(s)||0);return n?`${Math.floor(n/60)}:${String(n%60).padStart(2,'0')} min/km`:'–'};

  function tidHtml(tid){
    if(!tid||!Number(tid.low_pct)&&!Number(tid.moderate_pct)&&!Number(tid.high_pct))return '';
    return `<div class="v020-tid" aria-label="Geschätzte Intensitätsverteilung über vier Wochen"><div><span>Niedrig</span><strong>${Number(tid.low_pct||0).toFixed(0)}%</strong></div><div><span>Moderat</span><strong>${Number(tid.moderate_pct||0).toFixed(0)}%</strong></div><div><span>Hoch</span><strong>${Number(tid.high_pct||0).toFixed(0)}%</strong></div></div>`;
  }

  function installWeekTid(science){
    const card=screen.querySelector('.plan-quality');if(!card||card.querySelector('.v020-tid-wrap'))return;
    const tid=science.rolling_intensity_distribution;if(!tid||!Object.keys(tid).length)return;
    const wrap=document.createElement('div');wrap.className='v020-tid-wrap';wrap.innerHTML=`<div class="v020-mini-head"><strong>4-Wochen-Intensität</strong><span>Planungsschätzung · nicht starre Vorgabe</span></div>${tidHtml(tid)}`;card.prepend(wrap);
  }

  async function enhanceWorkoutCard(card){
    if(card.dataset.scienceLoaded)return;card.dataset.scienceLoaded='loading';const id=Number(card.dataset.workout);if(!id)return;
    try{
      const science=await api(`api/v2/workouts/${id}/science`);card.dataset.scienceLoaded='done';
      const info=card.querySelector('.week-info');if(info&&!info.querySelector('.v020-target-badge')){
        const badge=document.createElement('span');badge.className='v020-target-badge';badge.textContent=targetLabels[science.physiological_target]||formLabels[science.workout_form]||'Trainingsreiz';info.insertBefore(badge,info.firstChild);
      }
      installWeekTid(science);
    }catch{card.dataset.scienceLoaded='error'}
  }

  function enhanceWorkoutCards(){screen?.querySelectorAll('.week-workout[data-workout]').forEach(enhanceWorkoutCard)}

  async function enhanceWorkoutModal(id){
    const modalEl=modalRoot.querySelector('.modal');if(!modalEl||modalEl.dataset.scienceEnhanced)return;modalEl.dataset.scienceEnhanced='loading';
    try{
      const science=await api(`api/v2/workouts/${id}/science`);modalEl.dataset.scienceEnhanced='done';
      const row=modalEl.querySelector('.button-row');
      const box=document.createElement('section');box.className='v020-why';
      const label=targetLabels[science.physiological_target]||'Trainingsreiz',form=formLabels[science.workout_form]||science.workout_form||'';
      const load=science.load||{};const tid=science.rolling_intensity_distribution||{};const p=science.training_paces||{};
      box.innerHTML=`<div class="v020-mini-head"><strong>Warum diese Einheit?</strong><span>${esc(label)}${form?` · ${esc(form)}`:''}</span></div><p>${esc(science.why||'Diese Einheit ist Teil der periodisierten Wochenplanung.')}</p>${Number(load.score)>0?`<div class="v020-load"><span>interner Belastungsscore</span><strong>${Math.round(Number(load.score))}</strong><small>${Number(load.marathon_pace_min||0)>0?`${Math.round(Number(load.marathon_pace_min))} min MP · `:''}${Math.round(Number(load.low_min||0))} min niedrig · ${Math.round(Number(load.moderate_min||0))} min moderat · ${Math.round(Number(load.high_min||0))} min hoch</small></div>`:''}${science.physiological_target==='marathon_specific'&&p.current_estimated_marathon_pace_s_per_km?`<div class="v020-pace-note"><span>Aktuell geschätzte MP</span><strong>${paceText(p.current_estimated_marathon_pace_s_per_km)}</strong><span>Ziel-MP</span><strong>${paceText(p.goal_marathon_pace_s_per_km)}</strong></div>`:''}${tidHtml(tid)}<small class="v020-evidence-note">Belastung und Intensitätsanteile sind Planungsmodelle. Sie sind keine medizinische Bewertung und keine starren wissenschaftlichen Grenzwerte.</small>`;
      if(row)row.parentElement.insertBefore(box,row);else modalEl.appendChild(box);
      if(science.status==='completed'&&row&&!row.querySelector('[data-v020-feedback]')){
        const b=document.createElement('button');b.className='button';b.type='button';b.dataset.v020Feedback='1';b.textContent=science.feedback?'Feedback ändern':'Belastung bewerten';b.addEventListener('click',()=>openFeedbackModal(id,science.feedback));row.appendChild(b);
      }
    }catch{modalEl.dataset.scienceEnhanced='error'}
  }

  function openFeedbackModal(workoutId,current=null){
    const f=current||{};
    modal('Kurzes Trainingsfeedback',`<form class="form-grid" id="v020-feedback-form"><p class="form-note">Deine subjektive Rückmeldung ist ein gleichwertiges Recovery-Signal. Sie ergänzt Health-Daten und entscheidet nicht allein über den Plan.</p><label class="field"><span>Wie anstrengend war die Einheit? · RPE 1–10</span><input class="input" type="number" name="rpe" min="1" max="10" value="${Number(f.rpe||6)}" required></label><label class="field"><span>Wie fühlen sich die Beine an? · 1 schlecht, 5 frisch</span><input class="input" type="number" name="legs" min="1" max="5" value="${Number(f.legs||3)}" required></label><label class="field"><span>Schmerzen / Beschwerden</span><select class="select" name="pain"><option value="none" ${f.pain==='none'||!f.pain?'selected':''}>Nein</option><option value="light" ${f.pain==='light'?'selected':''}>Leicht</option><option value="relevant" ${f.pain==='relevant'?'selected':''}>Relevant</option></select></label><label class="field"><span>Wie erholt fühlst du dich? · 1 schlecht, 5 sehr gut</span><input class="input" type="number" name="recovery" min="1" max="5" value="${Number(f.recovery||3)}" required></label><button class="button primary" type="submit">Feedback speichern</button></form>`,m=>m.querySelector('form')?.addEventListener('submit',async e=>{
      e.preventDefault();const form=e.currentTarget;try{
        const result=await api(`api/v2/workouts/${workoutId}/feedback`,{method:'POST',body:{rpe:Number(form.rpe.value),legs:Number(form.legs.value),pain:form.pain.value,recovery:Number(form.recovery.value)}});closeModal();toast(result.suggestion_id?'Feedback gespeichert · Coach-Vorschlag wartet auf deine Entscheidung.':'Feedback gespeichert.');
      }catch(err){toast(err.message,true)}
    }));
  }

  async function enhanceReadiness(){
    if(screen?.querySelector('.page-head h1')?.textContent?.trim()!=='Heute'||screen.querySelector('.v020-readiness'))return;
    const recoverySection=[...screen.querySelectorAll('.section')].find(x=>x.querySelector('.section-head h2')?.textContent?.trim()==='Recovery Signale');if(!recoverySection)return;recoverySection.dataset.readinessLoading='1';
    try{
      const r=await api('api/v2/readiness');if(screen.querySelector('.v020-readiness'))return;
      const label=r.level==='red'?'Rot · deutliche Anpassung prüfen':r.level==='yellow'?'Gelb · Belastung aufmerksam steuern':'Grün · normale Planung';const first=(r.reasons||[])[0]||'Mehrere Recovery-Signale werden gemeinsam bewertet.';
      const card=document.createElement('article');card.className=`v020-readiness ${esc(r.level||'green')}`;card.innerHTML=`<div><span class="v020-readiness-dot" aria-hidden="true"></span><strong>Readiness: ${esc(label)}</strong></div><p>${esc(first)}</p><small>HRV, Ruhepuls, Schlaf und subjektives Feedback werden relativ zu deiner persönlichen Baseline und gemeinsam betrachtet. Keine medizinische Diagnose.</small>`;const metrics=recoverySection.querySelector('.metric-row');recoverySection.insertBefore(card,metrics||null);
    }catch{}
  }

  document.addEventListener('click',e=>{
    const menu=e.target.closest?.('[data-workout-menu]');if(menu){const id=Number(menu.dataset.workoutMenu);setTimeout(()=>enhanceWorkoutModal(id),90)}
  },true);

  const observer=new MutationObserver(()=>{enhanceWorkoutCards();enhanceReadiness()});
  if(screen){observer.observe(screen,{childList:true,subtree:true});enhanceWorkoutCards();enhanceReadiness()}
})();
