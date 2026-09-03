(() => {
  const PASSCODE_KEY='driver_passcode';
  const $=id=>document.getElementById(id);
  const passcode=()=>localStorage.getItem(PASSCODE_KEY)||'';
  const headers=json=>{const h={'x-driver-passcode':passcode()};if(json)h['Content-Type']='application/json';return h};
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const msg=(text,type='ok')=>{const b=$('ugatuMsg');if(!b)return;b.className='notice '+type;b.textContent=text;b.hidden=false;clearTimeout(msg.t);msg.t=setTimeout(()=>b.hidden=true,4200)};
  let alerts=[];

  function injectUI(){
    const nav=[...document.querySelectorAll('.bottom button')].find(b=>b.textContent.trim()==='TASKS');
    if(nav&&!nav.id)nav.id='tasksNav';
    if(!$('taskAlertSheet'))document.body.insertAdjacentHTML('beforeend',`<div id="taskAlertSheet" class="overlay" hidden><div class="sheet"><div class="sheetHead"><h2>Tasks & Alerts <span id="taskUnreadBadge" style="font-size:12px;background:#dc2626;color:white;border-radius:999px;padding:4px 8px">0</span></h2><button id="taskAlertClose">Close</button></div><div id="taskAlertSummary" class="context">Loading…</div><div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:7px;margin-bottom:12px"><button id="taskFilterAll" class="primary" style="margin:0;min-height:44px">ALL</button><button id="taskFilterUnread" style="border:0;border-radius:12px;font-weight:900">UNREAD</button><button id="taskFilterUrgent" style="border:0;border-radius:12px;font-weight:900">URGENT</button></div><div id="taskAlertList"></div></div></div>`);
    if(!$('taskAlertBadge')){
      const b=document.createElement('span');b.id='taskAlertBadge';b.hidden=true;b.style.cssText='position:fixed;right:69px;bottom:58px;z-index:12;background:#dc2626;color:#fff;border-radius:999px;min-width:22px;height:22px;padding:0 6px;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:900';document.body.appendChild(b);
    }
  }

  async function loadCenter(){const r=await fetch('/api/ugatu/driver-center',{headers:headers(false)});if(!r.ok){const e=await r.json().catch(()=>({}));throw new Error(e.detail||'Could not load tasks and alerts')}return await r.json()}
  async function markRead(id){await fetch(`/api/ugatu/driver-center/${encodeURIComponent(id)}/read`,{method:'POST',headers:headers(true),body:'{}'}).catch(()=>{});const a=alerts.find(x=>x.id===id);if(a)a.read=true;updateBadge()}
  function updateBadge(){const n=alerts.filter(a=>!a.read).length;const b=$('taskAlertBadge');if(b){b.textContent=n>99?'99+':String(n);b.hidden=!n}$('taskUnreadBadge').textContent=n}
  function selectStop(taskId){if(!taskId)return false;const row=document.querySelector(`.taskRow[data-id="${CSS.escape(String(taskId))}"]`);if(row){row.click();return true}return false}
  function navigate(a){if(a.latitude!=null&&a.longitude!=null)window.location.href=`/?destination=${encodeURIComponent(`${a.latitude},${a.longitude}`)}`;else window.location.href=`/?destination=${encodeURIComponent(a.location_text||'')}`}
  function action(a){
    markRead(a.id);
    if(a.kind==='vehicle'){msg(a.message,'bad');return}
    if(!a.task_id)return;
    if(!selectStop(a.task_id)){msg('This task is no longer in the active stop list.','warn');return}
    $('taskAlertSheet').hidden=true;
    if(a.kind==='document')return setTimeout(()=>$('docsBtn')?.click(),50);
    if(a.kind==='late')return setTimeout(()=>$('issueBtn')?.click(),50);
    if(a.kind==='pickup'||a.kind==='urgent'||a.kind==='assignment')return setTimeout(()=>$('scanBtn')?.click(),50);
  }
  function card(a){const p=a.priority||'NORMAL';const bg=p==='URGENT'?'#fef2f2':p==='HIGH'?'#fff7ed':'#f8fafc';const border=p==='URGENT'?'#fecaca':p==='HIGH'?'#fed7aa':'#e5e7eb';return `<div class="context" style="background:${bg};border:1px solid ${border};padding:14px;opacity:${a.read?.72:1}"><div style="display:flex;justify-content:space-between;gap:8px"><div><b>${esc(a.title)}</b><br><small>${esc(a.ucode||'')}</small></div><span style="font-size:10px;font-weight:900">${esc(p)}</span></div><div style="margin-top:7px">${esc(a.message)}</div>${a.task_number?`<small>${esc(a.task_number)} · ${esc(String(a.status||'').replaceAll('_',' '))}</small>`:''}<div style="display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-top:10px"><button class="taskAct" data-id="${esc(a.id)}" style="min-height:42px;border:0;border-radius:10px;background:#111827;color:#fff;font-weight:900">OPEN ACTION</button>${a.task_id?`<button class="taskNav" data-id="${esc(a.id)}" style="min-height:42px;border:0;border-radius:10px;font-weight:900">NAVIGATE</button>`:`<button class="taskRead" data-id="${esc(a.id)}" style="min-height:42px;border:0;border-radius:10px;font-weight:900">MARK READ</button>`}</div></div>`}
  function render(filter='ALL'){let rows=alerts;if(filter==='UNREAD')rows=rows.filter(a=>!a.read);if(filter==='URGENT')rows=rows.filter(a=>a.priority==='URGENT'||a.priority==='HIGH');$('taskAlertList').innerHTML=rows.map(card).join('')||'<div class="empty">No matching tasks or alerts.</div>';document.querySelectorAll('.taskAct').forEach(b=>b.onclick=()=>action(alerts.find(a=>a.id===b.dataset.id)));document.querySelectorAll('.taskNav').forEach(b=>b.onclick=()=>{const a=alerts.find(x=>x.id===b.dataset.id);markRead(a.id);navigate(a)});document.querySelectorAll('.taskRead').forEach(b=>b.onclick=()=>{markRead(b.dataset.id);render(filter)})}
  async function openCenter(filter='ALL'){if(!passcode())return msg('Log in first.','bad');try{const out=await loadCenter();alerts=out.results||[];$('taskAlertSummary').innerHTML=`<strong>${out.count||0}</strong> active tasks/alerts · <strong>${out.unread_count||0}</strong> unread`;updateBadge();render(filter);$('taskAlertSheet').hidden=false}catch(e){msg(e.message||'Could not load tasks and alerts.','bad')}}
  async function refreshBadge(){if(!passcode())return;try{const out=await loadCenter();alerts=out.results||[];updateBadge()}catch{}}

  injectUI();
  $('tasksNav')?.addEventListener('click',e=>{e.preventDefault();e.stopImmediatePropagation();openCenter('ALL')},true);
  $('taskAlertClose')?.addEventListener('click',()=>{$('taskAlertSheet').hidden=true});
  $('taskFilterAll')?.addEventListener('click',()=>render('ALL'));
  $('taskFilterUnread')?.addEventListener('click',()=>render('UNREAD'));
  $('taskFilterUrgent')?.addEventListener('click',()=>render('URGENT'));
  setTimeout(refreshBadge,900);setInterval(refreshBadge,30000);
})();