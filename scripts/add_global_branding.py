from pathlib import Path
import re

ROOT = Path('.')
LOGO_PATH = '/assets/uganda-national-grid-logo.png'

PAGES = [
    'index.html',
    'submit.html',
    'ship.html',
    'admin.html',
    'driver.html',
    'review.html',
    'test-tool.html',
    'track.html',
    'business-documents/invoice.html',
    'business-documents/bill-of-lading.html',
    'business-documents/receipt.html',
]

STYLE = r'''
<style id="ungGlobalBrandStyle">
  .ungGlobalBrand{
    flex:0 0 auto;
    width:100%;
    min-height:58px;
    padding:5px 12px;
    display:flex;
    align-items:center;
    justify-content:center;
    background:#fff;
    border-bottom:1px solid rgba(15,23,42,.12);
    position:relative;
    z-index:4200;
  }
  .ungGlobalBrand a{display:flex;align-items:center;justify-content:center;text-decoration:none;line-height:0;}
  .ungGlobalBrand img{
    display:block;
    width:min(230px,62vw);
    max-height:56px;
    object-fit:contain;
  }
  @media(max-width:600px){
    .ungGlobalBrand{min-height:52px;padding:4px 10px;}
    .ungGlobalBrand img{width:min(205px,68vw);max-height:50px;}
  }
  @media print{
    .ungGlobalBrand{border-bottom:0;padding:0 0 8px;min-height:0;}
    .ungGlobalBrand img{width:190px;max-height:50px;}
  }
</style>
'''

MARKUP = f'''\n<div class="ungGlobalBrand" id="ungGlobalBrand"><a href="/" aria-label="Uganda National Grid home"><img src="{LOGO_PATH}" alt="Uganda National Grid" /></a></div>\n'''

for rel in PAGES:
    p = ROOT / rel
    if not p.exists():
        print('missing', rel)
        continue
    s = p.read_text(encoding='utf-8')
    if 'id="ungGlobalBrand"' not in s:
        if '</head>' in s and 'id="ungGlobalBrandStyle"' not in s:
            s = s.replace('</head>', STYLE + '\n</head>', 1)
        # Handles <body> and <body class="...">.
        s, n = re.subn(r'(<body\b[^>]*>)', r'\1' + MARKUP, s, count=1, flags=re.I)
        if not n:
            print('no body tag', rel)
        p.write_text(s, encoding='utf-8')

# Serve the shared logo asset from FastAPI.
main = ROOT / 'main.py'
if main.exists():
    s = main.read_text(encoding='utf-8')
    if 'app.mount("/assets"' not in s:
        needle = 'UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")\n'
        insert = (
            'ASSETS_DIR = os.path.join(BASE_DIR, "assets")\n'
            'if os.path.isdir(ASSETS_DIR):\n'
            '    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")\n\n'
        )
        if needle in s:
            s = s.replace(needle, insert + needle, 1)
        else:
            raise RuntimeError('Could not find uploads mount anchor in main.py')
        main.write_text(s, encoding='utf-8')

print('Global Uganda National Grid branding patch complete')
