// DDR V2.0E radar map overlay
// Polls a GeoJSON FeatureCollection and renders confirmed radar tracks.
// Load this file after Leaflet and before app.js so it can capture the map.
(function () {
  if (!window.L) return;

  const originalMapFactory = L.map;
  let capturedMap = null;

  L.map = function () {
    const map = originalMapFactory.apply(this, arguments);
    if (!capturedMap) {
      capturedMap = map;
      window.DDR_MAP = map;
      window.dispatchEvent(new CustomEvent('ddr-map-ready', { detail: { map } }));
    }
    return map;
  };

  const POLL_MS = 1000;
  const STALE_MS = 7000;
  const MAX_TRAIL_POINTS = 40;
  const FEED_URL = window.DDR_RADAR_FEED_URL || '/radar/tracks.geojson';

  const markers = new Map();
  const trails = new Map();
  const lastSeen = new Map();

  function escapeHtml(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (c) {
      return {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      }[c];
    });
  }

  function radarIcon(status, motion) {
    const confirmed = status === 'CONFIRMED';
    const label = confirmed ? '●' : '○';
    const border = confirmed ? '#ff3b30' : '#ffcc00';
    const glow = confirmed ? 'rgba(255,59,48,.45)' : 'rgba(255,204,0,.35)';

    return L.divIcon({
      className: 'ddr-radar-icon',
      html:
        '<div style="width:28px;height:28px;border-radius:50%;background:rgba(8,15,28,.92);' +
        'border:2px solid ' + border + ';box-shadow:0 0 0 6px ' + glow + ';display:flex;' +
        'align-items:center;justify-content:center;color:' + border + ';font-size:16px;font-weight:800">' +
        label + '</div>' +
        '<div style="margin-top:7px;transform:translateX(-36px);width:100px;text-align:center;' +
        'font-size:10px;font-weight:800;color:white;text-shadow:0 1px 3px #000">' +
        escapeHtml(motion || 'TRACK') + '</div>',
      iconSize: [28, 44],
      iconAnchor: [14, 14]
    });
  }

  function popupHtml(props) {
    const confidence = Number(props.confidence);
    const confidenceText = Number.isFinite(confidence)
      ? Math.round(confidence * 100) + '%'
      : '--';

    const range = Number(props.receiver_range_m);
    const rangeText = Number.isFinite(range)
      ? (range >= 1000 ? (range / 1000).toFixed(2) + ' km' : Math.round(range) + ' m')
      : '--';

    const bearing = Number(props.bearing_deg);
    const bearingText = Number.isFinite(bearing) ? bearing.toFixed(1) + '°' : '--';

    const speed = Number(props.radial_speed_mps);
    const speedText = Number.isFinite(speed) ? speed.toFixed(1) + ' m/s' : '--';

    return (
      '<div style="min-width:190px">' +
      '<div style="font-weight:800;margin-bottom:6px">DDR RADAR TRACK</div>' +
      '<div><b>ID:</b> ' + escapeHtml(props.track_id || 'UNKNOWN') + '</div>' +
      '<div><b>Status:</b> ' + escapeHtml(props.status || 'UNKNOWN') + '</div>' +
      '<div><b>Range:</b> ' + rangeText + '</div>' +
      '<div><b>Bearing:</b> ' + bearingText + '</div>' +
      '<div><b>Motion:</b> ' + escapeHtml(props.motion || 'UNKNOWN') + '</div>' +
      '<div><b>Radial speed:</b> ' + speedText + '</div>' +
      '<div><b>Confidence:</b> ' + confidenceText + '</div>' +
      '<div><b>SNR:</b> ' + escapeHtml(props.snr_db == null ? '--' : props.snr_db + ' dB') + '</div>' +
      '</div>'
    );
  }

  function getMap() {
    return capturedMap || window.DDR_MAP || null;
  }

  function removeTrack(trackId) {
    const map = getMap();
    if (!map) return;

    const marker = markers.get(trackId);
    if (marker) map.removeLayer(marker);

    const trail = trails.get(trackId);
    if (trail) map.removeLayer(trail);

    markers.delete(trackId);
    trails.delete(trackId);
    lastSeen.delete(trackId);
  }

  function pruneStaleTracks() {
    const now = Date.now();
    for (const [trackId, timestamp] of lastSeen.entries()) {
      if (now - timestamp > STALE_MS) removeTrack(trackId);
    }
  }

  function renderFeature(feature) {
    const map = getMap();
    if (!map || !feature || !feature.geometry || feature.geometry.type !== 'Point') return;

    const coords = feature.geometry.coordinates || [];
    const lon = Number(coords[0]);
    const lat = Number(coords[1]);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;

    const props = feature.properties || {};
    const trackId = String(props.track_id || 'DDR-UNKNOWN');
    const point = [lat, lon];

    let marker = markers.get(trackId);
    if (!marker) {
      marker = L.marker(point, {
        icon: radarIcon(props.status, props.motion),
        zIndexOffset: 800
      }).addTo(map);
      markers.set(trackId, marker);
    } else {
      marker.setLatLng(point);
      marker.setIcon(radarIcon(props.status, props.motion));
    }

    marker.bindPopup(popupHtml(props));

    let trail = trails.get(trackId);
    if (!trail) {
      trail = L.polyline([point], {
        color: '#ff3b30',
        weight: 2,
        opacity: 0.8,
        dashArray: '5 5'
      }).addTo(map);
      trails.set(trackId, trail);
    } else {
      const points = trail.getLatLngs();
      points.push(L.latLng(lat, lon));
      if (points.length > MAX_TRAIL_POINTS) points.shift();
      trail.setLatLngs(points);
    }

    lastSeen.set(trackId, Date.now());
  }

  function renderFeed(feed) {
    if (!feed || feed.type !== 'FeatureCollection' || !Array.isArray(feed.features)) return;
    feed.features.forEach(renderFeature);
    pruneStaleTracks();

    window.dispatchEvent(new CustomEvent('ddr-radar-update', {
      detail: {
        sensor_id: feed.sensor_id || null,
        count: feed.features.length,
        timestamp: feed.timestamp || Date.now() / 1000
      }
    }));
  }

  async function poll() {
    try {
      const response = await fetch(FEED_URL, {
        cache: 'no-store',
        headers: { Accept: 'application/geo+json, application/json' }
      });

      if (!response.ok) throw new Error('DDR radar feed HTTP ' + response.status);

      const feed = await response.json();
      renderFeed(feed);
    } catch (error) {
      // Keep the base map operational even when the radar node is offline.
      console.debug('DDR radar feed unavailable:', error && error.message ? error.message : error);
      pruneStaleTracks();
    }
  }

  window.DDR_RADAR = {
    renderFeed,
    removeTrack,
    getMap,
    feedUrl: FEED_URL
  };

  window.addEventListener('load', function () {
    poll();
    setInterval(poll, POLL_MS);
  });
})();
