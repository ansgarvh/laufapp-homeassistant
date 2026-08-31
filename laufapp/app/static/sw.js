'use strict';
const CACHE='laufapp-v0.2.16';
const staticUrls=()=>['./','styles.css?v=0.2.5','app.js?v=0.2.16','manifest.webmanifest?v=0.2.5','icon-192.png?v=0.2.5','assets/bugfix.css?v=0.2.5','assets/v020.css?v=0.2.5','assets/v020.js?v=0.2.5','assets/v020_science.css?v=0.2.5','assets/v020_science.js?v=0.2.5','assets/v023_aggressiveness.js?v=0.2.5','assets/v025.css?v=0.2.5','assets/v025.js?v=0.2.5','assets/v0213.css?v=0.2.13','assets/v0213.js?v=0.2.13','assets/v0215.css?v=0.2.15'].map(p=>new URL(p,self.registration.scope).toString());
self.addEventListener('install',event=>{event.waitUntil(caches.open(CACHE).then(c=>c.addAll(staticUrls())).catch(()=>{}));self.skipWaiting();});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))));self.clients.claim();});
self.addEventListener('fetch',event=>{
  const req=event.request;if(req.method!=='GET')return;
  const u=new URL(req.url);if(u.pathname.includes('/api/'))return;
  event.respondWith(fetch(req,{cache:'no-store'}).then(res=>{if(res.ok){const copy=res.clone();caches.open(CACHE).then(c=>c.put(req,copy));}return res;}).catch(()=>caches.match(req).then(r=>r||caches.match(new URL('./',self.registration.scope).toString()))));
});
