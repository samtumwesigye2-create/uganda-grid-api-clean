(() => {
  const $=id=>document.getElementById(id);
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const msg=(text,type='ok')=>{const b=$('ugatuMsg');if(!b)return;b.className='notice '+type;b.textContent=text;b.hidden=false;clearTimeout(msg.t);msg.t=setTimeout(()=>b.hidden=true,4600)};

  function installOverlayHiddenFix(){
    if($('ugatuOverlayHiddenFix'))return;
    const style=document.createElement('style');
    style.id='ugatuOverlayHiddenFix';
    style.textContent='[hidden]{display:none!important}.overlay[hidden]{display:none!important}';
    document.head.appendChild(style);
  }

  async function secureState(){
    const api=window.UGATUOffline;
    if(!api)return {count:0,conflicts:[],rows:[],secure:false};
    try{
      const [count,rows,conflicts]=await Promise.all([api.count(),api.list(),api.conflicts()]);
      return {count:Number(count||0),rows:Array.isArray(rows)?rows:[],conflicts:Array.isArray(conflicts)?conflicts:[],secure:true};
    }catch{return {count:0,conflicts:[],rows:[],secure:true,error:true}}
  }

  async function guardRouteClose(e){
    if(!e.isTrusted)return;
    const state=await secureState();
    if(!state.secure)return;
    if(state.count>0){
      e.preventDefault();e.stopImmediatePropagation();
      const conflictCount=state.conflicts.length;
      msg(conflictCount
        ? `Route close blocked · ${state.count} encrypted offline transaction(s), including ${conflictCount} conflict(s), must be reconciled.`
        : `Route close blocked · ${state.count} encrypted offline transaction(s) must synchronize first.`,'warn');
      if(conflictCount)$('ugatuConflictBtn')?.click();else $('syncBtn')?.click();
    }
  }

  async function openSecureOffline(e){
    e.preventDefault();e.stopImmediatePropagation();
    const state=await secureState();
    const title=$('moreListTitle'),summary=$('moreListSummary'),body=$('moreListBody'),sheet=$('moreListSheet');
    if(!title||!summary||!body||!sheet)return;
    title.textContent='Offline & Sync';
    const retry=state.rows.filter(x=>x.state==='RETRY').length;
    const queued=state.rows.filter(x=>!x.state||x.state==='QUEUED').length;
    summary.innerHTML=`<strong>${state.count}</strong> encrypted transaction(s) · <strong>${state.conflicts.length}</strong> conflict(s)`;
    body.innerHTML=`<div class="context"><b>${navigator.onLine?'ONLINE':'OFFLINE'}</b><br>${state.secure?'Encrypted IndexedDB queue active.':'Secure queue is not initialized yet.'}<br><small>${queued} queued · ${retry} retry · ${state.conflicts.length} conflict</small></div>`+
      (state.rows.slice(0,12).map(x=>`<div class="context"><b>${esc(x.ucode||x.body?.ucode||'UGATU')}</b> · ${esc(x.state||'QUEUED')}<br><small>${esc(x.id||'')} · ${esc(x.device_time||x.created_at||'')}</small>${x.last_error?`<br><small>${esc(x.last_error)}</small>`:''}</div>`).join('')||'<div class="empty">All offline transactions are clear.</div>')+
      `<button id="moreSecureSyncNow" class="primary">SYNC NOW</button>${state.conflicts.length?'<button id="moreSecureConflicts" style="width:100%;margin-top:8px;min-height:44px;border:0;border-radius:10px;font-weight:900;background:#fee2e2;color:#991b1b">REVIEW CONFLICTS</button>':''}`;
    sheet.hidden=false;
    setTimeout(()=>{
      $('moreSecureSyncNow')?.addEventListener('click',()=>{$('syncBtn')?.click();setTimeout(()=>openSecureOffline({preventDefault(){},stopImmediatePropagation(){}}),700)});
      $('moreSecureConflicts')?.addEventListener('click',()=>$('ugatuConflictBtn')?.click());
    },0);
  }

  function hook(){
    installOverlayHiddenFix();
    const close=$('completeRouteBtn');
    if(close&&!close.dataset.secureFinalGuard){close.dataset.secureFinalGuard='1';close.addEventListener('click',guardRouteClose,true)}
    const offline=document.querySelector('[data-more="offline"]');
    if(offline&&!offline.dataset.secureFinalHook){offline.dataset.secureFinalHook='1';offline.addEventListener('click',openSecureOffline,true)}
  }

  hook();
  setInterval(hook,4000);
  document.addEventListener('ugatu-offline-change',hook);
})();
