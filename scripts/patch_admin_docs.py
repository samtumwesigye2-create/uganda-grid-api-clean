from pathlib import Path

path = Path('admin.html')
text = path.read_text(encoding='utf-8')

css_marker = '  .dashNote { font-size:11px; color:#666; margin-top:6px; }\n'
css = '''  .doc-launch-section { margin:4px 0 22px; padding:14px; background:#151829; border:1px solid #2a2d3e; border-radius:12px; }\n  .doc-launch-title { font-size:13px; font-weight:800; letter-spacing:.06em; color:#9fb0ff; margin-bottom:10px; }\n  .doc-launch-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; }\n  .doc-launch-card { display:block; text-decoration:none; color:#fff; border-radius:10px; padding:14px; min-height:112px; border:1px solid rgba(255,255,255,.12); }\n  .doc-launch-card.invoice { background:linear-gradient(135deg,#087b4c,#12a66a); }\n  .doc-launch-card.bol { background:linear-gradient(135deg,#274ec7,#3b6cff); }\n  .doc-launch-card.receipt { background:linear-gradient(135deg,#6d27a8,#9138cc); }\n  .doc-launch-card .doc-icon { font-size:24px; display:block; margin-bottom:8px; }\n  .doc-launch-card strong { display:block; font-size:16px; margin-bottom:4px; }\n  .doc-launch-card small { display:block; color:rgba(255,255,255,.82); line-height:1.35; }\n  .doc-launch-card .doc-action { display:block; margin-top:10px; font-size:12px; font-weight:800; }\n  @media (max-width:650px) { .doc-launch-grid { grid-template-columns:1fr; } .doc-launch-card { min-height:auto; } }\n'''

if 'doc-launch-section' not in text:
    if css_marker not in text:
        raise SystemExit('CSS marker not found')
    text = text.replace(css_marker, css_marker + css, 1)

text = text.replace('data-tab="invoices">Invoices</div>', 'data-tab="invoices">Invoice Records</div>')
text = text.replace('data-tab="bol">Bill of Lading</div>', 'data-tab="bol">B/L Records</div>')

tabs_marker = '    <div class="tab" data-tab="data">Data</div>\n  </div>\n'
launcher = '''    <div class="tab" data-tab="data">Data</div>\n  </div>\n\n  <section class="doc-launch-section">\n    <div class="doc-launch-title">BUSINESS DOCUMENTS</div>\n    <div class="doc-launch-grid">\n      <a class="doc-launch-card invoice" href="/business-documents/invoice.html">\n        <span class="doc-icon">▣</span><strong>Invoice</strong>\n        <small>Create a clean customer invoice with automatic totals and print/PDF support.</small>\n        <span class="doc-action">CREATE INVOICE →</span>\n      </a>\n      <a class="doc-launch-card bol" href="/business-documents/bill-of-lading.html">\n        <span class="doc-icon">▤</span><strong>Bill of Lading</strong>\n        <small>Create shipping paperwork for shipper, consignee, carrier and goods.</small>\n        <span class="doc-action">CREATE B/L →</span>\n      </a>\n      <a class="doc-launch-card receipt" href="/business-documents/receipt.html">\n        <span class="doc-icon">▧</span><strong>Receipt</strong>\n        <small>Create payment receipts with automatic totals and print/PDF support.</small>\n        <span class="doc-action">CREATE RECEIPT →</span>\n      </a>\n    </div>\n  </section>\n'''

if '<section class="doc-launch-section">' not in text:
    if tabs_marker not in text:
        raise SystemExit('Tabs marker not found')
    text = text.replace(tabs_marker, launcher, 1)

path.write_text(text, encoding='utf-8')
