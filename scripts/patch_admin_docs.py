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

# Compact document button base styling if an earlier patch left the large version behind.
text = re.sub(
    r'  \.doc-launch-section \{.*?@media \(max-width:650px\) \{ \.doc-launch-grid .*?\}\n',
    '''  .doc-launch-section { margin:0 0 14px; padding:14px 16px; background:#101827; border:1px solid #233149; border-radius:11px; }\n  .doc-launch-title { font-size:12px; font-weight:800; letter-spacing:.05em; color:#5680ff; margin-bottom:10px; }\n  .doc-launch-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:14px; }\n  .doc-launch-card { display:flex; align-items:center; gap:10px; text-decoration:none; color:#fff; border-radius:8px; padding:12px 14px; min-height:56px; border:1px solid rgba(255,255,255,.12); }\n  .doc-launch-card.invoice { background:linear-gradient(135deg,#073c30,#075f43); border-color:#078458; }\n  .doc-launch-card.bol { background:linear-gradient(135deg,#102a55,#173d79); border-color:#2c5aaa; }\n  .doc-launch-card.receipt { background:linear-gradient(135deg,#2c1747,#4b216f); border-color:#693598; }\n  .doc-launch-card .doc-icon { font-size:21px; display:inline; margin:0; }\n  .doc-launch-card strong { display:inline; font-size:13px; margin:0; }\n  .doc-launch-card small, .doc-launch-card .doc-action { display:none; }\n  @media (max-width:650px) { .doc-launch-grid { grid-template-columns:1fr; gap:7px; } }\n''',
    text,
    count=1,
    flags=re.S
)

# Add operational dashboard CSS if needed.
css_anchor = '</style>'
layout_css = r'''
  /* --- Operations dashboard layout --- */
  body { background:#07111e; padding:0; min-height:100vh; }
  #main {
    max-width:1600px;
    margin:0 auto;
    padding:18px;
    grid-template-columns:220px minmax(0,1fr);
    grid-template-rows:auto minmax(0,1fr);
    gap:18px;
  }
  #main.admin-ready { display:grid !important; }
  .adminHeader {
    grid-column:1 / -1;
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:16px;
    padding:0 4px 12px;
    border-bottom:1px solid #1b2b40;
  }
  .adminBrand h1 { text-align:left; font-size:24px; margin:0 0 3px; color:#f5f7fb; }
  .adminBrand p { margin:0; color:#77879c; font-size:12px; }
  .adminProfile { display:flex; align-items:center; gap:10px; color:#e9edf4; }
  .adminAvatar { width:38px; height:38px; display:flex; align-items:center; justify-content:center; border-radius:50%; background:#263eb2; font-weight:800; }
  .adminRole { color:#7d8ba0; font-size:10px; margin-top:2px; }

  .tabs {
    grid-column:1;
    grid-row:2;
    display:flex;
    flex-direction:column;
    align-self:start;
    position:sticky;
    top:16px;
    gap:5px;
    padding:8px;
    margin:0;
    background:#0b1624;
    border:1px solid #1d2b3d;
    border-radius:10px;
  }
  .tab {
    width:100%;
    text-align:left;
    padding:11px 12px;
    border:0;
    border-radius:7px;
    background:transparent;
    color:#d6dce5;
    font-size:13px;
  }
  .tab:hover { background:#121f30; }
  .tab.active { background:linear-gradient(135deg,#3155ed,#4268ff); color:#fff; border:0; }

  .panel { grid-column:2; grid-row:2; min-width:0; }
  #panel-dashboard { background:transparent; }
  .dashboard-actions { background:#0d1826; border:1px solid #1d2b3d; border-radius:10px; padding:18px; margin-bottom:12px; }
  .welcome-line { font-size:21px; }
  .welcome-sub { font-size:12px; margin-bottom:0; }
  .dashboard-grid { grid-template-columns:repeat(4,minmax(0,1fr)); gap:14px; margin:12px 0 0; }
  .stat-tile { min-height:116px; text-align:left; padding:15px; border-radius:8px; border:1px solid #24436a; background:linear-gradient(135deg,#102344,#10213a); }
  .stat-tile:nth-child(2) { border-color:#176246; background:linear-gradient(135deg,#10382f,#0c2c28); }
  .stat-tile:nth-child(3) { border-color:#563a79; background:linear-gradient(135deg,#35224f,#2d1c43); }
  .stat-tile:nth-child(4) { border-color:#745518; background:linear-gradient(135deg,#40351c,#332a16); }
  .stat-tile .stat-value { font-size:28px; margin-top:16px; }
  .stat-tile .stat-label { font-size:12px; color:#d4dae5; }
  .stat-tile.warn .stat-value { color:#ffd05a; }

  .admin-section, .doc-launch-section { background:#0d1826; border:1px solid #1d2b3d; border-radius:10px; padding:15px 16px; margin-bottom:12px; }
  .admin-section-title, .doc-launch-title { color:#5680ff; font-size:12px; font-weight:800; letter-spacing:.04em; margin-bottom:11px; }
  .quick-grid { grid-template-columns:repeat(6,minmax(0,1fr)); gap:10px; }
  .quick-btn { min-height:84px; background:#101b2a; border:1px solid #28364a; border-radius:7px; color:#edf2fa; transition:.15s ease; }
  .quick-btn:hover { transform:translateY(-1px); border-color:#466bff; }
  .quick-btn .qicon { font-size:25px; color:#4f72ff; }
  .ops-grid { grid-template-columns:repeat(4,minmax(0,1fr)); gap:0; }
  .op-tile { border-radius:0; border:0; border-right:1px solid #243247; background:transparent; padding:8px 20px; }
  .op-tile:first-child { padding-left:8px; }
  .op-tile:last-child { border-right:0; }
  .op-tile .op-label { font-size:10px; }
  .op-tile .op-value { font-size:24px; }
  .activity-row { padding:10px 4px; }
  .activity-time { margin-left:auto; }
  .last-updated { text-align:right; padding:4px 2px 12px; }
  .barTrack { background:#07101c !important; }

  @media(max-width:1000px) {
    #main { grid-template-columns:1fr; grid-template-rows:auto auto 1fr; padding:12px; }
    .adminHeader { grid-column:1; }
    .tabs { grid-column:1; grid-row:2; position:static; flex-direction:row; flex-wrap:wrap; justify-content:flex-start; padding:7px; }
    .tab { width:auto; flex:0 0 auto; }
    .panel { grid-column:1; grid-row:3; }
    .dashboard-grid { grid-template-columns:repeat(2,1fr); }
    .quick-grid { grid-template-columns:repeat(3,1fr); }
  }
  @media(max-width:600px) {
    #main { padding:8px; gap:9px; }
    .adminHeader { padding:6px 4px 9px; }
    .adminBrand h1 { font-size:19px; }
    .adminBrand p, .adminProfile .profileText { display:none; }
    .tabs { gap:4px; overflow-x:auto; flex-wrap:nowrap; -webkit-overflow-scrolling:touch; }
    .tab { white-space:nowrap; padding:9px 11px; font-size:12px; }
    .dashboard-actions { padding:13px; }
    .dashboard-grid { grid-template-columns:repeat(2,1fr); gap:7px; }
    .stat-tile { min-height:94px; padding:11px; }
    .stat-tile .stat-value { font-size:22px; margin-top:10px; }
    .quick-grid { grid-template-columns:repeat(3,1fr); gap:6px; }
    .quick-btn { min-height:70px; padding:7px 4px; font-size:10px; }
    .ops-grid { grid-template-columns:repeat(2,1fr); gap:6px; }
    .op-tile { border:1px solid #243247; border-radius:7px; padding:9px; }
    .doc-launch-section, .admin-section { padding:11px; }
  }
'''
if '/* --- Operations dashboard layout --- */' not in text:
    text = text.replace(css_anchor, layout_css + '\n</style>', 1)

# Replace the plain title with a proper dashboard header.
plain_header = '  <h1>Uganda National Grid Admin</h1>\n  <div class="tabs">'
rich_header = '''  <header class="adminHeader">
    <div class="adminBrand">
      <h1>Uganda National Grid Admin</h1>
      <p>Manage operations, shipments and documents</p>
    </div>
    <div class="adminProfile">
      <div class="adminAvatar">AD</div>
      <div class="profileText"><strong>Admin</strong><div class="adminRole">Super Administrator</div></div>
    </div>
  </header>
  <div class="tabs">'''
if plain_header in text:
    text = text.replace(plain_header, rich_header, 1)

# Add simple icons to existing navigation labels without changing data-tab behavior.
nav_labels = {
    'dashboard': '⌂ Dashboard', 'submissions': '▤ Submissions', 'orders': '🛒 Orders',
    'analytics': '▥ Analytics', 'reports': '▧ Reports', 'mailing': '✉ Mailing',
    'shipments': '🚚 Shipments', 'invoices': '＄ Invoice Records', 'bol': '▤ B/L Records',
    'inventory': '◇ Inventory', 'fleet': '🚚 Fleet', 'staff': '● Staff', 'data': '◉ Data'
}
for key, label in nav_labels.items():
    text = re.sub(r'(<div class="tab(?: active)?" data-tab="' + re.escape(key) + r'">).*?(</div>)', r'\1' + label + r'\2', text, count=1)

# Replace Dashboard panel with live operational dashboard.
new_dashboard = '''  <div class="panel active" id="panel-dashboard">
    <section class="dashboard-actions">
      <div>
        <div class="welcome-line">Welcome back, Admin 👋</div>
        <div class="welcome-sub">Here’s what’s happening with your operations today.</div>
      </div>
      <button class="refreshBtn" onclick="loadDashboard()">↻ Refresh</button>
      <div id="dashboardStats" class="dashboard-grid"></div>
    </section>

    <section class="doc-launch-section">
      <div class="doc-launch-title">BUSINESS DOCUMENTS</div>
      <div class="doc-launch-grid">
        <a class="doc-launch-card invoice" href="/business-documents/invoice.html"><span class="doc-icon">＄</span><strong>Invoice</strong></a>
        <a class="doc-launch-card bol" href="/business-documents/bill-of-lading.html"><span class="doc-icon">▤</span><strong>Bill of Lading</strong></a>
        <a class="doc-launch-card receipt" href="/business-documents/receipt.html"><span class="doc-icon">▧</span><strong>Receipt</strong></a>
      </div>
    </section>

    <section class="admin-section">
      <div class="admin-section-title">QUICK ACTIONS</div>
      <div class="quick-grid">
        <button class="quick-btn" onclick="window.location.href='/submit'"><span class="qicon">＋</span>New Submission</button>
        <button class="quick-btn" onclick="switchAdminTab('shipments');setTimeout(()=>document.getElementById('shipLookupInput')?.focus(),100)"><span class="qicon">⌖</span>Track Shipment</button>
        <button class="quick-btn" onclick="switchAdminTab('inventory');setTimeout(()=>document.getElementById('invProdSku')?.focus(),100)"><span class="qicon">◇</span>Add Inventory</button>
        <button class="quick-btn" onclick="switchAdminTab('reports')"><span class="qicon">▧</span>Reports</button>
        <button class="quick-btn" onclick="switchAdminTab('mailing')"><span class="qicon">✉</span>Mailing</button>
        <button class="quick-btn" onclick="switchAdminTab('staff');setTimeout(()=>document.getElementById('staffName')?.focus(),100)"><span class="qicon">●</span>Add Staff</button>
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

# Reusable tab switcher for dashboard quick actions.
helper_marker = "document.querySelectorAll('.subtab').forEach(sub => {"
helper = '''function switchAdminTab(name) {
  const tab = document.querySelector('.tab[data-tab="' + name + '"]');
  if (tab) tab.click();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

'''
if 'function switchAdminTab(name)' not in text and helper_marker in text:
    text = text.replace(helper_marker, helper + helper_marker, 1)

# Ensure unlocking uses the grid layout class and loads Dashboard first.
text = text.replace("document.getElementById('main').style.display = 'block';", "document.getElementById('main').classList.add('admin-ready');")
text = text.replace('  loadSubmissions();\n}', '  loadDashboard();\n}', 1)

# Live dashboard loader using current backend APIs and real records.
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
      <div class="stat-tile"><div class="stat-label">Total Submissions</div><div class="stat-value">${submissions.length}</div></div>
      <div class="stat-tile"><div class="stat-label">Active Shipments</div><div class="stat-value">${activeShipments}</div></div>
      <div class="stat-tile"><div class="stat-label">Inventory Units</div><div class="stat-value">${totalUnits.toLocaleString()}</div></div>
      <div class="stat-tile${pendingSubmissions + unpaidInvoices ? ' warn' : ''}"><div class="stat-label">Pending Items</div><div class="stat-value">${pendingSubmissions + unpaidInvoices}</div></div>
    `;

    const statusCount = status => shipments.filter(s => (s.delivery_status || 'created') === status).length;
    const inTransit = statusCount('in_transit') + statusCount('out_for_delivery') + statusCount('picked_up');
    const delivered = statusCount('delivered');
    const pending = statusCount('created') + statusCount('delayed');
    const cancelled = statusCount('cancelled') + statusCount('returned') + statusCount('failed_delivery');
    opsOut.innerHTML = `
      <div class="op-tile"><div class="op-label">🚚 IN TRANSIT</div><div class="op-value">${inTransit}</div><div class="op-label">Shipments</div></div>
      <div class="op-tile"><div class="op-label">✓ DELIVERED</div><div class="op-value">${delivered}</div><div class="op-label">Shipments</div></div>
      <div class="op-tile"><div class="op-label">◷ PENDING</div><div class="op-value">${pending}</div><div class="op-label">Shipments</div></div>
      <div class="op-tile"><div class="op-label">✕ CANCELLED / FAILED</div><div class="op-value">${cancelled}</div><div class="op-label">Shipments</div></div>
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
    shipments.forEach(s => activity.push({t:Number(s.updated_at || s.created_at || 0), icon:'🚚', text:`Shipment ${s.shipment_number || ''} updated to ${(s.delivery_status || 'created').replace(/_/g,' ')}`}));
    submissions.forEach(s => activity.push({t:Number(s.created_at || 0), icon:'＋', text:`New ${s.building_type || 'building'} submission — ${s.status || 'pending'}`}));
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
