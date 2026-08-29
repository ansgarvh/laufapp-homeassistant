'use strict';
const CACHE='laufapp-v0.2.1';
const staticUrls=()=>['./','styles.css','app.js','manifest.webmanifest','icon-192.png','assets/bugfix.css','assets/v020.css','assets/v020.js','assets/v020_science.css','assets/v020_science.js'].map(p=>new URL(p,self.registration.scope).toString());
self.addEventListener('install',event=>{event.waitUntil(caches.open(CACHE).then(c=>c.addAll(staticUrls())).catch(()=>{}));self.skipWaiting();});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))));self.clients.claim();});
self.addEventListener('fetch',event=>{
  const req=event.request;if(req.method!=='GET')return;
  const u=new URL(req.url);if(u.pathname.includes('/api/'))return;
  event.respondWith(fetch(req).then(res=>{if(res.ok){const copy=res.clone();caches.open(CACHE).then(c=>c.put(req,copy));}return res;}).catch(()=>caches.match(req).then(r=>r||caches.match(new URL('./',self.registration.scope).toString()))));
});
