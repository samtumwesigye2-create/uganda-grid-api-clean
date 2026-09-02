const CACHE_NAME = 'ugamap-cache-v6-clean';

self.addEventListener('install', event => {
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names.map(name => caches.delete(name)));
    await self.clients.claim();
  })());
});

// Intentionally no fetch handler.
// UGAMAP files, Leaflet, map tiles and APIs now load directly from the network.
// This removes the old app.js rewriting/concatenation path that could leave
// the homepage permanently stuck on "Loading...".
