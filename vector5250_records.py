"""Independent Vector 5250 system-of-record store."""
import os, sqlite3, time, uuid
from fastapi import APIRouter, Header, HTTPException, Query, Body
from auth import require_permission, is_master

BASE=os.path.dirname(os.path.abspath(__file__))
DB=os.path.join(BASE,'vector5250.db')
router=APIRouter(tags=['Vector 5250 Records'])
PERM='warehouse:manager'

def auth(code:str):
    if is_master(code): return
    try: require_permission(code,PERM)
    except HTTPException: raise HTTPException(status_code=403,detail='Vector 5250 manager access required')

def db():
    c=sqlite3.connect(DB,timeout=30,isolation_level=None);c.row_factory=sqlite3.Row;c.execute('PRAGMA busy_timeout=30000');return c

def init():
    c=db();c.execute('BEGIN IMMEDIATE')
    c.execute('''CREATE TABLE IF NOT EXISTS vector_records(id TEXT PRIMARY KEY,record_no TEXT UNIQUE NOT NULL,record_type TEXT NOT NULL,title TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'ACTIVE',location TEXT NOT NULL DEFAULT '',owner TEXT NOT NULL DEFAULT '',reference TEXT NOT NULL DEFAULT '',details TEXT NOT NULL DEFAULT '',created_at REAL NOT NULL,updated_at REAL NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS vector_journal(id TEXT PRIMARY KEY,record_no TEXT,action TEXT NOT NULL,user_id TEXT NOT NULL,screen_id TEXT NOT NULL,detail TEXT NOT NULL DEFAULT '',created_at REAL NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS vector_locks(record_no TEXT PRIMARY KEY,user_id TEXT NOT NULL,locked_at REAL NOT NULL,expires_at REAL NOT NULL)''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_vector_records_type ON vector_records(record_type,status,updated_at)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_vector_journal_time ON vector_journal(created_at)')
    c.execute('COMMIT');c.close()
init()

def journal(c,record_no,action,user_id,screen_id,detail=''):
    c.execute('INSERT INTO vector_journal VALUES(?,?,?,?,?,?,?)',(str(uuid.uuid4()),record_no,action,user_id,screen_id,detail,time.time()))

def clean_locks(c): c.execute('DELETE FROM vector_locks WHERE expires_at<?',(time.time(),))

@router.get('/vector5250/api/records')
def list_records(q:str=Query(''),record_type:str=Query(''),status:str=Query(''),limit:int=Query(25,ge=1,le=100),offset:int=Query(0,ge=0),x_access_code:str=Header(default='')):
    auth(x_access_code);c=db();sql='SELECT * FROM vector_records WHERE 1=1';a=[]
    if q:
        sql+=' AND (record_no LIKE ? OR title LIKE ? OR reference LIKE ? OR location LIKE ?)';v='%'+q.strip()+'%';a += [v,v,v,v]
    if record_type: sql+=' AND record_type=?';a.append(record_type.upper())
    if status: sql+=' AND status=?';a.append(status.upper())
    total=c.execute('SELECT COUNT(*) n FROM ('+sql+')',a).fetchone()['n'];sql+=' ORDER BY updated_at DESC,record_no LIMIT ? OFFSET ?';a += [limit,offset]
    rows=[dict(x) for x in c.execute(sql,a).fetchall()];c.close();return {'count':total,'offset':offset,'limit':limit,'more':offset+len(rows)<total,'results':rows}

@router.post('/vector5250/api/records')
def create_record(payload:dict=Body(...),x_access_code:str=Header(default=''),x_vector_user:str=Header(default='SYSTEM')):
    auth(x_access_code);record_type=str(payload.get('record_type') or 'GENERAL').upper();record_no=str(payload.get('record_no') or '').strip().upper()
    if not record_no: record_no=f'{record_type[:3]}-{time.strftime("%Y%m%d")}-{uuid.uuid4().hex[:5].upper()}'
    title=str(payload.get('title') or record_no).strip();now=time.time();c=db();c.execute('BEGIN IMMEDIATE')
    try:
        c.execute('INSERT INTO vector_records VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),record_no,record_type,title,str(payload.get('status') or 'ACTIVE').upper(),str(payload.get('location') or ''),str(payload.get('owner') or ''),str(payload.get('reference') or ''),str(payload.get('details') or ''),now,now));journal(c,record_no,'CREATE',x_vector_user,'V5250-CRT','Record created');c.execute('COMMIT');return dict(c.execute('SELECT * FROM vector_records WHERE record_no=?',(record_no,)).fetchone())
    except sqlite3.IntegrityError:c.execute('ROLLBACK');raise HTTPException(409,'Record number already exists')
    finally:c.close()

@router.get('/vector5250/api/records/{record_no}')
def get_record(record_no:str,x_access_code:str=Header(default='')):
    auth(x_access_code);c=db();r=c.execute('SELECT * FROM vector_records WHERE record_no=?',(record_no.upper(),)).fetchone();clean_locks(c);lock=c.execute('SELECT * FROM vector_locks WHERE record_no=?',(record_no.upper(),)).fetchone();c.close()
    if not r: raise HTTPException(404,'Vector record not found')
    return {**dict(r),'lock':dict(lock) if lock else None}

@router.put('/vector5250/api/records/{record_no}')
def update_record(record_no:str,payload:dict=Body(...),x_access_code:str=Header(default=''),x_vector_user:str=Header(default='SYSTEM')):
    auth(x_access_code);c=db();c.execute('BEGIN IMMEDIATE');clean_locks(c);r=c.execute('SELECT * FROM vector_records WHERE record_no=?',(record_no.upper(),)).fetchone()
    if not r:c.execute('ROLLBACK');c.close();raise HTTPException(404,'Vector record not found')
    lock=c.execute('SELECT * FROM vector_locks WHERE record_no=?',(record_no.upper(),)).fetchone()
    if lock and lock['user_id']!=x_vector_user:c.execute('ROLLBACK');c.close();raise HTTPException(409,f"Record locked by {lock['user_id']}")
    vals={k:payload.get(k,r[k]) for k in ['title','status','location','owner','reference','details']};c.execute('UPDATE vector_records SET title=?,status=?,location=?,owner=?,reference=?,details=?,updated_at=? WHERE record_no=?',(vals['title'],str(vals['status']).upper(),vals['location'],vals['owner'],vals['reference'],vals['details'],time.time(),record_no.upper()));journal(c,record_no.upper(),'CHANGE',x_vector_user,'V5250-CHG','Record changed');c.execute('COMMIT');out=dict(c.execute('SELECT * FROM vector_records WHERE record_no=?',(record_no.upper(),)).fetchone());c.close();return out

@router.post('/vector5250/api/records/{record_no}/lock')
def lock_record(record_no:str,x_access_code:str=Header(default=''),x_vector_user:str=Header(default='SYSTEM')):
    auth(x_access_code);c=db();c.execute('BEGIN IMMEDIATE');clean_locks(c);r=c.execute('SELECT 1 FROM vector_records WHERE record_no=?',(record_no.upper(),)).fetchone()
    if not r:c.execute('ROLLBACK');c.close();raise HTTPException(404,'Vector record not found')
    lock=c.execute('SELECT * FROM vector_locks WHERE record_no=?',(record_no.upper(),)).fetchone()
    if lock and lock['user_id']!=x_vector_user:c.execute('ROLLBACK');c.close();raise HTTPException(409,f"Record locked by {lock['user_id']}")
    now=time.time();c.execute('INSERT OR REPLACE INTO vector_locks VALUES(?,?,?,?)',(record_no.upper(),x_vector_user,now,now+900));journal(c,record_no.upper(),'LOCK',x_vector_user,'V5250-WRK','Record locked');c.execute('COMMIT');c.close();return {'record_no':record_no.upper(),'locked_by':x_vector_user,'expires_in':900}

@router.delete('/vector5250/api/records/{record_no}/lock')
def unlock_record(record_no:str,x_access_code:str=Header(default=''),x_vector_user:str=Header(default='SYSTEM')):
    auth(x_access_code);c=db();c.execute('BEGIN IMMEDIATE');lock=c.execute('SELECT * FROM vector_locks WHERE record_no=?',(record_no.upper(),)).fetchone()
    if lock and lock['user_id'] not in {x_vector_user,'SYSTEM'}:c.execute('ROLLBACK');c.close();raise HTTPException(409,f"Record locked by {lock['user_id']}")
    c.execute('DELETE FROM vector_locks WHERE record_no=?',(record_no.upper(),));journal(c,record_no.upper(),'UNLOCK',x_vector_user,'V5250-WRK','Record unlocked');c.execute('COMMIT');c.close();return {'record_no':record_no.upper(),'unlocked':True}

@router.get('/vector5250/api/journal')
def journal_rows(limit:int=Query(50,ge=1,le=200),record_no:str=Query(''),x_access_code:str=Header(default='')):
    auth(x_access_code);c=db();q='SELECT * FROM vector_journal';a=[]
    if record_no:q+=' WHERE record_no=?';a.append(record_no.upper())
    q+=' ORDER BY created_at DESC LIMIT ?';a.append(limit);rows=[dict(x) for x in c.execute(q,a).fetchall()];c.close();return {'results':rows}
