(function(){
  function loadRegistry(cb){
    if(window.UGATU) return cb();
    var s=document.createElement('script');
    s.src='/ugatu/ucodes.js';
    s.onload=cb;
    s.onerror=function(){console.error('UGATU registry failed to load');};
    document.head.appendChild(s);
  }

  function install(){
    if(document.getElementById('ugatuCommandBar')) return;
    var style=document.createElement('style');
    style.textContent=`
      #ugatuCommandBar{grid-column:1/-1;display:flex;align-items:center;gap:8px;background:#0d1826;border:1px solid #1d2b3d;border-radius:10px;padding:10px 12px;position:sticky;top:0;z-index:90;box-shadow:0 8px 24px rgba(0,0,0,.22)}
      #ugatuCommandBar .ugatu-label{font-size:11px;font-weight:800;letter-spacing:.08em;color:#8fa3ff;white-space:nowrap}
      #ugatuCommandInput{flex:1;min-width:120px;background:#07111e;color:#fff;border:1px solid #30425a;border-radius:7px;padding:9px 11px;text-transform:uppercase;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:14px;outline:none}
      #ugatuCommandInput:focus{border-color:#5e7cff;box-shadow:0 0 0 2px rgba(94,124,255,.15)}
      #ugatuGo{border:0;border-radius:7px;background:#3b5bfd;color:#fff;font-weight:800;padding:9px 15px;cursor:pointer}
      #ugatuStatus{font-size:11px;color:#8e93a8;min-width:90px;text-align:right;white-space:nowrap}
      #ugatuSuggest{position:fixed;z-index:999;background:#0d1826;border:1px solid #30425a;border-radius:8px;max-height:260px;overflow:auto;box-shadow:0 12px 30px rgba(0,0,0,.45);display:none}
      .ugatu-option{padding:9px 11px;cursor:pointer;font-size:12px;color:#dce3ee;border-bottom:1px solid #18263a}.ugatu-option:last-child{border-bottom:0}.ugatu-option:hover{background:#172b45}.ugatu-code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-weight:800;color:#8fa3ff;margin-right:10px}
      @media(max-width:650px){#ugatuCommandBar{gap:6px;padding:8px}.ugatu-label{display:none!important}#ugatuStatus{display:none}#ugatuGo{padding:9px 12px}}
    `;
    document.head.appendChild(style);

    var main=document.getElementById('main');
    if(!main) return;
    var bar=document.createElement('div');
    bar.id='ugatuCommandBar';
    bar.innerHTML='<div class="ugatu-label">UGATU COMMAND</div><input id="ugatuCommandInput" autocomplete="off" autocapitalize="characters" spellcheck="false" placeholder="Enter U-Code e.g. ZIP07"><button id="ugatuGo" type="button">GO</button><div id="ugatuStatus">Ready</div>';
    main.insertBefore(bar, main.firstChild);
    var sug=document.createElement('div'); sug.id='ugatuSuggest'; document.body.appendChild(sug);

    var input=document.getElementById('ugatuCommandInput');
    var status=document.getElementById('ugatuStatus');

    function routeTransaction(tx){
      status.textContent=tx.code+' · '+tx.name;
      var route=tx.route || '';
      var hash=route.indexOf('#')>=0 ? route.split('#')[1] : '';
      var base=route.split('#')[0];
      if(base && base !== location.pathname && !(base==='/admin' && location.pathname.indexOf('/admin')===0)){
        location.href=route; return;
      }
      if(hash){
        var map={
          'zip-create':'submissions','zip-edit':'submissions','zip-view':'submissions','zip-search':'submissions','zip-approve':'submissions','zip-assign':'submissions','zip-reassign':'submissions','zip-history':'submissions','zip-generate':'submissions','zip-population':'submissions','zip-reserve':'submissions','zip-special':'submissions','zip-coverage':'submissions',
          'invoice-new':'invoices','invoice-edit':'invoices','invoice-view':'invoices','invoice-void':'invoices','invoices':'invoices','invoice-approve':'invoices','invoice-pdf':'invoices',
          'bol-new':'bol','bol-edit':'bol','bol-view':'bol','bol-release':'bol','bol-export':'bol',
          'receipt-new':'reports','receipt-view':'reports','receipt-void':'reports','receipts':'reports','receipt-print':'reports',
          'security':'staff','mfa':'staff','sessions':'staff','session-revoke':'staff','security-audit':'staff',
          'configuration':'data','status':'dashboard','services':'dashboard','approvals':'dashboard','audit':'data','database':'data',
          'reports-operations':'analytics','reports-shipments':'analytics','reports-inventory':'analytics','reports-warehouse':'analytics','reports-zipper':'analytics','reports-finance':'analytics','reports-users':'analytics','reports-performance':'analytics',
          'system':'dashboard','health':'dashboard','service-status':'dashboard','maintenance':'data','jobs':'data','releases':'data','logs':'data'
        };
        if(map[hash] && typeof window.switchAdminTab==='function') window.switchAdminTab(map[hash]);
        location.hash=hash;
      }
    }

    function execute(){
      var code=(input.value||'').trim().toUpperCase();
      if(!code) return;
      var res=window.UGATU.executeUGATU(code,['*']);
      if(!res.ok){status.textContent='Unknown U-Code'; input.select(); return;}
      routeTransaction(res);
      hideSuggestions();
    }
    function hideSuggestions(){sug.style.display='none';}
    function showSuggestions(){
      var q=(input.value||'').trim(); if(!q){hideSuggestions();return;}
      var rows=window.UGATU.searchUGATU(q).slice(0,8); if(!rows.length){hideSuggestions();return;}
      var r=input.getBoundingClientRect(); sug.style.left=r.left+'px'; sug.style.top=(r.bottom+4)+'px'; sug.style.width=Math.max(r.width,300)+'px';
      sug.innerHTML=rows.map(function(x){return '<div class="ugatu-option" data-code="'+x.code+'"><span class="ugatu-code">'+x.code+'</span>'+x.name+'</div>';}).join('');
      sug.style.display='block';
      Array.from(sug.querySelectorAll('.ugatu-option')).forEach(function(el){el.onclick=function(){input.value=el.dataset.code;execute();};});
    }

    document.getElementById('ugatuGo').addEventListener('click',execute);
    input.addEventListener('keydown',function(e){if(e.key==='Enter'){e.preventDefault();execute();} if(e.key==='Escape')hideSuggestions();});
    input.addEventListener('input',showSuggestions);
    document.addEventListener('click',function(e){if(!bar.contains(e.target)&&!sug.contains(e.target))hideSuggestions();});
    window.addEventListener('resize',hideSuggestions);
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',function(){loadRegistry(install);}); else loadRegistry(install);
})();
