// UGAMAP routing transport compatibility fix.
// Keep browser navigation same-origin. Railway proxies this request to Valhalla,
// removing mobile CORS/preflight dependence on the public routing server.
(function () {
  const nativeFetch = window.fetch.bind(window);
  window.fetch = function (input, init) {
    try {
      const url = typeof input === 'string' ? input : (input && input.url) || '';
      const opts = init || {};
      if (url === 'https://valhalla1.openstreetmap.de/route' && String(opts.method || 'GET').toUpperCase() === 'POST' && opts.body) {
        const next = Object.assign({}, opts, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: opts.body
        });
        return nativeFetch('/routing/route', next);
      }
    } catch (_) {}
    return nativeFetch(input, init);
  };
})();
