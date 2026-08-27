(function () {
  if (!window.L) return;

  const originalMap = L.map;
  let initialized = false;

  async function getJson(path) {
    const r = await fetch(path, { headers: { Accept: 'application/json' }, cache: 'no-store' });
    if (!r.ok) throw new Error(path + ' returned HTTP ' + r.status);
    return r.json();
  }

  async function initializeBoundaries(map) {
    if (initialized || !map) return;
    initialized = true;
    try {
      const [states, zips] = await Promise.all([
        getJson('/geography/states'),
        getJson('/geography/zips')
      ]);

      const stateLayer = L.geoJSON(states, {
        style: { color: '#f59e0b', weight: 3, fillOpacity: 0.025 },
        onEachFeature: function (f, layer) {
          const p = f.properties || {};
          layer.bindPopup('<b>' + (p.state_name || p.state_code || 'State') + '</b><br>State: ' + (p.state_code || '') + '<br>Grid prefix: ' + (p.grid_prefix || '') + '<br>Postal prefix: ' + (p.postal_prefix || ''));
        }
      });

      const zipLayer = L.geoJSON(zips, {
        style: function (f) {
          const n = Number(String((f.properties || {}).zip_code || '0').slice(-1)) || 1;
          const palette = ['#2563eb', '#16a34a', '#d97706', '#7c3aed', '#dc2626'];
          return { color: palette[(n - 1) % palette.length], weight: 1.5, fillOpacity: 0.10 };
        },
        onEachFeature: function (f, layer) {
          const p = f.properties || {};
          layer.bindPopup('<b>ZIP ' + (p.zip_code || '') + '</b><br>' + (p.state_name || '') + '<br>Region: ' + (p.postal_region || ''));
        }
      });

      L.control.layers(null, {
        'State Boundaries': stateLayer,
        'ZIP Zones': zipLayer
      }, { collapsed: true, position: 'topright' }).addTo(map);

      stateLayer.addTo(map);
      window.UGAMAP = window.UGAMAP || {};
      window.UGAMAP.boundaries = { states: stateLayer, zips: zipLayer };
    } catch (e) {
      initialized = false;
      console.error('Boundary layers unavailable:', e);
    }
  }

  // The boundary module is prepended to app.js by the service worker, so the
  // old window-load hook could fire before app.js created its Leaflet map.
  // Initialize immediately when app.js calls L.map instead.
  L.map = function () {
    const map = originalMap.apply(this, arguments);
    window.__UGAMAP_LEAFLET_MAP__ = map;
    setTimeout(function () { initializeBoundaries(map); }, 0);
    return map;
  };
  Object.keys(originalMap).forEach(function (k) {
    try { L.map[k] = originalMap[k]; } catch (_) {}
  });
})();
