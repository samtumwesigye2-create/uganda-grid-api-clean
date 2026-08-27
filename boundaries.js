(function () {
  if (!window.L) return;

  // Capture the application's Leaflet map without changing its routing code.
  const originalMap = L.map;
  L.map = function () {
    const map = originalMap.apply(this, arguments);
    window.__UGAMAP_LEAFLET_MAP__ = map;
    return map;
  };
  Object.keys(originalMap).forEach(k => { try { L.map[k] = originalMap[k]; } catch (_) {} });

  async function getJson(path) {
    const r = await fetch(path, { headers: { Accept: 'application/json' } });
    if (!r.ok) throw new Error(path + ' returned HTTP ' + r.status);
    return r.json();
  }

  window.addEventListener('load', async function () {
    const map = window.__UGAMAP_LEAFLET_MAP__;
    if (!map) return;
    try {
      const [states, zips] = await Promise.all([
        getJson('/geography/states'),
        getJson('/geography/zips')
      ]);

      const stateLayer = L.geoJSON(states, {
        style: { color: '#111827', weight: 3, fillOpacity: 0.03 },
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
      console.error('Boundary layers unavailable:', e);
    }
  });
})();
