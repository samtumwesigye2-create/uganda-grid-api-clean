(function(){
  function loadScript(src,ready,cb){
    if(ready()) return cb();
    var s=document.createElement('script');s.src=src;s.onload=cb;s.onerror=function(){console.error('UGATU dependency failed: '+src);};document.head.appendChild(s);
  }
  function boot(){
    loadScript('/ugatu/ucodes.js',function(){return !!window.UGATU;},function(){
      loadScript('/ugatu/roles.js',function(){return !!window.UGATURoles;},install);
    });
  }
  function install(){
    if(document.getElementById('ugatuCommandBar')) return;
    var style=document.createElement('style');style.textContent=`#ugatuCommandBar{grid-column:1/-1;display:flex;align-items:center;gap:8px;background:#0d1826;border:1px solid #1d2b3d;border-radius:10px;padding:10px 12px;position:sticky;top:0;z-index:90;box-shadow:0 8px 24px rgba(0,0,0,.22)}#ugatuCommandBar .ugatu-label{font-size:11px;font-weight:800;letter-spacing:.08em;color:#8fa3ff;white-space:nowrap}#ugatuCommandInput{flex:1;min-width:120px;background:#07111e;color:#fff;border:1px solid #30425a;border-radius:7px;padding:9px 11px;text-transform:uppercase;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:14px;outline:none}#ugatuCommandInput:focus{border-color:#5e7cff;box-shadow:0 0 0 2px rgba(94,124,255,.15)}#ugatuGo{border:0;border-radius:7px;background:#3b5bfd;color:#fff;font-weight:800;padding:9px 15px;cursor:pointer}#ugatuStatus{font-size:11px;color:#8e93a8;min-width:120px;text-align:right;white-space:nowrap}#ugatuSuggest{position:fixed;z-index:999;background:#0d1826;border:1px solid #30425a;border-radius:8px;max-height:260px;overflow:auto;box-shadow:0 12px 30px rgba(0,0,0,.45);display:none}.ugatu-option{padding:9px 11px;cursor:pointer;font-size:12px;color:#dce3ee;border-bottom:1px solid #18263a}.ugatu-option:last-child{border-bottom:0}.ugatu-option:hover{background:#172b45}.ugatu-code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-weight:800;color:#8fa3ff;margin-right:10px}@media(max-width:650px){#ugatuCommandBar{gap:6px;padding:8px}.ugatu-label{display:none!important}#ugatuStatus{display:none}#ugatuGo{padding:9px 12px}}`;document.head.appendChild(style);
    var main=document.getElementById('main');if(!main)return;
    var bar=document.createElement('div');bar.id='ugatuCommandBar';bar.innerHTML='<div class="ugatu-label">UGATU COMMAND</div><input id="ugatuCommandInput" autocomplete="off" autocapitalize="characters" spellcheck="false" placeholder="Enter U-Code e.g. ZIP07"><button id="ugatuGo" type="button">GO</button><div id="ugatuStatus">Checking role…</div>';main.insertBefore(bar,main.firstChild);
    var sug=document.createElement('div');sug.id='ugatuSuggest';document.body.appendChild(sug);
    var input=document.getElementById('ugatuCommandInput'),status=document.getElementById('ugatuStatus'),currentRole='customer',currentUser=null;

    function localToken(){
      var keys=['ugatu_session_token_v1','auth_token','session_token','token'];
      for(var i=0;i<keys.length;i++){var v=localStorage.getItem(keys[i]);if(v)return v;}
      return '';
    }
    async function resolveRole(){
      if(window.UGATU_CURRENT_USER&&window.UGATU_CURRENT_USER.ugatu_role){currentUser=window.UGATU_CURRENT_USER;currentRole=currentUser.ugatu_role;showRole();return;}
      var token=localToken();
      if(token){
        try{var r=await fetch('/auth/me?token='+encodeURIComponent(token),{cache:'no-store'});if(r.ok){currentUser=await r.json();currentRole=currentUser.ugatu_role||'customer';window.UGATU_CURRENT_USER=currentUser;showRole();return;}}catch(_){ }
      }
      if(typeof window.PASS==='string'&&window.PASS){currentRole='administrator';showRole();return;}
      currentRole='customer';showRole();
    }
    function showRole(){status.textContent=String(currentRole||'customer').replace(/_/g,' ');}
    function authorized(code){return window.UGATURoles.ugatuAuthorize(currentRole,code);}
    function routeTransaction(tx){
      status.textContent=tx.code+' · '+tx.name;
      var route=tx.route||'',hash=route.indexOf('#')>=0?route.split('#')[1]:'',base=route.split('#')[0];
      if(base&&base!==location.pathname&&!(base==='/admin'&&location.pathname.indexOf('/admin')===0)){location.href=route;return;}
      if(hash){var map={'zip-create':'submissions','zip-edit':'submissions','zip-view':'submissions','zip-search':'submissions','zip-approve':'submissions','zip-assign':'submissions','zip-reassign':'submissions','zip-history':'submissions','zip-generate':'submissions','zip-population':'submissions','zip-reserve':'submissions','zip-special':'submissions','zip-coverage':'submissions','invoice-new':'invoices','invoice-edit':'invoices','invoice-view':'invoices','invoice-void':'invoices','invoices':'invoices','invoice-approve':'invoices','invoice-pdf':'invoices','bol-new':'bol','bol-edit':'bol','bol-view':'bol','bol-release':'bol','bol-export':'bol','receipt-new':'reports','receipt-view':'reports','receipt-void':'reports','receipts':'reports','receipt-print':'reports','security':'staff','mfa':'staff','sessions':'staff','session-revoke':'staff','security-audit':'staff','configuration':'data','status':'dashboard','services':'dashboard','approvals':'dashboard','audit':'data','database':'data','reports-operations':'analytics','reports-shipments':'analytics','reports-inventory':'analytics','reports-warehouse':'analytics','reports-zipper':'analytics','reports-finance':'analytics','reports-users':'analytics','reports-performance':'analytics','system':'dashboard','health':'dashboard','service-status':'dashboard','maintenance':'data','jobs':'data','releases':'data','logs':'data'};if(map[hash]&&typeof window.switchAdminTab==='function')window.switchAdminTab(map[hash]);location.hash=hash;}
    }
    function execute(){
      var code=(input.value||'').trim().toUpperCase();if(!code)return;
      var tx=window.UGATU.getUGATUTransaction(code);if(!tx){status.textContent='Unknown U-Code';input.select();return;}
      var auth=authorized(code);if(!auth.ok){status.textContent='Not authorized · '+code;input.select();hideSuggestions();return;}
      routeTransaction({code:code,name:tx.name,route:tx.route,permission:tx.permission});hideSuggestions();
    }
    function hideSuggestions(){sug.style.display='none';}
    function showSuggestions(){
      var q=(input.value||'').trim();if(!q){hideSuggestions();return;}
      var rows=window.UGATU.searchUGATU(q).filter(function(x){return authorized(x.code).ok;}).slice(0,8);if(!rows.length){hideSuggestions();return;}
      var r=input.getBoundingClientRect();sug.style.left=r.left+'px';sug.style.top=(r.bottom+4)+'px';sug.style.width=Math.max(r.width,300)+'px';sug.innerHTML=rows.map(function(x){return '<div class="ugatu-option" data-code="'+x.code+'"><span class="ugatu-code">'+x.code+'</span>'+x.name+'</div>';}).join('');sug.style.display='block';Array.from(sug.querySelectorAll('.ugatu-option')).forEach(function(el){el.onclick=function(){input.value=el.dataset.code;execute();};});
    }
    document.getElementById('ugatuGo').addEventListener('click',execute);input.addEventListener('keydown',function(e){if(e.key==='Enter'){e.preventDefault();execute();}if(e.key==='Escape')hideSuggestions();});input.addEventListener('input',showSuggestions);document.addEventListener('click',function(e){if(!bar.contains(e.target)&&!sug.contains(e.target))hideSuggestions();});window.addEventListener('resize',hideSuggestions);window.addEventListener('storage',resolveRole);window.UGATURefreshRole=resolveRole;resolveRole();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();
