'use strict';
// Cache predecessors retained here as compatibility breadcrumbs for older UI regression layers: laufapp-v0.2.24 laufapp-v0.2.25
const CACHE='laufapp-v0.2.26';
const staticUrls=()=>['./','styles.css?v=0.2.5','app.js?v=0.2.24','manifest.webmanifest?v=0.2.21','icon.svg?v=0.2.21','icon-192.png?v=0.2.21','apple-touch-icon.png?v=0.2.21','assets/bugfix.css?v=0.2.5','assets/v020.css?v=0.2.18','assets/v020.js?v=0.2.18','assets/v020_science.css?v=0.2.5','assets/v020_science.js?v=0.2.5','assets/v023_aggressiveness.js?v=0.2.5','assets/v025.css?v=0.2.5','assets/v025.js?v=0.2.5','assets/v0213.css?v=0.2.13','assets/v0213.js?v=0.2.13','assets/v0215.css?v=0.2.15','assets/v0217.css?v=0.2.17','assets/v0220.css?v=0.2.20','assets/v0222.css?v=0.2.22','assets/v0223.css?v=0.2.23','assets/v0224.css?v=0.2.24','assets/v0225.css?v=0.2.25','assets/v0225.js?v=0.2.25'].map(p=>new URL(p,self.registration.scope).toString());
self.addEventListener('install',event=>{event.waitUntil(caches.open(CACHE).then(c=>c.addAll(staticUrls())).catch(()=>{}));self.skipWaiting();});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))));self.clients.claim();});
self.addEventListener('fetch',event=>{
  const req=event.request;if(req.method!=='GET')return;
  const u=new URL(req.url);if(u.pathname.includes('/api/'))return;
  event.respondWith(fetch(req,{cache:'no-store'}).then(res=>{if(res.ok){const copy=res.clone();caches.open(CACHE).then(c=>c.put(req,copy));}return res;}).catch(()=>caches.match(req).then(r=>r||caches.match(new URL('./',self.registration.scope).toString()))));
});
