(() => {
  const PASSCODE_KEY='driver_passcode';
  const QUEUE_KEY='ugatu_driver_offline_queue_v3';
  const DEVICE_KEY='ugatu_device_id';
  const SCAN_STATE_KEY='ugatu_driver_scan_state_v1';
  const WORK_STATE_KEY='ugatu_driver_work_state_v1';
  let passcode=localStorage.getItem(PASSCODE_KEY)||'';
  let driver=null,tasks=[],selectedTaskId=null;

  const $=id=>document.getElementById(id);
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const reqId=()=>`DRV-${Date.now()}-${Math.random().toString(36).slice(2,10)}`;
  const readJson=(key,fallback)=>{try{return JSON.parse(localStorage.getItem(key)||JSON.stringify(fallback))}catch{return fallback}};
  const queue=()=>readJson(QUEUE_KEY,[]);
  const saveQueue=q=>localStorage.setItem(QUEUE_KEY,JSON.stringify(q));
  const scanState=()=>readJson(SCAN_STATE_KEY,{});
  const workState=()=>readJson(WORK_STATE_KEY,{});
  const saveScanState=s=>localStorage.setItem(SCAN_STATE_KEY,JSON.stringify(s));
  const saveWorkState=s=>localStorage.setItem(WORK_STATE_KEY,JSON.stringify(s));
  const deviceId=()=>{let d=localStorage.getItem(DEVICE_KEY);if(!d){d=`IPAD-${Date.now()}-${Math.random().toString(36).slice(2,8)}`;localStorage.setItem(DEVICE_KEY,d)}return d};
  const setMsg=(text,type='ok')=>{$('ugatuMsg').className='notice '+type;$('ugatuMsg').textContent=text;$('ugatuMsg').hidden=false;clearTimeout(setMsg.t);setMsg.t=setTimeout(()=>{$('ugatuMsg').hidden=true},4200)};
  function headers(json=false){const h={'x-driver-passcode':passcode};if(json)h['Content-Type']='application/json';return h}
  function taskMode(t){if(!t)return'PICKUP';const type=String(t.task_type||'').toLowerCase();if(type.includes('warehouse_transfer')||type.includes('handoff'))return'HANDOFF';if(type.includes('pickup'))return'PICKUP';return'DELIVERY'}
  function activeTasks(){return tasks.filter(t=>!['completed','failed','cancelled','dropped_off_customer','dropped_off_warehouse'].includes(String(t.status||'').toLowerCase()))}
  function selectedTask(){return tasks.find(t=>String(t.id)===String(selectedTaskId))||activeTasks()[0]||tasks[0]||null}
  function expectedIds(t){if(!t)return[];const raw=[t.package_id,t.freight_id,t.item_id,t.tracking_number,t.shipment_number];for(const key of ['package_ids','freight_ids','item_ids'])if(Array.isArray(t[key]))raw.push(...t[key]);return raw.filter(Boolean).map(v=>String(v).trim().toUpperCase())}
  function travelStatus(t){return taskMode(t)==='PICKUP'?'en_route_pickup':'en_route_dropoff'}
  function arrivedStatus(t){return taskMode(t)==='PICKUP'?'arrived_pickup':'arrived_dropoff'}
  function completeStatus(t){if(taskMode(t)==='PICKUP')return'picked_up';if(String(t.task_type||'').toLowerCase()==='dropoff_customer')return'dropped_off_customer';return'dropped_off_warehouse'}
  function proofUCode(t){return taskMode(t)==='PICKUP'?'U-1640':'U-1630'}
  function isArrived(t){return String(t?.status||'')===arrivedStatus(t)}
  function hasScan(t){return !!scanState()[String(t?.id)]}
  function hasOpened(t){return !!workState()[String(t?.id)]}
  function markScan(t,mode,item,queued=false){const s=scanState();s[String(t.id)]={mode,item,queued,at:new Date().toISOString()};saveScanState(s)}
  function markOpened(t){const s=workState();s[String(t.id)]={at:new Date().toISOString()};saveWorkState(s)}
  function clearStopState(taskId){const s=scanState(),w=workState();delete s[String(taskId)];delete w[String(taskId)];saveScanState(s);saveWorkState(w)}

  function render(){
    $('driverName').textContent=driver?.name||'Driver';const active=selectedTask();if(active&&!selectedTaskId)selectedTaskId=active.id;
    $('routeSummary').textContent=tasks.length?`${activeTasks().length} active stops · ${tasks.filter(t=>taskMode(t)==='PICKUP').length} pickups`:'No active work';
    $('currentStop').innerHTML=active?`<strong>${esc(active.location_text||'Current stop')}</strong><span>${esc(active.task_number||'')} ${active.shipment_number?'· '+esc(active.shipment_number):''}</span><span class="mutedOnDark">${taskMode(active)} · ${esc(String(active.status||'assigned').replaceAll('_',' '))}</span>`:'<strong>No active stop</strong><span>Dispatch assignments will appear here.</span>';
    if(active)$('scanMode').value=taskMode(active);$('offlineCount').textContent=queue().length;
    const phase=active?`${isArrived(active)?'ARRIVED':'NOT ARRIVED'} · ${hasOpened(active)?'WORK OPEN':'WORK NOT OPEN'} · ${hasScan(active)?'SCAN RECORDED':'SCAN REQUIRED'}`:'NO STOP';
    $('stopPhase').textContent=phase;
    $('arriveBtn').disabled=!active||isArrived(active)||['picked_up','dropped_off_customer','dropped_off_warehouse'].includes(String(active?.status||''));
    $('workBtn').disabled=!active||!isArrived(active)||hasOpened(active);
    $('completeBtn').disabled=!active||!isArrived(active)||!hasOpened(active)||!hasScan(active);
    $('taskList').innerHTML=tasks.slice(0,12).map(t=>`<button class="taskRow ${String(t.id)===String(selectedTaskId)?'selected':''}" data-id="${esc(t.id)}"><span class="pill ${taskMode(t).toLowerCase()}">${taskMode(t)}</span><b>${esc(t.location_text||'Stop')}</b><small>${esc(t.task_number||'')} ${t.shipment_number?'· '+esc(t.shipment_number):''} · ${esc(String(t.status||'assigned').replaceAll('_',' '))}</small></button>`).join('')||'<div class="empty">No active tasks.</div>';
    document.querySelectorAll('.taskRow').forEach(b=>b.onclick=()=>{selectedTaskId=b.dataset.id;render();setMsg('Stop selected. Driver actions now use this stop.')});
  }

  async function login(){const code=$('passcode').value.trim();if(code)passcode=code;if(!passcode)return setMsg('Enter your driver passcode.','bad');try{const r=await fetch('/driver/me',{headers:headers()});if(!r.ok)throw 0;driver=await r.json();localStorage.setItem(PASSCODE_KEY,passcode);$('login').hidden=true;$('app').hidden=false;await loadTasks();await syncQueue()}catch{setMsg('Driver login failed.','bad')}}
  async function loadTasks(){try{const r=await fetch('/driver/tasks',{headers:headers()});if(!r.ok)throw 0;const d=await r.json();tasks=d.results||[];if(selectedTaskId&&!tasks.some(t=>String(t.id)===String(selectedTaskId)))selectedTaskId=null;render()}catch{setMsg('Could not load tasks.','bad')}}
  function baseParams(t){return{route_id:t?.route_id||t?.route_number||null,stop_id:t?.id||null,task_id:t?.id||null,shipment_id:t?.shipment_id||t?.shipment_number||null,task_number:t?.task_number||null,location_text:t?.location_text||null}}

  async function postCommand(ucode,parameters,requestId,allowOffline=false){const body={ucode,parameters,client_request_id:requestId||reqId(),actor_id:driver?.id||driver?.driver_id||driver?.name||'DRIVER',role:'DRIVER',device_id:deviceId(),offline:false};try{const r=await fetch('/api/ugatu/execute',{method:'POST',headers:headers(true),body:JSON.stringify(body)});if(!r.ok){const e=await r.json().catch(()=>({}));throw new Error(e.detail||`UGATU rejected ${ucode}`)}return await r.json()}catch(e){if(allowOffline&&(!navigator.onLine||String(e.message).includes('Failed to fetch'))){const q=queue();q.push({kind:'command',body,createdAt:new Date().toISOString()});saveQueue(q);render();return{queued:true,ucode}}throw e}}
  async function postTaskStatus(t,status,photo=null,note=''){const fd=new FormData();fd.append('status',status);if(note)fd.append('note',note);if(photo)fd.append('photo',photo);const r=await fetch(`/dispatch/tasks/${encodeURIComponent(t.id)}/status`,{method:'POST',headers:headers(),body:fd});if(!r.ok){const e=await r.json().catch(()=>({}));throw new Error(e.detail||`Could not move stop to ${status.replaceAll('_',' ')}`)}return await r.json()}

  async function arrive(){const t=selectedTask();if(!t)return setMsg('Select a stop first.','bad');if(!navigator.onLine)return setMsg('Arrival needs a connection so dispatch sees your stop status immediately.','warn');try{let current=String(t.status||'assigned');if(current==='assigned'){await postTaskStatus(t,travelStatus(t));current=travelStatus(t)}if(current===travelStatus(t))await postTaskStatus(t,arrivedStatus(t));else if(current!==arrivedStatus(t))throw new Error(`This stop cannot be marked arrived from ${current.replaceAll('_',' ')}.`);await postCommand('U-1830',{...baseParams(t),stop_type:taskMode(t)},reqId(),false);await loadTasks();setMsg('Arrived at stop · U-1830')}catch(e){setMsg(e.message||'Could not record arrival.','bad')}}
  async function openWork(){const t=selectedTask();if(!t)return setMsg('Select a stop first.','bad');if(!isArrived(t))return setMsg('Tap ARRIVE before opening stop work.','bad');try{await postCommand('U-1840',{...baseParams(t),stop_type:taskMode(t),action:'OPEN_STOP_WORK'},reqId(),true);markOpened(t);render();setMsg('Stop work opened · U-1840')}catch(e){setMsg(e.message||'Could not open stop work.','bad')}}

  async function executeScan(payload){const t=tasks.find(x=>String(x.id)===String(payload.taskId))||selectedTask();if(!t)return setMsg('Select an active stop before scanning.','bad'),false;if(!isArrived(t))return setMsg('Record ARRIVE before scanning freight at this stop.','bad'),false;if(!hasOpened(t))return setMsg('Tap WORK STOP before scanning freight.','bad'),false;const mode=payload.mode,expected=taskMode(t);if(mode!==expected)return setMsg(`Selected stop is ${expected}. Change stop instead of forcing a ${mode} scan.`,'bad'),false;const allowed=expectedIds(t);const scanned=String(payload.item).trim().toUpperCase();if(allowed.length&&!allowed.includes(scanned))return setMsg('This package/freight ID does not match the selected stop.','bad'),false;const ucode=mode==='PICKUP'?'U-1550':mode==='HANDOFF'?'U-1570':'U-1560';try{const out=await postCommand(ucode,{...baseParams(t),package_id:payload.item,scan_mode:mode},payload.requestId,true);markScan(t,mode,payload.item,!!out.queued);if(out.queued)setMsg(`${mode} saved offline. It will sync automatically.`,'warn');else setMsg(`${mode} recorded · ${out.ucode}`);$('scanValue').value='';render();return true}catch(e){setMsg(e.message||'Scan failed.','bad');return false}}

  async function syncQueue(){if(!navigator.onLine)return;const q=queue();if(!q.length)return;const left=[];for(const item of q){try{const r=await fetch('/api/ugatu/execute',{method:'POST',headers:headers(true),body:JSON.stringify({...item.body,offline:false})});if(!r.ok)throw 0}catch{left.push(item)}}saveQueue(left);render();if(q.length&&!left.length)setMsg(`${q.length} offline transaction${q.length===1?'':'s'} synchronized.`);else if(left.length)setMsg(`${left.length} transaction${left.length===1?'':'s'} still waiting to sync.`,'warn')}

  function openScan(){const t=selectedTask();if(!t)return setMsg('Select an active stop first.','bad');if(!isArrived(t))return setMsg('Tap ARRIVE first.','bad');if(!hasOpened(t))return setMsg('Tap WORK STOP first.','bad');$('scanMode').value=taskMode(t);$('scanMode').disabled=true;$('scanContext').textContent=`${t.location_text||'Selected stop'} · ${t.task_number||''}`;$('scanSheet').hidden=false;$('scanValue').focus()}
  function closeScan(){$('scanSheet').hidden=true}
  async function submitScan(){const item=$('scanValue').value.trim();if(!item)return setMsg('Scan or enter a package/freight ID.','bad');const t=selectedTask();const ok=await executeScan({mode:$('scanMode').value,item,taskId:t?.id,requestId:reqId()});if(ok)closeScan()}

  function openComplete(){const t=selectedTask();if(!t)return setMsg('Select a stop first.','bad');if(!isArrived(t)||!hasOpened(t)||!hasScan(t))return setMsg('ARRIVE, WORK STOP and SCAN must be completed first.','bad');$('completeContext').textContent=`${taskMode(t)} · ${t.location_text||''} ${t.task_number?'· '+t.task_number:''}`;$('proofRecipient').value='';$('proofNotes').value='';$('proofPhoto').value='';$('completeSheet').hidden=false}
  function closeComplete(){$('completeSheet').hidden=true}
  async function submitComplete(){const t=selectedTask();if(!t)return;const photo=$('proofPhoto').files[0];if(!photo)return setMsg('Take a proof photo before completing this stop.','bad');if(!navigator.onLine)return setMsg('Stop completion needs a connection to upload proof. Your scan remains saved.','warn');const proof=proofUCode(t);const recipient=$('proofRecipient').value.trim(),notes=$('proofNotes').value.trim();try{await postCommand(proof,{...baseParams(t),recipient_name:recipient,notes,proof_type:taskMode(t)},reqId(),false);await postTaskStatus(t,completeStatus(t),photo,notes||`UGATU ${proof} proof captured`);const finishedId=t.id;clearStopState(finishedId);closeComplete();const previousIndex=tasks.findIndex(x=>String(x.id)===String(finishedId));await loadTasks();const remaining=activeTasks().filter(x=>String(x.id)!==String(finishedId));if(remaining.length){const next=remaining[Math.max(0,Math.min(previousIndex,remaining.length-1))]||remaining[0];selectedTaskId=next.id;render();setMsg(`Stop completed · ${proof}. Next stop selected: ${next.location_text||next.task_number}`)}else{setMsg(`Stop completed · ${proof}. No other active stops.`)}}catch(e){setMsg(e.message||'Could not complete stop.','bad')}}

  function openDocs(){const t=selectedTask();if(!t)return setMsg('Select a stop to view its documents.','bad');$('docsTitle').textContent=t.shipment_number?`Documents · ${t.shipment_number}`:'Stop Documents';$('docsContext').textContent=`${t.location_text||''} ${t.task_number?'· '+t.task_number:''}`;$('docShipment').textContent=t.shipment_number||t.shipment_id||'Current shipment';$('docBol').href='/business-documents/bill-of-lading.html';$('docReceipt').href='/business-documents/receipt.html';$('docsSheet').hidden=false;postCommand('U-1600',{...baseParams(t),action:'OPEN_DOCUMENT_CENTER'},reqId(),false).catch(()=>{})}
  function closeDocs(){$('docsSheet').hidden=true}
  function openIssue(){const t=selectedTask();if(!t)return setMsg('Select the stop with the problem first.','bad');$('issueContext').textContent=`${taskMode(t)} · ${t.location_text||''} ${t.task_number?'· '+t.task_number:''}`;$('issueReason').value='CUSTOMER_UNAVAILABLE';$('issueNotes').value='';$('issueSheet').hidden=false}
  function closeIssue(){$('issueSheet').hidden=true}
  async function submitIssue(){const t=selectedTask();if(!t)return;const ucode=taskMode(t)==='PICKUP'?'U-1320':'U-1310';const reason=$('issueReason').value,notes=$('issueNotes').value.trim();try{const out=await postCommand(ucode,{...baseParams(t),reason_code:reason,notes},reqId(),true);closeIssue();setMsg(out.queued?'Issue saved offline and will sync.':`Issue reported · ${ucode}`,out.queued?'warn':'ok')}catch(e){setMsg(e.message||'Could not report issue.','bad')}}

  $('loginBtn').onclick=login;$('passcode').addEventListener('keydown',e=>{if(e.key==='Enter')login()});$('arriveBtn').onclick=arrive;$('workBtn').onclick=openWork;$('completeBtn').onclick=openComplete;$('completeClose').onclick=closeComplete;$('completeSubmit').onclick=submitComplete;$('scanBtn').onclick=openScan;$('scanClose').onclick=closeScan;$('scanSubmit').onclick=submitScan;$('refreshBtn').onclick=loadTasks;$('syncBtn').onclick=syncQueue;$('ordersBtn').onclick=()=>document.querySelector('.tasks').scrollIntoView({behavior:'smooth'});$('docsBtn').onclick=openDocs;$('docsClose').onclick=closeDocs;$('issueBtn').onclick=openIssue;$('issueClose').onclick=closeIssue;$('issueSubmit').onclick=submitIssue;$('ordersNav').onclick=()=>document.querySelector('.tasks').scrollIntoView({behavior:'smooth'});window.addEventListener('online',syncQueue);if(passcode)login();
})();