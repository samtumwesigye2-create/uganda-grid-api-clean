window.addEventListener('load', () => {
  const G = id => document.getElementById(id);
  const start = G('start');
  const dest = G('dest');
  const navigate = G('navigate');
  const mode = G('mode');
  const status = G('status');
  const info = G('info');
  const myLocation = G('myLocation');
  const startBox = G('ss');
  const destBox = G('ds');

  if (!window.L || !G('map')) return;

  const map = L.map('map').setView([1.3733, 32.2903], 7);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '\u00A9 OpenStreetMap contributors'
  }).addTo(map);

  let routeLine = null;
  let userMarker = null;
  let navMarker = null;
  let navAnimId = null;
  const selected = { start: null, dest: null };
  const requestSeq = { start: 0, dest: 0 };

  const setStatus = (text, type = '') => {
    status.textContent = text;
    status.className = 'status' + (type ? ' ' + type : '');
  };

  const escapeHtml = value => String(value || '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));

  const isGridId = q => /^UG-[A-Z0-9]+-\d+$/i.test(q.trim());
  const apiCandidates = () => {
    const urls = [];
    if (location.protocol.startsWith('http')) urls.push(location.origin);
    urls.push('https://uganda-grid-api-clean-production.up.railway.app');
    return [...new Set(urls)];
  };

  async function gridSearch(q) {
    let lastError = null;
    for (const base of apiCandidates()) {
      try {
        const r = await fetch(base + '/search?q=' + encodeURIComponent(q));
        if (!r.ok) throw new Error('HTTP ' + r.status);
        const d = await r.json();
        if (Array.isArray(d.results)) return d.results;
      } catch (e) {
        lastError = e;
      }
    }
    throw lastError || new Error('Grid service unavailable');
  }

  async function nominatim(q, limit = 5) {
    const url = 'https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&countrycodes=ug&limit=' + limit + '&q=' + encodeURIComponent(q);
    const r = await fetch(url, { headers: { 'Accept': 'application/json' } });
    if (!r.ok) throw new Error('Address search unavailable');
    return await r.json();
  }

  async function searchAddress(q) {
    if (/^UG-/i.test(q)) {
      const grid = await gridSearch(q);
      return grid.map(x => ({
        lat: Number(x.latitude ?? x.lat),
        lon: Number(x.longitude ?? x.lon),
        address: x.address || x.display_name || x.grid_id || q,
        grid_id: x.grid_id || ''
      })).filter(x => Number.isFinite(x.lat) && Number.isFinite(x.lon));
    }
    const places = await nominatim(q, 5);
    return places.map(x => ({
      lat: Number(x.lat),
      lon: Number(x.lon),
      address: x.display_name,
      grid_id: ''
    }));
  }

  function clearSelection(type) {
    selected[type] = null;
    const out = G(type === 'start' ? 'sr' : 'dr');
    if (out) out.textContent = '';
  }

  function saveSelection(type, place) {
    selected[type] = place;
    const input = type === 'start' ? start : dest;
    const out = G(type === 'start' ? 'sr' : 'dr');
    input.value = place.address || place.grid_id || '';
    input.dataset.lat = String(place.lat);
    input.dataset.lon = String(place.lon);
    input.dataset.address = place.address || '';
    if (out) out.textContent = (place.grid_id ? place.grid_id + ' \u2014 ' : '') + (place.address || 'Selected');
    setStatus('\u2713 ' + (type === 'start' ? 'Start' : 'Destination') + ' selected', 'ok');
  }

  async function updateSuggestions(type) {
    const input = type === 'start' ? start : dest;
    const box = type === 'start' ? startBox : destBox;
    const q = input.value.trim();
    clearSelection(type);
    input.dataset.lat = '';
    input.dataset.lon = '';
    const seq = ++requestSeq[type];

    if (q.length < 3) {
      box.style.display = 'none';
      return;
    }

    try {
      const results = await searchAddress(q);
      if (seq !== requestSeq[type]) return;
      box.innerHTML = '';
      if (!results.length) {
        box.style.display = 'none';
        setStatus('No matching location found', 'err');
        return;
      }
      results.forEach(place => {
        const item = document.createElement('div');
        item.textContent = (place.grid_id ? place.grid_id + ' \u2014 ' : '') + place.address;
        item.addEventListener('pointerdown', e => {
          e.preventDefault();
          saveSelection(type, place);
          box.style.display = 'none';
        });
        box.appendChild(item);
      });
      box.style.display = 'block';
    } catch (e) {
      console.error(e);
      box.style.display = 'none';
      setStatus(e.message || 'Search failed', 'err');
    }
  }

  let startTimer = null;
  let destTimer = null;
  start.addEventListener('input', () => {
    clearTimeout(startTimer);
    startTimer = setTimeout(() => updateSuggestions('start'), 250);
  });
  dest.addEventListener('input', () => {
    clearTimeout(destTimer);
    destTimer = setTimeout(() => updateSuggestions('dest'), 250);
  });

  async function locateText(q) {
    const text = q.trim();
    if (!text) throw new Error('Enter both start and destination');
    if (isGridId(text)) {
      const xs = await gridSearch(text);
      const x = xs.find(v => String(v.grid_id || '').toUpperCase() === text.toUpperCase()) || xs[0];
      if (!x) throw new Error('Grid ID not found');
      const p = {
        lat: Number(x.latitude ?? x.lat),
        lon: Number(x.longitude ?? x.lon),
        address: x.address || x.grid_id,
        grid_id: x.grid_id || text
      };
      if (!Number.isFinite(p.lat) || !Number.isFinite(p.lon)) throw new Error('Grid ID has invalid coordinates');
      return p;
    }
    const xs = await nominatim(text, 1);
    if (!xs[0]) throw new Error('Location not found: ' + text);
    return { lat: Number(xs[0].lat), lon: Number(xs[0].lon), address: xs[0].display_name, grid_id: '' };
  }

  async function getCoordinates(type, input) {
    if (selected[type]) return selected[type];
    const lat = Number(input.dataset.lat);
    const lon = Number(input.dataset.lon);
    if (Number.isFinite(lat) && Number.isFinite(lon) && input.dataset.lat && input.dataset.lon) {
      return { lat, lon, address: input.dataset.address || input.value, grid_id: '' };
    }
    return await locateText(input.value);
  }

  function haversine(a, b) {
    const R = 6371000;
    const p = Math.PI / 180;
    const dLat = (b.lat - a.lat) * p;
    const dLon = (b.lon - a.lon) * p;
    const x = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * p) * Math.cos(b.lat * p) * Math.sin(dLon / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(x));
  }

  function bearing(a, b) {
    const toRad = d => d * Math.PI / 180;
    const toDeg = r => r * 180 / Math.PI;
    const y = Math.sin(toRad(b.lon - a.lon)) * Math.cos(toRad(b.lat));
    const x = Math.cos(toRad(a.lat)) * Math.sin(toRad(b.lat)) -
              Math.sin(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.cos(toRad(b.lon - a.lon));
    return (toDeg(Math.atan2(y, x)) + 360) % 360;
  }

  function makeArrowIcon(deg) {
    return L.divIcon({
      className: 'nav-arrow-icon',
      html: '<div style="width:34px;height:34px;display:flex;align-items:center;justify-content:center;transform:rotate(' + deg + 'deg);">' +
            '<svg width="30" height="30" viewBox="0 0 24 24"><path d="M12 2 L19 21 L12 17 L5 21 Z" fill="#1d4ed8" stroke="#ffffff" stroke-width="1.5"/></svg>' +
            '</div>',
      iconSize: [34, 34],
      iconAnchor: [17, 17]
    });
  }

  function stopSimulation() {
    if (navAnimId) {
      cancelAnimationFrame(navAnimId);
      navAnimId = null;
    }
  }

  function simulateNavigation(pts) {
    stopSimulation();
    if (!pts || pts.length < 2) return;
    if (navMarker) { map.removeLayer(navMarker); navMarker = null; }

    const segDist = [];
    let total = 0;
    for (let i = 0; i < pts.length - 1; i++) {
      const d = haversine({ lat: pts[i][0], lon: pts[i][1] }, { lat: pts[i + 1][0], lon: pts[i + 1][1] });
      segDist.push(d);
      total += d;
    }
    if (total === 0) return;

    const initialDeg = bearing({ lat: pts[0][0], lon: pts[0][1] }, { lat: pts[1][0], lon: pts[1][1] });
    navMarker = L.marker(pts[0], { icon: makeArrowIcon(initialDeg), zIndexOffset: 1000 }).addTo(map);

    const totalAnimMs = Math.min(45000, Math.max(12000, total / 3));
    const startTime = performance.now();
    setStatus('Navigating...', 'ok');

    function frame(now) {
      const elapsed = now - startTime;
      let t = elapsed / totalAnimMs;
      if (t >= 1) t = 1;
      const targetDist = t * total;

      let acc = 0, segIndex = 0;
      for (; segIndex < segDist.length; segIndex++) {
        if (acc + segDist[segIndex] >= targetDist) break;
        acc += segDist[segIndex];
      }
      segIndex = Math.min(segIndex, segDist.length - 1);
      const segLen = segDist[segIndex] || 0;
      const segT = segLen > 0 ? (targetDist - acc) / segLen : 0;
      const p1 = pts[segIndex];
      const p2 = pts[segIndex + 1] || pts[segIndex];
      const lat = p1[0] + (p2[0] - p1[0]) * segT;
      const lon = p1[1] + (p2[1] - p1[1]) * segT;
      const deg = bearing({ lat: p1[0], lon: p1[1] }, { lat: p2[0], lon: p2[1] });

      navMarker.setLatLng([lat, lon]);
      navMarker.setIcon(makeArrowIcon(deg));
      map.panTo([lat, lon], { animate: false });

      if (t < 1) {
        navAnimId = requestAnimationFrame(frame);
      } else {
        setStatus('Arrived at destination', 'ok');
        navAnimId = null;
      }
    }

    navAnimId = requestAnimationFrame(frame);
  }

  function decodeShape(str) {
    let index = 0, lat = 0, lon = 0;
    const out = [];
    while (index < str.length) {
      let shift = 0, result = 0, b;
      do { b = str.charCodeAt(index++) - 63; result |= (b & 31) << shift; shift += 5; } while (b >= 32);
      lat += (result & 1) ? ~(result >> 1) : (result >> 1);
      shift = 0; result = 0;
      do { b = str.charCodeAt(index++) - 63; result |= (b & 31) << shift; shift += 5; } while (b >= 32);
      lon += (result & 1) ? ~(result >> 1) : (result >> 1);
      out.push([lat / 1e6, lon / 1e6]);
    }
    return out;
  }

  async function getRoute(a, b) {
    if (mode.value === 'flight') {
      const distance = haversine(a, b);
      return { pts: [[a.lat, a.lon], [b.lat, b.lon]], distance, duration: distance / 800000 * 3600 };
    }

    const costing = mode.value === 'walking' ? 'pedestrian' : mode.value === 'cycling' ? 'bicycle' : 'auto';
    const payload = { locations: [{ lat: a.lat, lon: a.lon }, { lat: b.lat, lon: b.lon }], costing, units: 'kilometers' };
    const r = await fetch('https://valhalla1.openstreetmap.de/route', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
    });
    if (!r.ok) throw new Error('Routing service unavailable');
    const d = await r.json();
    const leg = d && d.trip && d.trip.legs && d.trip.legs[0];
    if (!leg || !leg.shape) throw new Error('No route found');
    return {
      pts: decodeShape(leg.shape),
      distance: Number((leg.summary && leg.summary.length) || 0) * 1000,
      duration: Number((leg.summary && leg.summary.time) || 0)
    };
  }

  function formatTime(seconds) {
    const minutes = Math.max(1, Math.round(seconds / 60));
    if (minutes < 60) return minutes + ' min';
    return Math.floor(minutes / 60) + ' hr ' + (minutes % 60) + ' min';
  }

  async function drawRoute() {
    try {
      navigate.disabled = true;
      stopSimulation();
      setStatus('Calculating route...');
      const a = await getCoordinates('start', start);
      const b = await getCoordinates('dest', dest);
      if (Math.abs(a.lat - b.lat) < 1e-7 && Math.abs(a.lon - b.lon) < 1e-7) throw new Error('Start and destination are the same');
      const route = await getRoute(a, b);
      if (routeLine) map.removeLayer(routeLine);
      routeLine = L.polyline(route.pts, { color: '#d71920', weight: 6, smoothFactor: 1 }).addTo(map);
      map.fitBounds(routeLine.getBounds(), { padding: [30, 30] });
      const label = (mode.options[mode.selectedIndex] && mode.options[mode.selectedIndex].text) || 'Route';
      info.innerHTML = '<span class="routecard">' + escapeHtml(label) + '</span>' +
        '<span class="routecard">\uD83D\uDCCF ' + (route.distance / 1000).toFixed(1) + ' km</span>' +
        '<span class="routecard">\u23F1 ' + escapeHtml(formatTime(route.duration)) + '</span>';
      setStatus('\u2713 Route ready', 'ok');
      setTimeout(() => simulateNavigation(route.pts), 600);
    } catch (e) {
      console.error(e);
      setStatus(e.message || 'Unable to calculate route', 'err');
    } finally {
      navigate.disabled = false;
    }
  }

  navigate.addEventListener('click', drawRoute);
  mode.addEventListener('change', () => {
    if (start.value.trim() && dest.value.trim()) drawRoute();
  });

  myLocation.addEventListener('click', () => {
    if (!navigator.geolocation) {
      setStatus('Location is not supported on this device', 'err');
      return;
    }
    setStatus('Getting your location...');
    navigator.geolocation.getCurrentPosition(position => {
      const p = { lat: position.coords.latitude, lon: position.coords.longitude, address: 'Current location', grid_id: '' };
      selected.start = p;
      start.value = 'Current location';
      start.dataset.lat = String(p.lat);
      start.dataset.lon = String(p.lon);
      start.dataset.address = p.address;
      G('sr').textContent = '\uD83D\uDCCD Current location';
      if (userMarker) map.removeLayer(userMarker);
      userMarker = L.marker([p.lat, p.lon]).addTo(map).bindPopup('You are here').openPopup();
      map.setView([p.lat, p.lon], 16);
      setStatus('\uD83D\uDCCD Current location set as start', 'ok');
    }, error => {
      console.error(error);
      setStatus('Unable to access your location. Check browser location permission.', 'err');
    }, { enableHighAccuracy: true, timeout: 12000, maximumAge: 30000 });
  });

  const googleMaps = G('googleMaps');
  if (googleMaps) googleMaps.addEventListener('click', () => {
    if (!dest.value.trim()) {
      setStatus('Enter a destination first', 'err');
      return;
    }
    const q = selected.dest ? (selected.dest.lat + ',' + selected.dest.lon) : dest.value.trim();
    window.open('https://www.google.com/maps/search/?api=1&query=' + encodeURIComponent(q), '_blank');
  });

  map.on('click', () => {
    startBox.style.display = 'none';
    destBox.style.display = 'none';
  });
  document.addEventListener('click', e => {
    if (!start.contains(e.target) && !startBox.contains(e.target)) startBox.style.display = 'none';
    if (!dest.contains(e.target) && !destBox.contains(e.target)) destBox.style.display = 'none';
  });

  setTimeout(() => map.invalidateSize(), 300);
  setStatus('\uD83C\uDDFA\uD83C\uDDEC Uganda National Grid ready', 'ok');
});
const reportBtn = document.getElementById("reportBtn");
const reportMenu = document.getElementById("reportMenu");

if (reportBtn && reportMenu) {
  reportBtn.onclick = () => {
    reportMenu.style.display =
      reportMenu.style.display === "none" ? "block" : "none";
  };

  document.querySelectorAll(".reportType").forEach(button => {
    button.onclick = () => {
      const type = button.textContent;
      document.getElementById("status").textContent =
        "Report selected: " + type;

      reportMenu.style.display = "none";
    };
  });
}
