from pathlib import Path

path = Path('admin.html')
text = path.read_text(encoding='utf-8')

old_css = '''  .doc-launch-section { margin:4px 0 22px; padding:14px; background:#151829; border:1px solid #2a2d3e; border-radius:12px; }
  .doc-launch-title { font-size:13px; font-weight:800; letter-spacing:.06em; color:#9fb0ff; margin-bottom:10px; }
  .doc-launch-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; }
  .doc-launch-card { display:block; text-decoration:none; color:#fff; border-radius:10px; padding:14px; min-height:112px; border:1px solid rgba(255,255,255,.12); }
  .doc-launch-card.invoice { background:linear-gradient(135deg,#087b4c,#12a66a); }
  .doc-launch-card.bol { background:linear-gradient(135deg,#274ec7,#3b6cff); }
  .doc-launch-card.receipt { background:linear-gradient(135deg,#6d27a8,#9138cc); }
  .doc-launch-card .doc-icon { font-size:24px; display:block; margin-bottom:8px; }
  .doc-launch-card strong { display:block; font-size:16px; margin-bottom:4px; }
  .doc-launch-card small { display:block; color:rgba(255,255,255,.82); line-height:1.35; }
  .doc-launch-card .doc-action { display:block; margin-top:10px; font-size:12px; font-weight:800; }
  @media (max-width:650px) { .doc-launch-grid { grid-template-columns:1fr; } .doc-launch-card { min-height:auto; } }
'''
new_css = '''  .doc-launch-section { margin:0 0 12px; padding:8px 10px; background:#151829; border:1px solid #2a2d3e; border-radius:9px; }
  .doc-launch-title { font-size:10px; font-weight:800; letter-spacing:.06em; color:#9fb0ff; margin-bottom:6px; }
  .doc-launch-grid { display:flex; gap:6px; flex-wrap:wrap; }
  .doc-launch-card { display:inline-flex; align-items:center; gap:5px; text-decoration:none; color:#fff; border-radius:7px; padding:7px 10px; min-height:0; border:1px solid rgba(255,255,255,.12); font-size:12px; }
  .doc-launch-card.invoice { background:linear-gradient(135deg,#087b4c,#12a66a); }
  .doc-launch-card.bol { background:linear-gradient(135deg,#274ec7,#3b6cff); }
  .doc-launch-card.receipt { background:linear-gradient(135deg,#6d27a8,#9138cc); }
  .doc-launch-card .doc-icon { font-size:13px; display:inline; margin:0; }
  .doc-launch-card strong { display:inline; font-size:12px; margin:0; }
  .doc-launch-card small, .doc-launch-card .doc-action { display:none; }
  @media (max-width:650px) { .doc-launch-grid { flex-wrap:wrap; } .doc-launch-card { flex:0 0 auto; } }
'''
if old_css in text:
    text = text.replace(old_css, new_css, 1)

path.write_text(text, encoding='utf-8')
