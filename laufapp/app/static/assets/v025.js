(() => {
  'use strict';
  const root=document.getElementById('screen');
  if(!root)return;
  let enhancing=false;
  const esc=s=>String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const base=()=>new URL('.',document.baseURI);
  const api=async path=>{const r=await fetch(new URL(path,base()),{cache:'no-store'});if(!r.ok)throw new Error(`HTTP ${r.status}`);return r.json()};
  const distName=d=>Math.abs(d-5)<.2?'5 km':Math.abs(d-10)<.2?'10 km':Math.abs(d-21.0975)<.3?'Halbmarathon':Math.abs(d-42.195)<.4?'Marathon':`${Number(d).toLocaleString('de-DE',{maximumFractionDigits:1})} km`;
  const secondsText=v=>{let s=Math.round(Number(v)||0),h=Math.floor(s/3600),m=Math.floor((s%3600)/60),x=s%60;return h?`${h}:${String(m).padStart(2,'0')}:${String(x).padStart(2,'0')}`:`${m}:${String(x).padStart(2,'0')}`};
  const niceDate=s=>{if(!s)return '–';const [y,m,d]=String(s).slice(0,10).split('-').map(Number);return new Date(Date.UTC(y,m-1,d)).toLocaleDateString('de-DE',{day:'2-digit',month:'2-digit',year:'numeric',timeZone:'UTC'})};
  const sourceLabel=s=>s==='apple_health_best'?'Apple Health':s==='race'?'Wettkampf':s==='time_trial'?'Testlauf':'manuell';
  const rank=d=>Math.abs(d-21.0975)<.3?0:Math.abs(d-42.195)<.4?1:Math.abs(d-10)<.2?2:Math.abs(d-5)<.2?3:4;

  function bestPerDistance(stored){
    const map=new Map();
    for(const m of stored||[]){
      const key=distName(Number(m.distance_km));
      const current=map.get(key);
      if(!current||Number(m.duration_s)<Number(current.duration_s))map.set(key,m);
    }
    return [...map.values()].sort((a,b)=>rank(Number(a.distance_km))-rank(Number(b.distance_km)));
  }

  function bestCard(marks){
    if(!marks.length)return '';
    const primary=marks[0];
    const rows=marks.map(m=>`<div class="v025-best-row"><div><strong>${esc(distName(Number(m.distance_km)))}</strong><span>${esc(niceDate(m.mark_date))} · ${esc(sourceLabel(m.source))}${m.label?` · ${esc(m.label)}`:''}</span></div><b>${esc(secondsText(m.duration_s))}</b></div>`).join('');
    return `<article class="card v025-best-card" id="v025-best-card"><div class="v025-best-kicker"><span>🏆 Deine Bestzeiten</span><span>${esc(sourceLabel(primary.source))}</span></div><div class="v025-best-main"><div class="v025-best-copy"><span>${esc(distName(Number(primary.distance_km)))}</span><strong>${esc(secondsText(primary.duration_s))}</strong></div><div class="v025-best-meta">am ${esc(niceDate(primary.mark_date))}</div><span class="v025-best-source">${esc(sourceLabel(primary.source))}</span></div><button class="v025-best-all" id="v025-best-toggle" type="button">Alle Bestzeiten anzeigen ›</button><div class="v025-best-list">${rows}</div></article>`;
  }

  function addPredictionDetails(preds){
    const cards=[...root.querySelectorAll('.forecast')];
    const improved=[];
    for(const p of preds||[]){
      const label=distName(Number(p.distance_km));
      const card=cards.find(c=>c.querySelector('span')?.textContent?.trim().toLowerCase()===label.toLowerCase());
      const delta=Number(p.improvement_since_best_seconds||0);
      if(card&&delta>0){
        card.classList.add('v025-improved');
        if(!card.querySelector('.v025-delta')){
          const badge=document.createElement('small');badge.className='v025-delta';badge.textContent=`−${secondsText(delta)} seit Bestzeit`;card.appendChild(badge);
        }
        improved.push(p);
      }
    }
    const hm=(preds||[]).find(p=>Math.abs(Number(p.distance_km)-21.0975)<.3);
    if(hm?.performance_anchor){
      const grid=root.querySelector('.forecast-grid');
      if(grid&&!root.querySelector('.v025-prediction-info')){
        const info=document.createElement('div');info.className='v025-prediction-info';
        const delta=Number(hm.improvement_since_best_seconds||0);
        const suffix=delta>0?` Die aktuellen Daten stützen derzeit eine Verbesserung von ${secondsText(delta)}.`:' Aktuell reicht die neuere Trainingsevidenz noch nicht für eine schnellere Punktprognose; die Bestzeit bleibt der sichere Leistungsanker.';
        info.innerHTML=`<span class="v025-info-icon">i</span><div><b>Prognose-Info Halbmarathon</b>Basis ist deine Bestzeit vom ${esc(niceDate(hm.performance_anchor.date))}.${esc(suffix)}</div>`;
        grid.insertAdjacentElement('afterend',info);
      }
    }
  }

  async function enhance(){
    if(enhancing||root.dataset.v025Enhanced==='1')return;
    const h1=root.querySelector('.page-head h1');
    if(!h1||h1.textContent.trim()!=='Fortschritt')return;
    enhancing=true;root.dataset.v025Enhanced='1';
    try{
      const [marksData,predData]=await Promise.all([api('api/v2/performance-marks'),api('api/predictions')]);
      if(root.querySelector('.page-head h1')?.textContent.trim()!=='Fortschritt')return;
      const marks=bestPerDistance(marksData.stored||[]);
      const head=root.querySelector('.page-head');
      if(head&&marks.length&&!head.querySelector('.v025-best-head-action')){
        const action=document.createElement('button');action.className='v025-best-head-action';action.type='button';action.textContent='🏆 Bestzeiten';action.addEventListener('click',()=>document.getElementById('v025-best-card')?.scrollIntoView({behavior:'smooth',block:'start'}));head.appendChild(action);
      }
      const grid=root.querySelector('.forecast-grid');
      if(grid&&marks.length&&!root.querySelector('#v025-best-card'))grid.insertAdjacentHTML('beforebegin',bestCard(marks));
      document.getElementById('v025-best-toggle')?.addEventListener('click',e=>{const card=document.getElementById('v025-best-card');const expanded=card?.classList.toggle('expanded');e.currentTarget.textContent=expanded?'Bestzeiten einklappen ↑':'Alle Bestzeiten anzeigen ›'});
      addPredictionDetails(predData.predictions||[]);
    }catch(_err){
      root.dataset.v025Enhanced='0';
    }finally{enhancing=false}
  }

  const observer=new MutationObserver(()=>{if(root.querySelector('.page-head h1')?.textContent.trim()!=='Fortschritt')root.dataset.v025Enhanced='0';enhance()});
  observer.observe(root,{childList:true,subtree:true});
  enhance();
})();
