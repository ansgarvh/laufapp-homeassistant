(() => {
  'use strict';

  const screen=document.getElementById('screen');
  const toastNode=document.getElementById('toast');
  const notes={
    gradual:'Langsamere Progression von Wochenumfang und Belastung. Sicherheits- und Recovery-Regeln bleiben unverändert.',
    steady:'Ausgewogene Progression als Standard. Umfang und spezifische Belastung steigen kontrolliert innerhalb des Trainingsblocks.',
    progressive:'Schnellere Progression bei guter Verträglichkeit. Harte Wochen-/Longrun-Limits, Recovery und Qualitätsbudget bleiben weiterhin bindend.',
    very_progressive:'Noch offensiver: in normalen Belastungswochen liegt das Wochenziel rund 2,5 % über „Aggressiv“. Recovery-, Taper-, Rennwochen sowie deine Wochen- und Longrun-Grenzen bleiben unverändert bindend.'
  };
  const apiPath=path=>new URL(path.replace(/^\//,''),new URL('.',document.baseURI)).toString();
  async function api(path,options={}){
    const init={...options,headers:{...(options.headers||{})}};
    if(options.body&&typeof options.body!=='string'){
      init.headers['Content-Type']='application/json';init.body=JSON.stringify(options.body);
    }
    const res=await fetch(apiPath(path),init);let data=null;try{data=await res.json()}catch{}
    if(!res.ok){const d=data?.detail;throw new Error(typeof d==='string'?d:`Fehler ${res.status}`)}
    return data;
  }
  function toast(message,error=false){
    if(!toastNode)return;toastNode.textContent=message;toastNode.className=`toast show${error?' error':''}`;
    clearTimeout(toast._timer);toast._timer=setTimeout(()=>toastNode.className='toast',3200);
  }

  async function enhance(){
    if(screen?.querySelector('.page-head h1')?.textContent?.trim()!=='Einstellungen')return;
    const field=screen.querySelector('[data-v020-aggressiveness]');
    if(!field||field.dataset.v023Aggressiveness)return;
    field.dataset.v023Aggressiveness='1';
    const oldSelect=field.querySelector('select');
    if(!oldSelect)return;

    // Replace the old three-level select to remove its legacy PATCH listener.
    const select=oldSelect.cloneNode(false);
    select.innerHTML='<option value="gradual">Konservativ</option><option value="steady">Moderat</option><option value="progressive">Aggressiv</option><option value="very_progressive">Sehr aggressiv</option>';
    oldSelect.replaceWith(select);
    const note=field.querySelector('.v020-aggressiveness-note');

    try{
      const current=await api('api/v2/settings/aggressiveness');
      const value=['gradual','steady','progressive','very_progressive'].includes(current.training_volume_profile)?current.training_volume_profile:'steady';
      select.value=value;if(note)note.textContent=notes[value];
    }catch(err){toast(`Planungsaggressivität konnte nicht geladen werden: ${err.message}`,true)}

    select.addEventListener('change',async()=>{
      const value=select.value;select.disabled=true;if(note)note.textContent=notes[value]||notes.steady;
      try{
        await api('api/v2/settings/aggressiveness',{method:'PATCH',body:{training_volume_profile:value}});
        toast('Planungsaggressivität gespeichert. Plan neu berechnen, um sie anzuwenden.');
      }catch(err){toast(err.message,true)}
      finally{select.disabled=false}
    });
  }

  const observer=new MutationObserver(enhance);
  if(screen){observer.observe(screen,{childList:true,subtree:true});enhance()}
})();
