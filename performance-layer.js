// UGAMAP performance layer: network-only acceleration. No routing, map, or ZIPPER behavior changes.
(function () {
  const nativeFetch = window.fetch.bind(window);
  const cache = new Map();
  const inflight = new Map();
  const MAX_CACHE = 80;
  const SEARCH_TTL = 30000;
  const SESSION_PREFIX = 'ugamap-search-v1:';

  function addPreconnect(href) {
    try {
      if (document.querySelector('link[rel="preconnect"][href="' + href + '"]')) return;
      const link = document.createElement('link');
      link.rel = 'preconnect';
      link.href = href;
      link.crossOrigin = 'anonymous';
      document.head.appendChild(link);
    } catch (_) {}
  }

  // Open the expensive third-party connections early, without prefetching tiles.
  addPreconnect('https://a.tile.openstreetmap.org');
  addPreconnect('https://b.tile.openstreetmap.org');
  addPreconnect('https://c.tile.openstreetmap.org');
  addPreconnect('https://photon.komoot.io');
  addPreconnect('https://server.arcgisonline.com');

  function isSearchGet(url, options) {
    const method = String((options && options.method) || 'GET').toUpperCase();
    if (method !== 'GET') return false;
    const s = String(url || '');
    return s.includes('/search?q=') || s.includes('photon.komoot.io/api/?q=');
  }

  function keyFor(url) { return String(url || ''); }
  function storageKey(key) { return SESSION_PREFIX + encodeURIComponent(key); }

  function prune() {
    if (cache.size <= MAX_CACHE) return;
    const oldest = [...cache.entries()].sort((a,b) => a[1].time - b[1].time);
    oldest.slice(0, cache.size - MAX_CACHE).forEach(([k]) => cache.delete(k));
  }

  function restoreSession(key) {
    try {
      const raw = sessionStorage.getItem(storageKey(key));
      if (!raw) return null;
      const item = JSON.parse(raw);
      if (!item || Date.now() - Number(item.time || 0) >= SEARCH_TTL) {
        sessionStorage.removeItem(storageKey(key));
        return null;
      }
      return new Response(item.body || '', {
        status: Number(item.status || 200),
        statusText: item.statusText || 'OK',
        headers: item.headers || {'Content-Type':'application/json'}
      });
    } catch (_) { return null; }
  }

  function persistSession(key, response) {
    try {
      const copy = response.clone();
      copy.text().then(body => {
        try {
          const headers = {};
          copy.headers.forEach((v,k) => { headers[k] = v; });
          sessionStorage.setItem(storageKey(key), JSON.stringify({
            time: Date.now(),
            status: copy.status,
            statusText: copy.statusText,
            headers,
            body
          }));
        } catch (_) {}
      }).catch(() => {});
    } catch (_) {}
  }

  window.fetch = function ugamapFastFetch(url, options) {
    if (!isSearchGet(url, options)) return nativeFetch(url, options);

    const key = keyFor(url);
    const now = Date.now();
    const hit = cache.get(key);
    if (hit && now - hit.time < SEARCH_TTL) {
      return Promise.resolve(hit.response.clone());
    }

    const restored = restoreSession(key);
    if (restored) {
      cache.set(key, {time: now, response: restored.clone()});
      prune();
      return Promise.resolve(restored);
    }

    // Reuse an identical request already in flight instead of sending duplicates.
    if (inflight.has(key)) {
      return inflight.get(key).then(r => r.clone());
    }

    const controller = new AbortController();
    const externalSignal = options && options.signal;
    if (externalSignal) {
      if (externalSignal.aborted) controller.abort();
      else externalSignal.addEventListener('abort', () => controller.abort(), {once:true});
    }
    const timer = setTimeout(() => controller.abort(), 8000);
    const requestOptions = Object.assign({}, options || {}, { signal: controller.signal });

    const promise = nativeFetch(url, requestOptions).then(response => {
      clearTimeout(timer);
      if (response.ok) {
        cache.set(key, {time: Date.now(), response: response.clone()});
        persistSession(key, response);
        prune();
      }
      return response;
    }).finally(() => {
      clearTimeout(timer);
      inflight.delete(key);
    });

    inflight.set(key, promise);
    return promise.then(r => r.clone());
  };

  // Tune only the standard street tile layer. This keeps the same provider and appearance,
  // but asks Leaflet to refresh visible tiles sooner on mobile and retain fewer hidden tiles.
  if (window.L && typeof L.tileLayer === 'function') {
    const originalTileLayer = L.tileLayer;
    L.tileLayer = function ugamapFastTileLayer(url, options) {
      const opts = Object.assign({}, options || {});
      if (String(url || '').includes('tile.openstreetmap.org')) {
        if (opts.updateWhenIdle == null) opts.updateWhenIdle = false;
        if (opts.updateWhenZooming == null) opts.updateWhenZooming = true;
        if (opts.updateInterval == null) opts.updateInterval = 100;
        if (opts.keepBuffer == null || opts.keepBuffer > 4) opts.keepBuffer = 4;
      }
      return originalTileLayer.call(this, url, opts);
    };
    Object.keys(originalTileLayer).forEach(k => { try { L.tileLayer[k] = originalTileLayer[k]; } catch (_) {} });
  }

  // Warm only UGAMAP's own API connection. Do not bulk-prefetch third-party map tiles.
  const warm = () => {
    try {
      if (location.protocol.indexOf('http') === 0) nativeFetch(location.origin + '/system/startup-status', {cache:'no-store'}).catch(() => {});
    } catch (_) {}
  };
  if ('requestIdleCallback' in window) requestIdleCallback(warm, {timeout:2500});
  else setTimeout(warm, 1200);

  window.UGAMAP = window.UGAMAP || {};
  window.UGAMAP.performance = {searchCache: cache, inflight: inflight};
})();
