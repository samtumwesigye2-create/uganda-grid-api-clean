// Visible ZIPPER cell + 5-digit label layer for UGAMAP.
(function () {
  if (!window.L || typeof L.map !== 'function') return;

  const originalMap = L.map;
  if (!originalMap.__ugamapZipWrapped) {
    const wrapped = function () {
      const instance = originalMap.apply(this, arguments);
      window.UGAMAP = window.UGAMAP || {};
      window.UGAMAP.map = instance;
      return instance;
    };
    Object.keys(originalMap).forEach(k => { try { wrapped[k] = originalMap[k]; } catch (_) {} });
    wrapped.__ugamapZipWrapped = true;
    L.map = wrapped;
  }

  function zipCodeOf(feature) {
    const p = (feature && feature.properties) || {};
    const raw = String(p.zip_code || p.zipper_id || '').trim();
    return /^\d{5}$/.test(raw) ? raw : '';
  }

  function labelHtml(code) {
    return '<div style="background:rgba(255,255,255,.92);border:1px solid rgba(15,23,42,.35);border-radius:5px;padding:2px 5px;font:700 11px/1.1 system-ui,-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;color:#111827;box-shadow:0 1px 2px rgba(0,0,0,.18);white-space:nowrap;">' + code + '</div>';
  }

  async function install() {
    const map = window.UGAMAP && window.UGAMAP.map;
    if (!map || map.__zipperVisibleLayerInstalled) return;
    map.__zipperVisibleLayerInstalled = true;

    let data;
    try {
      const r = await fetch('/geography/zipper', { cache: 'no-store' });
      if (!r.ok) throw new Error('ZIPPER geography HTTP ' + r.status);
      data = await r.json();
    } catch (e) {
      console.error('ZIPPER visible map layer failed to load', e);
      map.__zipperVisibleLayerInstalled = false;
      return;
    }

    const polygons = L.geoJSON(data, {
      pane: 'overlayPane',
      style: function () {
        return { color: '#111827', weight: 1, opacity: 0.78, fillColor: '#2563eb', fillOpacity: 0.08 };
      },
      onEachFeature: function (feature, layer) {
        const code = zipCodeOf(feature);
        const p = (feature && feature.properties) || {};
        if (code) {
          layer.bindPopup('<b>ZIP ' + code + '</b><br>' + (p.district || '') + (p.state_code ? '<br>' + p.state_code : ''));
        }
      }
    }).addTo(map);

    const labels = L.layerGroup().addTo(map);
    const labelMarkers = [];

    polygons.eachLayer(function (layer) {
      const feature = layer.feature || {};
      const code = zipCodeOf(feature);
      if (!code || typeof layer.getBounds !== 'function') return;
      const center = layer.getBounds().getCenter();
      const marker = L.marker(center, {
        interactive: false,
        keyboard: false,
        icon: L.divIcon({ className: 'ugamap-zip-label', html: labelHtml(code), iconSize: null })
      });
      marker.__zipCode = code;
      labelMarkers.push(marker);
    });

    function refreshLabels() {
      labels.clearLayers();
      const z = map.getZoom();
      if (z < 7) return;
      const bounds = map.getBounds().pad(0.15);
      let shown = 0;
      const limit = z >= 12 ? 1200 : z >= 10 ? 550 : z >= 9 ? 300 : z >= 8 ? 160 : 90;
      for (const marker of labelMarkers) {
        if (shown >= limit) break;
        if (bounds.contains(marker.getLatLng())) {
          labels.addLayer(marker);
          shown += 1;
        }
      }
    }

    map.on('zoomend moveend', refreshLabels);
    refreshLabels();

    window.UGAMAP = window.UGAMAP || {};
    window.UGAMAP.zipperLayer = { polygons: polygons, labels: labels, refresh: refreshLabels };
  }

  window.addEventListener('load', function () {
    setTimeout(install, 150);
  });
})();
