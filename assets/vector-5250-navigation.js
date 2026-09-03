(function(){
  'use strict';
  if(window.__VECTOR5250_NAV__) return;
  window.__VECTOR5250_NAV__=true;

  const state={history:[],index:-1,authorized:false,commands:{},lastRefresh:0};
  const $=id=>document.getElementById(id);
  const esc=v=>String(v==null?'':v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  function accessCode(){return (($('dashCode')&&$('dashCode').value)||localStorage.getItem('vector5250-access')||'').trim();}
  function warehouseId(){return (($('dashWarehouse')&&$('dashWarehouse').value)||localStorage.getItem('warehouse-command-id')||'main').trim()||'main';}
  function setMessage(text,type){const m=$('v5250msg');if(!m)return;m.textContent=text||'';m.dataset.type=type||'info';}
  function pushHistory(command){if(!command)return; if(state.history[state.history.length-1]!==command)state.history.push(command);state.index=state.history.length;}
  function focusCommand(){const i=$('v5250cmd');if(i){i.focus();i.select();}}

  async function authorize(showError=true){
    const code=accessCode();
    if(!code){state.authorized=false;if(showError)setMessage('ACCESS CODE REQUIRED','error');return false;}
    localStorage.setItem('vector5250-access',code);
    try{
      const r=await fetch('/warehouse/manager/session',{headers:{'x-access-code':code},cache:'no-store'});
      const d=await r.json().catch(()=>({}));
      if(!r.ok)throw new Error(d.detail||'ACCESS DENIED');
      state.authorized=true;state.commands=d.commands||{};
      setMessage('MANAGER SESSION ACTIVE · '+String(d.role||'warehouse_manager').toUpperCase(),'ok');
      return true;
    }catch(e){state.authorized=false;if(showError)setMessage(String(e.message||'ACCESS DENIED').toUpperCase(),'error');return false;}
  }

  function scrollToElement(el){if(!el)return false;el.scrollIntoView({behavior:'smooth',block:'start'});return true;}
  function openLayerSafe(name){if(typeof window.openLayer==='function'){window.openLayer(name);return true;}const b=document.querySelector('.layer[data-op="'+name+'"]');if(b){b.click();return true;}return false;}
  function showDashboard(){window.scrollTo({top:0,behavior:'smooth'});if(typeof window.loadDashboard==='function')window.loadDashboard();return true;}
  function showExceptions(){const boxes=document.querySelector('.alertGrid');if(scrollToElement(boxes))return true;return false;}
  function showDocuments(){return scrollToElement(document.querySelector('.panel .docs')||$('docs'));}
  function showRecent(){return scrollToElement($('recent')||document.querySelector('.recent'));}
  function showSearch(){const q=prompt('Search warehouse reference, SKU, location or U-Code');if(!q)return true;const needle=q.trim().toLowerCase();let hit=null;document.querySelectorAll('#recent tr').forEach(tr=>{if(!hit&&tr.textContent.toLowerCase().includes(needle))hit=tr;});if(hit){hit.scrollIntoView({behavior:'smooth',block:'center'});hit.style.outline='3px solid #35d07f';setTimeout(()=>hit.style.outline='',1800);setMessage('MATCH FOUND: '+q,'ok');}else setMessage('NO RECENT MATCH: '+q,'error');return true;}
  function showFavorites(){setMessage('FAVORITES: 0 DASHBOARD · 1 EXCEPTIONS · 2 DISPATCH · 4 WAREHOUSE · 5 DOCUMENTS','info');return true;}
  function showOrders(){location.href='/ship#orders';return true;}
  function showAlertsTasks(){const box=document.querySelector('.alertGrid');if(box)box.scrollIntoView({behavior:'smooth',block:'start'});setMessage('ALERTS & TASKS CENTER','ok');return true;}
  function showWarehouse(){const grid=$('layers');if(grid)grid.scrollIntoView({behavior:'smooth',block:'start'});return true;}

  function routeTarget(target){
    const map={dashboard:showDashboard,exceptions:showExceptions,dispatch:()=>openLayerSafe('dispatch'),orders:showOrders,warehouse:showWarehouse,documents:showDocuments,alerts:showAlertsTasks,search:showSearch,recent:showRecent,favorites:showFavorites};
    const fn=map[target];return fn?fn():false;
  }

  async function execute(raw){
    const command=String(raw||'').trim().toUpperCase();if(!command)return;
    pushHistory(command);
    if(!(await authorize())){focusCommand();return;}
    const normalized=command.replace(/^U\s*/,'U-').replace(/^U--/,'U-');
    const tx=state.commands[normalized]||state.commands[command];
    if(!tx){setMessage('INVALID COMMAND: '+command,'error');focusCommand();return;}
    const ok=routeTarget(tx.target);
    setMessage(ok?normalized+' · '+tx.label:'COMMAND UNAVAILABLE: '+normalized,ok?'ok':'error');
    const i=$('v5250cmd');if(i){i.value='';i.focus();}
  }

  function goBack(){if(history.length>1)history.back();else window.scrollTo({top:0,behavior:'smooth'});setMessage('F3 · BACK','info');}
  function refresh(){state.lastRefresh=Date.now();if(typeof window.loadDashboard==='function')window.loadDashboard();setMessage('F5 · REFRESH REQUESTED','ok');}
  function cancel(){const modal=$('modal');if(modal&&modal.classList.contains('open'))modal.classList.remove('open');const scan=$('scanModal');if(scan&&scan.classList.contains('open')&&typeof window.stopScan==='function')window.stopScan();setMessage('F12 · CANCEL','info');focusCommand();}

  function install(){
    const main=document.querySelector('main.wrap')||document.body;if(!main||$('vector5250'))return;
    const style=document.createElement('style');style.textContent=`#vector5250{background:#020b06;color:#8cffad;border:1px solid #173d26;border-radius:14px;padding:14px 16px;margin:0 0 14px;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;box-shadow:0 12px 30px #0002}#vector5250 .vrow{display:flex;gap:10px;align-items:center;flex-wrap:wrap}#vector5250 .vtitle{font-weight:900;letter-spacing:.06em;color:#c9ffd6}#vector5250 .vsub{font-size:12px;color:#6dbe82;margin-top:4px}#vector5250 .vcmd{display:grid;grid-template-columns:auto 1fr auto;gap:8px;align-items:center;margin-top:12px}#v5250cmd{min-width:0;width:100%;background:#001c0c;border:1px solid #2b7042;color:#dcffe6;border-radius:6px;padding:11px 12px;font:700 16px ui-monospace,SFMono-Regular,Menlo,monospace;text-transform:uppercase;outline:none}#v5250cmd:focus{border-color:#6dff9b;box-shadow:0 0 0 2px #6dff9b22}.vgo,.vf{border:1px solid #356f47;background:#0b2a15;color:#c9ffd6;border-radius:6px;padding:10px 12px;font-weight:800;cursor:pointer}.vkeys{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}.vkey{font-size:11px}.vmenu{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:6px;margin-top:10px}.vmenu button{background:#06150b;color:#9ee9b1;border:1px solid #1f5030;border-radius:6px;padding:8px;text-align:left;font:600 11px ui-monospace,SFMono-Regular,Menlo,monospace;cursor:pointer}#v5250msg{margin-top:9px;font-size:12px;min-height:16px}#v5250msg[data-type=error]{color:#ff7d7d}#v5250msg[data-type=ok]{color:#83ffab}#v5250msg[data-type=info]{color:#7dcfff}@media(max-width:650px){#vector5250{border-radius:10px;padding:12px}.vmenu{grid-template-columns:repeat(2,1fr)}#vector5250 .vcmd{grid-template-columns:1fr}.vlabel{display:none}.vgo{width:100%}}`;document.head.appendChild(style);
    const box=document.createElement('section');box.id='vector5250';box.innerHTML=`<div class="vrow"><div><div class="vtitle">VECTOR 5250 OPERATIONS</div><div class="vsub">WAREHOUSE MANAGER COMMAND TERMINAL · MANAGER AND ABOVE ONLY</div></div></div><div class="vcmd"><span class="vlabel">COMMAND ==&gt;</span><input id="v5250cmd" autocomplete="off" autocapitalize="characters" spellcheck="false" aria-label="Vector 5250 command"><button class="vgo" id="v5250go" type="button">ENTER</button></div><div class="vmenu"><button data-cmd="0">0 Manager Dashboard</button><button data-cmd="1">1 Exceptions</button><button data-cmd="2">2 Dispatch</button><button data-cmd="3">3 Orders</button><button data-cmd="4">4 Warehouse</button><button data-cmd="5">5 Documents</button><button data-cmd="6">6 Alerts & Tasks</button><button data-cmd="7">7 Search</button><button data-cmd="8">8 Recent</button><button data-cmd="9">9 Favorites</button></div><div class="vkeys"><button class="vf vkey" data-key="F3">F3 Back</button><button class="vf vkey" data-key="F5">F5 Refresh</button><button class="vf vkey" data-key="F9">F9 History</button><button class="vf vkey" data-key="F12">F12 Cancel</button></div><div id="v5250msg" data-type="info">ENTER ACCESS CODE ABOVE, THEN TYPE 0–9 OR A U-CODE</div>`;
    main.insertBefore(box,main.firstChild);
    $('v5250go').onclick=()=>execute($('v5250cmd').value);
    $('v5250cmd').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();execute(e.currentTarget.value);}else if(e.key==='ArrowUp'){e.preventDefault();if(state.history.length){state.index=Math.max(0,state.index-1);e.currentTarget.value=state.history[state.index]||'';}}else if(e.key==='ArrowDown'){e.preventDefault();if(state.history.length){state.index=Math.min(state.history.length,state.index+1);e.currentTarget.value=state.index===state.history.length?'':state.history[state.index]||'';}}else if(e.key==='F3'){e.preventDefault();goBack();}else if(e.key==='F5'){e.preventDefault();refresh();}else if(e.key==='F12'){e.preventDefault();cancel();}});
    box.querySelectorAll('[data-cmd]').forEach(b=>b.onclick=()=>execute(b.dataset.cmd));
    box.querySelectorAll('[data-key]').forEach(b=>b.onclick=()=>{const k=b.dataset.key;if(k==='F3')goBack();if(k==='F5')refresh();if(k==='F9'){setMessage('HISTORY: '+(state.history.slice(-8).join(' · ')||'EMPTY'),'info');}if(k==='F12')cancel();});
    const dc=$('dashCode');if(dc)dc.addEventListener('change',()=>authorize(false));
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install);else install();
})();
