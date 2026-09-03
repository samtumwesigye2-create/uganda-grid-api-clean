(() => {
  const PASSCODE_KEY='driver_passcode';
  const ROUTE_KEY='ugatu_driver_route_session_v1';
  const DEVICE_KEY='ugatu_device_id';
  const QUEUE_KEYS=['ugatu_driver_offline_queue_v3','ugatu_driver_offline_queue_v2','ugatu_driver_offline_queue_v1'];
  const $=id=>document.getElementById(id);
  const rid=()=>`ROUTE-${Date.now()}-${Math.random().toString(36).slice(2,10)}`;
  const passcode=()=>localStorage.getItem(PASSCODE_KEY)||'';
  const deviceId=()=>localStorage.getItem(DEVICE_KEY)||'DRIVER-IPAD';
  const getRoute=()=>{try{return JSON.parse(localStorage.getItem(ROUTE_KEY)||'null')}catch{return null}};
  const setRoute=v=>v?localStorage.setItem(ROUTE_KEY,JSON.stringify(v)):localStorage.removeItem(ROUTE_KEY);
  const offlineCount=()=>QUEUE_KEYS.reduce((n,k)=>{try{return n+(JSON.parse(localStorage.getItem(k)||'[]').length||0)}catch{return n}},0);
  const msg=(text,type='ok')=>{const b=$('ugatuMsg');if(!b)return;b.className='notice '+type;b.textContent=text;b.hidden=false;clearTimeout(msg.t);msg.t=setTimeout(()=>b.hidden=true,4300)};
  const headers=json=>{const h={'x-driver-passcode':passcode()};if(json)h['Content-Type']='application/json';return h};

  async function tasks(){
    const r=await fetch('/driver/tasks',{headers:headers(false)});
    if(!r.ok)throw new Error('Could not load route stops.');
    const d=await r.json();return d.results||[];
  }
  async function manifest(){
    const r=await fetch('/api/ugatu/driver-route/manifest',{headers:headers(false)});
    if(!r.ok)throw new Error('Could not reconcile route manifest.');
    return await r.json();
  }
  async function command(ucode,parameters,requestId){
    const body={ucode,parameters,client_request_id:requestId||rid(),actor_id:'DRIVER',role:'DRIVER',device_id:deviceId(),offline:false};
    const r=await fetch('/api/ugatu/execute',{method:'POST',headers:headers(true),body:JSON.stringify(body)});
    if(!r.ok){const e=await r.json().catch(()=>({}));throw new Error(e.detail||`UGATU rejected ${ucode}`)}
    return await r.json();
  }
  function renderRoute(){
    const s=getRoute();
    if($('routeState'))$('routeState').textContent=s?`ROUTE ACTIVE · started ${new Date(s.startedAt).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}`:'ROUTE NOT STARTED';
    if($('startRouteBtn'))$('startRouteBtn').disabled=!!s;
    if($('completeRouteBtn'))$('completeRouteBtn').disabled=!s;
  }
  async function startRoute(){
    if(!passcode())return msg('Log in first.','bad');
    try{
      const list=await tasks();
      if(!list.length)return msg('No assigned stops are available to start.','warn');
      const requestId=rid();
      await command('U-1810',{planned_stop_count:list.length,pickup_count:list.filter(x=>String(x.task_type||'').includes('pickup')).length},requestId);
      setRoute({id:requestId,startedAt:new Date().toISOString(),initialStopIds:list.map(x=>x.id)});
      renderRoute();msg(`Route started · U-1810 · ${list.length} stops`);
    }catch(e){msg(e.message||'Could not start route.','bad')}
  }
  async function openManifest(){
    if(!passcode())return msg('Log in first.','bad');
    try{
      const m=await manifest();
      $('manifestSummary').innerHTML=`<strong>${m.active_count}</strong> active stops · <strong>${m.pickup_count}</strong> pickups · <strong>${m.custody_count}</strong> items currently in pickup custody`;
      $('manifestWarning').textContent=m.unaccounted_count?`${m.unaccounted_count} pickup item(s) remain in driver custody. Route close will stay blocked until work is reconciled.`:'Custody reconciliation currently clear.';
      $('manifestList').innerHTML=(m.active||[]).map(x=>`<div class="context"><strong>${String(x.task_number||'Stop')}</strong> · ${String(x.task_type||'').replaceAll('_',' ')}<br><span>${String(x.location_text||'')}</span><br><small>${String(x.status||'assigned').replaceAll('_',' ')}</small></div>`).join('')||'<div class="empty">No active manifest stops.</div>';
      $('manifestSheet').hidden=false;
    }catch(e){msg(e.message||'Could not open manifest.','bad')}
  }
  function closeManifest(){$('manifestSheet').hidden=true}
  function openPickup(){if(!getRoute())return msg('Start the route before adding a dynamic pickup.','bad');$('dynamicLocation').value='';$('dynamicItem').value='';$('dynamicShipment').value='';$('dynamicNotes').value='';$('dynamicPickupSheet').hidden=false;$('dynamicLocation').focus()}
  function closePickup(){$('dynamicPickupSheet').hidden=true}
  async function addPickup(){
    const location=$('dynamicLocation').value.trim();
    if(!location)return msg('Enter the pickup location.','bad');
    const body={client_request_id:rid(),location_text:location,package_id:$('dynamicItem').value.trim()||null,shipment_number:$('dynamicShipment').value.trim()||null,notes:$('dynamicNotes').value.trim()};
    try{
      const r=await fetch('/api/ugatu/driver-route/dynamic-pickup',{method:'POST',headers:headers(true),body:JSON.stringify(body)});
      if(!r.ok){const e=await r.json().catch(()=>({}));throw new Error(e.detail||'Could not add pickup')}
      const out=await r.json();closePickup();msg(`Dynamic pickup added · ${out.task?.task_number||'U-1860'}`);setTimeout(()=>location.reload(),650);
    }catch(e){msg(e.message||'Could not add dynamic pickup.','bad')}
  }
  async function completeRoute(){
    if(!getRoute())return msg('Route is not active.','bad');
    if(offlineCount())return msg(`${offlineCount()} offline transaction(s) still need to sync before route close.`,'warn');
    try{
      const m=await manifest();
      if(m.active_count)return msg(`${m.active_count} active stop(s) remain. Complete or resolve them before closing the route.`,'warn');
      if(m.unaccounted_count)return msg(`${m.unaccounted_count} item(s) are still unaccounted for in custody reconciliation.`,'bad');
      const r=await fetch('/api/ugatu/driver-route/complete-route',{method:'POST',headers:headers(true),body:JSON.stringify({client_request_id:rid(),device_id:deviceId()})});
      if(!r.ok){const e=await r.json().catch(()=>({}));const detail=typeof e.detail==='object'?e.detail.message:e.detail;throw new Error(detail||'Route close rejected')}
      const out=await r.json();setRoute(null);renderRoute();msg(`Route completed · ${out.ugatu?.ucode||'U-1890'} · custody reconciled`);
    }catch(e){msg(e.message||'Could not complete route.','bad')}
  }

  $('startRouteBtn')?.addEventListener('click',startRoute);
  $('manifestBtn')?.addEventListener('click',openManifest);
  $('manifestClose')?.addEventListener('click',closeManifest);
  $('dynamicPickupBtn')?.addEventListener('click',openPickup);
  $('dynamicPickupClose')?.addEventListener('click',closePickup);
  $('dynamicPickupSubmit')?.addEventListener('click',addPickup);
  $('completeRouteBtn')?.addEventListener('click',completeRoute);
  renderRoute();
})();