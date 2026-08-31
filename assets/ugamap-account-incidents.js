(() => {
  const TOKEN_KEY='ugamap_account_token_v1';
  const nativeFetch=window.fetch.bind(window);
  const token=()=>localStorage.getItem(TOKEN_KEY)||'';
  const auth=()=>token()?{'Authorization':'Bearer '+token()}:{};

  // Transparently attach the signed-in account to incident writes already made by app.js.
  window.fetch=async function(input,init={}){
    const url=typeof input==='string'?input:(input&&input.url)||'';
    const isIncidentWrite=(/\/report(?:$|\?)/.test(url) || /\/reports\/[^/]+\/confirm(?:$|\?)/.test(url));
    if(isIncidentWrite){
      const headers=new Headers(init.headers||{});
      if(token()) headers.set('Authorization','Bearer '+token());
      init={...init,headers};
    }
    const response=await nativeFetch(input,init);
    if(isIncidentWrite && response.status===401){
      const btn=document.getElementById('ugAcctBtn');
      if(btn) setTimeout(()=>btn.click(),0);
      setTimeout(()=>{
        const msg=document.getElementById('ugAcctMsg');
        if(msg){msg.textContent='Sign in to submit or confirm incident reports.';msg.style.color='#fca5a5';}
      },30);
    }
    return response;
  };

  function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
  function time(ts){try{return new Date(Number(ts)*1000).toLocaleString();}catch(_){return '';}}

  async function showMyReports(){
    if(!token()) return;
    const holder=document.getElementById('ugMyReportsList');
    if(holder) holder.innerHTML='<div class="ugAcctSmall">Loading reports…</div>';
    try{
      const r=await nativeFetch('/account/my-reports',{headers:auth()});
      const d=await r.json();
      if(!r.ok) throw new Error(d.detail||('HTTP '+r.status));
      const rows=Array.isArray(d.results)?d.results:[];
      if(!holder)return;
      if(!rows.length){holder.innerHTML='<div class="ugAcctSmall">You have not submitted any reports yet.</div>';return;}
      holder.innerHTML=rows.map(x=>'<div style="border:1px solid #334155;border-radius:10px;padding:9px;margin-top:8px">'
        +'<b>'+esc(String(x.category||'incident').replace(/_/g,' '))+'</b> · '+esc(String(x.status||'new').toUpperCase())
        +(x.note?'<div style="margin-top:4px">'+esc(x.note)+'</div>':'')
        +'<div class="ugAcctSmall">'+esc(time(x.created_at))+' · '+Number(x.confirm_yes||0)+' confirmed · '+Number(x.confirm_no||0)+' not there</div>'
        +'</div>').join('');
    }catch(e){if(holder)holder.innerHTML='<div style="color:#fca5a5;font-size:12px">'+esc(e.message)+'</div>';}
  }

  function install(){
    const profile=document.getElementById('ugAcctProfile');
    if(!profile || document.getElementById('ugMyReports'))return false;
    const section=document.createElement('div');section.id='ugMyReports';
    section.innerHTML='<hr style="border:0;border-top:1px solid #334155;margin:16px 0"><div style="display:flex;justify-content:space-between;align-items:center;gap:8px"><b>My Reports</b><button id="ugRefreshReports" class="secondary" type="button">Refresh</button></div><div id="ugMyReportsList" class="ugAcctSmall" style="margin-top:6px">Open your profile to load reports.</div>';
    const logout=document.getElementById('ugLogout');
    profile.insertBefore(section,logout?logout.previousElementSibling:null);
    const btn=document.getElementById('ugRefreshReports');if(btn)btn.onclick=showMyReports;
    const acct=document.getElementById('ugAcctBtn');if(acct)acct.addEventListener('click',()=>setTimeout(showMyReports,150));
    return true;
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>{let n=0;const t=setInterval(()=>{if(install()||++n>30)clearInterval(t);},100);});
  else {let n=0;const t=setInterval(()=>{if(install()||++n>30)clearInterval(t);},100);}
})();
