(function () {
  'use strict';
  const byId = (id) => document.getElementById(id);
  const toolbar = document.querySelector('.hero .toolbar');
  if (!toolbar || byId('dashWarehouse')) return;

  const warehouse = document.createElement('input');
  warehouse.id = 'dashWarehouse';
  warehouse.value = localStorage.getItem('warehouse-command-id') || 'main';
  warehouse.placeholder = 'Warehouse ID';
  warehouse.setAttribute('aria-label', 'Warehouse ID');
  warehouse.style.cssText = 'padding:10px;border:1px solid #cbd5e1;border-radius:8px;min-width:150px';
  const openButton = toolbar.querySelector('button');
  toolbar.insertBefore(warehouse, openButton);

  const refresh = document.createElement('button');
  refresh.className = 'btn secondary';
  refresh.type = 'button';
  refresh.textContent = '↻ Refresh';
  refresh.onclick = () => window.loadDashboard();
  openButton.insertAdjacentElement('afterend', refresh);

  const status = document.createElement('div');
  status.id = 'dashStatus';
  status.setAttribute('role', 'status');
  status.style.cssText = 'margin-top:10px;padding:9px 11px;border-radius:8px;background:#eef2ff;color:#3446a8;font-size:13px';
  status.textContent = 'Enter your staff access code and warehouse ID.';
  toolbar.insertAdjacentElement('afterend', status);

  const escapeHtml = (value) => String(value == null ? '' : value).replace(/[&<>]/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[char]));
  window.loadDashboard = async function () {
    const code = (byId('dashCode').value || '').trim();
    const warehouseId = (warehouse.value || '').trim() || 'main';
    if (!code) {
      status.style.cssText += ';background:#feecec;color:#b42318';
      status.textContent = 'Staff access code is required.';
      byId('dashCode').focus();
      return;
    }
    localStorage.setItem('warehouse-command-id', warehouseId);
    byId('warehouse').value = warehouseId;
    status.style.cssText += ';background:#eef2ff;color:#3446a8';
    status.textContent = 'Loading ' + warehouseId + ' command data…';
    openButton.disabled = true;
    try {
      const response = await fetch('/warehouse/dashboard?warehouse_id=' + encodeURIComponent(warehouseId), {
        headers: {'x-access-code': code}, cache: 'no-store'
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Dashboard unavailable');
      byId('kReceive').textContent = data.today.receiving || 0;
      byId('kPick').textContent = data.today.picking || 0;
      byId('kDispatch').textContent = data.today.dispatch || 0;
      byId('kPut').textContent = data.today.putaway || 0;
      byId('kLow').textContent = (data.low_stock || []).length;
      byId('kAlerts').textContent = (data.alerts || []).length;
      byId('alerts').innerHTML = (data.alerts || []).map((alert) => '<div class="alertItem ' + (alert.level === 'critical' ? 'critical' : '') + '"><b>' + escapeHtml(alert.type).toUpperCase() + '</b> · ' + escapeHtml(alert.message) + '<br><small>' + escapeHtml(alert.reference) + '</small></div>').join('') || '<span class="muted">No active alerts.</span>';
      byId('lowStock').innerHTML = (data.low_stock || []).map((item) => '<div class="low"><b>' + escapeHtml(item.product_sku) + '</b> · ' + escapeHtml(item.warehouse_id) + '<span style="float:right">Qty ' + escapeHtml(item.quantity_on_hand) + '</span></div>').join('') || '<span class="muted">No low-stock items.</span>';
      const recentResponse = await fetch('/warehouse/operations?limit=50&warehouse_id=' + encodeURIComponent(warehouseId), {
        headers: {'x-access-code': code}, cache: 'no-store'
      });
      const recentData = await recentResponse.json();
      if (!recentResponse.ok) throw new Error(recentData.detail || 'Recent records unavailable');
      byId('recent').innerHTML = (recentData.results || []).map((row) => '<tr><td>' + escapeHtml(row.reference_no) + '</td><td>' + escapeHtml(row.operation_type) + '</td><td>' + escapeHtml(row.action_code) + '</td><td>' + escapeHtml(row.sku) + '</td><td>' + escapeHtml(row.quantity) + '</td><td>' + escapeHtml(row.location_code) + '</td><td>' + escapeHtml(row.status) + '</td><td>' + new Date(row.created_at * 1000).toLocaleString() + '</td></tr>').join('') || '<tr><td colspan="8">No records for this warehouse.</td></tr>';
      status.style.cssText += ';background:#eaf8f1;color:#087b4c';
      status.textContent = 'Live command data loaded for ' + warehouseId + ' · ' + new Date().toLocaleTimeString();
    } catch (error) {
      status.style.cssText += ';background:#feecec;color:#b42318';
      status.textContent = error.message;
    } finally {
      openButton.disabled = false;
    }
  };
})();
