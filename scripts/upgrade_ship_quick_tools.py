from pathlib import Path

# Register backend router
mp = Path('main.py')
main = mp.read_text(encoding='utf-8')
needle = "from drivers import router as drivers_router\napp.include_router(drivers_router)\n"
insert = needle + "\nfrom customer_tools import router as customer_tools_router\napp.include_router(customer_tools_router)\n"
if "customer_tools_router" not in main and needle in main:
    main = main.replace(needle, insert, 1)
    mp.write_text(main, encoding='utf-8')

# Upgrade customer ship page
p = Path('ship.html')
s = p.read_text(encoding='utf-8')
if 'id="customerQuickToolsV1"' in s:
    raise SystemExit(0)

css = r'''
<style id="customerQuickToolsCssV1">
.customerTopbar{position:sticky;top:0;z-index:2000;display:flex;align-items:center;justify-content:space-between;gap:12px;background:#fff;border-bottom:1px solid #ddd;padding:10px 12px;margin:-12px -12px 14px;color:#0f1220}
.customerBrand{font-weight:800;font-size:15px}.customerMenuBtn{width:42px;height:42px;margin:0;padding:0;border-radius:10px;border:1px solid #ddd;background:#fff;color:#0f1220;font-size:24px;line-height:1}
.quickToolsPanel{background:#fff;border:1px solid #ddd;border-radius:14px;padding:18px;margin-bottom:14px}.quickToolsPanel h2{margin:0 0 5px;font-size:19px}.quickToolsGrid{display:grid;grid-template-columns:repeat(3,1fr);border:1px solid #e4e4e4;border-radius:12px;overflow:hidden;margin-top:12px}.quickTool{background:#fff;border:0;border-right:1px solid #e4e4e4;border-bottom:1px solid #e4e4e4;border-radius:0;padding:18px 10px;margin:0;color:#0b5791;min-height:112px;font-weight:800;font-size:14px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:9px}.quickTool:nth-child(3n){border-right:0}.quickTool:nth-last-child(-n+3){border-bottom:0}.quickToolIcon{font-size:25px}.quickTool:active{background:#f1f5f9}
.menuDrawer{position:fixed;inset:0;z-index:5000;display:none;background:rgba(0,0,0,.45)}.menuDrawer.open{display:block}.menuSheet{margin-left:auto;width:min(92vw,430px);height:100%;background:#fff;color:#0f1220;overflow:auto;box-shadow:-12px 0 36px rgba(0,0,0,.25)}.menuHead{position:sticky;top:0;background:#fff;display:flex;align-items:center;justify-content:space-between;padding:14px 18px;border-bottom:3px solid #e2593a;z-index:2}.menuHead b{font-size:17px}.menuClose{width:42px;height:42px;margin:0;background:none;border:0;color:#0b5791;font-size:28px;padding:0}.menuSection{border-bottom:1px solid #cbd5e1}.menuSectionBtn{width:100%;margin:0;border:0;border-radius:0;background:#fff;color:#0b5791;text-align:left;padding:18px;font-size:17px;display:flex;justify-content:space-between;align-items:center}.menuItems{display:none;background:#f8fafc;padding:4px 18px 14px}.menuSection.open .menuItems{display:block}.menuItems button,.menuItems a{display:block;width:100%;margin:6px 0;padding:11px 12px;border:0;border-radius:8px;background:#fff;color:#334155;text-align:left;text-decoration:none;font-size:14px}.toolDialog{position:fixed;inset:0;z-index:5500;display:none;background:rgba(0,0,0,.55);padding:18px;align-items:center;justify-content:center}.toolDialog.open{display:flex}.toolDialogBox{width:min(100%,480px);max-height:86vh;overflow:auto;background:#fff;color:#111;border-radius:14px;padding:18px}.toolDialogBox h3{margin-top:0}.toolDialogBox label{color:#555}.toolDialogBox input,.toolDialogBox textarea{background:#f7f7f7;color:#111;border:1px solid #ccc}.toolDialogBox textarea{width:100%;min-height:90px;border-radius:8px;padding:12px}.toolDialogActions{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:14px}.toolDialogActions button{margin:0}.toolStatus{font-size:13px;margin-top:10px}.toolStatus.ok{color:#087b4c}.toolStatus.err{color:#b42318}
@media(max-width:620px){.quickToolsGrid{grid-template-columns:repeat(3,1fr)}.quickTool{font-size:12px;padding:14px 6px;min-height:105px}.customerTopbar{margin:-12px -12px 14px}}
</style>
'''

html = r'''
<div class="customerTopbar" id="customerQuickToolsV1"><div class="customerBrand">Uganda National Grid • Ship & Mail</div><button class="customerMenuBtn" id="customerMenuBtn" aria-label="Open menu">⋯</button></div>
<section class="quickToolsPanel" id="customerQuickToolsPanel"><h2>Quick Tools</h2><div class="marketingLead">Common shipping and delivery actions.</div><div class="quickToolsGrid">
<button class="quickTool" data-tool="create"><span class="quickToolIcon">📦</span>Create Shipment</button>
<button class="quickTool" data-tool="label"><span class="quickToolIcon">🏷️</span>Shipping Label</button>
<button class="quickTool" data-tool="alerts"><span class="quickToolIcon">✉️</span>Delivery Alerts</button>
<button class="quickTool" data-tool="pobox"><span class="quickToolIcon">📮</span>PO Box Request</button>
<button class="quickTool" data-tool="price"><span class="quickToolIcon">🧮</span>Calculate Price</button>
<button class="quickTool" data-tool="hold"><span class="quickToolIcon">✋</span>Hold Delivery</button>
<button class="quickTool" data-tool="lookup"><span class="quickToolIcon">🔎</span>Address Lookup</button>
<button class="quickTool" data-tool="change"><span class="quickToolIcon">🏠</span>Change Address</button>
<button class="quickTool" data-tool="pickup"><span class="quickToolIcon">🚚</span>Schedule Pickup</button>
</div></section>
<div class="menuDrawer" id="customerMenuDrawer"><div class="menuSheet"><div class="menuHead"><b>Ship & Mail</b><button class="menuClose" id="customerMenuClose">×</button></div>
<div class="menuSection"><button class="menuSectionBtn">Quick Tools <span>⌄</span></button><div class="menuItems"><button data-tool="track">Track Shipment</button><button data-tool="price">Calculate a Price</button><button data-tool="pickup">Schedule Pickup</button><button data-tool="lookup">Address Lookup</button></div></div>
<div class="menuSection"><button class="menuSectionBtn">Send <span>⌄</span></button><div class="menuItems"><button data-tool="create">Create Shipment</button><button data-tool="label">Create Shipping Label</button><button data-tool="pickup">Schedule Pickup</button></div></div>
<div class="menuSection"><button class="menuSectionBtn">Receive <span>⌄</span></button><div class="menuItems"><button data-tool="alerts">Delivery Alerts</button><button data-tool="hold">Hold Delivery</button><button data-tool="change">Change Delivery Address</button><button data-tool="pobox">PO Box Request</button></div></div>
<div class="menuSection"><button class="menuSectionBtn">Shop <span>⌄</span></button><div class="menuItems"><button data-tool="label">Shipping Labels</button><button data-tool="price">Rates & Pricing</button></div></div>
<div class="menuSection"><button class="menuSectionBtn">Business <span>⌄</span></button><div class="menuItems"><button data-tool="create">Business Shipping</button><a href="/driver">Carrier / Driver Opportunities</a></div></div>
<div class="menuSection"><button class="menuSectionBtn">International <span>⌄</span></button><div class="menuItems"><button data-tool="international">International Rates</button><button data-tool="international">International Shipping</button></div></div>
<div class="menuSection"><button class="menuSectionBtn">Help <span>⌄</span></button><div class="menuItems"><button data-tool="track">Tracking Help</button><button data-tool="support">Customer Support</button></div></div>
</div></div>
<div class="toolDialog" id="serviceToolDialog"><div class="toolDialogBox"><h3 id="serviceToolTitle">Service Request</h3><div id="serviceToolHint" style="font-size:13px;color:#666"></div><label>Name</label><input id="serviceName"><label>Email</label><input id="serviceEmail" type="email"><label>Phone</label><input id="servicePhone"><label id="serviceTrackingLabel">Tracking number (if applicable)</label><input id="serviceTracking"><label>Address</label><input id="serviceAddress"><label>Details</label><textarea id="serviceDetails"></textarea><div class="toolStatus" id="serviceToolStatus"></div><div class="toolDialogActions"><button type="button" id="serviceToolCancel" class="btn" style="background:#666">Cancel</button><button type="button" id="serviceToolSubmit" class="btn secondary">Submit</button></div></div></div>
'''

js = r'''
<script id="customerQuickToolsJsV1">
(function(){
const $=id=>document.getElementById(id); const drawer=$('customerMenuDrawer'); const dialog=$('serviceToolDialog'); let requestType='';
function closeDrawer(){drawer&&drawer.classList.remove('open')}
$('customerMenuBtn')?.addEventListener('click',()=>drawer.classList.add('open')); $('customerMenuClose')?.addEventListener('click',closeDrawer); drawer?.addEventListener('click',e=>{if(e.target===drawer)closeDrawer()});
document.querySelectorAll('.menuSectionBtn').forEach(b=>b.addEventListener('click',()=>b.parentElement.classList.toggle('open')));
function scrollToId(id){closeDrawer(); const el=$(id); if(el){el.scrollIntoView({behavior:'smooth',block:'start'});}}
function selectTab(name){const b=document.querySelector('.tab[data-tab="'+name+'"]'); if(b){b.click(); setTimeout(()=>b.scrollIntoView({behavior:'smooth',block:'start'}),80)}}
function openRequest(type,title,hint){closeDrawer();requestType=type;$('serviceToolTitle').textContent=title;$('serviceToolHint').textContent=hint||'';$('serviceToolStatus').textContent='';dialog.classList.add('open')}
function run(tool){
 if(tool==='create'||tool==='label'){selectTab('ship');scrollToId('panel-ship');return}
 if(tool==='price'){selectTab('ship');scrollToId('panel-ship');return}
 if(tool==='track'){selectTab('track');return}
 if(tool==='international'){selectTab('ship'); if(window.setRateMode) window.setRateMode('international'); scrollToId('panel-ship');return}
 if(tool==='lookup'){window.location.href='/?focus=address';return}
 if(tool==='pickup')return openRequest('schedule_pickup','Schedule a Pickup','Tell us where and when your shipment should be collected.');
 if(tool==='hold')return openRequest('hold_delivery','Hold Delivery','Request a temporary hold for an existing shipment.');
 if(tool==='change')return openRequest('change_address','Change Delivery Address','Submit the tracking number and requested new delivery address.');
 if(tool==='pobox')return openRequest('po_box','PO Box Request','Submit your contact details and preferred service area.');
 if(tool==='alerts')return openRequest('delivery_alerts','Delivery Alerts','Register for shipment delivery notifications.');
 if(tool==='support')return openRequest('delivery_alerts','Customer Support','Send your question and contact information.');
}
document.addEventListener('click',e=>{const b=e.target.closest('[data-tool]');if(b){e.preventDefault();run(b.dataset.tool)}});
$('serviceToolCancel')?.addEventListener('click',()=>dialog.classList.remove('open')); dialog?.addEventListener('click',e=>{if(e.target===dialog)dialog.classList.remove('open')});
$('serviceToolSubmit')?.addEventListener('click',async()=>{const out=$('serviceToolStatus');out.className='toolStatus';out.textContent='Submitting…';const fd=new FormData();fd.append('request_type',requestType);fd.append('name',$('serviceName').value||'');fd.append('email',$('serviceEmail').value||'');fd.append('phone',$('servicePhone').value||'');fd.append('tracking_number',$('serviceTracking').value||'');fd.append('address',$('serviceAddress').value||'');fd.append('details',$('serviceDetails').value||'');try{const r=await fetch('/customer-tools/request',{method:'POST',body:fd});const d=await r.json();if(!r.ok)throw new Error(d.detail||'Unable to submit');out.className='toolStatus ok';out.textContent='Request received: '+d.request_id;}catch(err){out.className='toolStatus err';out.textContent=err.message||'Unable to submit request';}});
})();
</script>
'''

# CSS before head closes
s = s.replace('</head>', css + '\n</head>', 1)
# Topbar and tools before marketing home
marker = '<section class="shipMarketingHome" id="shipMarketingHome">'
s = s.replace(marker, html + '\n' + marker, 1)
# JS before body closes
s = s.replace('</body>', js + '\n</body>', 1)
p.write_text(s, encoding='utf-8')
