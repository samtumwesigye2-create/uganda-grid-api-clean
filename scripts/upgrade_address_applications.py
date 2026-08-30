from pathlib import Path

# ---------------- submit.html ----------------
submit = Path('submit.html')
s = submit.read_text(encoding='utf-8')

# Replace the single-purpose residential UI with dual application tabs.
start = s.index('<main>')
end = s.index('</main>') + len('</main>')
new_main = r'''<main>
  <a href="/" class="back">&larr; Back to map</a>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:16px">
    <button type="button" id="resTab" style="background:#2563eb;color:#fff">Residential Application</button>
    <button type="button" id="comTab" style="background:#e5e7eb;color:#111827">Commercial Application</button>
  </div>

  <section id="resForm">
    <h2 style="font-size:18px;margin:0 0 6px">Residential Address Application</h2>
    <p style="font-size:13px;color:#6b7280;margin:0 0 14px">For homes and single-address properties. Applications are reviewed before an official Grid ID is issued.</p>

    <div class="field"><label for="resName">Applicant full name</label><input id="resName" type="text" placeholder="Full legal name" /></div>
    <div class="field"><label for="resEmail">Email address</label><input id="resEmail" type="email" placeholder="you@example.com" /></div>
    <div class="field"><label for="resPhone">Phone number</label><input id="resPhone" type="tel" placeholder="+256..." /></div>
    <div class="field"><label for="resAddressText">Preferred address / location description</label><input id="resAddressText" type="text" placeholder="Village, road, landmark or preferred address wording" /></div>

    <div class="field">
      <label for="buildingType">What is this location?</label>
      <select id="buildingType">
        <option value="residence">Home / Residence</option>
        <option value="hospital">Hospital / Health Facility</option>
        <option value="police">Police Station</option>
        <option value="government">Government Office</option>
        <option value="other">Other single-address property</option>
      </select>
    </div>

    <div class="field"><label>Location</label><button type="button" id="captureBtn">Capture My Coordinates</button><div id="coordsBox" class="coordsBox">No coordinates captured yet</div></div>
    <div class="field"><label for="mediaInput">Photo or video of the building</label><input type="file" id="mediaInput" accept="image/*,video/*" capture="environment" /><div id="previewWrap"></div></div>
    <div class="field"><label for="noteInput">Additional description</label><textarea id="noteInput" placeholder="e.g. Blue gate, next to the primary school"></textarea></div>
    <button type="button" id="submitBtn">Submit Residential Application</button>
    <div id="statusBox" class="status"></div>
  </section>

  <section id="comForm" style="display:none">
    <h2 style="font-size:18px;margin:0 0 6px">Commercial Address Application</h2>
    <p style="font-size:13px;color:#6b7280;margin:0 0 14px">For businesses, offices, apartment buildings and properties requiring multiple unit labels.</p>
    <div class="field"><label for="comCompany">Company / organization name</label><input id="comCompany" type="text" /></div>
    <div class="field"><label for="comName">Applicant / authorized representative</label><input id="comName" type="text" /></div>
    <div class="field"><label for="comEmail">Email address</label><input id="comEmail" type="email" placeholder="you@company.com" /></div>
    <div class="field"><label for="comPhone">Phone number</label><input id="comPhone" type="tel" placeholder="+256..." /></div>
    <div class="field"><label for="comBuilding">Building / property name</label><input id="comBuilding" type="text" placeholder="Optional" /></div>
    <div class="field"><label for="comAddress">Requested official address wording</label><input id="comAddress" type="text" placeholder="Road, area, city / district" /></div>
    <div class="field"><label for="comUnits">Units / suites / apartments</label><textarea id="comUnits" placeholder="e.g. Shop 1, Shop 2, Office A, Office B"></textarea></div>
    <div class="field"><label>Location</label><button type="button" id="comCaptureBtn" style="background:#2563eb;color:#fff">Capture Commercial Coordinates</button><div id="comCoordsBox" class="coordsBox">No coordinates captured yet</div></div>
    <div class="field"><label for="comProof">Proof of ownership / authorization</label><input type="file" id="comProof" accept="image/*,application/pdf" /></div>
    <button type="button" id="comSubmitBtn" style="background:#d71920;color:#fff">Submit Commercial Application</button>
    <div id="comStatusBox" class="status"></div>
  </section>
</main>'''
s = s[:start] + new_main + s[end:]

# Inputs need same styling as select/textarea.
s = s.replace('select,textarea,input[type=file]{width:100%;', 'select,textarea,input[type=file],input[type=text],input[type=email],input[type=tel]{width:100%;')

# Replace old JS entirely.
js_start = s.index('<script>')
js_end = s.index('</script>', js_start) + len('</script>')
new_js = r'''<script>
(function(){
  let resLat=null,resLon=null,comLat=null,comLon=null;
  const $=id=>document.getElementById(id);
  function status(id,text,type){const e=$(id);e.textContent=text;e.className='status'+(type?' '+type:'')}
  function candidates(){const a=[];if(location.protocol.indexOf('http')===0)a.push(location.origin);a.push('https://uganda-grid-api-clean-production.up.railway.app');return [...new Set(a)]}
  function switchForm(which){$('resForm').style.display=which==='res'?'':'none';$('comForm').style.display=which==='com'?'':'none';$('resTab').style.background=which==='res'?'#2563eb':'#e5e7eb';$('resTab').style.color=which==='res'?'#fff':'#111827';$('comTab').style.background=which==='com'?'#2563eb':'#e5e7eb';$('comTab').style.color=which==='com'?'#fff':'#111827'}
  $('resTab').onclick=()=>switchForm('res'); $('comTab').onclick=()=>switchForm('com');

  function capture(boxId,setter){if(!navigator.geolocation){$(boxId).textContent='Location is not supported on this device';return}$(boxId).textContent='Getting your location...';navigator.geolocation.getCurrentPosition(p=>{setter(p.coords.latitude,p.coords.longitude);$(boxId).textContent='Captured: '+p.coords.latitude.toFixed(6)+', '+p.coords.longitude.toFixed(6)+' (accuracy ~'+Math.round(p.coords.accuracy)+'m)';$(boxId).className='coordsBox ok'},()=>{$(boxId).textContent='Unable to get location. Check permissions.'},{enableHighAccuracy:true,timeout:15000,maximumAge:0})}
  $('captureBtn').onclick=()=>capture('coordsBox',(a,b)=>{resLat=a;resLon=b});
  $('comCaptureBtn').onclick=()=>capture('comCoordsBox',(a,b)=>{comLat=a;comLon=b});

  $('mediaInput').addEventListener('change',()=>{const wrap=$('previewWrap');wrap.innerHTML='';const f=$('mediaInput').files&&$('mediaInput').files[0];if(!f)return;const u=URL.createObjectURL(f);if(f.type.indexOf('video')===0){const v=document.createElement('video');v.src=u;v.controls=true;v.className='preview';wrap.appendChild(v)}else{const im=document.createElement('img');im.src=u;im.className='preview';wrap.appendChild(im)}});

  $('submitBtn').onclick=async()=>{
    const name=$('resName').value.trim(), email=$('resEmail').value.trim(), phone=$('resPhone').value.trim(), addr=$('resAddressText').value.trim();
    if(!name||!email||!phone||!addr){status('statusBox','Name, email, phone and address description are required.','err');return}
    if(resLat===null||resLon===null){status('statusBox','Please capture your coordinates first.','err');return}
    const fd=new FormData();fd.append('lat',resLat);fd.append('lon',resLon);fd.append('building_type',$('buildingType').value);fd.append('note',$('noteInput').value.trim());fd.append('applicant_name',name);fd.append('applicant_email',email);fd.append('applicant_phone',phone);fd.append('requested_address',addr);const f=$('mediaInput').files&&$('mediaInput').files[0];if(f)fd.append('file',f);
    $('submitBtn').disabled=true;status('statusBox','Submitting...','');let data=null;
    for(const base of candidates()){try{const r=await fetch(base+'/submissions',{method:'POST',body:fd});if(r.ok){data=await r.json();break}}catch(e){}}
    $('submitBtn').disabled=false;if(data){status('statusBox','Submitted for admin review. Application ID: '+data.id,'ok')}else status('statusBox','Unable to submit. Please try again.','err');
  };

  $('comSubmitBtn').onclick=async()=>{
    const company=$('comCompany').value.trim(),name=$('comName').value.trim(),email=$('comEmail').value.trim(),phone=$('comPhone').value.trim(),addr=$('comAddress').value.trim(),units=$('comUnits').value.trim();
    if(!company||!name||!email||!phone||!addr||!units){status('comStatusBox','Company, applicant, email, phone, address and units are required.','err');return}
    if(comLat===null||comLon===null){status('comStatusBox','Please capture commercial coordinates first.','err');return}
    const fd=new FormData();fd.append('company_name',company);fd.append('applicant_name',name);fd.append('applicant_email',email);fd.append('applicant_phone',phone);fd.append('building_name',$('comBuilding').value.trim());fd.append('address_text',addr);fd.append('latitude',comLat);fd.append('longitude',comLon);fd.append('units',units);const f=$('comProof').files&&$('comProof').files[0];if(f)fd.append('proof',f);
    $('comSubmitBtn').disabled=true;status('comStatusBox','Submitting...','');let data=null;
    for(const base of candidates()){try{const r=await fetch(base+'/commercial/apply',{method:'POST',body:fd});if(r.ok){data=await r.json();break}}catch(e){}}
    $('comSubmitBtn').disabled=false;if(data){status('comStatusBox','Commercial application submitted for admin review. Application ID: '+data.id,'ok')}else status('comStatusBox','Unable to submit commercial application.','err');
  };
})();
</script>'''
s = s[:js_start] + new_js + s[js_end:]
p.write_text(s,encoding='utf-8')

# ---------------- main.py residential extra fields ----------------
p=Path('main.py'); m=p.read_text(encoding='utf-8')
old='''async def create_submission(lat: float = Form(...), lon: float = Form(...), building_type: str = Form(...), note: str = Form(""), file: UploadFile = File(None)):'''
new='''async def create_submission(lat: float = Form(...), lon: float = Form(...), building_type: str = Form(...), note: str = Form(""), applicant_name: str = Form(""), applicant_email: str = Form(""), applicant_phone: str = Form(""), requested_address: str = Form(""), file: UploadFile = File(None)):'''
if old in m:m=m.replace(old,new)
old_dict='''submission = {"id": str(uuid.uuid4()), "lat": lat, "lon": lon, "building_type": building_type, "note": note.strip()[:300], "media_url": media_url, "media_type": media_type, "status": "pending", "assigned_grid_id": "", "assigned_address": "", "created_at": time.time()}'''
new_dict='''submission = {"id": str(uuid.uuid4()), "application_type": "residential", "applicant_name": applicant_name.strip()[:120], "applicant_email": applicant_email.strip()[:160], "applicant_phone": applicant_phone.strip()[:60], "requested_address": requested_address.strip()[:240], "lat": lat, "lon": lon, "building_type": building_type, "note": note.strip()[:300], "media_url": media_url, "media_type": media_type, "status": "pending", "assigned_grid_id": "", "assigned_address": "", "created_at": time.time()}'''
if old_dict in m:m=m.replace(old_dict,new_dict)
p.write_text(m,encoding='utf-8')

# ---------------- commercial.py add applicant email migration ----------------
p=Path('commercial.py'); c=p.read_text(encoding='utf-8')
# migration after create table block init; safe repeated ALTER guarded
needle='''    conn.execute("INSERT OR IGNORE INTO commercial_grid_counter (id, next_number) VALUES (1, 1)")'''
replacement='''    conn.execute("INSERT OR IGNORE INTO commercial_grid_counter (id, next_number) VALUES (1, 1)")\n    try:\n        conn.execute("ALTER TABLE commercial_applications ADD COLUMN applicant_email TEXT DEFAULT ''")\n    except sqlite3.OperationalError:\n        pass'''
if needle in c and 'ADD COLUMN applicant_email' not in c:c=c.replace(needle,replacement)
c=c.replace('''        applicant_phone: str = Form(...),\n        building_name: str = Form(""),''','''        applicant_phone: str = Form(...),\n        applicant_email: str = Form(""),\n        building_name: str = Form(""),''')
# use explicit insert including applicant_email when column exists
old_insert='''            INSERT INTO commercial_applications\n            (id, company_name, applicant_name, applicant_phone, building_name,\n             address_text, latitude, longitude, units, proof_url, status,\n             assigned_grid_id, created_at)\n            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)'''
new_insert='''            INSERT INTO commercial_applications\n            (id, company_name, applicant_name, applicant_phone, applicant_email, building_name,\n             address_text, latitude, longitude, units, proof_url, status,\n             assigned_grid_id, created_at)\n            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)'''
if old_insert in c:c=c.replace(old_insert,new_insert)
old_vals='''            (application_id, company_name, applicant_name, applicant_phone,\n             building_name, address_text, latitude, longitude,\n             ",".join(unit_list), proof_url, "pending", "", time.time()),'''
new_vals='''            (application_id, company_name, applicant_name, applicant_phone, applicant_email.strip(),\n             building_name, address_text, latitude, longitude,\n             ",".join(unit_list), proof_url, "pending", "", time.time()),'''
if old_vals in c:c=c.replace(old_vals,new_vals)
p.write_text(c,encoding='utf-8')

# ---------------- admin.html override Submissions to combine both queues ----------------
p=Path('admin.html'); a=p.read_text(encoding='utf-8')
marker='addressUnifiedSubmissionsV1'
if marker not in a:
    addon=r'''
<script id="addressUnifiedSubmissionsV1">
(function(){
function esc(v){return String(v==null?'':v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
async function getJson(url){const r=await fetch(url,{headers:authHeaders()});if(!r.ok)throw new Error('HTTP '+r.status);return r.json()}
window.loadSubmissions=async function(){
 const out=document.getElementById('submissionsOut'); if(!out)return; out.innerHTML='<div class="empty">Loading address applications…</div>';
 try{
   const results=await Promise.allSettled([getJson('/submissions'),getJson('/commercial/applications')]);
   const residential=results[0].status==='fulfilled'?(results[0].value.results||[]):[];
   const commercial=results[1].status==='fulfilled'?(results[1].value.results||[]):[];
   const rows=[...residential.map(x=>({...x,_kind:'Residential'})),...commercial.map(x=>({...x,_kind:'Commercial'}))].sort((x,y)=>(y.created_at||0)-(x.created_at||0));
   if(!rows.length){out.innerHTML='<div class="empty">No address applications yet.</div>';return}
   out.innerHTML=rows.map(x=>{
     const id=esc(x.id), status=esc(x.status||'pending');
     const who=x._kind==='Commercial'?(esc(x.company_name)+'<br><small>'+esc(x.applicant_name)+'</small>'):esc(x.applicant_name||'Residential applicant');
     const contact=esc(x.applicant_email||'')+(x.applicant_phone?'<br>'+esc(x.applicant_phone):'');
     const address=esc(x.address_text||x.requested_address||x.note||'');
     const media=x.proof_url||x.media_url; const proof=media?'<a class="viewLink" href="'+esc(media)+'" target="_blank">View file</a>':'—';
     let actions='';
     if((x.status||'pending')==='pending'){
       if(x._kind==='Commercial') actions='<button class="rowBtn edit" onclick="decideCommercialAddress(\''+id+'\',\'approve\')">Approve</button><button class="rowBtn delete" onclick="decideCommercialAddress(\''+id+'\',\'deny\')">Reject</button>';
       else actions='<button class="rowBtn edit" onclick="approveResidentialAddress(\''+id+'\',\''+esc((x.requested_address||'').replace(/'/g,"\\'"))+'\')">Approve</button><button class="rowBtn delete" onclick="denyResidentialAddress(\''+id+'\')">Reject</button>';
     }
     return '<div class="formBox"><div style="display:flex;justify-content:space-between;gap:8px"><strong>'+x._kind+' Application</strong><span class="badge '+status+'">'+status+'</span></div><div style="font-size:12px;color:#aaa;margin:8px 0">ID: '+id+'</div><div><b>Applicant:</b> '+who+'</div><div><b>Contact:</b> '+contact+'</div><div><b>Requested address:</b> '+address+'</div>'+(x.units?'<div><b>Units:</b> '+esc(x.units)+'</div>':'')+'<div style="margin-top:6px">'+proof+'</div><div style="margin-top:10px">'+actions+'</div></div>';
   }).join('');
 }catch(e){out.innerHTML='<div class="empty">Unable to load address applications: '+esc(e.message)+'</div>'}
};
window.decideCommercialAddress=async function(id,action){try{await authedPost('/commercial/applications/'+encodeURIComponent(id)+'/decision',{action});loadSubmissions()}catch(e){alert(e.message)}};
window.denyResidentialAddress=async function(id){try{await authedPost('/submissions/'+encodeURIComponent(id)+'/decision',{action:'deny',grid_id:'',address:''});loadSubmissions()}catch(e){alert(e.message)}};
window.approveResidentialAddress=async function(id,suggested){const grid=prompt('Official Grid ID to assign:');if(!grid)return;const addr=prompt('Official address wording:',suggested||'');if(!addr)return;try{await authedPost('/submissions/'+encodeURIComponent(id)+'/decision',{action:'approve',grid_id:grid,address:addr});loadSubmissions()}catch(e){alert(e.message)}};
})();
</script>
'''
    a=a.replace('</body>',addon+'\n</body>')
p.write_text(a,encoding='utf-8')
