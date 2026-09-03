(() => {
  const nativeFetch = window.fetch.bind(window);
  const DELIVERY_STATUSES = new Set(['picked_up','en_route_dropoff','arrived_dropoff']);

  function isCombinedPickup(task) {
    if (!task) return false;
    const type = String(task.task_type || '').toLowerCase();
    const notes = String(task.notes || '').toLowerCase();
    if (!type.includes('pickup')) return false;
    if (notes.includes('pickup_only') || notes.includes('[pickup_only]')) return false;
    return Boolean(task.shipment_number);
  }

  function deliveryLeg(task) {
    return isCombinedPickup(task) && DELIVERY_STATUSES.has(String(task.status || '').toLowerCase());
  }

  async function responseJson(response) {
    try { return await response.clone().json(); } catch { return null; }
  }

  function jsonResponse(data, original) {
    const headers = new Headers(original.headers);
    headers.set('content-type', 'application/json');
    return new Response(JSON.stringify(data), {
      status: original.status,
      statusText: original.statusText,
      headers,
    });
  }

  async function rewriteDriverTasks(response) {
    if (!response.ok) return response;
    const data = await responseJson(response);
    if (!data || !Array.isArray(data.results)) return response;
    data.results = data.results.map(task => {
      if (!deliveryLeg(task)) return task;
      return {
        ...task,
        ugatu_original_task_type: task.task_type,
        ugatu_original_status: task.status,
        ugatu_leg: 'DELIVERY',
        task_type: 'dropoff_customer',
        // Present picked_up as the beginning of the delivery leg. The POST
        // bridge below preserves the real server transition picked_up ->
        // en_route_dropoff -> arrived_dropoff.
        status: String(task.status).toLowerCase() === 'picked_up' ? 'en_route_dropoff' : task.status,
      };
    });
    return jsonResponse(data, response);
  }

  async function rewriteDriverOrders(response, requestInit) {
    if (!response.ok) return response;
    const data = await responseJson(response);
    if (!data || !Array.isArray(data.results)) return response;
    const headers = requestInit?.headers || {};
    const rows = [];
    for (const row of data.results) {
      if (!deliveryLeg(row)) { rows.push(row); continue; }
      let detail = null;
      try {
        const r = await nativeFetch(`/api/ugatu/driver-orders/${encodeURIComponent(row.task_id)}`, { headers });
        if (r.ok) detail = await r.json();
      } catch {}
      const order = detail?.order || {};
      const shipment = detail?.shipment || {};
      rows.push({
        ...row,
        service_type: 'DELIVERY',
        location_text: order.delivery_address || shipment.delivery || row.location_text,
        delivery_grid_id: order.delivery_grid_id || row.delivery_grid_id || '',
        // The dispatch task coordinates are the pickup coordinates. Do not
        // send a driver back to the pickup point during the delivery leg.
        latitude: null,
        longitude: null,
        ugatu_leg: 'DELIVERY',
      });
    }
    data.results = rows;
    data.pickup_count = rows.filter(x => x.service_type === 'PICKUP').length;
    data.delivery_count = rows.filter(x => x.service_type === 'DELIVERY').length;
    data.handoff_count = rows.filter(x => x.service_type === 'HANDOFF').length;
    return jsonResponse(data, response);
  }

  async function bridgePickedUpToDropoff(url, init) {
    if (!/\/dispatch\/tasks\/[^/]+\/status(?:\?|$)/.test(url) || String(init?.method || 'GET').toUpperCase() !== 'POST') return null;
    const body = init?.body;
    if (!(body instanceof FormData) || body.get('status') !== 'arrived_dropoff') return null;

    // The UI intentionally represents server state picked_up as
    // en_route_dropoff so the driver sees the next leg immediately. Before
    // ARRIVE is accepted, advance the real server state one legal step.
    const transition = new FormData();
    transition.append('status', 'en_route_dropoff');
    transition.append('note', 'UGATU automatic pickup-to-delivery leg transition');
    const pre = await nativeFetch(url, { ...init, body: transition });
    if (!pre.ok && pre.status !== 409) return pre;
    return nativeFetch(url, init);
  }

  window.fetch = async (input, init = {}) => {
    const url = typeof input === 'string' ? input : input?.url || '';
    const bridged = await bridgePickedUpToDropoff(url, init);
    if (bridged) return bridged;

    const response = await nativeFetch(input, init);
    if (url === '/driver/tasks' || url.startsWith('/driver/tasks?')) return rewriteDriverTasks(response);
    if (url === '/api/ugatu/driver-orders' || url.startsWith('/api/ugatu/driver-orders?')) return rewriteDriverOrders(response, init);
    return response;
  };

  window.UGATULegLifecycle = {
    isCombinedPickup,
    deliveryLeg,
    version: '1.0.0',
  };
})();