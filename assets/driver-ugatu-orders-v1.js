(() => {
  const PASSCODE_KEY='driver_passcode';
  const $=id=>document.getElementById(id);
  const passcode=()=>localStorage.getItem(PASSCODE_KEY)||'';
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const headers=()=>({'x-driver-passcode':passcode()});
  const msg=(text,type='ok')=>{const b=$('ugatuMsg');if(!b)return;b.className='notice '+type;b.textContent=text;b.hidden=false;clearTimeout(msg.t);msg.t=setTimeout(()=>b.hidden=true,4200)};
  let data=[];

  function injectUI(){
    if(!$('ordersSheet'))document.body.insertAdjacentHTML('beforeend',`<div id="ordersSheet" class="overlay" hidden><div class="sheet"><div class="sheetHead"><h2>My Orders</h2><button id="ordersClose">Close</button></div><div id="ordersSummary" class="context">Loading orders…</div><div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:12px"><button id="ordersAll" class="primary" style="margin:0;min-height:46px">ALL</button><button id="ordersPickup" style="min-height:46px;border:0;border-radius:12px;background:#dbeafe;color:#1d4ed8;font-weight:900">PICKUPS</button><button id="ordersDelivery" style="min-height:46px;border:0;border-radius:12px;background:#dcfce7;color:#166534;font-weight:900">DELIVERIES</button></div><div id="ordersList"></div></div></div>`);
    if(!$('orderDetailSheet'))document.body.insertAdjacentHTML('beforeend',`<div id="orderDetailSheet" class="overlay" hidden><div class="sheet"><div class="sheetHead"><h2 id="orderDetailTitle">Order</h2><button id="orderDetailClose">Close</button></div><div id="orderDetailBody"></div></div></div>`);
  }

  async function fetchOrders(){
    const r=await fetch('/api/ugatu/driver-orders',{headers:headers()});
    if(!r.ok){const e=await r.json().catch(()=>({}));throw new Error(e.detail||'Could not load driver orders')}
    return await r.json();
  }
  function typeClass(t){return t==='PICKUP'?'pickup':t==='HANDOFF'?'handoff':'delivery'}
  function orderCard(x){
    const freight=x.freight||{};
    const weight=freight.weight_kg!=null?`${freight.weight_kg} kg`:'Weight not listed';
    return `<div class="context" style="padding:14px"><div style="display:flex;justify-content:space-between;gap:10px;align-items:start"><div><span class="pill ${typeClass(x.service_type)}">${esc(x.service_type)}</span><strong style="display:block;margin-top:7px">${esc(x.order_number||x.shipment_number||x.task_number||'Order')}</strong><small>${esc(x.shipment_number||'No shipment number')}</small></div><small style="font-weight:800;text-transform:uppercase">${esc(String(x.status||'assigned').replaceAll('_',' '))}</small></div><div style="margin-top:10px"><b>${esc(x.customer_name||'Customer')}</b><br><span>${esc(x.location_text||'Location not listed')}</span></div><div style="font-size:12px;color:#64748b;margin-top:8px">${esc(weight)} · ${freight.item_count||0} line item(s) · ${freight.quantity||0} total units</div><button class="orderOpenBtn" data-task="${esc(x.task_id)}" style="width:100%;min-height:46px;margin-top:10px;border:0;border-radius:12px;background:#111827;color:#fff;font-weight:900">OPEN ORDER</button></div>`;
  }
  function render(filter='ALL'){
    const rows=filter==='ALL'?data:data.filter(x=>x.service_type===filter);
    $('ordersList').innerHTML=rows.map(orderCard).join('')||'<div class="empty">No matching driver orders.</div>';
    document.querySelectorAll('.orderOpenBtn').forEach(b=>b.onclick=()=>openDetail(b.dataset.task));
  }
  async function openOrders(filter='ALL'){
    if(!passcode())return msg('Log in first.','bad');
    try{
      const out=await fetchOrders();data=out.results||[];
      $('ordersSummary').innerHTML=`<strong>${out.count||0}</strong> active orders · <strong>${out.pickup_count||0}</strong> pickups · <strong>${out.delivery_count||0}</strong> deliveries`;
      render(filter);$('ordersSheet').hidden=false;
    }catch(e){msg(e.message||'Could not load orders.','bad')}
  }
  function selectStop(taskId){
    const row=document.querySelector(`.taskRow[data-id="${CSS.escape(String(taskId))}"]`);
    if(row){row.click();return true}
    return false;
  }
  function navigationUrl(x){
    if(x.delivery_grid_id)return `/?destination=${encodeURIComponent(x.delivery_grid_id)}`;
    if(x.latitude!=null&&x.longitude!=null)return `/?destination=${encodeURIComponent(`${x.latitude},${x.longitude}`)}`;
    return `/?destination=${encodeURIComponent(x.location_text||'')}`;
  }
  function openDetail(taskId){
    const x=data.find(v=>String(v.task_id)===String(taskId));if(!x)return;
    const freight=x.freight||{}, items=freight.items||[];
    $('orderDetailTitle').textContent=x.order_number||x.shipment_number||x.task_number||'Order';
    $('orderDetailBody').innerHTML=`<div class="context"><strong>${esc(x.service_type)} · ${esc(String(x.status||'assigned').replaceAll('_',' '))}</strong><br>${esc(x.customer_name||'Customer')} ${x.customer_phone?'· '+esc(x.customer_phone):''}<br>${esc(x.location_text||'')} ${x.delivery_grid_id?'· '+esc(x.delivery_grid_id):''}</div><div class="context"><strong>Freight</strong><br>${freight.weight_kg!=null?esc(freight.weight_kg)+' kg · ':''}${freight.item_count||0} line item(s) · ${freight.quantity||0} total units${freight.shipment_type?' · '+esc(freight.shipment_type):''}${freight.speed_tier?' · '+esc(freight.speed_tier):''}</div>${items.length?`<div class="context"><strong>Items</strong>${items.map(i=>`<div style="padding:7px 0;border-bottom:1px solid #e5e7eb"><b>${esc(i.sku||'Item')}</b> · ${esc(i.name||'')}<br><small>Qty ${esc(i.quantity||0)}</small></div>`).join('')}</div>`:''}<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px"><button id="orderNavigate" class="primary" style="margin:0">NAVIGATE</button><button id="orderScan" style="border:0;border-radius:14px;font-weight:900">SCAN</button><button id="orderDocs" style="border:0;border-radius:14px;font-weight:900">DOCUMENTS</button><button id="orderIssue" style="border:0;border-radius:14px;font-weight:900">REPORT ISSUE</button></div>`;
    $('orderNavigate').onclick=()=>{window.location.href=navigationUrl(x)};
    $('orderScan').onclick=()=>{if(!selectStop(x.task_id))return msg('This order is no longer in the active stop list.','warn');$('orderDetailSheet').hidden=true;$('ordersSheet').hidden=true;setTimeout(()=>$('scanBtn')?.click(),50)};
    $('orderDocs').onclick=()=>{if(!selectStop(x.task_id))return msg('This order is no longer in the active stop list.','warn');$('orderDetailSheet').hidden=true;$('ordersSheet').hidden=true;setTimeout(()=>$('docsBtn')?.click(),50)};
    $('orderIssue').onclick=()=>{if(!selectStop(x.task_id))return msg('This order is no longer in the active stop list.','warn');$('orderDetailSheet').hidden=true;$('ordersSheet').hidden=true;setTimeout(()=>$('issueBtn')?.click(),50)};
    $('orderDetailSheet').hidden=false;
  }

  injectUI();
  $('ordersBtn')?.addEventListener('click',e=>{e.preventDefault();e.stopImmediatePropagation();openOrders('ALL')},true);
  $('ordersNav')?.addEventListener('click',e=>{e.preventDefault();e.stopImmediatePropagation();openOrders('ALL')},true);
  $('ordersClose')?.addEventListener('click',()=>{$('ordersSheet').hidden=true});
  $('orderDetailClose')?.addEventListener('click',()=>{$('orderDetailSheet').hidden=true});
  $('ordersAll')?.addEventListener('click',()=>render('ALL'));
  $('ordersPickup')?.addEventListener('click',()=>render('PICKUP'));
  $('ordersDelivery')?.addEventListener('click',()=>render('DELIVERY'));
})();