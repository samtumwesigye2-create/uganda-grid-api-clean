// UGAMAP routing transport compatibility fix.
// The public Valhalla demo supports GET /route?json=... as well as POST.
// Convert only that cross-origin route request to GET to avoid browser
// preflight/CORS failures on mobile while leaving every other fetch untouched.
(function () {
  const nativeFetch = window.fetch.bind(window);
  window.fetch = function (input, init) {
    try {
      const url = typeof input === 'string' ? input : (input && input.url) || '';
      const opts = init || {};
      if (url === 'https://valhalla1.openstreetmap.de/route' && String(opts.method || 'GET').toUpperCase() === 'POST' && opts.body) {
        const routeUrl = url + '?json=' + encodeURIComponent(String(opts.body));
        const next = Object.assign({}, opts);
        next.method = 'GET';
        delete next.body;
        delete next.headers;
        return nativeFetch(routeUrl, next);
      }
    } catch (_) {}
    return nativeFetch(input, init);
  };
})();
