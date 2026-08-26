from pathlib import Path

path = Path('index.html')
text = path.read_text(encoding='utf-8')

if 'customerLogisticsHome' in text:
    raise SystemExit('Customer logistics home already installed')

css = r'''

/* ---- Customer logistics homepage ---- */
.customerLogisticsHome{flex:0 0 auto;max-width:1100px;width:100%;margin:0 auto;padding:16px 12px 8px}
.customerHero{background:linear-gradient(135deg,#121d39 0%,#15264d 55%,#0d1830 100%);border:1px solid var(--border-subtle);border-radius:18px;padding:22px;box-shadow:0 16px 40px rgba(0,0,0,.25)}
.customerEyebrow{font-size:11px;font-weight:800;letter-spacing:.1em;color:#8fa3ff;text-transform:uppercase;margin-bottom:8px}
.customerHero h2{font-size:30px;line-height:1.08;margin:0 0 8px;max-width:760px}
.customerHero p{margin:0;color:var(--text-secondary);font-size:14px;max-width:760px}
.trackBar{display:grid;grid-template-columns:1fr auto auto;gap:8px;margin-top:18px}
.trackBar input{padding:14px 16px;font-size:15px;background:#0d1528;border:1px solid var(--border-strong)}
.trackBar button{width:auto;padding:12px 18px;background:var(--accent-blue)}
.trackBar .quoteBtn{background:#fff;color:#14213d}
.audienceRow{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px}
.audienceBtn{display:flex;align-items:center;justify-content:space-between;text-decoration:none;color:#fff;background:#18233f;border:1px solid var(--border-subtle);border-radius:12px;padding:13px 14px;font-weight:800}
.customerSection{margin-top:14px;background:#121a2e;border:1px solid var(--border-subtle);border-radius:16px;padding:16px}
.customerSection h3{margin:0 0 5px;font-size:18px}
.sectionLead{color:var(--text-secondary);font-size:12px;margin-bottom:12px}
.serviceGrid{display:grid;grid-template-columns:repeat(4,1fr);gap:9px}
.serviceCard{background:#18233a;border:1px solid var(--border-subtle);border-radius:12px;padding:14px;min-height:120px}
.serviceIcon{font-size:24px;margin-bottom:8px}.serviceCard b{display:block;font-size:13px}.serviceCard span{display:block;margin-top:5px;color:var(--text-secondary);font-size:11px;line-height:1.4}
.areaGrid,.trustGrid{display:grid;grid-template-columns:repeat(3,1fr);gap:9px}
.areaCard,.trustCard{background:#18233a;border:1px solid var(--border-subtle);border-radius:12px;padding:13px}
.areaCard b,.trustCard b{display:block;font-size:13px}.areaCard span,.trustCard span{display:block;color:var(--text-secondary);font-size:11px;margin-top:4px}
.customerCta{display:grid;grid-template-columns:1.3fr .7fr;gap:12px;align-items:center;background:linear-gradient(135deg,#263c8a,#172c68)}
.customerCta button{background:#fff;color:#15224a;width:auto;padding:11px 16px}
.customerFooter{margin:14px 0 4px;background:#0e1628;border:1px solid var(--border-subtle);border-radius:16px;padding:16px;display:grid;grid-template-columns:1.4fr 1fr 1fr;gap:16px;font-size:12px}
.customerFooter b{display:block;margin-bottom:7px}.customerFooter a{display:block;color:#aeb9d4;text-decoration:none;margin:5px 0}.customerFooter span{display:block;color:#8f99b2;margin:5px 0}
.customerTrackResult{display:none;margin-top:10px;background:#0d1528;border:1px solid var(--border-subtle);border-radius:10px;padding:11px;font-size:12px}.customerTrackResult.show{display:block}
.customerTrackResult.ok{color:#8ef0b4;border-color:rgba(34,197,94,.35)}.customerTrackResult.err{color:#ffaaaa;border-color:rgba(224,51,47,.4)}
@media(max-width:760px){
  .customerHero{padding:17px}.customerHero h2{font-size:24px}
  .trackBar{grid-template-columns:1fr 1fr}.trackBar input{grid-column:1/-1}
  .trackBar button{width:100%}.serviceGrid{grid-template-columns:1fr 1fr}.areaGrid,.trustGrid{grid-template-columns:1fr}.customerCta{grid-template-columns:1fr}.customerFooter{grid-template-columns:1fr}.audienceRow{grid-template-columns:1fr 1fr}
}
body.navigating .customerLogisticsHome{display:none}
'''
text = text.replace('</style>', css + '\n</style>', 1)

home = r'''
<section class="customerLogisticsHome" id="customerLogisticsHome">
  <div class="customerHero">
    <div class="customerEyebrow">UGANDA NATIONAL GRID LOGISTICS</div>
    <h2>Move freight across Uganda and beyond with one connected network.</h2>
    <p>Track shipments, request transport, manage local and regional deliveries, and connect with the Uganda National Grid logistics network.</p>
    <div class="trackBar">
      <input id="customerTrackInput" autocomplete="off" placeholder="Enter tracking number e.g. UG-SHIP-000001" />
      <button type="button" id="customerTrackBtn">Track</button>
      <button type="button" class="quoteBtn" id="customerQuoteBtn">Get a Quote</button>
    </div>
    <div id="customerTrackResult" class="customerTrackResult"></div>
    <div class="audienceRow">
      <a class="audienceBtn" href="#customerServices"><span>Ship With Us</span><span>→</span></a>
      <a class="audienceBtn" href="#customerDrive"><span>Drive For Us</span><span>→</span></a>
    </div>
  </div>

  <section class="customerSection" id="customerServices">
    <h3>Core Services</h3><div class="sectionLead">Flexible transport options for domestic, regional and international supply chains.</div>
    <div class="serviceGrid">
      <div class="serviceCard"><div class="serviceIcon">✈</div><b>Air Freight</b><span>Priority and time-sensitive cargo coordination through major airports.</span></div>
      <div class="serviceCard"><div class="serviceIcon">⚓</div><b>Ocean & Port Freight</b><span>Regional import/export coordination through East African seaports and inland connections.</span></div>
      <div class="serviceCard"><div class="serviceIcon">🚛</div><b>Regional Trucking</b><span>Road freight between Uganda and neighboring regional markets.</span></div>
      <div class="serviceCard"><div class="serviceIcon">📦</div><b>Local Delivery</b><span>City, district and last-mile delivery for parcels, commercial goods and scheduled routes.</span></div>
    </div>
  </section>

  <section class="customerSection">
    <h3>Service Areas & Lanes</h3><div class="sectionLead">Primary corridors can expand as network capacity and carrier partnerships grow.</div>
    <div class="areaGrid">
      <div class="areaCard"><b>Uganda Nationwide</b><span>Kampala, Entebbe, Jinja, Mbarara, Gulu, Mbale, Hoima, Arua and additional districts.</span></div>
      <div class="areaCard"><b>East Africa</b><span>Regional road links toward Kenya, Rwanda, Tanzania, South Sudan and DRC.</span></div>
      <div class="areaCard"><b>International Connections</b><span>Air and ocean freight handoff through partner airports, ports and forwarding networks.</span></div>
    </div>
  </section>

  <section class="customerSection">
    <h3>Trust & Operational Visibility</h3><div class="sectionLead">Only publish verified performance claims, certifications, insurance limits and customer testimonials.</div>
    <div class="trustGrid">
      <div class="trustCard"><b>Shipment Visibility</b><span>Customer tracking, delivery status updates and operational records.</span></div>
      <div class="trustCard"><b>Documented Freight</b><span>Invoices, bills of lading, receipts and shipment records managed through the platform.</span></div>
      <div class="trustCard"><b>Real Operations</b><span>Use verified photos of actual vehicles, warehouses and staff when available.</span></div>
    </div>
  </section>

  <section class="customerSection customerCta">
    <div><h3>Ready to move a shipment?</h3><div class="sectionLead" style="margin:0">Use the existing route and shipment tools below to calculate your movement and request service.</div></div>
    <button type="button" id="customerStartQuote">Start a Quote</button>
  </section>

  <section class="customerSection" id="customerDrive">
    <h3>Drive For Us</h3><div class="sectionLead">Drivers and carrier partners can register interest to support pickup, line-haul and last-mile operations.</div>
    <button type="button" id="customerDriverBtn" class="secondaryBtn">Open Driver / Carrier Registration</button>
  </section>

  <footer class="customerFooter">
    <div><b>Uganda National Grid Logistics</b><span>Customer shipping, tracking and logistics services.</span><span>Headquarters: Add verified physical address</span></div>
    <div><b>Contact</b><span>Phone: Add main business number</span><span>Email: Add customer service email</span></div>
    <div><b>Quick Links</b><a href="#customerServices">Services</a><a href="#customerDrive">Drive For Us</a><a href="#" onclick="return false">FAQ</a><a href="#" onclick="return false">Terms & Privacy</a></div>
  </footer>
</section>
'''
marker = '<div class="contentScroll" id="contentScroll">\n<main class="panel">'
if marker not in text:
    raise SystemExit('contentScroll marker not found')
text = text.replace(marker, '<div class="contentScroll" id="contentScroll">\n' + home + '\n<main class="panel">', 1)

js = r'''
<script>
(function(){
  const input=document.getElementById('customerTrackInput');
  const result=document.getElementById('customerTrackResult');
  function show(msg,ok){result.textContent=msg;result.className='customerTrackResult show '+(ok?'ok':'err');}
  async function track(){
    const n=(input.value||'').trim();
    if(!n){show('Enter a tracking number first.',false);return;}
    show('Checking shipment '+n+'…',true);
    const candidates=['/ship/'+encodeURIComponent(n),'/ship/track/'+encodeURIComponent(n),'/tracking/'+encodeURIComponent(n)];
    for(const url of candidates){
      try{const r=await fetch(url);if(!r.ok)continue;const d=await r.json();const status=(d.delivery_status||d.status||d.current_status||'found').toString().replace(/_/g,' ');show(n+' — '+status,true);return;}catch(e){}
    }
    show('Tracking number not found or public tracking is not enabled yet.',false);
  }
  document.getElementById('customerTrackBtn')?.addEventListener('click',track);
  input?.addEventListener('keydown',e=>{if(e.key==='Enter')track();});
  function scrollToQuote(){document.querySelector('main.panel')?.scrollIntoView({behavior:'smooth',block:'start'});}
  document.getElementById('customerQuoteBtn')?.addEventListener('click',scrollToQuote);
  document.getElementById('customerStartQuote')?.addEventListener('click',scrollToQuote);
  document.getElementById('customerDriverBtn')?.addEventListener('click',()=>{
    const tabs=[...document.querySelectorAll('.navTab')];
    const target=tabs.find(x=>/driver|account|profile|more/i.test(x.textContent||''));
    if(target) target.click(); else show('Driver / carrier registration can be connected to your application form next.',false);
  });
})();
</script>
'''
text = text.replace('</body>', js + '\n</body>', 1)
path.write_text(text, encoding='utf-8')
