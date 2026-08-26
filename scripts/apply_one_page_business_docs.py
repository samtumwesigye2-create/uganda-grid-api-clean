from pathlib import Path

files = [
    Path('business-documents/invoice.html'),
    Path('business-documents/bill-of-lading.html'),
    Path('business-documents/receipt.html'),
]
link = '<link rel="stylesheet" href="/business-documents/one-page-print.css?v=2">'
for p in files:
    s = p.read_text(encoding='utf-8')
    if 'one-page-print.css' in s:
        s = s.replace('one-page-print.css?v=1','one-page-print.css?v=2')
    else:
        marker = '</title>'
        if marker not in s:
            raise SystemExit(f'Missing title marker in {p}')
        s = s.replace(marker, marker + link, 1)
    p.write_text(s, encoding='utf-8')
