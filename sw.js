const CACHE_NAME = 'ugamap-cache-v1';
const APP_SHELL = ['/', '/app.js'];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(APP_SHELL)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(names =>
      Promise.all(names.filter(n => n !== CACHE_NAME).map(n => caches.delete(n)))
    )
  );
  self.clients.claim();
});

function isTileRequest(url) {
  return /tile\.openstreetmap\.org/.test(url) || /unpkg\.com\/leaflet/.test(url);
}

self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = req.url;

  // Map tiles + Leaflet library: cache-first so recently viewed areas and
  // the map library keep working with a weak/lost connection.
  if (isTileRequest(url)) {
    event.respondWith(
      caches.open(CACHE_NAME).then(cache =>
        cache.match(req).then(cached => {
          const fetchPromise = fetch(req).then(res => {
            if (res && res.ok) cache.put(req, res.clone());
            return res;
          }).catch(() => cached);
          return cached || fetchPromise;
        })
      )
    );
    return;
  }

  // App shell (/, /app.js): network-first so updates are picked up, fall
  // back to cache when offline.
  if (APP_SHELL.includes(new URL(url).pathname)) {
    event.respondWith(
      fetch(req).then(res => {
        if (res && res.ok) {
          caches.open(CACHE_NAME).then(cache => cache.put(req, res.clone()));
        }
        return res;
      }).catch(() => caches.match(req))
    );
    return;
  }

  // Everything else (API calls, search, routing): always go to the
  // network — this data must stay fresh.
});
