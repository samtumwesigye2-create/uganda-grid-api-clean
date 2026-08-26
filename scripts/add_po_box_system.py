from pathlib import Path

# ---------------- ship.html ----------------
ship = Path('ship.html')
s = ship.read_text(encoding='utf-8')

if 'id="poBoxApplicationDialog"' not in s:
    modal = r'''
<div class="toolDialog" id="poBoxApplicationDialog">
  <div class="toolDialogBox">
    <h3>Apply for a P.O. Box</h3>
    <p style="font-size:13px;color:#666;margin-top:-4px">Applications are reviewed by Uganda National Grid administration before any box number is assigned.</p>
    <div id="poBoxApplyForm">
      <label>Full name *</label><input id="poName" placeholder="Applicant name" />
      <label>Email</label><input id="poEmail" type="email" placeholder="you@example.com" />
      <label>Phone</label><input id="poPhone" placeholder="+256..." />
      <label>Physical / National Grid address *</label><input id="poAddress" placeholder="Street address or National Grid address" />
      <label>Grid ID (recommended)</label><input id="poGridId" placeholder="e.g. UG-ENT-000400" />
      <label>Preferred service branch *</label>
      <select id="poBranch">
        <option value="">Select branch</option>
        <option>Kampala Central</option><option>Entebbe</option><option>Jinja</option><option>Mbarara</option>
        <option>Gulu</option><option>Mbale</option><option>Fort Portal</option><option>Arua</option><option>Masaka</option><option>Lira</option>
      </select>
      <label>Box size</label>
      <select id="poSize"><option value="small">Small</option><option value="medium">Medium</option><option value="large">Large</option><option value="business">Business</option></select>
      <label>Business name (optional)</label><input id="poBusiness" placeholder="Business or organization" />
      <label>Notes (optional)</label><textarea id="poNotes" placeholder="Any special requirements"></textarea>
      <div class="toolStatus" id="poApplyStatus"></div>
      <div class="toolDialogActions"><button type="button" id="poCancel">Cancel</button><button class="btn secondary" type="button" id="poSubmit">Submit Application</button></div>
    </div>
    <hr style="border:0;border-top:1px solid #ddd;margin:20px 0">
    <h3 style="font-size:16px">Check or update an application</h3>
    <label>Application ID</label><input id="poCheckId" placeholder="UG-POA-XXXXXXXXXX" />
    <label>Email or phone used on application</label><input id="poCheckContact" placeholder="Email or phone" />
    <button class="btn secondary" type="button" id="poCheckBtn">Check Status</button>
    <div class="toolStatus" id="poCheckStatus"></div>
    <button class="btn" type="button" id="poReviseBtn" style="display:none">Submit Requested Changes Using Form Above</button>
  </div>
</div>
'''
    s = s.replace('<script id="customerQuickToolsJsV1">', modal + '\n<script id="customerQuickToolsJsV1">', 1)

if 'id="poBoxWorkflowJsV1"' not in s:
    script = r'''
<script id="poBoxWorkflowJsV1">
(function(){
 const $=id=>document.getElementById(id), dlg=$('poBoxApplicationDialog'); let checkedApplication=null;
 function open(){ dlg?.classList.add('open'); $('poApplyStatus').textContent=''; }
 function close(){ dlg?.classList.remove('open'); }
 document.addEventListener('click',function(e){
   const b=e.target.closest('[data-tool="pobox"]'); if(!b)return;
   e.preventDefault(); e.stopImmediatePropagation(); open();
 },true);
 $('poCancel')?.addEventListener('click',close); dlg?.addEventListener('click',e=>{if(e.target===dlg)close()});
 function appData(){ return {
   name:$('poName').value.trim(), email:$('poEmail').value.trim(), phone:$('poPhone').value.trim(),
   physical_address:$('poAddress').value.trim(), grid_id:$('poGridId').value.trim(), preferred_branch:$('poBranch').value,
   box_size:$('poSize').value, business_name:$('poBusiness').value.trim(), notes:$('poNotes').value.trim()
 };}
 function fillFD(obj){const fd=new FormData();Object.entries(obj).forEach(([k,v])=>fd.append(k,v||''));return fd;}
 $('poSubmit')?.addEventListener('click',async()=>{
   const out=$('poApplyStatus'), data=appData(); out.className='toolStatus'; out.textContent='Submitting for review…';
   try{const r=await fetch('/po-box/apply',{method:'POST',body:fillFD(data)});const d=await r.json();if(!r.ok)throw new Error(d.detail||'Unable to submit');
     out.className='toolStatus ok';out.innerHTML='Application submitted. <b>'+d.application_id+'</b>. Save this ID to check status.';$('poCheckId').value=d.application_id;
   }catch(err){out.className='toolStatus err';out.textContent=err.message||'Unable to submit application';}
 });
 $('poCheckBtn')?.addEventListener('click',async()=>{
   const out=$('poCheckStatus'), id=$('poCheckId').value.trim().toUpperCase(), contact=$('poCheckContact').value.trim();
   out.className='toolStatus';out.textContent='Checking…';$('poReviseBtn').style.display='none'; checkedApplication=null;
   try{const r=await fetch('/po-box/application/'+encodeURIComponent(id)+'?contact='+encodeURIComponent(contact),{cache:'no-store'});const d=await r.json();if(!r.ok)throw new Error(d.detail||'Unable to check');checkedApplication=d;
     let text='Status: '+String(d.status).replaceAll('_',' '); if(d.assigned_po_box) text+=' • Assigned: '+d.assigned_po_box; if(d.admin_note) text+=' • Admin note: '+d.admin_note;
     out.className='toolStatus '+(d.status==='approved'?'ok':'');out.textContent=text;
     if(d.status==='changes_requested'){$('poReviseBtn').style.display='block';$('poAddress').value=d.physical_address||'';$('poGridId').value=d.grid_id||'';$('poBranch').value=d.preferred_branch||'';$('poSize').value=d.box_size||'small';}
   }catch(err){out.className='toolStatus err';out.textContent=err.message||'Unable to check application';}
 });
 $('poReviseBtn')?.addEventListener('click',async()=>{
   if(!checkedApplication)return; const out=$('poCheckStatus'),id=checkedApplication.application_id,contact=$('poCheckContact').value.trim(), data=appData(); data.contact=contact;
   out.className='toolStatus';out.textContent='Submitting requested changes…';
   try{const r=await fetch('/po-box/application/'+encodeURIComponent(id)+'/revise',{method:'POST',body:fillFD(data)});const d=await r.json();if(!r.ok)throw new Error(d.detail||'Unable to update');out.className='toolStatus ok';out.textContent='Changes submitted. Application returned to admin review.';$('poReviseBtn').style.display='none';}
   catch(err){out.className='toolStatus err';out.textContent=err.message||'Unable to submit changes';}
 });
})();
</script>
'''
    s = s.replace('</body>', script + '\n</body>', 1)

ship.write_text(s, encoding='utf-8')

# ---------------- admin.html ----------------
admin = Path('admin.html')
a = admin.read_text(encoding='utf-8')

if 'data-tab="poboxes"' not in a:
    a = a.replace('<div class="tab" data-tab="submissions">▤ Submissions</div>', '<div class="tab" data-tab="submissions">▤ Submissions</div>\n    <div class="tab" data-tab="poboxes">📮 P.O. Boxes</div>', 1)

if 'id="panel-poboxes"' not in a:
    panel = r'''
  <div class="panel" id="panel-poboxes">
    <div class="dashboard-actions">
      <div><div class="welcome-line">P.O. Box Administration</div><div class="welcome-sub">Review applications, prevent duplicate assignments and maintain the national P.O. Box registry.</div></div>
      <button class="refreshBtn" onclick="loadPoBoxes()">↻ Refresh</button>
    </div>
    <div class="subtabs" id="poBoxSubtabs">
      <button class="subtab active" type="button" data-po-filter="pending">Pending Review</button>
      <button class="subtab" type="button" data-po-filter="changes_requested">Changes Requested</button>
      <button class="subtab" type="button" data-po-filter="approved">Approved</button>
      <button class="subtab" type="button" data-po-filter="rejected">Rejected</button>
      <button class="subtab" type="button" data-po-filter="">All</button>
    </div>
    <div id="poBoxApplicationsOut"></div>
    <section class="admin-section" style="margin-top:14px"><div class="admin-section-title">ACTIVE P.O. BOX REGISTRY</div><div id="poBoxRegistryOut"></div></section>
  </div>
'''
    a = a.replace('  <div class="panel active" id="panel-dashboard">', panel + '\n  <div class="panel active" id="panel-dashboard">', 1)

if "if (name === 'poboxes') loadPoBoxes();" not in a:
    a = a.replace("if (name === 'submissions') loadSubmissions();", "if (name === 'submissions') loadSubmissions();\n    if (name === 'poboxes') loadPoBoxes();", 1)

if 'id="poBoxAdminJsV1"' not in a:
    script = r'''
<script id="poBoxAdminJsV1">
let poBoxFilter='pending';
function poEsc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function poDate(ts){try{return new Date(Number(ts)*1000).toLocaleString()}catch(e){return ''}}
async function poDecision(id,action){
 let note='', assigned='';
 if(action==='request_changes'){note=prompt('Tell the customer exactly what must be changed:')||'';if(!note)return;}
 if(action==='reject'){note=prompt('Reason for rejection (shown to customer):')||'';if(!note)return;}
 if(action==='approve'){if(!confirm('Approve this application? The system will block duplicate addresses and P.O. Box numbers.'))return;assigned=prompt('Optional: enter a specific P.O. Box number, or leave blank for automatic assignment:')||'';note=prompt('Optional approval note:')||'';}
 try{const d=await authedPost('/admin/po-box/applications/'+encodeURIComponent(id)+'/decision',{action,admin_note:note,assigned_po_box:assigned});showToast(action==='approve'?'Approved and assigned '+d.po_box:'Application updated');await loadPoBoxes();}
 catch(e){showToast(e.message||'Unable to update application',true);}
}
function renderPoApps(rows){
 const out=document.getElementById('poBoxApplicationsOut'); if(!out)return;
 if(!rows.length){out.innerHTML='<div class="empty">No P.O. Box applications in this status.</div>';return;}
 out.innerHTML=rows.map(r=>`<div class="admin-section" style="margin-bottom:9px">
   <div style="display:flex;justify-content:space-between;gap:10px;align-items:flex-start"><div><b>${poEsc(r.id)}</b><div style="font-size:12px;color:#9aa4bd;margin-top:3px">${poEsc(r.name)} • ${poEsc(r.email||r.phone)}</div></div><span class="badge ${poEsc(r.status)}">${poEsc(String(r.status).replaceAll('_',' '))}</span></div>
   <div style="font-size:12px;line-height:1.55;margin-top:9px"><b>Physical address:</b> ${poEsc(r.physical_address)} ${r.grid_id?' • <b>Grid ID:</b> '+poEsc(r.grid_id):''}<br><b>Branch:</b> ${poEsc(r.preferred_branch)} • <b>Size:</b> ${poEsc(r.box_size)}${r.business_name?'<br><b>Business:</b> '+poEsc(r.business_name):''}${r.notes?'<br><b>Applicant notes:</b> '+poEsc(r.notes):''}${r.admin_note?'<br><b>Admin note:</b> '+poEsc(r.admin_note):''}${r.assigned_po_box?'<br><b>Assigned P.O. Box:</b> '+poEsc(r.assigned_po_box):''}<br><span style="color:#687489">Revision ${poEsc(r.revision)} • ${poDate(r.created_at)}</span></div>
   ${r.status==='pending'?`<div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:10px"><button class="rowBtn edit" onclick="poDecision('${poEsc(r.id)}','approve')">Approve</button><button class="rowBtn toggle" onclick="poDecision('${poEsc(r.id)}','request_changes')">Request Change</button><button class="rowBtn delete" onclick="poDecision('${poEsc(r.id)}','reject')">Reject</button></div>`:''}
 </div>`).join('');
}
async function loadPoBoxes(){
 const appsOut=document.getElementById('poBoxApplicationsOut'),regOut=document.getElementById('poBoxRegistryOut'); if(!appsOut||!regOut)return;
 appsOut.innerHTML='<div class="empty">Loading applications…</div>';regOut.innerHTML='<div class="empty">Loading registry…</div>';
 try{const q=poBoxFilter?'?status='+encodeURIComponent(poBoxFilter):'';const [a,r]=await Promise.all([authedFetch('/admin/po-box/applications'+q),authedFetch('/admin/po-box/registry')]);renderPoApps(a.results||[]);
   const rows=r.results||[];if(!rows.length){regOut.innerHTML='<div class="empty">No P.O. Boxes assigned yet.</div>';}else{renderTable(regOut,rows,[{label:'P.O. Box',key:'po_box'},{label:'Holder',key:'holder_name'},{label:'Physical Address',key:'physical_address'},{label:'Grid ID',key:'grid_id'},{label:'Branch',key:'branch'},{label:'Size',key:'box_size'},{label:'Status',render:x=>'<span class="badge approved">'+poEsc(x.status)+'</span>'}]);}
 }catch(e){appsOut.innerHTML='<div class="empty">'+poEsc(e.message||'Unable to load')+'</div>';regOut.innerHTML='';}
}
document.querySelectorAll('[data-po-filter]').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('[data-po-filter]').forEach(x=>x.classList.remove('active'));b.classList.add('active');poBoxFilter=b.dataset.poFilter||'';loadPoBoxes();}));
</script>
'''
    a = a.replace('</body>', script + '\n</body>', 1)

admin.write_text(a, encoding='utf-8')
