from pathlib import Path

p = Path('ship.html')
s = p.read_text(encoding='utf-8')

if 'shipMarketingHome' in s:
    raise SystemExit('Ship marketing home already installed')

css = r'''
  /* ---- Customer logistics marketing additions ---- */
  body { max-width:1180px; margin:0 auto; }
  .shipMarketingHome { margin-bottom:18px; }
  .shipHero { background:linear-gradient(135deg,#0f1220 0%,#182548 60%,#10182e 100%); color:#fff; border-radius:16px; padding:26px; margin-bottom:14px; }
  .shipHero .eyebrow { font-size:11px; font-weight:800; letter-spacing:.09em; color:#9fb0ff; margin-bottom:8px; }
  .shipHero h1 { margin:0 0 8px; font-size:30px; line-height:1.08; }
  .shipHero p { color:#c0c7d8; margin:0; max-width:760px; line-height:1.5; }
  .heroTrackBar { display:grid; grid-template-columns:1fr auto auto; gap:8px; margin-top:18px; }
  .heroTrackBar input { background:#0d1324; border-color:#3a4260; padding:14px 16px; }
  .heroTrackBar button { border:0; border-radius:8px; padding:12px 18px; color:#fff; font-weight:700; cursor:pointer; }
  .heroTrackBar .trackHeroBtn { background:#e2593a; }
  .heroTrackBar .quoteHeroBtn { background:#3b5bfd; }
  .audienceEntry { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:12px; }
  .audienceEntry a { display:flex; justify-content:space-between; align-items:center; background:#1a1d2e; color:#fff; border:1px solid #30364e; border-radius:10px; padding:13px 14px; text-decoration:none; font-weight:700; }
  .marketingSection { background:#fff; border:1px solid #ddd; border-radius:14px; padding:18px; margin-bottom:14px; }
  .marketingSection h2 { margin:0 0 5px; font-size:19px; }
  .marketingLead { color:#666; font-size:13px; margin-bottom:12px; }
  .serviceGrid { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; }
  .serviceBox,.laneBox,.trustBox,.testimonialBox { border:1px solid #e0e0e0; border-radius:10px; padding:14px; background:#fafafa; }
  .serviceBox b,.laneBox b,.trustBox b,.testimonialBox b { display:block; margin-bottom:5px; }
  .serviceBox span,.laneBox span,.trustBox span,.testimonialBox span { color:#666; font-size:12px; line-height:1.45; }
  .serviceIcon { font-size:22px; margin-bottom:8px; }
  .laneGrid,.trustGrid { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; }
  .testimonialGrid { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:10px; }
  .trustNumber { color:#3b5bfd; font-size:22px; font-weight:800; margin-bottom:4px; }
  .marketingCta { background:#0f1220; color:#fff; display:grid; grid-template-columns:1fr auto; gap:16px; align-items:center; }
  .marketingCta .marketingLead { color:#aaa; margin:0; }
  .marketingCta button { width:auto; min-width:160px; margin:0; }
  .shipFooter { background:#0f1220; color:#fff; border-radius:14px; padding:18px; display:grid; grid-template-columns:1.4fr 1fr 1fr; gap:18px; margin-top:14px; }
  .shipFooter b { display:block; margin-bottom:7px; }
  .shipFooter span,.shipFooter a { display:block; color:#b8bfd0; font-size:12px; margin:5px 0; text-decoration:none; }
  .provisionalNote { font-size:10px; color:#888; margin-top:8px; }
  @media(max-width:760px){
    body { padding:12px; }
    .shipHero { padding:19px; }
    .shipHero h1 { font-size:24px; }
    .heroTrackBar { grid-template-columns:1fr 1fr; }
    .heroTrackBar input { grid-column:1/-1; }
    .heroTrackBar button { width:100%; }
    .serviceGrid { grid-template-columns:1fr 1fr; }
    .laneGrid,.trustGrid,.testimonialGrid,.shipFooter { grid-template-columns:1fr; }
    .marketingCta { grid-template-columns:1fr; }
    .marketingCta button { width:100%; }
  }
'''
s = s.replace('</style>', css + '\n</style>', 1)

home = r'''
<section class="shipMarketingHome" id="shipMarketingHome">
  <div class="shipHero">
    <div class="eyebrow">UGANDA NATIONAL GRID LOGISTICS</div>
    <h1>Ship, track and manage freight from one place.</h1>
    <p>Domestic deliveries, regional freight and international forwarding with shipment visibility from pickup through delivery.</p>
    <div class="heroTrackBar">
      <input id="heroTrackingNumber" autocomplete="off" placeholder="Enter tracking number e.g. UG-SHIP-000001" />
      <button class="trackHeroBtn" type="button" id="heroTrackBtn">Track</button>
      <button class="quoteHeroBtn" type="button" id="heroQuoteBtn">Get a Quote</button>
    </div>
    <div class="audienceEntry">
      <a href="#" id="shipWithUsBtn"><span>Ship With Us</span><span>→</span></a>
      <a href="/driver"><span>Drive For Us</span><span>→</span></a>
    </div>
  </div>

  <section class="marketingSection">
    <h2>Core Services</h2>
    <div class="marketingLead">Flexible transport options for parcels, commercial freight and regional supply chains.</div>
    <div class="serviceGrid">
      <div class="serviceBox"><div class="serviceIcon">✈</div><b>Air Freight</b><span>Priority and time-sensitive cargo coordination through major airports.</span></div>
      <div class="serviceBox"><div class="serviceIcon">⚓</div><b>Ocean & Port Freight</b><span>Import/export coordination through East African ports with inland connections to Uganda.</span></div>
      <div class="serviceBox"><div class="serviceIcon">🚛</div><b>Regional Trucking</b><span>Road freight throughout Uganda and across neighboring East African markets.</span></div>
      <div class="serviceBox"><div class="serviceIcon">📦</div><b>Local Delivery</b><span>City, district and last-mile delivery for parcels and commercial goods.</span></div>
    </div>
  </section>

  <section class="marketingSection">
    <h2>Service Areas & Lanes</h2>
    <div class="marketingLead">Primary operating corridors and planned regional connections.</div>
    <div class="laneGrid">
      <div class="laneBox"><b>Uganda Nationwide</b><span>Kampala, Entebbe, Jinja, Mbarara, Gulu, Mbale, Hoima, Arua and additional districts.</span></div>
      <div class="laneBox"><b>East Africa</b><span>Road corridors toward Kenya, Rwanda, Tanzania, South Sudan and eastern DRC.</span></div>
      <div class="laneBox"><b>International Connections</b><span>Air and ocean freight handoff through partner airports, ports and forwarding networks.</span></div>
    </div>
  </section>

  <section class="marketingSection">
    <h2>Trust & Credibility</h2>
    <div class="marketingLead">Provisional launch information — these figures will be replaced with verified operating data.</div>
    <div class="trustGrid">
      <div class="trustBox"><div class="trustNumber">5+ yrs</div><b>Team Experience</b><span>Combined logistics and transport experience across the launch team.</span></div>
      <div class="trustBox"><div class="trustNumber">98%</div><b>On-Time Target</b><span>Service target for scheduled deliveries once full operations begin.</span></div>
      <div class="trustBox"><div class="trustNumber">Insured</div><b>Freight Coverage</b><span>Commercial cargo and carrier coverage planned for active operating lanes.</span></div>
    </div>
    <div class="testimonialGrid">
      <div class="testimonialBox"><b>“Fast and easy to coordinate.”</b><span>Sample testimonial — Kampala commercial shipper</span></div>
      <div class="testimonialBox"><b>“Clear shipment updates from pickup to delivery.”</b><span>Sample testimonial — regional freight customer</span></div>
    </div>
  </section>

  <section class="marketingSection marketingCta">
    <div><h2 style="color:#fff">Ready to move a shipment?</h2><div class="marketingLead">Use the working rate calculator below for domestic or international service.</div></div>
    <button class="btn secondary" type="button" id="marketingQuoteBtn">Get a Quote</button>
  </section>
</section>
'''
marker = '<div class="header">\n  <h1>Ship & Mail</h1>'
if marker not in s:
    raise SystemExit('ship header marker not found')
s = s.replace(marker, home + '\n<div class="header">\n  <h1>Ship & Mail</h1>', 1)

footer = r'''
<footer class="shipFooter">
  <div><b>Uganda National Grid Logistics</b><span>Domestic, regional and international shipping services.</span><span>Headquarters: Kampala, Uganda</span><div class="provisionalNote">Launch contact information shown below is provisional.</div></div>
  <div><b>Contact</b><span>+256 200 900 100</span><span>support@ugandanationalgrid.com</span></div>
  <div><b>Quick Links</b><a href="#shipMarketingHome">Services</a><a href="/driver">Drive For Us</a><a href="#" onclick="return false">FAQ</a><a href="#" onclick="return false">Terms & Privacy</a></div>
</footer>
'''
s = s.replace('\n<script>\ndocument.querySelectorAll', '\n' + footer + '\n<script>\ndocument.querySelectorAll', 1)

js = r'''

function activateShipTab(name) {
  const tab = document.querySelector(`.tab[data-tab="${name}"]`);
  if (!tab) return;
  tab.click();
  document.querySelector('.tabs')?.scrollIntoView({behavior:'smooth', block:'start'});
}

document.getElementById('heroTrackBtn')?.addEventListener('click', () => {
  const n = document.getElementById('heroTrackingNumber').value.trim();
  activateShipTab('track');
  if (n) document.getElementById('trackNumber').value = n;
  if (n) trackShipment();
});
document.getElementById('heroTrackingNumber')?.addEventListener('keydown', e => {
  if (e.key === 'Enter') document.getElementById('heroTrackBtn').click();
});
document.getElementById('heroQuoteBtn')?.addEventListener('click', () => activateShipTab('ship'));
document.getElementById('marketingQuoteBtn')?.addEventListener('click', () => activateShipTab('ship'));
document.getElementById('shipWithUsBtn')?.addEventListener('click', e => { e.preventDefault(); activateShipTab('ship'); });
'''
s = s.replace('\nlet selectedQuote = null;', js + '\nlet selectedQuote = null;', 1)

p.write_text(s, encoding='utf-8')
