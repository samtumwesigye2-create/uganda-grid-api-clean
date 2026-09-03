(() => {
  const PASSCODE_KEY='driver_passcode';
  const $=id=>document.getElementById(id);
  const passcode=()=>localStorage.getItem(PASSCODE_KEY)||'';
  const headers=()=>({'x-driver-passcode':passcode()});
  let live=null,loading=false,lastAt=0;

  async function loadLive(){
    if(!passcode()||loading||!navigator.onLine)return null;
    const now=Date.now();if(now-lastAt<12000&&live)return live;
    loading=true;
    try{
      const r=await fetch('/api/ugatu/driver-routing',{headers:headers()});
      if(!r.ok)throw new Error('routing unavailable');
      live=await r.json();lastAt=Date.now();return live;
    }catch{return null}finally{loading=false}
  }

  function renderLive(data){
    const n=data?.next_stop;if(!n)return;
    const reason=$('nextStopReason'),text=$('nextStopText'),eta=$('nextStopEta');
    if(reason)reason.textContent=n.priority_reason||'UGAMAP ROAD TIME';
    if(text)text.innerHTML=`<strong>${n.task_number||'Stop'} · ${n.leg_mode||n.task_type||'STOP'}</strong><br>${n.delivery_grid_id||n.delivery_address||n.location_text||''}`;
    if(eta){
      eta.textContent=n.ugamap_route_available
        ? `UGAMAP live route · ${n.road_distance_km} km road distance · ~${n.eta_minutes} min · ${n.ugamap_provider||'routing'}`
        : 'UGAMAP route unavailable for this stop; dashboard fallback remains active.';
    }
    const list=$('sequenceList');
    if(list&&data.sequence?.length&&!$('sequenceBox')?.hidden){
      list.innerHTML=data.sequence.map(x=>`<button class="seqRow liveRouteRow" data-task="${String(x.id||'').replace(/"/g,'&quot;')}" style="display:block;width:100%;text-align:left;border:0;border-bottom:1px solid #e5e7eb;background:transparent;padding:10px 2px"><b>#${x.sequence} · ${x.leg_mode||x.task_type||'STOP'} · ${x.task_number||''}</b><br><span>${x.delivery_grid_id||x.delivery_address||x.location_text||''}</span><br><small>${x.priority_reason||''}${x.road_distance_km!=null?` · ${x.road_distance_km} km road`:''}${x.eta_minutes!=null?` · ~${x.eta_minutes} min`:''}</small></button>`).join('');
      document.querySelectorAll('.liveRouteRow').forEach(b=>b.onclick=()=>{const row=document.querySelector(`.taskRow[data-id="${CSS.escape(String(b.dataset.task))}"]`);if(row){row.click();$('sequenceBox').hidden=true}});
    }
  }

  function hookNavigation(){
    const btn=$('nextNavigateBtn');
    if(!btn||btn.dataset.ugamapLiveHook)return;
    btn.dataset.ugamapLiveHook='1';
    btn.addEventListener('click',e=>{
      const n=live?.next_stop;if(!n)return;
      e.preventDefault();e.stopImmediatePropagation();
      const dest=n.navigation_destination||n.delivery_grid_id||n.delivery_address||(n.latitude!=null&&n.longitude!=null?`${n.latitude},${n.longitude}`:(n.location_text||''));
      window.location.href=`/?destination=${encodeURIComponent(dest)}`;
    },true);
  }

  async function refreshFromDashboard(base){
    if(base?.routing_source==='UGAMAP_LIVE')return;
    const data=await loadLive();
    if(!data?.next_stop)return;
    renderLive(data);hookNavigation();
    document.dispatchEvent(new CustomEvent('ugatu:dashboard-refreshed',{detail:{...base,...data,routing_source:'UGAMAP_LIVE'}}));
  }

  document.addEventListener('ugatu:dashboard-refreshed',e=>refreshFromDashboard(e.detail));
  document.addEventListener('ugatu:stop-completed',()=>{lastAt=0;setTimeout(()=>loadLive().then(d=>{if(d){renderLive(d);document.dispatchEvent(new CustomEvent('ugatu:dashboard-refreshed',{detail:{...d,routing_source:'UGAMAP_LIVE'}}))}}),400)});
  window.addEventListener('online',()=>{lastAt=0;loadLive().then(renderLive)});
  setInterval(()=>{lastAt=0;loadLive().then(renderLive)},60000);
  setTimeout(()=>{hookNavigation();loadLive().then(renderLive)},1400);
})();
