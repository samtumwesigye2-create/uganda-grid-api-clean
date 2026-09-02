(() => {
  function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
  function ensure(){
    if(document.querySelector('.tab[data-tab="users"]')) return;
    const tabs=document.querySelector('.tabs'); const main=document.getElementById('main');
    if(!tabs||!main) return;
    const tab=document.createElement('button'); tab.className='tab'; tab.dataset.tab='users'; tab.textContent='Users'; tabs.appendChild(tab);
    const panel=document.createElement('div'); panel.className='panel'; panel.id='panel-users'; panel.innerHTML=`
      <div class="dashboard-actions"><div><div class="welcome-line">UGAMAP Users</div><div class="welcome-sub">Accounts, trust scores, flags, suspension and audit history.</div></div><button class="refreshBtn" id="ugUsersRefresh">Refresh</button></div>
      <div class="dashboard-grid" id="ugUserStats"></div>
      <div class="formBox"><div class="row2"><input id="ugUserSearch" placeholder="Search email or phone"><select id="ugUserFilter"><option value="all">All users</option><option value="flagged">Flagged</option><option value="suspended">Suspended</option><option value="trusted">Trusted</option></select></div></div>
      <div id="ugUsersOut"></div>
      <div id="ugUserAudit" class="formBox" style="display:none"></div>`;
    main.appendChild(panel);
    tab.addEventListener('click',()=>{document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));tab.classList.add('active');panel.classList.add('active');loadUsers();});
    document.getElementById('ugUsersRefresh').onclick=loadUsers;
    document.getElementById('ugUserSearch').addEventListener('input',renderFiltered);
    document.getElementById('ugUserFilter').addEventListener('change',renderFiltered);
  }
  let rows=[];
  async function loadUsers(){
    const out=document.getElementById('ugUsersOut'); if(!out)return; out.innerHTML='<div class="empty">Loading users…</div>';
    try{const d=await authedFetch('/admin/users');rows=Array.isArray(d.results)?d.results:[];renderStats();renderFiltered();}
    catch(e){out.innerHTML='<div class="empty">Unable to load users: '+esc(e.message)+'</div>';}
  }
  function renderStats(){
    const s=document.getElementById('ugUserStats');if(!s)return;
    const flagged=rows.filter(r=>r.flagged).length,suspended=rows.filter(r=>r.account_status==='suspended').length,trusted=rows.filter(r=>r.trust_level==='trusted').length;
    s.innerHTML=`<div class="stat-tile"><div class="stat-label">Total Users</div><div class="stat-value">${rows.length}</div></div><div class="stat-tile"><div class="stat-label">Trusted</div><div class="stat-value">${trusted}</div></div><div class="stat-tile warn"><div class="stat-label">Flagged</div><div class="stat-value">${flagged}</div></div><div class="stat-tile"><div class="stat-label">Suspended</div><div class="stat-value">${suspended}</div></div>`;
  }
  function renderFiltered(){
    const out=document.getElementById('ugUsersOut'); if(!out)return;
    const q=(document.getElementById('ugUserSearch')?.value||'').trim().toLowerCase(); const f=document.getElementById('ugUserFilter')?.value||'all';
    const list=rows.filter(r=>{if(q&&!String(r.email||'').toLowerCase().includes(q)&&!String(r.phone||'').toLowerCase().includes(q))return false;if(f==='flagged'&&!r.flagged)return false;if(f==='suspended'&&r.account_status!=='suspended')return false;if(f==='trusted'&&r.trust_level!=='trusted')return false;return true;});
    if(!list.length){out.innerHTML='<div class="empty">No matching users.</div>';return;}
    out.innerHTML='<table><thead><tr><th>User</th><th>Trust</th><th>Reports</th><th>Status</th><th>Actions</th></tr></thead><tbody>'+list.map(r=>`<tr><td><strong>${esc(r.email||r.id)}</strong><br><span style="color:#8e93a8">${esc(r.phone||'')}</span></td><td>${Number(r.score??50)}/100<br><span class="badge">${esc(r.trust_level||'standard')}</span>${r.flagged?' <span class="badge denied">FLAGGED</span>':''}</td><td>${Number(r.reports_total||0)} total<br>${Number(r.confirmed_reports||0)} confirmed / ${Number(r.disputed_reports||0)} disputed</td><td><span class="badge ${r.account_status==='suspended'?'denied':'approved'}">${esc(r.account_status||'active')}</span></td><td>${r.account_status==='suspended'?`<button class="rowBtn edit" onclick="ugUserStatus('${r.id}','active')">Reinstate</button>`:`<button class="rowBtn delete" onclick="ugUserStatus('${r.id}','suspended')">Suspend</button>`}<button class="rowBtn toggle" onclick="ugUserAudit('${r.id}')">Audit</button></td></tr>`).join('')+'</tbody></table>';
  }
  window.ugUserStatus=async function(id,status){const reason=prompt(status==='suspended'?'Reason for suspension:':'Reason for reinstatement:','');if(reason===null)return;try{await authedPost('/admin/users/'+encodeURIComponent(id)+'/status',{status,reason});if(typeof showNotifyToast==='function')showNotifyToast(status==='suspended'?'User suspended':'User reinstated');await loadUsers();}catch(e){if(typeof showNotifyToast==='function')showNotifyToast(e.message,true);}};
  window.ugUserAudit=async function(id){const box=document.getElementById('ugUserAudit');if(!box)return;box.style.display='block';box.innerHTML='<div class="empty">Loading audit…</div>';try{const d=await authedFetch('/admin/users/'+encodeURIComponent(id)+'/audit');const a=Array.isArray(d.results)?d.results:[];box.innerHTML='<h3 style="margin-top:0">Administrative Audit</h3>'+(a.length?a.map(x=>`<div class="activity-row"><div class="activity-main"><div class="activity-text"><strong>${esc(x.action)}</strong>${x.reason?' — '+esc(x.reason):''}</div><div class="activity-time">${new Date(Number(x.created_at)*1000).toLocaleString()}</div></div></div>`).join(''):'<div class="empty">No administrative actions yet.</div>');box.scrollIntoView({behavior:'smooth',block:'nearest'});}catch(e){box.innerHTML='<div class="empty">Unable to load audit.</div>';}};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',ensure);else ensure();
})();