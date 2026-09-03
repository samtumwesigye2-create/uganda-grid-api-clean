(function(){
'use strict';
const $=id=>document.getElementById(id);
let active=false,previous=null,timer=null,last=null;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function headers(){return {'x-access-code':sessionStorage.getItem('vector5250-access')||''};}
function stamp(v){if(!v)return 'NEVER';try{return new Date(v).toLocaleString()}catch{return String(v)}}
function health(ok){return ok?'ONLINE':'OFFLINE'}
async function getStatus(force){
  const url=force?'/vector5250/api/resilience/sync':'/vector5250/api/resilience';
  const r=await fetch(url,{method:force?'POST':'GET',headers:headers(),cache:'no-store'});
  const d=await r.json();if(!r.ok)throw Error(d.detail||'STATUS REQUEST FAILED');last=d;return d;
}
function statusFooter(d){
  let el=$('vectorResilienceLine');
  if(!el){el=document.createElement('div');el.id='vectorResilienceLine';el.className='hint';el.style.cssText='margin-top:18px;border-top:1px solid #123d20;padding-top:10px';document.querySelector('.terminal')?.appendChild(el);}
  const b=d&&d.backup_configured&&!d.backup_last_error,r=d&&d.relay_configured&&!d.relay_last_error;
  el.innerHTML='HOST LINKS // BACKUP: <span class="'+(b?'ok':'error')+'">'+health(b)+'</span> &nbsp; RELAY: <span class="'+(r?'ok':'error')+'">'+health(r)+'</span> &nbsp; POLL: '+esc(d?.poll_seconds||'--')+' SEC';
}
function screen(d){
  const host=$('hostScreen');if(!host)return;
  $('screenCode').textContent='SYSSTS';
  const backupOk=d.backup_configured&&!d.backup_last_error;
  const relayOk=d.relay_configured&&!d.relay_last_error;
  host.innerHTML='<div class="screen-title">VECTOR 5250 SYSTEM STATUS</div><div class="rule"></div>'+
  '<div class="recordrow"><span class="sel">1</span><span>PRIMARY VECTOR RECORD STORE</span><span class="status ok">ACTIVE</span></div>'+
  '<div class="recordrow"><span class="sel">2</span><span>INDEPENDENT BACKUP SERVICE</span><span class="status '+(backupOk?'ok':'error')+'">'+health(backupOk)+'</span></div>'+
  '<div class="recordrow"><span class="sel">3</span><span>DATA RELAY SERVER</span><span class="status '+(relayOk?'ok':'error')+'">'+health(relayOk)+'</span></div>'+
  '<div class="recordrow"><span class="sel">4</span><span>REPLICATION INTERVAL</span><span class="status">'+esc(d.poll_seconds)+' SEC</span></div>'+
  '<div class="box"><div>VECTOR RECORDS . . . . : '+esc(d.records)+'</div><div>JOURNAL ENTRIES . . . . : '+esc(d.journal)+'</div><div>LAST CHECK . . . . . . : '+esc(stamp(d.last_check))+'</div><div>LAST DATA CHANGE  . . . : '+esc(stamp(d.last_change))+'</div><div>BACKUP LAST SUCCESS . . : '+esc(stamp(d.backup_last_success))+'</div><div>RELAY LAST SUCCESS  . . : '+esc(stamp(d.relay_last_success))+'</div><div>BACKUP ERROR  . . . . . : '+esc(d.backup_last_error||'NONE')+'</div><div>RELAY ERROR . . . . . . : '+esc(d.relay_last_error||'NONE')+'</div></div>'+
  '<div class="hint">COMMANDS: SYNC=FORCE REPLICATION &nbsp; F5=REFRESH &nbsp; F3=RETURN</div><div class="command-area"><div class="commandline"><label>COMMAND ==&gt;</label><input id="sysstsCmd" class="hostinput" autocomplete="off" autocapitalize="characters" spellcheck="false"></div></div><div class="keys"><button class="key" id="sysstsBack">F3=BACK</button><button class="key" id="sysstsRefresh">F5=REFRESH</button><button class="key" id="sysstsSync">ENTER=SYNC</button></div>';
  $('msg').textContent='CPC1234  VECTOR HOST LINKS CHECKED';$('msg').className='msg ok';
  $('sysstsBack').onclick=close;$('sysstsRefresh').onclick=()=>refresh(false);$('sysstsSync').onclick=()=>refresh(true);
  $('sysstsCmd').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();const c=e.target.value.trim().toUpperCase();if(c==='SYNC'||c==='FORCE')refresh(true);else if(c==='F3'||c==='BACK')close();else refresh(false)}});
  setTimeout(()=>$('sysstsCmd')?.focus(),20);statusFooter(d);
}
async function refresh(force){try{$('msg').textContent=force?'CPI9801  FORCING VECTOR REPLICATION . . .':'CPI9800  CHECKING HOST LINKS . . .';$('msg').className='msg';screen(await getStatus(force));if(force){$('msg').textContent='CPC9802  VECTOR REPLICATION COMPLETED';$('msg').className='msg ok'}}catch(e){$('msg').textContent='CPF9809  '+e.message;$('msg').className='msg error'}}
function open(){if(active)return;const host=$('hostScreen');if(!host)return;active=true;previous={html:host.innerHTML,screen:$('screenCode').textContent,msg:$('msg').textContent,msgClass:$('msg').className};refresh(false);timer=setInterval(()=>refresh(false),15000)}
function close(){if(!active)return;active=false;if(timer){clearInterval(timer);timer=null}const host=$('hostScreen');if(previous){host.innerHTML=previous.html;$('screenCode').textContent=previous.screen;$('msg').textContent='CPC1000  RETURNED FROM SYSTEM STATUS';$('msg').className='msg ok';previous=null}}
async function background(){if(active)return;try{statusFooter(await getStatus(false))}catch{statusFooter(null)}}
document.addEventListener('keydown',e=>{
  if(active){if(e.key==='F3'){e.preventDefault();close()}else if(e.key==='F5'){e.preventDefault();refresh(false)}return}
  if(e.key==='Enter'){
    const cmd=$('cmd');if(!cmd)return;const c=cmd.value.trim().toUpperCase();if(['SYSSTS','STATUS','BACKUP','RELAY','U-9900'].includes(c)){e.preventDefault();e.stopImmediatePropagation();cmd.value='';open()}
  }
},true);
window.Vector5250SystemStatus={open,refresh};
setTimeout(background,2500);setInterval(background,15000);
})();