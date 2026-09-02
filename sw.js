const CACHE_NAME = 'ugamap-cache-v3';
const APP_SHELL = ['/', '/app.js', '/boundaries.js'];

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
  const parsed = new URL(req.url);
  const url = req.url;

  // Serve app.js without waiting on a second network request for boundaries.js.
  // The boundary module is already pre-cached during service-worker install.
  // This prevents the whole map application from being stuck on "Loading..."
  // when the boundary request is slow or temporarily unavailable.
  if (parsed.origin === self.location.origin && parsed.pathname === '/app.js') {
    event.respondWith((async () => {
      try {
        const appRes = await fetch(req, { cache: 'no-store' });
        if (!appRes.ok) throw new Error('app.js HTTP ' + appRes.status);
        const appText = await appRes.text();

        const boundaryReq = new Request('/boundaries.js');
        let boundaryRes = await caches.match(boundaryReq);
        if (!boundaryRes) {
          try {
            const freshBoundary = await fetch(boundaryReq, { cache: 'no-store' });
            if (freshBoundary.ok) {
              boundaryRes = freshBoundary.clone();
              const cache = await caches.open(CACHE_NAME);
              cache.put(boundaryReq, freshBoundary.clone()).catch(() => {});
            }
          } catch (_) {}
        }

        const boundaryText = boundaryRes ? await boundaryRes.text() : '';
        const combined = boundaryText + '\n\n' + appText;
        const response = new Response(combined, {
          status: 200,
          headers: {
            'Content-Type': 'application/javascript; charset=utf-8',
            'Cache-Control': 'no-cache, no-store, must-revalidate'
          }
        });

        const cache = await caches.open(CACHE_NAME);
        cache.put(req, response.clone()).catch(() => {});
        return response;
      } catch (_) {
        const cached = await caches.match(req);
        return cached || fetch(req);
      }
    })());
    return;
  }

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

  // Home shell: network-first so updates are picked up, fall back to cache.
  if (parsed.pathname === '/') {
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

  // Everything else (API calls, search, routing): always go to the network.
});
