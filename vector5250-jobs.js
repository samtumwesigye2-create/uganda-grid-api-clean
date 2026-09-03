(function(){
'use strict';
const core=()=>window.VECTOR5250;
const $=id=>document.getElementById(id);
const host=()=>document.getElementById('hostScreen');
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const headers=()=>({'x-access-code':sessionStorage.getItem('vector5250-access')||'','x-vector-user':core()?.state?.user||'SYSTEM'});
let previous='main',heartbeatTimer=null,activeSession=false;

function setHeader(code){const e=$('screenCode');if(e)e.textContent=code;}
function setMsg(text,type=''){const e=$('msg');if(!e)return;e.textContent=text||'';e.className='msg '+type;}
function cmdline(extra=''){
 return '<div class="command-area"><div class="commandline"><label>COMMAND ==&gt;</label><input id="cmd" class="hostinput" autocomplete="off" autocapitalize="characters" spellcheck="false"></div></div><div class="keys">'+extra+'<button class="key" data-vjob-key="F3">F3=BACK</button><button class="key" data-vjob-key="F5">F5=REFRESH</button><button class="key" data-vjob-key="F12">F12=CANCEL</button></div>';
}
function beginCustom(name){const c=core();if(!c?.state?.signedOn)return false;previous=c.state.current||'main';c.state.current=name;return true;}
function leave(){const c=core();if(c){c.state.current=previous;c.render(previous,false);} }
function bindCustom(refresh){
 host().querySelectorAll('[data-vjob-key]').forEach(b=>b.onclick=()=>{const k=b.dataset.vjobKey;if(k==='F3')leave();else if(k==='F5')refresh();else if(k==='F12'){const i=$('cmd');if(i)i.value='';setMsg('REQUEST CANCELLED','');}});
 const input=$('cmd');if(input)input.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();const v=input.value.trim().toUpperCase();if(v==='F3'||v==='BACK')leave();else if(v==='F5'||v==='REFRESH')refresh();else if(v==='WRKSBS'||v==='SBS'||v==='U-9920')showSubsystems(false);else if(v==='WRKACTJOB'||v==='JOBS'||v==='U-9910')showJobs(false);else setMsg('CPF0001  INVALID COMMAND OR SELECTION: '+v,'error');input.value='';}else if(e.key==='F3'){e.preventDefault();leave()}else if(e.key==='F5'){e.preventDefault();refresh()}});
}
async function showJobs(push=true){
 if(push&&!beginCustom('active_jobs'))return;else if(!push){const c=core();if(c)c.state.current='active_jobs';}
 setHeader('ACTJOB');host().innerHTML='<div class="screen-title">WORK WITH ACTIVE JOBS</div><div class="box">LOADING ACTIVE VECTOR JOBS . . .</div>'+cmdline();bindCustom(()=>showJobs(false));
 try{
  const r=await fetch('/vector5250/api/jobs',{headers:headers(),cache:'no-store'}),d=await r.json();if(!r.ok)throw Error(d.detail||'ACTIVE JOB INQUIRY FAILED');
  let rows=(d.jobs||[]).map(j=>'<div class="recordrow" style="grid-template-columns:40px 1.15fr .85fr .8fr .7fr 1.45fr"><span><input class="hostinput vjobopt" maxlength="1" data-job="'+esc(j.job_name)+'" style="padding:2px;width:30px"></span><span>'+esc(j.job_name)+'</span><span>'+esc(j.user)+'</span><span>'+esc(j.subsystem)+'</span><span class="status">'+esc(j.status)+'</span><span>'+esc(j.function)+'</span></div>').join('');
  if(!rows)rows='<div class="box">NO ACTIVE VECTOR JOBS.</div>';
  host().innerHTML='<div class="screen-title">WORK WITH ACTIVE JOBS</div><div class="hint">CPU %: N/A &nbsp; ACTIVE INTERACTIVE: '+esc(d.active_interactive)+' &nbsp; 5=DISPLAY</div><div class="recordrow" style="grid-template-columns:40px 1.15fr .85fr .8fr .7fr 1.45fr"><span class="status">OPT</span><span class="status">JOB</span><span class="status">USER</span><span class="status">SBS</span><span class="status">STS</span><span class="status">FUNCTION</span></div>'+rows+'<div class="hint">TOTAL ACTIVE JOBS: '+esc(d.count)+' &nbsp; AUTO SESSION EXPIRY ENABLED</div>'+cmdline('<button class="key" data-vjob-key="SBS">WRKSBS</button>');
  bindCustom(()=>showJobs(false));
  host().querySelectorAll('.vjobopt').forEach(i=>i.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();if(i.value.trim()==='5')displayJob(i.dataset.job,d.jobs||[]);else setMsg('CPF6802  OPTION '+i.value+' NOT VALID','error')}}));
  host().querySelectorAll('[data-vjob-key="SBS"]').forEach(b=>b.onclick=()=>showSubsystems(false));
  setMsg('CPC1221  ACTIVE JOB INFORMATION RETRIEVED','ok');
 }catch(e){setMsg('CPF9898  '+e.message,'error');}
}
function displayJob(name,jobs){
 const j=(jobs||[]).find(x=>x.job_name===name);if(!j)return setMsg('CPF1338  JOB NOT FOUND','error');
 setHeader('DSPJOB');host().innerHTML='<div class="screen-title">DISPLAY JOB</div><div class="box"><div>JOB . . . . . . . : '+esc(j.job_name)+'</div><div>USER  . . . . . . : '+esc(j.user)+'</div><div>TYPE  . . . . . . : '+esc(j.type)+'</div><div>SUBSYSTEM . . . . : '+esc(j.subsystem)+'</div><div>STATUS  . . . . . : '+esc(j.status)+'</div><div>FUNCTION  . . . . : '+esc(j.function)+'</div><div>ELAPSED SECONDS . : '+esc(j.elapsed_seconds??'N/A')+'</div><div>IDLE SECONDS  . . : '+esc(j.idle_seconds??0)+'</div></div>'+cmdline();bindCustom(()=>displayJob(name,jobs));
}
async function showSubsystems(push=true){
 if(push&&!beginCustom('subsystems'))return;else if(!push){const c=core();if(c)c.state.current='subsystems';}
 setHeader('WRKSBS');host().innerHTML='<div class="screen-title">WORK WITH SUBSYSTEMS</div><div class="box">LOADING VECTOR SUBSYSTEMS . . .</div>'+cmdline();bindCustom(()=>showSubsystems(false));
 try{
  const r=await fetch('/vector5250/api/subsystems',{headers:headers(),cache:'no-store'}),d=await r.json();if(!r.ok)throw Error(d.detail||'SUBSYSTEM INQUIRY FAILED');
  const rows=(d.subsystems||[]).map(s=>'<div class="recordrow" style="grid-template-columns:1fr .8fr .8fr .8fr 2fr"><span>'+esc(s.subsystem)+'</span><span class="status">'+esc(s.status)+'</span><span>'+esc(s.active_jobs)+'</span><span>'+esc(s.max_jobs)+'</span><span>'+esc(s.description)+'</span></div>').join('');
  host().innerHTML='<div class="screen-title">WORK WITH SUBSYSTEMS</div><div class="recordrow" style="grid-template-columns:1fr .8fr .8fr .8fr 2fr"><span class="status">SUBSYSTEM</span><span class="status">STATUS</span><span class="status">ACTIVE</span><span class="status">MAX</span><span class="status">DESCRIPTION</span></div>'+rows+'<div class="hint">VECTOR HOST SUBSYSTEMS: '+esc(d.count)+'</div>'+cmdline('<button class="key" data-vjob-key="JOBS">WRKACTJOB</button>');
  bindCustom(()=>showSubsystems(false));host().querySelectorAll('[data-vjob-key="JOBS"]').forEach(b=>b.onclick=()=>showJobs(false));setMsg('CPC1201  SUBSYSTEM INFORMATION RETRIEVED','ok');
 }catch(e){setMsg('CPF9898  '+e.message,'error');}
}

function commandCapture(e){
 if(e.key!=='Enter'||e.target?.id!=='cmd')return;
 const c=String(e.target.value||'').trim().toUpperCase();
 if(['WRKACTJOB','JOBS','U-9910'].includes(c)){e.preventDefault();e.stopImmediatePropagation();e.target.value='';showJobs(true);return;}
 if(['WRKSBS','SBS','U-9920'].includes(c)){e.preventDefault();e.stopImmediatePropagation();e.target.value='';showSubsystems(true);return;}
}
document.addEventListener('keydown',commandCapture,true);

function sessionId(){let id=sessionStorage.getItem('vector5250-session-id');if(!id){id=(crypto.randomUUID?crypto.randomUUID():Date.now().toString(36)+Math.random().toString(36).slice(2));sessionStorage.setItem('vector5250-session-id',id);}return id;}
async function heartbeat(){
 const c=core();if(!c?.state?.signedOn)return;
 const payload={session_id:sessionId(),role:c.state.role||'',screen_id:$('screenCode')?.textContent||c.state.current||'MAIN',client_id:(navigator.userAgent||'').slice(0,80)};
 try{const r=await fetch('/vector5250/api/jobs/session',{method:'POST',headers:{...headers(),'Content-Type':'application/json'},body:JSON.stringify(payload),cache:'no-store'});activeSession=r.ok;}catch(_){activeSession=false;}
}
async function endSession(){if(!activeSession)return;const id=sessionStorage.getItem('vector5250-session-id');if(!id)return;try{await fetch('/vector5250/api/jobs/session/'+encodeURIComponent(id),{method:'DELETE',headers:headers(),keepalive:true});}catch(_){}activeSession=false;}
setInterval(()=>{const c=core();if(c?.state?.signedOn){if(!heartbeatTimer){heartbeat();heartbeatTimer=setInterval(heartbeat,20000);}}else if(heartbeatTimer){clearInterval(heartbeatTimer);heartbeatTimer=null;endSession();}},1000);
window.addEventListener('pagehide',()=>{endSession();});
window.VECTOR5250_JOBS={showJobs,showSubsystems,heartbeat};
})();