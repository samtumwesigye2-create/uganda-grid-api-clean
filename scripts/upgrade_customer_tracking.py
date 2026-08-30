from pathlib import Path
p=Path('ship.html')
s=p.read_text(encoding='utf-8')

css='''
  /* ---- Live customer tracking ---- */
  .liveTrackCard { display:none; margin-top:12px; background:#0d1324; border:1px solid #3a4260; border-radius:12px; padding:16px; }
  .liveTrackCard.show { display:block; }
  .liveTrackTop { display:flex; justify-content:space-between; gap:12px; align-items:flex-start; margin-bottom:14px; }
  .liveTrackNumber { font-size:13px; color:#9fb0ff; font-weight:800; }
  .liveTrackStatus { display:inline-block; padding:6px 10px; border-radius:999px; background:#173b2a; color:#82f0ae; font-size:12px; font-weight:800; }
  .liveTrackRoute { display:grid; grid-template-columns:1fr auto 1fr; gap:10px; align-items:center; padding:12px 0; border-top:1px solid #27304a; border-bottom:1px solid #27304a; }
  .liveTrackRoute small { display:block; color:#7f8aa6; margin-bottom:3px; }
  .liveTrackRoute b { color:#fff; font-size:13px; overflow-wrap:anywhere; }
  .routeArrow { color:#7382aa; }
  .statusTimeline { margin-top:14px; }
  .timelineItem { position:relative; padding:0 0 14px 25px; color:#b8bfd0; font-size:12px; }
  .timelineItem:before { content:''; position:absolute; left:5px; top:4px; width:9px; height:9px; border-radius:50%; background:#3b5bfd; box-shadow:0 0 0 3px #1b2850; }
  .timelineItem:not(:last-child):after { content:''; position:absolute; left:9px; top:16px; bottom:0; width:1px; background:#33405e; }
  .timelineItem b { display:block; color:#fff; font-size:13px; margin-bottom:2px; }
  .timelineItem .time { color:#78849f; font-size:11px; }
  .trackingError { color:#ffabab; font-size:13px; }
  .trackingLoading { color:#b8bfd0; font-size:13px; }
'''
if '/* ---- Live customer tracking ---- */' not in s:
    s=s.replace('</style>',css+'\n</style>',1)

hero='''    <div class="heroTrackBar">
      <input id="heroTrackingNumber" autocomplete="off" placeholder="Enter tracking number e.g. UG-SHIP-000001" />
      <button class="trackHeroBtn" type="button" id="heroTrackBtn">Track</button>
      <button class="quoteHeroBtn" type="button" id="heroQuoteBtn">Get a Quote</button>
    </div>'''
hero_new=hero+'''\n    <div class="liveTrackCard" id="heroTrackResult" aria-live="polite"></div>'''
if 'id="heroTrackResult"' not in s:
    s=s.replace(hero,hero_new,1)

old='''async function trackShipment() {
  const number = document.getElementById('trackNumber').value.trim();
  const box = document.getElementById('trackResult');
  if (!number) {
    box.innerHTML = '<div class="msg error">Please enter a shipment number.</div>';
    return;
  }
  window.location.href = `/ship/receipt/${encodeURIComponent(number)}`;
}'''
new='''function statusLabel(value) {
  return String(value || 'created').replace(/_/g, ' ').replace(/\\b\\w/g, c => c.toUpperCase());
}

function trackingMarkup(data) {
  const history = Array.isArray(data.history) ? data.history : [];
  const timeline = history.length ? history.map(h => `
    <div class="timelineItem">
      <b>${statusLabel(h.status)}</b>
      ${h.note ? `<div>${h.note}</div>` : ''}
      <div class="time">${h.at || ''}</div>
    </div>`).join('') : '<div class="timelineItem"><b>Shipment created</b></div>';
  return `
    <div class="liveTrackTop">
      <div><div class="liveTrackNumber">${data.shipment_number}</div><div style="color:#fff;font-size:17px;font-weight:800;margin-top:3px">Shipment Status</div></div>
      <span class="liveTrackStatus">${statusLabel(data.current_status)}</span>
    </div>
    <div class="liveTrackRoute">
      <div><small>FROM</small><b>${data.pickup || 'Origin'}</b></div>
      <div class="routeArrow">→</div>
      <div style="text-align:right"><small>TO</small><b>${data.delivery || 'Destination'}</b></div>
    </div>
    <div class="statusTimeline">${timeline}</div>`;
}

async function loadTracking(number, box) {
  number = String(number || '').trim().toUpperCase();
  if (!number) {
    box.classList && box.classList.add('show');
    box.innerHTML = '<div class="trackingError">Please enter a shipment number.</div>';
    return;
  }
  box.classList && box.classList.add('show');
  box.innerHTML = '<div class="trackingLoading">Checking shipment status…</div>';
  try {
    const res = await fetch(`/ship/${encodeURIComponent(number)}/track`, {cache:'no-store'});
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      box.innerHTML = `<div class="trackingError">${data.detail || 'Shipment not found. Check the tracking number and try again.'}</div>`;
      return;
    }
    box.innerHTML = trackingMarkup(data);
  } catch (e) {
    box.innerHTML = '<div class="trackingError">Tracking is temporarily unavailable. Please try again.</div>';
  }
}

async function trackShipment() {
  const number = document.getElementById('trackNumber').value.trim();
  const box = document.getElementById('trackResult');
  await loadTracking(number, box);
}
'''
if old in s:
    s=s.replace(old,new,1)
else:
    print('old trackShipment block not found')

# Replace hero handler if it currently redirects to receipt, otherwise add a capturing handler.
marker='''// Live hero tracking upgrade'''
if marker not in s:
    s=s.replace('</script>',f'''\n{marker}\nconst heroTrackInputLive = document.getElementById('heroTrackingNumber');
const heroTrackButtonLive = document.getElementById('heroTrackBtn');
const heroTrackResultLive = document.getElementById('heroTrackResult');
if (heroTrackButtonLive && heroTrackResultLive) {{
  heroTrackButtonLive.addEventListener('click', function(e) {{
    e.preventDefault(); e.stopImmediatePropagation();
    loadTracking(heroTrackInputLive.value, heroTrackResultLive);
  }}, true);
  heroTrackInputLive.addEventListener('keydown', function(e) {{
    if (e.key === 'Enter') {{ e.preventDefault(); loadTracking(heroTrackInputLive.value, heroTrackResultLive); }}
  }});
}}
</script>''',1)

p.write_text(s,encoding='utf-8')
