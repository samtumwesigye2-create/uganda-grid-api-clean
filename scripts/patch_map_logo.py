from pathlib import Path

p = Path('index.html')
s = p.read_text(encoding='utf-8')

css_marker = 'header p{margin:1px 0 0;font-size:10px;color:var(--text-secondary)}'
css_add = css_marker + "\nheader .titleWrap{display:flex;align-items:center;justify-content:center;gap:8px;text-align:left;min-width:0}\n.mapHeaderLogo{width:34px;height:34px;object-fit:contain;display:block;flex:0 0 auto;border-radius:4px;background:#fff}\n.mapHeaderText{min-width:0;text-align:left}\n@media(max-width:420px){.mapHeaderLogo{width:30px;height:30px}header h1{font-size:14px}header p{font-size:9px}}"

if '.mapHeaderLogo{' not in s:
    if css_marker not in s:
        raise SystemExit('Expected header CSS marker not found; refusing to modify index.html')
    s = s.replace(css_marker, css_add, 1)

old = '''<div class="titleWrap">\n<h1>Uganda National Grid</h1>\n<p>Search, route and navigate across Uganda</p>\n</div>'''
new = '''<div class="titleWrap">\n<img class="mapHeaderLogo" src="/assets/uganda-national-grid-logo.png?v=map-logo-1" alt="Uganda National Grid">\n<div class="mapHeaderText">\n<h1>Uganda National Grid</h1>\n<p>Search, route and navigate across Uganda</p>\n</div>\n</div>'''

if 'class="mapHeaderLogo"' not in s:
    if old not in s:
        raise SystemExit('Expected map header markup not found; refusing to modify index.html')
    s = s.replace(old, new, 1)

p.write_text(s, encoding='utf-8')
print('Map logo patch applied safely')
