(()=>{
  const WORKSPACE_SELECTOR='.workspace';
  const originalSelect=window.selectModule;
  if(typeof originalSelect==='function'){
    window.selectModule=function(i){
      originalSelect(i);
      const workspace=document.querySelector(WORKSPACE_SELECTOR);
      if(workspace){
        workspace.setAttribute('tabindex','-1');
        requestAnimationFrame(()=>{
          workspace.scrollIntoView({behavior:'smooth',block:'start'});
          try{workspace.focus({preventScroll:true})}catch(_e){}
        });
      }
    };
  }

  // The old page checked /health, which is not guaranteed to exist in the
  // production composition. Use the production startup endpoint instead.
  window.health=async function(){
    const state=document.getElementById('state');
    try{
      const response=await fetch('/system/startup-status',{cache:'no-store'});
      if(!response.ok) throw new Error('HTTP '+response.status);
      const data=await response.json();
      state.textContent=data.process_alive===false?'NETWORK ERROR':'NETWORK ONLINE';
    }catch(_e){
      state.textContent='NETWORK ERROR';
    }
  };

  // On phones make it obvious that each card opens a real working console.
  const style=document.createElement('style');
  style.textContent=`
    @media(max-width:480px){
      .service{min-height:112px;cursor:pointer;touch-action:manipulation}
      .service:after{content:'OPEN WORKSPACE  ›';display:block;margin-top:10px;font-size:10px;color:#7ec3ff;font-weight:900}
      .workspace{scroll-margin-top:92px}
      .workspace h2{margin-top:0}
    }
  `;
  document.head.appendChild(style);
  window.health();
})();
