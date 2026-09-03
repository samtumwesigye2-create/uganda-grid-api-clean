from __future__ import annotations

import os, sqlite3, time, uuid
from typing import Any, Dict

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse

router = APIRouter(prefix='/api/ugatu/driver-documents', tags=['UGATU Driver Documents'])
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'data_hub.db')
DOC_DIR = os.path.join(BASE_DIR, 'uploads', 'platform-docs')
os.makedirs(DOC_DIR, exist_ok=True)


def _conn():
    c = sqlite3.connect(DB_PATH); c.row_factory = sqlite3.Row; return c


def _driver(passcode: str) -> Dict[str, Any]:
    if not passcode: raise HTTPException(401, 'Driver passcode required')
    c = _conn()
    try: row = c.execute('SELECT * FROM drivers WHERE passcode=? AND is_active=1', (passcode,)).fetchone()
    finally: c.close()
    if not row: raise HTTPException(401, 'Invalid driver passcode')
    return dict(row)


def _task_for_driver(c, driver_id: str, task_id: str):
    row = c.execute('SELECT * FROM dispatch_tasks WHERE id=? AND driver_id=?', (task_id, driver_id)).fetchone()
    if not row: raise HTTPException(404, 'Driver task not found')
    return dict(row)


def _ensure_platform_tables(c):
    c.execute('''CREATE TABLE IF NOT EXISTS platform_documents(id TEXT PRIMARY KEY,name TEXT NOT NULL,stored_name TEXT NOT NULL,mime_type TEXT,size INTEGER NOT NULL,version INTEGER NOT NULL DEFAULT 1,tags TEXT,owner TEXT,created_at REAL NOT NULL,updated_at REAL NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS platform_document_versions(id TEXT PRIMARY KEY,document_id TEXT NOT NULL,version INTEGER NOT NULL,stored_name TEXT NOT NULL,size INTEGER NOT NULL,created_at REAL NOT NULL)''')


@router.get('/task/{task_id}')
def documents_for_task(task_id: str, x_driver_passcode: str = Header(default='')):
    d = _driver(x_driver_passcode); c = _conn()
    try:
        _ensure_platform_tables(c); t = _task_for_driver(c, d['id'], task_id)
        refs = [task_id, t.get('task_number') or '', t.get('shipment_number') or '']
        clauses = ' OR '.join(['tags LIKE ?' for _ in refs])
        rows = c.execute(f'SELECT * FROM platform_documents WHERE {clauses} ORDER BY updated_at DESC', tuple('%'+r+'%' for r in refs)).fetchall()
    finally: c.close()
    docs = [dict(x) for x in rows]
    return {
        'task_id': task_id,
        'shipment_number': t.get('shipment_number'),
        'templates': [
            {'type':'BOL','name':'Bill of Lading','url':'/business-documents/bill-of-lading.html'},
            {'type':'RECEIPT','name':'Receipt / Proof Document','url':'/business-documents/receipt.html'},
        ],
        'documents': docs,
    }


@router.get('/{document_id}/download')
def driver_document_download(document_id: str, x_driver_passcode: str = Header(default='')):
    d = _driver(x_driver_passcode); c = _conn()
    try:
        _ensure_platform_tables(c)
        doc = c.execute('SELECT * FROM platform_documents WHERE id=?', (document_id,)).fetchone()
        if not doc: raise HTTPException(404, 'Document not found')
        tags = str(doc['tags'] or '')
        tasks = c.execute('SELECT id,task_number,shipment_number FROM dispatch_tasks WHERE driver_id=?', (d['id'],)).fetchall()
        allowed = any(str(x['id']) in tags or str(x['task_number'] or '') in tags or (x['shipment_number'] and str(x['shipment_number']) in tags) for x in tasks)
        if not allowed: raise HTTPException(403, 'Document is not assigned to this driver')
        path = os.path.join(DOC_DIR, doc['stored_name'])
        name = doc['name']; mime = doc['mime_type'] or 'application/octet-stream'; version = doc['version']
    finally: c.close()
    if not os.path.isfile(path): raise HTTPException(404, 'Stored file is missing')
    return FileResponse(path, filename=name, media_type=mime, headers={'X-Document-Version': str(version)})


@router.post('/task/{task_id}/scan')
async def scan_document(task_id: str, file: UploadFile = File(...), document_type: str = Form('SCANNED_DOCUMENT'), notes: str = Form(''), x_driver_passcode: str = Header(default='')):
    d = _driver(x_driver_passcode); data = await file.read()
    if not data: raise HTTPException(400, 'Document image/file is empty')
    if len(data) > 15*1024*1024: raise HTTPException(413, 'Document exceeds 15 MB')
    c = _conn()
    try:
        _ensure_platform_tables(c); t = _task_for_driver(c, d['id'], task_id)
        did = 'DOC-' + uuid.uuid4().hex[:10].upper(); version = 1; now = time.time()
        stored = f'{did}-v1-{uuid.uuid4().hex[:8]}'
        with open(os.path.join(DOC_DIR, stored), 'wb') as fh: fh.write(data)
        tags = '|'.join(filter(None, ['UGATU_DRIVER', document_type.strip().upper(), task_id, t.get('task_number'), t.get('shipment_number'), f"driver:{d['id']}", notes[:300]]))
        c.execute('INSERT INTO platform_documents VALUES (?,?,?,?,?,?,?,?,?,?)', (did, file.filename or 'driver-document', stored, file.content_type or 'application/octet-stream', len(data), version, tags, d['id'], now, now))
        c.execute('INSERT INTO platform_document_versions VALUES (?,?,?,?,?,?)', (str(uuid.uuid4()), did, version, stored, len(data), now))
        c.commit()
    finally: c.close()
    return {'id': did, 'task_id': task_id, 'shipment_number': t.get('shipment_number'), 'document_type': document_type.strip().upper(), 'version': 1, 'size': len(data), 'linked': True}
