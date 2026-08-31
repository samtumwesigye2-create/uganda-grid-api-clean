(() => {
  const POLL_MS = 5000;
  const STORAGE_KEY = 'ugamap_admin_seen_report_ids_v1';
  let initialized = false;
  let seen = new Set();

  try { seen = new Set(JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')); } catch (_) {}

  function saveSeen() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(Array.from(seen).slice(-500))); } catch (_) {}
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
      const newest = fresh[fresh.length - 1];
      notify(newest, fresh.length);
      if (typeof window.loadReports === 'function') window.loadReports();
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
