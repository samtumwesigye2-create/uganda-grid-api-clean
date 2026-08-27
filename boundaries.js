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
        style: { color: '#f59e0b', weight: 3, fillColor: '#f59e0b', fillOpacity: 0.015 },
        onEachFeature: function (f, layer) {
          const p = f.properties || {};
          const name = p.state_name || p.state_code || 'State';
          const postalPrefix = p.postal_prefix || '';
          const gridPrefix = p.grid_prefix || '';
          layer.bindPopup('<b>' + name + '</b><br>State: ' + (p.state_code || '') + '<br>Grid prefix: ' + gridPrefix + '<br>Postal prefix: ' + postalPrefix);
          layer._ugamapStateLabel = postalPrefix ? (name + ' · ZIP ' + postalPrefix) : name;
        }
      });

      const palette = ['#38bdf8','#22c55e','#facc15','#c084fc','#fb7185','#2dd4bf','#fb923c','#60a5fa','#a3e635','#f472b6'];
      const zipLayer = L.geoJSON(zips, {
        style: function (f) {
          const zip = String((f.properties || {}).zip_code || '');
          const n = Number(zip.slice(-2)) || 1;
          const color = palette[(n - 1) % palette.length];
          return { color: color, weight: 1.5, dashArray: '5 4', fillColor: color, fillOpacity: 0.12 };
        },
        onEachFeature: function (f, layer) {
          const p = f.properties || {};
          const zip = p.zip_code || '';
          layer.bindPopup('<b>ZIP ' + zip + '</b><br>' + (p.state_name || '') + '<br>Region: ' + (p.postal_region || ''));
          layer._ugamapZip = zip;
        }
      });

      if (!document.getElementById('ugamap-boundary-style')) {
        const style = document.createElement('style');
        style.id = 'ugamap-boundary-style';
        style.textContent = '.ugamap-zip-label{background:rgba(8,15,30,.86);color:#fff;border:1px solid rgba(255,255,255,.35);border-radius:5px;box-shadow:none;font-weight:700;font-size:10px;padding:2px 4px}.ugamap-zip-label:before{display:none}.ugamap-state-prefix{background:rgba(8,15,30,.92);color:#ffd166;border:1px solid rgba(245,158,11,.9);border-radius:7px;box-shadow:0 2px 8px rgba(0,0,0,.35);font-weight:800;font-size:11px;padding:3px 6px;white-space:nowrap}.ugamap-state-prefix:before{display:none}';
        document.head.appendChild(style);
      }

      function updateLabels() {
        const zoom = map.getZoom();
        const showZip = zoom >= 8;
        const showState = zoom >= 6 && zoom <= 9;

        zipLayer.eachLayer(function (layer) {
          const zip = layer._ugamapZip;
          if (!zip) return;
          if (showZip) {
            if (!layer.getTooltip()) layer.bindTooltip(String(zip), { permanent: true, direction: 'center', className: 'ugamap-zip-label', opacity: 0.92 });
            layer.openTooltip();
          } else if (layer.getTooltip()) {
            layer.unbindTooltip();
          }
        });

        stateLayer.eachLayer(function (layer) {
          const label = layer._ugamapStateLabel;
          if (!label) return;
          if (showState) {
            if (!layer.getTooltip()) layer.bindTooltip(label, { permanent: true, direction: 'center', className: 'ugamap-state-prefix', opacity: 0.96 });
            layer.openTooltip();
          } else if (layer.getTooltip()) {
            layer.unbindTooltip();
          }
        });
      }

      L.control.layers(null, { 'State Boundaries': stateLayer, 'ZIP Zones': zipLayer }, { collapsed: true, position: 'topright' }).addTo(map);
      stateLayer.addTo(map);
      zipLayer.addTo(map);
      updateLabels();
      map.on('zoomend', updateLabels);

      window.UGAMAP = window.UGAMAP || {};
      window.UGAMAP.boundaries = { states: stateLayer, zips: zipLayer, updateLabels: updateLabels };
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
