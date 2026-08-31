(() => {
  const POLL_MS = 5000;
  const STORAGE_KEY = 'ugamap_admin_seen_report_ids_v1';
  let initialized = false;
  let seen = new Set();

  try { seen = new Set(JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')); } catch (_) {}

  function saveSeen() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(Array.from(seen).slice(-500))); } catch (_) {}
  }

  function esc(v) {
    return String(v == null ? '' : v).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  function reportsTab() { return document.querySelector('.tab[data-tab="reports"]'); }

  function ensureBadge() {
    const tab = reportsTab();
    if (!tab) return null;
    let badge = tab.querySelector('.reportNotifyBadge');
    if (!badge) {
      badge = document.createElement('span');
      badge.className = 'reportNotifyBadge';
      badge.style.cssText = 'float:right;min-width:20px;padding:2px 6px;border-radius:999px;background:#e2593a;color:#fff;font-size:10px;font-weight:800;text-align:center;display:none';
      tab.appendChild(badge);
      tab.addEventListener('click', () => { badge.style.display = 'none'; badge.textContent = ''; });
    }
    return badge;
  }

  function notify(report, count) {
    const category = String(report.category || 'report').replace(/_/g, ' ');
    const note = String(report.note || '').trim();
    const message = `New ${category} report${note ? ': ' + note : ''}`;
    if (typeof window.showNotifyToast === 'function') window.showNotifyToast(message, false);
    else alert(message);
    const badge = ensureBadge();
    if (badge) { badge.textContent = String(count); badge.style.display = 'inline-block'; }
    if ('Notification' in window && Notification.permission === 'granted') {
      try { new Notification('UGAMAP — New Report', { body: message }); } catch (_) {}
    }
  }

  function mediaCell(r) {
    if (!r.media_url) return '<span style="color:#70768d">—</span>';
    const url = esc(r.media_url);
    if (String(r.media_type || '').startsWith('video/')) {
      return `<video src="${url}" controls playsinline style="width:110px;max-height:90px;border-radius:8px;background:#000"></video>`;
    }
    return `<a href="${url}" target="_blank" rel="noopener"><img src="${url}" alt="Report photo" style="width:90px;height:70px;object-fit:cover;border-radius:8px;border:1px solid #2a3a50"></a>`;
  }

  function mapLink(r) {
    const lat = Number(r.lat), lon = Number(r.lon);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return '—';
    return `<a class="viewLink" target="_blank" rel="noopener" href="/?report_lat=${encodeURIComponent(lat)}&report_lon=${encodeURIComponent(lon)}">View on Map</a>`;
  }

  function renderAdminReports(rows) {
    const out = document.getElementById('reportsOut');
    if (!out) return;
    if (!rows.length) { out.innerHTML = '<div class="empty">No reports yet.</div>'; return; }
    out.innerHTML = `<div style="overflow-x:auto"><table><thead><tr><th>Category</th><th>Note</th><th>Media</th><th>Location</th><th>Time</th><th>Status</th><th>Map</th></tr></thead><tbody>${rows.slice().sort((a,b)=>Number(b.created_at||0)-Number(a.created_at||0)).map(r => {
      const lat=Number(r.lat), lon=Number(r.lon);
      const location=Number.isFinite(lat)&&Number.isFinite(lon)?`${lat.toFixed(4)}, ${lon.toFixed(4)}`:'—';
      const when=r.created_at?new Date(Number(r.created_at)*1000).toLocaleString():'—';
      const status=esc(String(r.status||'new').toUpperCase());
      return `<tr><td>${esc(String(r.category||'').replace(/_/g,' '))}</td><td>${esc(r.note||'')}</td><td>${mediaCell(r)}</td><td>${location}</td><td>${esc(when)}</td><td><span class="badge pending">${status}</span></td><td>${mapLink(r)}</td></tr>`;
    }).join('')}</tbody></table></div>`;
  }

  window.loadReports = async function loadReportsEnhanced() {
    const out = document.getElementById('reportsOut');
    try {
      const res = await fetch('/core/reports', { cache:'no-store' });
      if (!res.ok) throw new Error('HTTP '+res.status);
      const data = await res.json();
      renderAdminReports(Array.isArray(data.results) ? data.results : []);
    } catch (e) {
      if (out) out.innerHTML = '<div class="empty">Error loading reports.</div>';
    }
  };

  async function poll() {
    try {
      const res = await fetch('/core/reports', { cache: 'no-store' });
      if (!res.ok) return;
      const data = await res.json();
      const rows = Array.isArray(data.results) ? data.results : [];
      if (!initialized) {
        rows.forEach(r => r.id && seen.add(r.id));
        saveSeen(); initialized = true; return;
      }
      const fresh = rows.filter(r => r.id && !seen.has(r.id));
      if (!fresh.length) return;
      fresh.forEach(r => seen.add(r.id)); saveSeen();
      notify(fresh[fresh.length - 1], fresh.length);
      window.loadReports();
    } catch (_) {}
  }

  document.addEventListener('DOMContentLoaded', () => {
    ensureBadge();
    if ('Notification' in window && Notification.permission === 'default') {
      document.addEventListener('click', () => Notification.requestPermission().catch(() => {}), { once: true });
    }
    poll(); setInterval(poll, POLL_MS);
  });
})();
