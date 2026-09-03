(() => {
  const PASSCODE_KEY='driver_passcode';
  const QUEUE_KEY='ugatu_driver_offline_queue_v1';
  let passcode=localStorage.getItem(PASSCODE_KEY)||'';
  let driver=null, tasks=[];

  const $=id=>document.getElementById(id);
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const reqId=()=>`DRV-${Date.now()}-${Math.random().toString(36).slice(2,10)}`;
  const queue=()=>JSON.parse(localStorage.getItem(QUEUE_KEY)||'[]');
  const saveQueue=q=>localStorage.setItem(QUEUE_KEY,JSON.stringify(q));
  const setMsg=(text,type='ok')=>{$('ugatuMsg').className='notice '+type;$('ugatuMsg').textContent=text;$('ugatuMsg').hidden=false;setTimeout(()=>{$('ugatuMsg').hidden=true},3500)};

  function headers(json=false){const h={'x-driver-passcode':passcode};if(json)h['Content-Type']='application/json';return h}
  function taskMode(t){
    if(!t)return 'PICKUP';
    const type=String(t.task_type||'').toLowerCase();
    if(type.includes('pickup'))return 'PICKUP';
    if(type.includes('warehouse_transfer'))return 'HANDOFF';
    return 'DELIVERY';
  }
  function activeTask(){return tasks.find(t=>!['completed','failed'].includes(t.status))||tasks[0]||null}
  function render(){
    $('driverName').textContent=driver?.name||'Driver';
    const active=activeTask();
    $('routeSummary').textContent=tasks.length?`${tasks.filter(t=>!['completed','failed'].includes(t.status)).length} active stops · ${tasks.filter(t=>taskMode(t)==='PICKUP').length} pickups`:'No active work';
    $('currentStop').innerHTML=active?`<strong>${esc(active.location_text||'Current stop')}</strong><span>${esc(active.task_number||'')} ${active.shipment_number?'· '+esc(active.shipment_number):''}</span>`:'<strong>No active stop</strong><span>Dispatch assignments will appear here.</span>';
    $('scanMode').value=taskMode(active);
    $('offlineCount').textContent=queue().length;
    $('taskList').innerHTML=tasks.slice(0,8).map(t=>`<button class="taskRow" data-id="${esc(t.id)}"><span class="pill ${taskMode(t).toLowerCase()}">${taskMode(t)}</span><b>${esc(t.location_text||'Stop')}</b><small>${esc(t.status||'assigned').replaceAll('_',' ')}</small></button>`).join('')||'<div class="empty">No active tasks.</div>';
  }

  async function login(){
    const code=$('passcode').value.trim(); if(code)passcode=code;
    if(!passcode)return setMsg('Enter your driver passcode.','bad');
    try{
      const r=await fetch('/driver/me',{headers:headers()}); if(!r.ok)throw 0;
      driver=await r.json();localStorage.setItem(PASSCODE_KEY,passcode);$('login').hidden=true;$('app').hidden=false;await loadTasks();await syncQueue();
    }catch{setMsg('Driver login failed.','bad')}
  }
  async function loadTasks(){
    try{const r=await fetch('/driver/tasks',{headers:headers()});const d=await r.json();tasks=d.results||[];render()}catch{setMsg('Could not load tasks.','bad')}
  }
  async function executeScan(payload){
    const mode=payload.mode;
    const ucode=mode==='PICKUP'?'U-1550':mode==='HANDOFF'?'U-1570':'U-1560';
    const active=activeTask();
    const body={ucode,parameters:{package_id:payload.item,route_id:active?.route_id||active?.route_number||null,stop_id:active?.id||null,task_id:active?.id||null,shipment_id:active?.shipment_id||active?.shipment_number||null,scan_mode:mode},client_request_id:payload.requestId,actor_id:driver?.id||driver?.driver_id||driver?.name||'DRIVER',role:'DRIVER',device_id:localStorage.getItem('ugatu_device_id')||navigator.userAgent.slice(0,100),offline:false};
    try{
      const r=await fetch('/api/ugatu/execute',{method:'POST',headers:headers(true),body:JSON.stringify(body)});if(!r.ok){const e=await r.json();throw new Error(e.detail||'UGATU rejected scan')}
      const out=await r.json();setMsg(`${mode} recorded · ${out.ucode}`);$('scanValue').value='';await loadTasks();return true;
    }catch(e){
      if(!navigator.onLine||String(e.message).includes('Failed to fetch')){const q=queue();q.push({...payload,createdAt:new Date().toISOString()});saveQueue(q);render();setMsg(`${mode} saved offline. It will sync automatically.`,'warn');$('scanValue').value='';return true}
      setMsg(e.message||'Scan failed.','bad');return false;
    }
  }
  async function syncQueue(){
    if(!navigator.onLine)return;let q=queue();if(!q.length)return;const left=[];
    for(const item of q){const ok=await executeScan({...item,fromSync:true});if(!ok)left.push(item)}
    saveQueue(left);render();if(q.length&&!left.length)setMsg(`${q.length} offline transaction${q.length===1?'':'s'} synchronized.`)
  }
  function openScan(){
    $('scanSheet').hidden=false;$('scanValue').focus();
  }
  function closeScan(){$('scanSheet').hidden=true}
  async function submitScan(){const item=$('scanValue').value.trim();if(!item)return setMsg('Scan or enter a package/freight ID.','bad');await executeScan({mode:$('scanMode').value,item,requestId:reqId()});closeScan()}

  $('loginBtn').onclick=login;$('passcode').addEventListener('keydown',e=>{if(e.key==='Enter')login()});
  $('scanBtn').onclick=openScan;$('scanClose').onclick=closeScan;$('scanSubmit').onclick=submitScan;
  $('refreshBtn').onclick=loadTasks;$('syncBtn').onclick=syncQueue;
  $('ordersBtn').onclick=()=>document.querySelector('.tasks').scrollIntoView({behavior:'smooth'});
  $('docsBtn').onclick=()=>setMsg('Document Center is mapped to U-1600; document viewer comes next.','warn');
  $('issueBtn').onclick=()=>setMsg('Report Issue is mapped to U-1310/U-1320; exception form comes next.','warn');
  window.addEventListener('online',syncQueue);
  if(passcode)login();
})();