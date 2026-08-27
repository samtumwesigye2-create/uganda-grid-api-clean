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
      const [states, zips] = await Promise.all([getJson('/geography/states'), getJson('/geography/zips')]);

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
          const palette = ['#38bdf8', '#22c55e', '#facc15', '#c084fc', '#fb7185'];
          return { color: palette[(n - 1) % palette.length], weight: 2, dashArray: '6 5', fillOpacity: 0.035 };
        },
        onEachFeature: function (f, layer) {
          const p = f.properties || {};
          const zip = p.zip_code || '';
          layer.bindPopup('<b>ZIP ' + zip + '</b><br>' + (p.state_name || '') + '<br>Region: ' + (p.postal_region || ''));
          if (zip) layer.bindTooltip(String(zip), { permanent: true, direction: 'center', className: 'ugamap-zip-label', opacity: 0.9 });
        }
      });

      if (!document.getElementById('ugamap-boundary-style')) {
        const style = document.createElement('style');
        style.id = 'ugamap-boundary-style';
        style.textContent = '.ugamap-zip-label{background:rgba(8,15,30,.82);color:#fff;border:1px solid rgba(255,255,255,.35);border-radius:5px;box-shadow:none;font-weight:700;font-size:10px;padding:2px 4px}.ugamap-zip-label:before{display:none}';
        document.head.appendChild(style);
      }

      L.control.layers(null, { 'State Boundaries': stateLayer, 'ZIP Zones': zipLayer }, { collapsed: true, position: 'topright' }).addTo(map);
      stateLayer.addTo(map);
      zipLayer.addTo(map);

      window.UGAMAP = window.UGAMAP || {};
      window.UGAMAP.boundaries = { states: stateLayer, zips: zipLayer };
    } catch (e) {
      initialized = false;
      console.error('Boundary layers unavailable:', e);
    }
  }

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
