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

  const map = L.map('map', { zoomControl: true }).setView([1.3733, 32.2903], 7);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '\u00A9 OpenStreetMap contributors'
  }).addTo(map);

  let routeLine = null;
  let userMarker = null;
  let navMarker = null;
  let navState = null;
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
    setStatus((type === 'start' ? 'Start' : 'Destination') + ' selected', 'ok');
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
        item.addEventListener('click', e => {
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

  // -----------------------------------------------------------------
  // Full-screen navigation mode, heading-up map rotation, auto-zoom
  // -----------------------------------------------------------------

  let followMode = false;
  let navFollowInitialized = false;
  let currentRotation = 0;
  let idleResumeTimer = null;
  const mapEl = G('map');
  const recenterFab = G('recenterFab');
  const navSummaryBar = G('navSummaryBar');
  const navEta = G('navEta');
  const navSpeedPill = G('navSpeedPill');
  const followBadge = G('followBadge');
  const turnProgressFill = G('turnProgressFill');
  const turnArrowGlyph = G('turnArrowGlyph');

  function setBodyNavigating(active) {
    document.body.classList.toggle('navigating', !!active);
    setTimeout(() => map.invalidateSize(), 60);
  }

  function zoomForMode() {
    if (mode.value === 'walking') return 18;
    if (mode.value === 'cycling') return 17;
    if (mode.value === 'flight') return map.getZoom();
    return 17;
  }

  function setMapRotation(headingDeg) {
    let target = -headingDeg;
    let diff = target - currentRotation;
    diff = ((diff + 180) % 360 + 360) % 360 - 180;
    target = currentRotation + diff;
    currentRotation = target;
    if (mapEl) mapEl.style.transform = 'translate(-50%,-50%) rotate(' + target + 'deg)';
  }

  function applyFollowView(lat, lon, headingDeg) {
    if (!followMode) return;
    if (!navFollowInitialized) {
      map.setView([lat, lon], zoomForMode(), { animate: true });
      navFollowInitialized = true;
    } else {
      map.panTo([lat, lon], { animate: true, duration: 0.5 });
    }
    if (mode.value !== 'flight') setMapRotation(headingDeg || 0);
  }

  function engageFollow() {
    followMode = true;
    navFollowInitialized = false;
    if (recenterFab) recenterFab.classList.remove('show');
    if (followBadge) followBadge.classList.add('show');
    const navRecenterBtn = G('navRecenter');
    if (navRecenterBtn) navRecenterBtn.classList.remove('due');
    clearTimeout(idleResumeTimer);
  }

  function disengageFollow() {
    followMode = false;
    if (recenterFab) recenterFab.classList.add('show');
    if (followBadge) followBadge.classList.remove('show');
    const navRecenterBtn = G('navRecenter');
    if (navRecenterBtn) navRecenterBtn.classList.add('due');
    setMapRotation(0);
  }

  function isActivelyNavigating() {
    return !!liveNav || !!navState;
  }

  map.on('dragstart', () => {
    if (!isActivelyNavigating() || !followMode) return;
    disengageFollow();
  });
  map.on('dragend', () => {
    if (!isActivelyNavigating() || followMode) return;
    clearTimeout(idleResumeTimer);
    idleResumeTimer = setTimeout(() => {
      if (isActivelyNavigating()) engageFollow();
    }, 8000);
  });

  function recenterNav() {
    clearTimeout(idleResumeTimer);
    engageFollow();
    const target = navMarker ? navMarker.getLatLng() : null;
    if (target) map.setView(target, zoomForMode(), { animate: true });
  }
  if (recenterFab) recenterFab.addEventListener('click', recenterNav);

  // ---- Night / dark map mode ----
  let nightManual = null; // null = auto by time, true/false = user override
  function isNightNow() {
    const h = new Date().getHours();
    return h >= 19 || h < 6;
  }
  function refreshNightMode() {
    const on = nightManual === null ? isNightNow() : nightManual;
    if (mapEl) mapEl.classList.toggle('map-dark', on);
    const btn = G('nightToggle');
    if (btn) btn.classList.toggle('on', on);
  }
  const nightToggleBtn = G('nightToggle');
  if (nightToggleBtn) nightToggleBtn.addEventListener('click', () => {
    const currentlyOn = nightManual === null ? isNightNow() : nightManual;
    nightManual = !currentlyOn;
    refreshNightMode();
  });
  refreshNightMode();
  setInterval(() => { if (nightManual === null) refreshNightMode(); }, 5 * 60 * 1000);

  // ---- ETA / speed / progress helpers ----
  function formatClock(date) {
    try {
      return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    } catch (e) {
      return '--:--';
    }
  }

  function updateEta(remainingSeconds) {
    if (!navEta) return;
    if (!Number.isFinite(remainingSeconds) || remainingSeconds < 0) {
      navEta.innerHTML = 'ETA <span class="etaVal">--:--</span>';
      return;
    }
    const arrival = new Date(Date.now() + remainingSeconds * 1000);
    navEta.innerHTML = 'ETA <span class="etaVal">' + formatClock(arrival) + '</span>';
  }

  function updateSpeedPill(kmh) {
    if (!navSpeedPill) return;
    navSpeedPill.textContent = Number.isFinite(kmh) && kmh >= 0 ? Math.round(kmh) + ' km/h' : '-- km/h';
  }

  function updateProgressBar(pct) {
    if (!turnProgressFill) return;
    const clamped = Math.max(0, Math.min(100, pct || 0));
    turnProgressFill.style.width = clamped + '%';
  }

  function glyphForInstruction(text) {
    const t = (text || '').toLowerCase();
    if (t.indexOf('left') !== -1) return '\u2B05';
    if (t.indexOf('right') !== -1) return '\u27A1';
    if (t.indexOf('arrive') !== -1 || t.indexOf('destination') !== -1) return '\u{1F3C1}';
    if (t.indexOf('roundabout') !== -1) return '\u21BB';
    return '\u2B06';
  }

  function showNavControls() {
    const nc = G('navControls');
    if (nc) nc.classList.add('active');
    if (navSummaryBar) navSummaryBar.classList.add('active');
    const pauseBtn = G('navPause');
    if (pauseBtn) pauseBtn.textContent = 'Pause';
  }

  function hideNavControls() {
    const nc = G('navControls');
    if (nc) nc.classList.remove('active');
    if (navSummaryBar) navSummaryBar.classList.remove('active');
    if (recenterFab) recenterFab.classList.remove('show');
    if (followBadge) followBadge.classList.remove('show');
  }

  // -----------------------------------------------------------------
  // Trip history (localStorage)
  // -----------------------------------------------------------------

  const TRIPS_KEY = 'ugamap_trips';
  function loadTrips() {
    try {
      const raw = localStorage.getItem(TRIPS_KEY);
      const arr = raw ? JSON.parse(raw) : [];
      return Array.isArray(arr) ? arr : [];
    } catch (e) {
      return [];
    }
  }
  function saveTripRecord(destAddress, distanceMeters, durationSeconds, travelMode) {
    try {
      const trips = loadTrips();
      trips.unshift({
        dest: destAddress || 'Destination',
        distanceKm: Math.round((distanceMeters / 1000) * 10) / 10,
        durationMin: Math.max(1, Math.round(durationSeconds / 60)),
        mode: travelMode,
        completedAt: Date.now()
      });
      localStorage.setItem(TRIPS_KEY, JSON.stringify(trips.slice(0, 20)));
    } catch (e) {
      console.error('saveTripRecord failed', e);
    }
  }
  function renderTrips() {
    const list = G('tripsList');
    if (!list) return;
    const trips = loadTrips();
    if (!trips.length) {
      list.innerHTML = '<div class="emptyState">No trips yet \u2014 completed navigations will show up here.</div>';
      return;
    }
    list.innerHTML = '';
    trips.forEach(t => {
      const row = document.createElement('div');
      row.className = 'tripItem';
      const when = new Date(t.completedAt).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
      row.innerHTML = '<div class="tripDest">' + escapeHtml(t.dest) + '</div>' +
        '<div class="tripMeta"><span>' + t.distanceKm + ' km</span><span>' + t.durationMin + ' min</span><span>' + escapeHtml(when) + '</span></div>';
      list.appendChild(row);
    });
  }
  function openTrips() {
    renderTrips();
    const overlay = G('tripsOverlay');
    if (overlay) overlay.classList.add('active');
  }
  const tripsCloseBtn = G('tripsClose');
  if (tripsCloseBtn) tripsCloseBtn.addEventListener('click', () => {
    const overlay = G('tripsOverlay');
    if (overlay) overlay.classList.remove('active');
  });
  const tripsOverlayEl = G('tripsOverlay');
  if (tripsOverlayEl) tripsOverlayEl.addEventListener('click', e => {
    if (e.target === tripsOverlayEl) tripsOverlayEl.classList.remove('active');
  });

  // -----------------------------------------------------------------
  // Share ETA
  // -----------------------------------------------------------------

  async function shareTrip() {
    const destAddr = (liveNav && liveNav.destination && liveNav.destination.address) ||
      (dest && dest.value) || 'my destination';
    const remainingSeconds = window.__ugamapRemainingSeconds;
    let etaText = '';
    if (Number.isFinite(remainingSeconds)) {
      etaText = ' ETA ' + formatClock(new Date(Date.now() + remainingSeconds * 1000)) + '.';
    }
    const text = 'Heading to ' + destAddr + ' via Uganda National Grid.' + etaText;
    if (navigator.share) {
      try {
        await navigator.share({ title: 'My trip', text });
        return;
      } catch (e) {
        // user cancelled or share failed; fall through to clipboard
      }
    }
    try {
      await navigator.clipboard.writeText(text);
      setStatus('Trip details copied to clipboard', 'ok');
    } catch (e) {
      setStatus(text, '');
    }
  }
  const navShareBtn = G('navShare');
  if (navShareBtn) navShareBtn.addEventListener('click', shareTrip);

  function stopSimulation() {
    if (navState && navState.rafId) cancelAnimationFrame(navState.rafId);
    navState = null;
    hideNavControls();
  }

  function navFrame(now) {
    if (!navState || navState.paused) return;
    const delta = now - navState.lastTime;
    navState.lastTime = now;
    navState.elapsed += delta;

    let t = navState.elapsed / navState.totalAnimMs;
    if (t >= 1) t = 1;
    const targetDist = t * navState.total;

    const pts = navState.pts;
    const segDist = navState.segDist;
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
    applyFollowView(lat, lon, deg);

    updateProgressBar((targetDist / navState.total) * 100);
    const remM = Math.max(0, navState.total - targetDist);
    const remSec = navState.totalDurationSec ? (1 - t) * navState.totalDurationSec : null;
    window.__ugamapRemainingSeconds = remSec;
    if (remSec != null) updateEta(remSec);
    const remLabel = remM >= 1000 ? (remM / 1000).toFixed(1) + ' km remaining' : Math.round(remM) + ' m remaining';
    info.innerHTML = '<span class="routecard">' + escapeHtml(remLabel) + '</span>';

    if (t < 1) {
      navState.rafId = requestAnimationFrame(navFrame);
    } else {
      setStatus('Arrived at destination', 'ok');
      saveTripRecord(navState.destAddress, navState.total, navState.realElapsedMs / 1000, mode.value);
      hideNavControls();
      hideTurnBanner();
      setBodyNavigating(false);
      navState = null;
    }
  }

  function simulateNavigation(pts, opts) {
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

    setBodyNavigating(true);
    engageFollow();

    navState = {
      pts, segDist, total, totalAnimMs,
      elapsed: 0,
      lastTime: performance.now(),
      paused: false,
      rafId: null,
      totalDurationSec: (opts && opts.durationSec) || null,
      destAddress: (opts && opts.destAddress) || (dest && dest.value) || 'Destination',
      realElapsedMs: 0
    };
    const realStart = Date.now();
    const trackReal = () => { if (navState) navState.realElapsedMs = Date.now() - realStart; };
    navState.realTracker = setInterval(trackReal, 1000);

    showNavControls();
    if (opts && opts.maneuvers && opts.maneuvers.length) {
      showTurnBanner(opts.maneuvers[0].instruction, 'Route preview \u2014 GPS unavailable');
    } else {
      showTurnBanner('Route preview', 'Live GPS unavailable on this device');
    }
    setStatus('Navigating (preview mode)...', 'ok');
    navState.rafId = requestAnimationFrame(navFrame);
  }

  // ---------------------------------------------------------------------
  // Live GPS turn-by-turn navigation with voice guidance
  // ---------------------------------------------------------------------

  let liveNav = null;
  let voiceEnabled = true;
  let lastSpokenText = '';

  const turnBanner = G('turnBanner');
  const turnMain = G('turnMain');
  const turnSub = G('turnSub');
  const voiceToggleBtn = G('voiceToggle');

  function speak(text) {
    if (!voiceEnabled || !text) return;
    if (!('speechSynthesis' in window)) return;
    if (text === lastSpokenText && window.speechSynthesis.speaking) return;
    lastSpokenText = text;
    try {
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text);
      u.rate = 1;
      u.pitch = 1;
      window.speechSynthesis.speak(u);
    } catch (e) {
      console.error('speech error', e);
    }
  }

  if (voiceToggleBtn) {
    voiceToggleBtn.addEventListener('click', () => {
      voiceEnabled = !voiceEnabled;
      voiceToggleBtn.classList.toggle('muted', !voiceEnabled);
      voiceToggleBtn.setAttribute('aria-pressed', String(!voiceEnabled));
      if (!voiceEnabled && 'speechSynthesis' in window) window.speechSynthesis.cancel();
      setStatus(voiceEnabled ? 'Voice guidance on' : 'Voice guidance off', 'ok');
    });
  }

  function showTurnBanner(main, sub) {
    if (!turnBanner) return;
    if (turnMain) turnMain.textContent = main || '';
    if (turnSub) turnSub.textContent = sub || '';
    if (turnArrowGlyph) turnArrowGlyph.textContent = glyphForInstruction(main);
    turnBanner.classList.add('active');
  }

  function hideTurnBanner() {
    if (turnBanner) turnBanner.classList.remove('active');
    updateProgressBar(0);
  }

  function computeCumDist(pts) {
    const cum = [0];
    for (let i = 1; i < pts.length; i++) {
      cum.push(cum[i - 1] + haversine({ lat: pts[i - 1][0], lon: pts[i - 1][1] }, { lat: pts[i][0], lon: pts[i][1] }));
    }
    return cum;
  }

  function parseManeuvers(rawManeuvers, pts, cumDist) {
    if (!Array.isArray(rawManeuvers) || !pts.length) return [];
    return rawManeuvers.map(m => {
      const idx = Math.min(Math.max(m.begin_shape_index || 0, 0), pts.length - 1);
      return {
        instruction: m.instruction || 'Continue',
        verbalPre: m.verbal_pre_transition_instruction || m.instruction || 'Continue',
        verbalPost: m.verbal_post_transition_instruction || m.instruction || 'Continue',
        atIndex: idx,
        atDistance: cumDist[idx] || 0,
        lat: pts[idx][0],
        lon: pts[idx][1]
      };
    });
  }

  async function getRoute(a, b) {
    if (mode.value === 'flight') {
      const distance = haversine(a, b);
      return { pts: [[a.lat, a.lon], [b.lat, b.lon]], distance, duration: distance / 800000 * 3600, maneuvers: [], cumDist: [0, distance] };
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
    const pts = decodeShape(leg.shape);
    const cumDist = computeCumDist(pts);
    const maneuvers = parseManeuvers(leg.maneuvers, pts, cumDist);
    return {
      pts,
      distance: Number((leg.summary && leg.summary.length) || 0) * 1000,
      duration: Number((leg.summary && leg.summary.time) || 0),
      maneuvers,
      cumDist
    };
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

  function announceThresholds() {
    if (mode.value === 'walking') return { announce: 50, instruct: 8 };
    if (mode.value === 'cycling') return { announce: 100, instruct: 12 };
    return { announce: 300, instruct: 15 };
  }

  function offRouteThreshold() {
    return mode.value === 'walking' ? 30 : mode.value === 'cycling' ? 40 : 60;
  }

  function projectToRoute(pos, pts, cumDist) {
    let best = { progress: 0, perp: Infinity };
    for (let i = 0; i < pts.length - 1; i++) {
      const p1 = { lat: pts[i][0], lon: pts[i][1] };
      const p2 = { lat: pts[i + 1][0], lon: pts[i + 1][1] };
      const dx = p2.lat - p1.lat, dy = p2.lon - p1.lon;
      const lenSq = dx * dx + dy * dy;
      let t = 0;
      if (lenSq > 0) {
        const wx = pos.lat - p1.lat, wy = pos.lon - p1.lon;
        t = Math.max(0, Math.min(1, (dx * wx + dy * wy) / lenSq));
      }
      const projLat = p1.lat + dx * t;
      const projLon = p1.lon + dy * t;
      const perp = haversine(pos, { lat: projLat, lon: projLon });
      if (perp < best.perp) {
        const segLen = haversine(p1, p2);
        best = { progress: cumDist[i] + segLen * t, perp };
      }
    }
    return best;
  }

  function stopLiveNav(finalStatus) {
    if (liveNav && liveNav.watchId != null && navigator.geolocation) {
      navigator.geolocation.clearWatch(liveNav.watchId);
    }
    liveNav = null;
    hideNavControls();
    hideTurnBanner();
    setBodyNavigating(false);
    setMapRotation(0);
    followMode = false;
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    if (navMarker) { map.removeLayer(navMarker); navMarker = null; }
    if (finalStatus) setStatus(finalStatus.text, finalStatus.type);
  }

  async function rerouteFrom(pos) {
    if (!liveNav) return;
    const now = Date.now();
    if (liveNav.lastRerouteAt && now - liveNav.lastRerouteAt < 8000) return;
    liveNav.lastRerouteAt = now;
    try {
      setStatus('Rerouting...', 'ok');
      speak('Recalculating route');
      const newRoute = await getRoute(pos, liveNav.destination);
      liveNav.route = newRoute;
      liveNav.maneuverIdx = 0;
      liveNav.announced = new Set();
      liveNav.offRouteStrikes = 0;
      if (routeLine) map.removeLayer(routeLine);
      routeLine = L.polyline(newRoute.pts, { color: '#d71920', weight: 6, smoothFactor: 1 }).addTo(map);
      try { localStorage.setItem('ugamap_last_route', JSON.stringify({ route: newRoute, destination: liveNav.destination, savedAt: Date.now() })); } catch (e) {}
      setStatus('Route updated', 'ok');
    } catch (e) {
      console.error('reroute failed', e);
      setStatus('Unable to reroute \u2014 continuing with last known route', 'err');
    }
  }

  function onLivePosition(position) {
    if (!liveNav || liveNav.paused) return;
    const pos = { lat: position.coords.latitude, lon: position.coords.longitude };
    const heading = Number.isFinite(position.coords.heading) ? position.coords.heading : null;
    const route = liveNav.route;
    const now = Date.now();

    // Speed: prefer GPS-reported speed, fall back to distance/time between fixes
    let speedKmh = null;
    if (Number.isFinite(position.coords.speed) && position.coords.speed >= 0) {
      speedKmh = position.coords.speed * 3.6;
    } else if (liveNav.lastPos && liveNav.lastFixTime) {
      const dtSec = (now - liveNav.lastFixTime) / 1000;
      if (dtSec > 0.5) {
        const dM = haversine(liveNav.lastPos, pos);
        speedKmh = (dM / dtSec) * 3.6;
      }
    }
    if (speedKmh != null) updateSpeedPill(speedKmh);

    if (!navMarker) {
      navMarker = L.marker([pos.lat, pos.lon], { icon: makeArrowIcon(heading || 0), zIndexOffset: 1000 }).addTo(map);
    } else {
      navMarker.setLatLng([pos.lat, pos.lon]);
    }

    const distToDest = haversine(pos, liveNav.destination);
    if (distToDest < 25) {
      speak('You have arrived at your destination');
      saveTripRecord(liveNav.destination.address, liveNav.route.distance, (now - liveNav.startTime) / 1000, mode.value);
      stopLiveNav({ text: 'Arrived at destination', type: 'ok' });
      return;
    }

    const { progress, perp } = projectToRoute(pos, route.pts, route.cumDist);
    const headingForRotation = heading != null ? heading : (liveNav.lastPos ? bearing(liveNav.lastPos, pos) : 0);
    applyFollowView(pos.lat, pos.lon, headingForRotation);

    updateProgressBar(route.distance ? (progress / route.distance) * 100 : 0);
    const remainingM = Math.max(0, route.distance - progress);
    const remainingFrac = route.distance ? remainingM / route.distance : 0;
    const remainingSec = route.duration ? remainingFrac * route.duration : null;
    window.__ugamapRemainingSeconds = remainingSec;
    updateEta(remainingSec);

    if (!route.maneuvers || !route.maneuvers.length) {
      navMarker.setIcon(makeArrowIcon(headingForRotation));
      liveNav.lastPos = pos;
      liveNav.lastFixTime = now;
      const remainingLabel = distToDest >= 1000 ? (distToDest / 1000).toFixed(1) + ' km remaining' : Math.round(distToDest) + ' m remaining';
      info.innerHTML = '<span class="routecard">' + escapeHtml(remainingLabel) + '</span>';
      return;
    }

    if (perp > offRouteThreshold()) {
      liveNav.offRouteStrikes = (liveNav.offRouteStrikes || 0) + 1;
      if (liveNav.offRouteStrikes >= 3) {
        liveNav.offRouteStrikes = 0;
        rerouteFrom(pos);
        return;
      }
    } else {
      liveNav.offRouteStrikes = 0;
    }

    while (liveNav.maneuverIdx < route.maneuvers.length - 1 &&
           route.maneuvers[liveNav.maneuverIdx].atDistance < progress - 5) {
      liveNav.maneuverIdx++;
    }
    const man = route.maneuvers[liveNav.maneuverIdx];
    const distToManeuver = Math.max(0, man.atDistance - progress);
    const { announce, instruct } = announceThresholds();

    const brg = bearing(pos, { lat: man.lat, lon: man.lon });
    navMarker.setIcon(makeArrowIcon(heading != null ? heading : brg));
    liveNav.lastPos = pos;
    liveNav.lastFixTime = now;

    const distLabel = distToManeuver >= 1000 ? (distToManeuver / 1000).toFixed(1) + ' km' : Math.round(distToManeuver) + ' m';
    showTurnBanner(man.instruction, 'In ' + distLabel);

    const instructKey = liveNav.maneuverIdx + '-instruct';
    const announceKey = liveNav.maneuverIdx + '-announce';
    if (distToManeuver <= instruct && !liveNav.announced.has(instructKey)) {
      liveNav.announced.add(instructKey);
      speak(man.verbalPost);
    } else if (distToManeuver <= announce && !liveNav.announced.has(announceKey)) {
      liveNav.announced.add(announceKey);
      speak(man.verbalPre);
    }

    const remainingLabel = remainingM >= 1000 ? (remainingM / 1000).toFixed(1) + ' km remaining' : Math.round(remainingM) + ' m remaining';
    info.innerHTML = '<span class="routecard">' + escapeHtml(remainingLabel) + '</span>';
  }

  function startNavigation(route, destination) {
    stopSimulation();
    stopLiveNav();
    setBodyNavigating(true);
    engageFollow();

    if (!navigator.geolocation) {
      setStatus('Live GPS not available \u2014 showing route preview', 'err');
      simulateNavigation(route.pts, { durationSec: route.duration, destAddress: destination.address, maneuvers: route.maneuvers });
      return;
    }

    liveNav = {
      route,
      destination,
      maneuverIdx: 0,
      announced: new Set(),
      offRouteStrikes: 0,
      paused: false,
      watchId: null,
      lastRerouteAt: 0,
      lastPos: null,
      lastFixTime: null,
      startTime: Date.now()
    };

    try { localStorage.setItem('ugamap_last_route', JSON.stringify({ route, destination, savedAt: Date.now() })); } catch (e) {}

    showNavControls();
    const pauseBtn = G('navPause');
    if (pauseBtn) pauseBtn.textContent = 'Pause';

    liveNav.watchId = navigator.geolocation.watchPosition(
      onLivePosition,
      err => {
        console.error('geolocation watch error', err);
        setStatus('Location signal lost \u2014 check GPS/permissions', 'err');
      },
      { enableHighAccuracy: true, maximumAge: 2000, timeout: 15000 }
    );

    setStatus('Navigating...', 'ok');
    if (route.maneuvers && route.maneuvers.length) {
      showTurnBanner(route.maneuvers[0].instruction, 'Starting navigation');
    }
  }

  function pauseResumeNav() {
    const btn = G('navPause');
    if (liveNav) {
      liveNav.paused = !liveNav.paused;
      if (btn) btn.textContent = liveNav.paused ? 'Resume' : 'Pause';
      setStatus(liveNav.paused ? 'Paused' : 'Navigating...', 'ok');
      if (liveNav.paused && 'speechSynthesis' in window) window.speechSynthesis.cancel();
      return;
    }
    if (!navState) return;
    if (!navState.paused) {
      navState.paused = true;
      if (navState.rafId) cancelAnimationFrame(navState.rafId);
      setStatus('Paused', 'ok');
      if (btn) btn.textContent = 'Resume';
    } else {
      navState.paused = false;
      navState.lastTime = performance.now();
      setStatus('Navigating...', 'ok');
      if (btn) btn.textContent = 'Pause';
      navState.rafId = requestAnimationFrame(navFrame);
    }
  }

  function cancelNav() {
    if (liveNav) {
      stopLiveNav({ text: 'Navigation cancelled', type: 'err' });
      return;
    }
    stopSimulation();
    hideTurnBanner();
    setBodyNavigating(false);
    if (navState && navState.realTracker) clearInterval(navState.realTracker);
    if (navMarker) { map.removeLayer(navMarker); navMarker = null; }
    setStatus('Navigation cancelled', 'err');
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
      stopLiveNav();
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
        '<span class="routecard">' + (route.distance / 1000).toFixed(1) + ' km</span>' +
        '<span class="routecard">' + escapeHtml(formatTime(route.duration)) + '</span>';
      setStatus('Route ready', 'ok');
      setTimeout(() => startNavigation(route, b), 600);
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

  const navPauseBtn = G('navPause');
  if (navPauseBtn) navPauseBtn.addEventListener('click', pauseResumeNav);
  const navCancelBtn = G('navCancel');
  if (navCancelBtn) navCancelBtn.addEventListener('click', cancelNav);
  const navRecenterBtn = G('navRecenter');
  if (navRecenterBtn) navRecenterBtn.addEventListener('click', recenterNav);
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
      G('sr').textContent = 'Current location';
      if (userMarker) map.removeLayer(userMarker);
      userMarker = L.marker([p.lat, p.lon]).addTo(map).bindPopup('You are here').openPopup();
      map.setView([p.lat, p.lon], 16);
      setStatus('Current location set as start', 'ok');
    }, error => {
      console.error(error);
      setStatus('Unable to access your location. Check browser location permission.', 'err');
      document.activeElement && document.activeElement.blur();
      const ss = G('ss'); if (ss) ss.style.display = 'none';
      const ds = G('ds'); if (ds) ds.style.display = 'none';
      const overlay = G('reportModalOverlay'); if (overlay) overlay.classList.remove('active');
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

  const REPORT_META = {
    police: { label: 'Police', icon: '\uD83D\uDE93' },
    accident: { label: 'Accident', icon: '\uD83D\uDCA5' },
    road_closure: { label: 'Road Closure', icon: '\uD83D\uDEA7' },
    bridge: { label: 'Bridge Issue', icon: '\uD83C\uDF09' },
    traffic: { label: 'Traffic', icon: '\uD83D\uDEA6' },
    weather: { label: 'Weather', icon: '\uD83C\uDF27\uFE0F' }
  };

  let reportMarkers = [];
  let pendingCategory = null;

  function makeReportIcon(category) {
    const meta = REPORT_META[category] || { icon: '\u26A0\uFE0F' };
    return L.divIcon({
      className: 'nav-arrow-icon',
      html: '<div style="font-size:22px;line-height:1;">' + meta.icon + '</div>',
      iconSize: [26, 26],
      iconAnchor: [13, 13]
    });
  }

  function timeAgo(createdAtSeconds) {
    const diff = Math.max(0, (Date.now() / 1000) - createdAtSeconds);
    const mins = Math.round(diff / 60);
    if (mins < 1) return 'just now';
    if (mins < 60) return mins + ' min ago';
    const hrs = Math.round(mins / 60);
    return hrs + ' hr ago';
  }

  function mediaHtml(rep, base) {
    if (!rep.media_url) return '';
    const url = base + rep.media_url;
    if (rep.media_type && rep.media_type.indexOf('video') === 0) {
      return '<br><video src="' + url + '" controls style="width:160px;border-radius:6px;margin-top:4px;"></video>';
    }
    return '<br><img src="' + url + '" style="width:160px;border-radius:6px;margin-top:4px;" />';
  }

  function renderReports(reports, base) {
    reportMarkers.forEach(m => map.removeLayer(m));
    reportMarkers = [];
    reports.forEach(rep => {
      const meta = REPORT_META[rep.category] || { label: rep.category, icon: '\u26A0\uFE0F' };
      const popupText = meta.label + (rep.note ? ' \u2014 ' + escapeHtml(rep.note) : '') +
        mediaHtml(rep, base) +
        '<br><span style="font-size:11px;color:#6b7280;">' + timeAgo(rep.created_at) + '</span>';
      const marker = L.marker([rep.lat, rep.lon], { icon: makeReportIcon(rep.category) })
        .addTo(map)
        .bindPopup(popupText);
      reportMarkers.push(marker);
    });
  }

  async function fetchReports() {
    let lastError = null;
    for (const base of apiCandidates()) {
      try {
        const r = await fetch(base + '/reports');
        if (!r.ok) { lastError = new Error('HTTP ' + r.status + ' from ' + base); continue; }
        const d = await r.json();
        if (Array.isArray(d.results)) {
          renderReports(d.results, base);
          return;
        }
        lastError = new Error('Unexpected response shape from ' + base);
      } catch (e) {
        lastError = e;
      }
    }
    console.error('fetchReports failed:', lastError);
  }
  function openReportModal(category) {
    pendingCategory = category;
    const overlay = G('reportModalOverlay');
    const title = G('modalTitle');
    const meta = REPORT_META[category];
    if (title) title.textContent = 'Report: ' + (meta ? meta.label : category);
    const noteEl = G('reportNote');
    const fileEl = G('reportFile');
    if (noteEl) noteEl.value = '';
    if (fileEl) fileEl.value = '';
    const modalStatus = G('modalStatus');
    if (modalStatus) modalStatus.textContent = '';
    if (overlay) overlay.classList.add('active');
  }

  function closeReportModal() {
    pendingCategory = null;
    const overlay = G('reportModalOverlay');
    if (overlay) overlay.classList.remove('active');
  }

  async function submitReportModal() {
    if (!pendingCategory) return;
    const center = map.getCenter();
    const noteEl = G('reportNote');
    const fileEl = G('reportFile');
    const modalStatus = G('modalStatus');
    const note = noteEl ? noteEl.value.trim() : '';
    const file = (fileEl && fileEl.files && fileEl.files[0]) ? fileEl.files[0] : null;

    if (file && file.size > 15 * 1024 * 1024) {
      if (modalStatus) modalStatus.textContent = 'File too large (max 15MB)';
      return;
    }

    const submitBtn = G('modalSubmit');
    if (submitBtn) submitBtn.disabled = true;
    if (modalStatus) modalStatus.textContent = 'Submitting...';

    let ok = false;
    let lastError = null;
    for (const base of apiCandidates()) {
      try {
        const formData = new FormData();
        formData.append('category', pendingCategory);
        formData.append('lat', String(center.lat));
        formData.append('lon', String(center.lng));
        formData.append('note', note);
        if (file) formData.append('file', file);
        const r = await fetch(base + '/report', { method: 'POST', body: formData });
        if (r.ok) { ok = true; break; }
        lastError = new Error('HTTP ' + r.status + ' from ' + base);
      } catch (e) {
        lastError = e;
      }
    }

    if (submitBtn) submitBtn.disabled = false;

    if (!ok) {
      console.error('submitReportModal failed:', lastError);
      if (modalStatus) modalStatus.textContent = 'Unable to submit report';
      return;
    }

    closeReportModal();
    setStatus('Report submitted', 'ok');
    fetchReports();
  }

  const reportBtn = G('reportBtn');
  const reportMenu = G('reportMenu');
  if (reportBtn && reportMenu) {
    document.querySelectorAll('.reportType').forEach(btn => {
      btn.addEventListener('click', () => {
        const category = btn.dataset.category;
        reportMenu.style.display = 'none';
        openReportModal(category);
      });
    });
  }

  const modalCancelBtn = G('modalCancel');
  if (modalCancelBtn) modalCancelBtn.addEventListener('click', closeReportModal);
  const modalSubmitBtn = G('modalSubmit');
  if (modalSubmitBtn) modalSubmitBtn.addEventListener('click', submitReportModal);
  const reportModalOverlay = G('reportModalOverlay');
  if (reportModalOverlay) reportModalOverlay.addEventListener('click', (e) => {
    if (e.target === reportModalOverlay) closeReportModal();
  });

  map.on('click', () => {
    startBox.style.display = 'none';
    destBox.style.display = 'none';
  });
  document.addEventListener('click', e => {
    if (!start.contains(e.target) && !startBox.contains(e.target)) startBox.style.display = 'none';
    if (!dest.contains(e.target) && !destBox.contains(e.target)) destBox.style.display = 'none';
  });

  // ---------------------------------------------------------------------
  // Home button: zoom the map in
  // ---------------------------------------------------------------------

  const tabHomeBtn = G('tabHome');
  if (tabHomeBtn) tabHomeBtn.addEventListener('click', () => {
    map.zoomIn();
  });

  // ---------------------------------------------------------------------
  // User accounts: signup / login / profile (menu button)
  // ---------------------------------------------------------------------

  const AUTH_TOKEN_KEY = 'ugamap_token';
  let authMode = 'login';

  function openOverlay(id) {
    const el = G(id);
    if (el) el.classList.add('active');
  }
  function closeOverlay(id) {
    const el = G(id);
    if (el) el.classList.remove('active');
  }

  function setProfileStatus(text, kind) {
    const statusEl = G('profileStatus');
    if (!statusEl) return;
    statusEl.textContent = text || '';
    statusEl.style.color = kind === 'ok' ? 'var(--success-text)' : kind === 'err' ? 'var(--err-text)' : 'var(--text-secondary)';
  }

  function setAuthMode(newMode) {
    authMode = newMode;
    const loginForm = G('loginForm');
    const signupForm = G('signupForm');
    const accountView = G('accountView');
    const authTabs = G('authTabs');
    const authActions = G('authActions');
    const accountActions = G('accountActions');
    const tabLogin = G('tabLogin');
    const tabSignup = G('tabSignup');
    const profileTitle = G('profileTitle');
    const profileSubmit = G('profileSubmit');

    if (loginForm) loginForm.style.display = newMode === 'login' ? '' : 'none';
    if (signupForm) signupForm.style.display = newMode === 'signup' ? '' : 'none';
    if (accountView) accountView.style.display = newMode === 'account' ? '' : 'none';
    if (authTabs) authTabs.style.display = newMode === 'account' ? 'none' : 'flex';
    if (authActions) authActions.style.display = newMode === 'account' ? 'none' : 'grid';
    if (accountActions) accountActions.style.display = newMode === 'account' ? 'grid' : 'none';
    if (tabLogin) tabLogin.classList.toggle('active', newMode === 'login');
    if (tabSignup) tabSignup.classList.toggle('active', newMode === 'signup');
    if (profileTitle) profileTitle.textContent = newMode === 'account' ? 'Account' : 'Welcome';
    if (profileSubmit) profileSubmit.textContent = newMode === 'signup' ? 'Sign up' : 'Log in';
    setProfileStatus('');
  }

  function fillAccountView(user) {
    if (G('accName')) G('accName').value = user.name || '';
    if (G('accEmail')) G('accEmail').value = user.email || '';
    if (G('accPhone')) G('accPhone').value = user.phone || '';
    if (G('accAddress')) G('accAddress').value = user.address || '';
  }

  async function checkSession() {
    const token = localStorage.getItem(AUTH_TOKEN_KEY);
    if (!token) {
      setAuthMode('login');
      return;
    }
    let lastError = null;
    for (const base of apiCandidates()) {
      try {
        const r = await fetch(base + '/auth/me?token=' + encodeURIComponent(token));
        if (r.status === 401 || r.status === 404) {
          localStorage.removeItem(AUTH_TOKEN_KEY);
          setAuthMode('login');
          return;
        }
        if (!r.ok) { lastError = new Error('HTTP ' + r.status); continue; }
        const d = await r.json();
        fillAccountView(d);
        setAuthMode('account');
        return;
      } catch (e) {
        lastError = e;
      }
    }
    if (lastError) console.error('checkSession failed', lastError);
    setAuthMode('login');
  }

  async function submitAuth() {
    if (authMode === 'signup') {
      const name = (G('suName').value || '').trim();
      const email = (G('suEmail').value || '').trim();
      const password = G('suPassword').value || '';
      const phone = (G('suPhone').value || '').trim();
      const address = (G('suAddress').value || '').trim();

      if (!name || !email || password.length < 6) {
        setProfileStatus('Name, email, and a 6+ character password are required', 'err');
        return;
      }

      setProfileStatus('Creating account...');
      let lastError = null;
      for (const base of apiCandidates()) {
        try {
          const r = await fetch(base + '/auth/signup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, email, password, phone, address })
          });
          const d = await r.json();
          if (!r.ok) {
            setProfileStatus(d.detail || 'Unable to create account', 'err');
            return;
          }
          localStorage.setItem(AUTH_TOKEN_KEY, d.token);
          fillAccountView(d);
          setAuthMode('account');
          return;
        } catch (e) {
          lastError = e;
        }
      }
      console.error('signup failed', lastError);
      setProfileStatus('Unable to reach the server', 'err');
      return;
    }

    const email = (G('loginEmail').value || '').trim();
    const password = G('loginPassword').value || '';
    if (!email || !password) {
      setProfileStatus('Enter your email and password', 'err');
      return;
    }

    setProfileStatus('Logging in...');
    let lastError = null;
    for (const base of apiCandidates()) {
      try {
        const r = await fetch(base + '/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password })
        });
        const d = await r.json();
        if (!r.ok) {
          setProfileStatus(d.detail || 'Invalid email or password', 'err');
          return;
        }
        localStorage.setItem(AUTH_TOKEN_KEY, d.token);
        fillAccountView(d);
        setAuthMode('account');
        return;
      } catch (e) {
        lastError = e;
      }
    }
    console.error('login failed', lastError);
    setProfileStatus('Unable to reach the server', 'err');
  }

  async function saveAccount() {
    const token = localStorage.getItem(AUTH_TOKEN_KEY);
    if (!token) { setAuthMode('login'); return; }
    const name = (G('accName').value || '').trim();
    const phone = (G('accPhone').value || '').trim();
    const address = (G('accAddress').value || '').trim();

    setProfileStatus('Saving...');
    let lastError = null;
    for (const base of apiCandidates()) {
      try {
        const r = await fetch(base + '/profile', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token, name, phone, address })
        });
        const d = await r.json();
        if (!r.ok) {
          setProfileStatus(d.detail || 'Unable to save', 'err');
          return;
        }
        fillAccountView(d);
        setProfileStatus('Saved', 'ok');
        return;
      } catch (e) {
        lastError = e;
      }
    }
    console.error('saveAccount failed', lastError);
    setProfileStatus('Unable to reach the server', 'err');
  }

  async function logoutAccount() {
    const token = localStorage.getItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(AUTH_TOKEN_KEY);
    if (token) {
      for (const base of apiCandidates()) {
        try {
          const formData = new FormData();
          formData.append('token', token);
          await fetch(base + '/auth/logout', { method: 'POST', body: formData });
          break;
        } catch (e) {
          // best effort
        }
      }
    }
    if (G('loginEmail')) G('loginEmail').value = '';
    if (G('loginPassword')) G('loginPassword').value = '';
    setAuthMode('login');
  }

  const menuBtn = G('menuBtn');
  if (menuBtn) menuBtn.addEventListener('click', () => {
    openOverlay('profileOverlay');
    checkSession();
  });
  const profileCancelBtn = G('profileCancel');
  if (profileCancelBtn) profileCancelBtn.addEventListener('click', () => closeOverlay('profileOverlay'));
  const profileOverlay = G('profileOverlay');
  if (profileOverlay) profileOverlay.addEventListener('click', e => {
    if (e.target === profileOverlay) closeOverlay('profileOverlay');
  });

  const tabLoginBtn = G('tabLogin');
  if (tabLoginBtn) tabLoginBtn.addEventListener('click', () => setAuthMode('login'));
  const tabSignupBtn = G('tabSignup');
  if (tabSignupBtn) tabSignupBtn.addEventListener('click', () => setAuthMode('signup'));
  const profileSubmitBtn = G('profileSubmit');
  if (profileSubmitBtn) profileSubmitBtn.addEventListener('click', submitAuth);
  const profileSaveBtn = G('profileSave');
  if (profileSaveBtn) profileSaveBtn.addEventListener('click', saveAccount);
  const profileLogoutBtn = G('profileLogout');
  if (profileLogoutBtn) profileLogoutBtn.addEventListener('click', logoutAccount);

  // ---------------------------------------------------------------------
  // More: weekly weather forecast by region + trending news
  // ---------------------------------------------------------------------

  const UGANDA_REGIONS = {
    'Kampala': [0.3476, 32.5825],
    'Entebbe': [0.0512, 32.4637],
    'Jinja': [0.4478, 33.2026],
    'Mbarara': [-0.6072, 30.6545],
    'Gulu': [2.7746, 32.2989],
    'Mbale': [1.0820, 34.1750],
    'Fort Portal': [0.6710, 30.2748],
    'Arua': [3.0201, 30.9111],
    'Masaka': [-0.3346, 31.7343],
    'Lira': [2.2350, 32.9096]
  };

  function weatherIcon(code) {
    if (code === 0) return '\u2600\uFE0F';
    if (code === 1 || code === 2) return '\u26C5';
    if (code === 3) return '\u2601\uFE0F';
    if (code === 45 || code === 48) return '\uD83C\uDF2B\uFE0F';
    if (code >= 51 && code <= 65) return '\uD83C\uDF27\uFE0F';
    if (code >= 80 && code <= 82) return '\uD83C\uDF26\uFE0F';
    if (code >= 95) return '\u26C8\uFE0F';
    return '\uD83C\uDF24\uFE0F';
  }

  async function fetchWeather(region) {
    const box = G('weatherForecast');
    if (!box) return;
    const coords = UGANDA_REGIONS[region];
    if (!coords) return;
    box.innerHTML = '<div style="font-size:12px;color:var(--text-secondary);">Loading forecast...</div>';
    try {
      const url = 'https://api.open-meteo.com/v1/forecast?latitude=' + coords[0] + '&longitude=' + coords[1] +
        '&daily=weathercode,temperature_2m_max,temperature_2m_min&timezone=Africa%2FKampala&forecast_days=7';
      const r = await fetch(url);
      if (!r.ok) throw new Error('Weather unavailable');
      const d = await r.json();
      const days = d.daily.time;
      box.innerHTML = '';
      days.forEach((day, i) => {
        const code = d.daily.weathercode[i];
        const hi = Math.round(d.daily.temperature_2m_max[i]);
        const lo = Math.round(d.daily.temperature_2m_min[i]);
        const label = new Date(day + 'T00:00:00').toLocaleDateString(undefined, { weekday: 'short' });
        const card = document.createElement('div');
        card.className = 'weatherCard';
        card.innerHTML = '<div class="wDay">' + escapeHtml(label) + '</div>' +
          '<div class="wIcon">' + weatherIcon(code) + '</div>' +
          '<div class="wHi">' + hi + '\u00B0</div>' +
          '<div class="wLo">' + lo + '\u00B0</div>';
        box.appendChild(card);
      });
    } catch (e) {
      console.error(e);
      box.innerHTML = '<div style="font-size:12px;color:var(--err-text);">Unable to load forecast</div>';
    }
  }

  async function fetchNews(region) {
    const list = G('newsList');
    if (!list) return;
    list.innerHTML = '<div style="font-size:12px;color:var(--text-secondary);">Loading news...</div>';
    let lastError = null;
    for (const base of apiCandidates()) {
      try {
        const r = await fetch(base + '/news?region=' + encodeURIComponent(region));
        if (!r.ok) { lastError = new Error('HTTP ' + r.status); continue; }
        const d = await r.json();
        if (!d.available) {
          list.innerHTML = '<div style="font-size:12px;color:var(--text-secondary);">' + escapeHtml(d.message || 'News feed not available') + '</div>';
          return;
        }
        if (!d.articles || !d.articles.length) {
          list.innerHTML = '<div style="font-size:12px;color:var(--text-secondary);">No trending stories right now</div>';
          return;
        }
        list.innerHTML = '';
        d.articles.forEach(a => {
          const item = document.createElement('a');
          item.href = a.url;
          item.target = '_blank';
          item.rel = 'noopener';
          item.className = 'newsItem';
          item.innerHTML = '<div class="newsTitle">' + escapeHtml(a.title) + '</div>' +
            '<div class="newsSource">' + escapeHtml(a.source || '') + '</div>';
          list.appendChild(item);
        });
        return;
      } catch (e) {
        lastError = e;
      }
    }
    console.error('fetchNews failed', lastError);
    list.innerHTML = '<div style="font-size:12px;color:var(--err-text);">Unable to load news</div>';
  }

  const weatherRegionSelect = G('weatherRegion');
  if (weatherRegionSelect) weatherRegionSelect.addEventListener('change', () => {
    fetchWeather(weatherRegionSelect.value);
    fetchNews(weatherRegionSelect.value);
  });

  const tabMoreBtn = G('tabMore');
  if (tabMoreBtn) tabMoreBtn.addEventListener('click', () => {
    openOverlay('moreOverlay');
    const region = weatherRegionSelect ? weatherRegionSelect.value : 'Kampala';
    fetchWeather(region);
    fetchNews(region);
  });
  const moreCloseBtn = G('moreClose');
  if (moreCloseBtn) moreCloseBtn.addEventListener('click', () => closeOverlay('moreOverlay'));
  const moreOverlay = G('moreOverlay');
  if (moreOverlay) moreOverlay.addEventListener('click', e => {
    if (e.target === moreOverlay) closeOverlay('moreOverlay');
  });

  // Expose a small hook so the inline bottom-nav script in index.html can
  // open the trip history overlay from the "Saved" tab.
  window.UGAMAP = window.UGAMAP || {};
  window.UGAMAP.openTrips = openTrips;

  fetchReports();
  setInterval(fetchReports, 30000);

  setTimeout(() => map.invalidateSize(), 300);
  setStatus('\uD83C\uDDFA\uD83C\uDDEC Uganda National Grid ready', 'ok');
});
