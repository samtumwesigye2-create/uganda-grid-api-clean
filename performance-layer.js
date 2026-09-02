// UGAMAP performance layer: network-only acceleration. No routing, map, or ZIPPER behavior changes.
(function () {
  const nativeFetch = window.fetch.bind(window);
  const cache = new Map();
  const inflight = new Map();
  const MAX_CACHE = 80;
  const SEARCH_TTL = 30000;

  function isSearchGet(url, options) {
    const method = String((options && options.method) || 'GET').toUpperCase();
    if (method !== 'GET') return false;
    const s = String(url || '');
    return s.includes('/search?q=') || s.includes('photon.komoot.io/api/?q=');
  }

  function keyFor(url) { return String(url || ''); }

  function prune() {
    if (cache.size <= MAX_CACHE) return;
    const oldest = [...cache.entries()].sort((a,b) => a[1].time - b[1].time);
    oldest.slice(0, cache.size - MAX_CACHE).forEach(([k]) => cache.delete(k));
  }

  window.fetch = function ugamapFastFetch(url, options) {
    if (!isSearchGet(url, options)) return nativeFetch(url, options);

    const key = keyFor(url);
    const now = Date.now();
    const hit = cache.get(key);
    if (hit && now - hit.time < SEARCH_TTL) {
      return Promise.resolve(hit.response.clone());
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

  // Warm only UGAMAP's own API connection. Do not prefetch third-party map tiles.
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
