from pathlib import Path
import re

path = Path('admin.html')
text = path.read_text(encoding='utf-8')

# Dashboard-first navigation.
text = text.replace('<div class="tab active" data-tab="submissions">Submissions</div>', '<div class="tab" data-tab="submissions">Submissions</div>')
text = text.replace('<div class="tab" data-tab="dashboard">Dashboard</div>', '<div class="tab active" data-tab="dashboard">Dashboard</div>')
text = text.replace('<div class="panel active" id="panel-submissions">', '<div class="panel" id="panel-submissions">')
text = text.replace('<div class="panel" id="panel-dashboard">', '<div class="panel active" id="panel-dashboard">')
text = text.replace('  loadSubmissions();\n}', '  loadDashboard();\n}', 1)

# Remove the old always-visible document section. It will live inside Dashboard.
text = re.sub(r'\n  <section class="doc-launch-section">.*?</section>\n\n  <div class="panel" id="panel-submissions">', '\n\n  <div class="panel" id="panel-submissions">', text, count=1, flags=re.S)

# Add dashboard/operations CSS once.
css_marker = '  @media (max-width:650px) { .doc-launch-grid { flex-wrap:wrap; } .doc-launch-card { flex:0 0 auto; } }\n'
extra_css = '''
  .admin-section { background:#151829; border:1px solid #2a2d3e; border-radius:10px; padding:12px; margin-bottom:12px; }
  .admin-section-title { color:#8fa3ff; font-size:11px; font-weight:800; letter-spacing:.06em; margin-bottom:9px; }
  .welcome-line { font-size:18px; font-weight:800; margin-bottom:2px; }
  .welcome-sub { color:#8e93a8; font-size:12px; margin-bottom:12px; }
  .quick-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; }
  .quick-btn { border:1px solid #30364e; background:#1a1d2e; color:#eee; border-radius:8px; padding:11px 8px; min-height:66px; cursor:pointer; text-align:center; font-size:12px; }
  .quick-btn .qicon { display:block; font-size:20px; color:#6580ff; margin-bottom:5px; }
  .ops-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:8px; }
  .op-tile { background:#101421; border:1px solid #292f43; border-radius:8px; padding:10px; }
  .op-tile .op-label { color:#8e93a8; font-size:10px; }
  .op-tile .op-value { font-size:19px; font-weight:800; margin-top:3px; }
  .activity-row { display:flex; gap:9px; align-items:flex-start; padding:9px 0; border-bottom:1px solid #252a3b; }
  .activity-row:last-child { border-bottom:0; }
  .activity-icon { width:28px; height:28px; border-radius:50%; background:#252f68; color:#9fb0ff; display:flex; align-items:center; justify-content:center; flex:0 0 auto; }
  .activity-main { flex:1; min-width:0; }
  .activity-text { font-size:12px; color:#ddd; }
  .activity-time { color:#70768d; font-size:10px; margin-top:2px; }
  .dashboard-actions { display:flex; justify-content:space-between; align-items:center; gap:8px; margin-bottom:10px; }
  .last-updated { color:#747b91; font-size:10px; }
  @media(max-width:650px){
    .quick-grid { grid-template-columns:repeat(3,1fr); }
    .ops-grid { grid-template-columns:repeat(2,1fr); }
    .quick-btn { min-height:60px; padding:9px 5px; font-size:11px; }
  }
'''
if '.quick-grid {' not in text and css_marker in text:
    text = text.replace(css_marker, css_marker + extra_css, 1)

# Replace Dashboard panel with the reorganized operational dashboard.
new_dashboard = '''  <div class="panel active" id="panel-dashboard">
    <div class="dashboard-actions">
      <div>
        <div class="welcome-line">Operations Dashboard</div>
        <div class="welcome-sub">Uganda National Grid administration and logistics overview</div>
      </div>
      <button class="refreshBtn" onclick="loadDashboard()">Refresh</button>
    </div>

    <div id="dashboardStats" class="dashboard-grid"></div>

    <section class="doc-launch-section">
      <div class="doc-launch-title">BUSINESS DOCUMENTS</div>
      <div class="doc-launch-grid">
        <a class="doc-launch-card invoice" href="/business-documents/invoice.html"><span class="doc-icon">▣</span><strong>Invoice</strong></a>
        <a class="doc-launch-card bol" href="/business-documents/bill-of-lading.html"><span class="doc-icon">▤</span><strong>Bill of Lading</strong></a>
        <a class="doc-launch-card receipt" href="/business-documents/receipt.html"><span class="doc-icon">▧</span><strong>Receipt</strong></a>
      </div>
    </section>

    <section class="admin-section">
      <div class="admin-section-title">QUICK ACTIONS</div>
      <div class="quick-grid">
        <button class="quick-btn" onclick="window.location.href='/submit'"><span class="qicon">＋</span>New Submission</button>
        <button class="quick-btn" onclick="switchAdminTab('shipments')"><span class="qicon">⌖</span>Track Shipment</button>
        <button class="quick-btn" onclick="switchAdminTab('inventory')"><span class="qicon">◇</span>Add Inventory</button>
        <button class="quick-btn" onclick="window.location.href='/business-documents/invoice.html'"><span class="qicon">＄</span>Create Invoice</button>
        <button class="quick-btn" onclick="window.location.href='/business-documents/bill-of-lading.html'"><span class="qicon">▤</span>Create B/L</button>
        <button class="quick-btn" onclick="switchAdminTab('staff')"><span class="qicon">●</span>Add Staff</button>
      </div>
    </section>

    <section class="admin-section">
      <div class="admin-section-title">OPERATIONAL OVERVIEW</div>
      <div id="operationalOverview" class="ops-grid"></div>
    </section>

    <section class="admin-section">
      <div class="admin-section-title">RECENT ACTIVITY</div>
      <div id="recentActivity"></div>
    </section>

    <section class="admin-section">
      <div class="admin-section-title">STOCK BY WAREHOUSE</div>
      <div id="dashboardWarehouseOut"></div>
    </section>

    <section class="admin-section">
      <div class="admin-section-title">LOW STOCK ITEMS</div>
      <div id="dashboardLowStockOut"></div>
    </section>
    <div class="last-updated" id="dashboardLastUpdated"></div>
  </div>'''
text = re.sub(r'  <div class="panel active" id="panel-dashboard">.*?\n  </div>\n\n  <div class="panel" id="panel-orders">', new_dashboard + '\n\n  <div class="panel" id="panel-orders">', text, count=1, flags=re.S)

# Add a reusable tab switcher for quick actions.
helper_marker = "document.querySelectorAll('.subtab').forEach(sub => {"
helper = '''function switchAdminTab(name) {
  const tab = document.querySelector('.tab[data-tab="' + name + '"]');
  if (tab) tab.click();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

'''
if 'function switchAdminTab(name)' not in text and helper_marker in text:
    text = text.replace(helper_marker, helper + helper_marker, 1)

# Replace the dashboard loader with a live operational view using existing APIs.
new_loader = r'''async function loadDashboard() {
  const statsBox = document.getElementById('dashboardStats');
  const whOut = document.getElementById('dashboardWarehouseOut');
  const lowOut = document.getElementById('dashboardLowStockOut');
  const opsOut = document.getElementById('operationalOverview');
  const activityOut = document.getElementById('recentActivity');
  statsBox.innerHTML = '<div class="empty">Loading…</div>';
  try {
    const [productsData, warehousesData, movementsData, reorderData, shipData, invData, subData] = await Promise.all([
      authedFetch('/inventory/products'),
      authedFetch('/inventory/warehouses'),
      authedFetch('/inventory/movements'),
      authedFetch('/inventory/reorder'),
      authedFetch('/ship/list'),
      authedFetch('/invoices'),
      authedFetch('/submissions'),
    ]);

    const products = productsData.results || [];
    const warehouses = warehousesData.results || [];
    const movements = movementsData.results || [];
    const reorder = reorderData.results || [];
    const shipments = shipData.results || [];
    const invoices = invData.results || [];
    const submissions = subData.results || [];

    const activeShipments = shipments.filter(s => !['delivered','cancelled','returned'].includes(s.delivery_status || 'created')).length;
    const pendingSubmissions = submissions.filter(s => (s.status || 'pending') === 'pending').length;
    const unpaidInvoices = invoices.filter(i => !['paid','void'].includes(i.status || 'unpaid')).length;
    const totalUnits = products.reduce((sum,p) => sum + Number(p.total_quantity_on_hand || 0), 0);

    statsBox.innerHTML = `
      <div class="stat-tile"><div class="stat-value">${submissions.length}</div><div class="stat-label">Submissions</div></div>
      <div class="stat-tile"><div class="stat-value">${activeShipments}</div><div class="stat-label">Active Shipments</div></div>
      <div class="stat-tile"><div class="stat-value">${totalUnits.toLocaleString()}</div><div class="stat-label">Units On Hand</div></div>
      <div class="stat-tile${pendingSubmissions + unpaidInvoices ? ' warn' : ''}"><div class="stat-value">${pendingSubmissions + unpaidInvoices}</div><div class="stat-label">Pending Items</div></div>
    `;

    const statusCount = status => shipments.filter(s => (s.delivery_status || 'created') === status).length;
    const inTransit = statusCount('in_transit') + statusCount('out_for_delivery') + statusCount('picked_up');
    const delivered = statusCount('delivered');
    const pending = statusCount('created') + statusCount('delayed');
    const cancelled = statusCount('cancelled') + statusCount('returned') + statusCount('failed_delivery');
    opsOut.innerHTML = `
      <div class="op-tile"><div class="op-label">IN TRANSIT</div><div class="op-value">${inTransit}</div></div>
      <div class="op-tile"><div class="op-label">DELIVERED</div><div class="op-value">${delivered}</div></div>
      <div class="op-tile"><div class="op-label">PENDING</div><div class="op-value">${pending}</div></div>
      <div class="op-tile"><div class="op-label">CANCELLED / FAILED</div><div class="op-value">${cancelled}</div></div>
    `;

    const stockByWarehouse = {};
    movements.forEach(m => {
      const wid = m.warehouse_id || 'main';
      const qty = Number(m.quantity || 0);
      const delta = m.movement_type === 'dispatch' ? -qty : qty;
      stockByWarehouse[wid] = (stockByWarehouse[wid] || 0) + delta;
    });
    const whRows = warehouses.map(w => ({name:w.name, units:Math.max(0, stockByWarehouse[w.id] || 0)}));
    if (whRows.length) {
      const maxUnits = Math.max(1, ...whRows.map(r => r.units));
      whOut.innerHTML = whRows.map(r => `<div class="barRow"><div class="barLabel">${r.name}</div><div class="barTrack"><div class="barFill" style="width:${(r.units/maxUnits*100).toFixed(0)}%"></div></div><div class="barValue">${r.units.toLocaleString()}</div></div>`).join('');
    } else whOut.innerHTML = '<div class="empty">No warehouses yet.</div>';

    if (reorder.length) {
      renderTable(lowOut, reorder, [
        { label:'SKU', key:'sku' }, { label:'Name', key:'name' },
        { label:'On Hand', key:'quantity_on_hand' }, { label:'Reorder Point', key:'reorder_point' }
      ]);
    } else lowOut.innerHTML = '<div class="empty">Nothing below reorder point.</div>';

    const activity = [];
    shipments.forEach(s => activity.push({t:Number(s.updated_at || s.created_at || 0), icon:'↗', text:`Shipment ${s.shipment_number || ''} — ${(s.delivery_status || 'created').replace(/_/g,' ')}`}));
    submissions.forEach(s => activity.push({t:Number(s.created_at || 0), icon:'＋', text:`Submission — ${s.building_type || 'building'} (${s.status || 'pending'})`}));
    invoices.forEach(i => activity.push({t:Number(i.created_at || 0), icon:'＄', text:`Invoice ${i.invoice_number || ''} — ${i.status || 'unpaid'}`}));
    movements.forEach(m => activity.push({t:Number(m.created_at || 0), icon:'◇', text:`Inventory ${m.movement_type || 'movement'} — ${m.product_sku || ''}`}));
    activity.sort((a,b) => b.t-a.t);
    const recent = activity.filter(a => a.t > 0).slice(0,5);
    activityOut.innerHTML = recent.length ? recent.map(a => `<div class="activity-row"><div class="activity-icon">${a.icon}</div><div class="activity-main"><div class="activity-text">${a.text}</div><div class="activity-time">${new Date(a.t*1000).toLocaleString()}</div></div></div>`).join('') : '<div class="empty">No recent activity yet.</div>';
    document.getElementById('dashboardLastUpdated').textContent = 'Last updated: ' + new Date().toLocaleTimeString();
  } catch (e) {
    statsBox.innerHTML = '<div class="empty">Error loading dashboard.</div>';
    if (opsOut) opsOut.innerHTML = '<div class="empty">Operational data unavailable.</div>';
    if (activityOut) activityOut.innerHTML = '<div class="empty">Recent activity unavailable.</div>';
  }
}
'''
text = re.sub(r'async function loadDashboard\(\) \{.*?\n\}\n\n// ---- Orders ----', new_loader + '\n// ---- Orders ----', text, count=1, flags=re.S)

path.write_text(text, encoding='utf-8')
