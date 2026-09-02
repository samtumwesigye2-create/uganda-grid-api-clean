const CACHE_NAME = 'ugamap-cache-v5';
const APP_SHELL = ['/', '/app.js', '/boundaries.js'];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(APP_SHELL)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(names => Promise.all(names.filter(n => n !== CACHE_NAME).map(n => caches.delete(n))))
  );
  self.clients.claim();
});

function isTileRequest(url) {
  return /tile\.openstreetmap\.org/.test(url) ||
         /unpkg\.com\/leaflet/.test(url) ||
         /cdn\.jsdelivr\.net\/npm\/leaflet/.test(url) ||
         /cdnjs\.cloudflare\.com\/ajax\/libs\/leaflet/.test(url);
}

self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const parsed = new URL(req.url);
  const url = req.url;

  if (parsed.origin === self.location.origin && parsed.pathname === '/app.js') {
    event.respondWith((async () => {
      try {
        const appRes = await fetch(req, { cache: 'no-store' });
        if (!appRes.ok) throw new Error('app.js HTTP ' + appRes.status);
        let appText = await appRes.text();

        appText = appText.replace(
          "window.addEventListener('load', () => {",
          "((fn) => { if (document.readyState === 'complete') fn(); else window.addEventListener('load', fn); })(() => {"
        );

        let boundaryText = '';
        try {
          const boundaryReq = new Request('/boundaries.js');
          const freshBoundary = await fetch(boundaryReq, { cache: 'no-store' });
          if (freshBoundary.ok) {
            boundaryText = await freshBoundary.text();
            const cache = await caches.open(CACHE_NAME);
            cache.put(boundaryReq, new Response(boundaryText, {
              headers: {'Content-Type':'application/javascript; charset=utf-8'}
            })).catch(() => {});
          }
        } catch (_) {
          try {
            const cachedBoundary = await caches.match('/boundaries.js');
            if (cachedBoundary) boundaryText = await cachedBoundary.text();
          } catch (_) {}
        }

        const payload = boundaryText + '\n\n' + appText;
        const payloadJson = JSON.stringify(payload);
        const combined = `
(function () {
  const ugamapCode = ${payloadJson};
  let started = false;

  function showError(message) {
    const status = document.getElementById('status');
    if (status) {
      status.textContent = message;
      status.className = 'status err';
    }
  }

  function runUGAMAP() {
    if (started) return;
    started = true;
    try {
      (0, eval)(ugamapCode);
    } catch (e) {
      started = false;
      console.error('UGAMAP startup failed:', e);
      showError('Map startup failed — reload once');
    }
  }

  function loadScript(src, onload, onerror) {
    const s = document.createElement('script');
    s.src = src;
    s.async = true;
    s.onload = onload;
    s.onerror = onerror;
    document.head.appendChild(s);
  }

  if (window.L) {
    runUGAMAP();
    return;
  }

  loadScript(
    'https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js',
    runUGAMAP,
    function () {
      loadScript(
        'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js',
        runUGAMAP,
        function () { showError('Map library unavailable — check connection and reload'); }
      );
    }
  );
})();`;

        return new Response(combined, {
          status: 200,
          headers: {
            'Content-Type': 'application/javascript; charset=utf-8',
            'Cache-Control': 'no-cache, no-store, must-revalidate'
          }
        });
      } catch (_) {
        return fetch(req);
      }
    })());
    return;
  }

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

  if (parsed.pathname === '/') {
    event.respondWith(
      fetch(req).then(res => {
        if (res && res.ok) caches.open(CACHE_NAME).then(cache => cache.put(req, res.clone()));
        return res;
      }).catch(() => caches.match(req))
    );
  }
});
