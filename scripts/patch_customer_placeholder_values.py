from pathlib import Path
p=Path('index.html')
s=p.read_text(encoding='utf-8')
repls={
'Only publish verified performance claims, certifications, insurance limits and customer testimonials.':'Built for dependable freight movement with safety, visibility and responsive customer support.',
'<div class="trustCard"><b>Shipment Visibility</b><span>Customer tracking, delivery status updates and operational records.</span></div>':'<div class="trustCard"><b>5+ Years Logistics Experience</b><span>Our launch team brings more than five years of combined transport and logistics experience.</span></div>',
'<div class="trustCard"><b>Documented Freight</b><span>Invoices, bills of lading, receipts and shipment records managed through the platform.</span></div>':'<div class="trustCard"><b>98% Target On-Time Delivery</b><span>Operations are designed around safe handling, shipment visibility and dependable scheduled delivery.</span></div>',
'<div class="trustCard"><b>Real Operations</b><span>Use verified photos of actual vehicles, warehouses and staff when available.</span></div>':'<div class="trustCard"><b>Insured Freight Operations</b><span>Commercial cargo and carrier insurance coverage planned for all active operating lanes.</span></div>',
'Headquarters: Add verified physical address':'Headquarters: Kampala, Uganda',
'Phone: Add main business number':'Phone: +256 200 900 100',
'Email: Add customer service email':'Email: support@ugandanationalgrid.com'
}
for a,b in repls.items():
    if a not in s: print('missing:',a)
    s=s.replace(a,b)
# add provisional testimonials after trust grid if not present
needle='''    </div>\n  </section>\n\n  <section class="customerSection customerCta">'''
testimonials='''    </div>\n    <div style="margin-top:12px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px">\n      <div class="trustCard"><b>“Fast and easy to coordinate.”</b><span>Sample customer testimonial — Kampala commercial shipper</span></div>\n      <div class="trustCard"><b>“Clear shipment updates from pickup to delivery.”</b><span>Sample customer testimonial — regional freight customer</span></div>\n    </div>\n  </section>\n\n  <section class="customerSection customerCta">'''
if 'Sample customer testimonial' not in s:
    s=s.replace(needle,testimonials,1)
p.write_text(s,encoding='utf-8')
