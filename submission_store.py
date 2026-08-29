import os, json, threading
from datetime import datetime, timezone

DATABASE_URL=os.environ.get("DATABASE_URL","").strip()
_lock=threading.Lock()
_memory=[]

def _connect():
    if not DATABASE_URL:return None
    import psycopg2
    return psycopg2.connect(DATABASE_URL)

def init_submission_store():
    conn=_connect()
    if not conn:return False
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                CREATE TABLE IF NOT EXISTS address_applications(
                    id UUID PRIMARY KEY,
                    lat DOUBLE PRECISION NOT NULL,
                    lon DOUBLE PRECISION NOT NULL,
                    building_type VARCHAR(32) NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    status VARCHAR(16) NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    assigned_grid_id VARCHAR(64),
                    assigned_address TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_address_applications_status_created
                ON address_applications(status,created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_address_applications_coords
                ON address_applications(lat,lon);
                """)
        return True
    finally:conn.close()

def create_submission(record):
    conn=_connect()
    if not conn:
        with _lock:_memory.append(dict(record))
        return record
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO address_applications
                (id,lat,lon,building_type,note,status,created_at)
                VALUES(%s,%s,%s,%s,%s,%s,to_timestamp(%s))""",
                (record['id'],record['lat'],record['lon'],record['building_type'],record.get('note',''),record.get('status','pending'),record['created_at']))
        return record
    finally:conn.close()

def list_submissions(status=''):
    conn=_connect()
    if not conn:
        with _lock:
            rows=[dict(x) for x in _memory if not status or x.get('status')==status]
        return list(reversed(rows))
    try:
        with conn.cursor() as cur:
            if status:
                cur.execute("SELECT id,lat,lon,building_type,note,status,EXTRACT(EPOCH FROM created_at),assigned_grid_id,assigned_address FROM address_applications WHERE status=%s ORDER BY created_at DESC",(status,))
            else:
                cur.execute("SELECT id,lat,lon,building_type,note,status,EXTRACT(EPOCH FROM created_at),assigned_grid_id,assigned_address FROM address_applications ORDER BY created_at DESC")
            return [_row(r) for r in cur.fetchall()]
    finally:conn.close()

def get_submission(submission_id):
    conn=_connect()
    if not conn:
        with _lock:
            x=next((x for x in _memory if x['id']==submission_id),None)
            return dict(x) if x else None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id,lat,lon,building_type,note,status,EXTRACT(EPOCH FROM created_at),assigned_grid_id,assigned_address FROM address_applications WHERE id=%s",(submission_id,))
            r=cur.fetchone();return _row(r) if r else None
    finally:conn.close()

def update_submission(submission_id, **changes):
    allowed={'status','assigned_grid_id','assigned_address'}
    changes={k:v for k,v in changes.items() if k in allowed}
    if not changes:return get_submission(submission_id)
    conn=_connect()
    if not conn:
        with _lock:
            for x in _memory:
                if x['id']==submission_id:x.update(changes);return dict(x)
        return None
    try:
        cols=list(changes);vals=[changes[k] for k in cols]
        sql='UPDATE address_applications SET '+','.join(f'{k}=%s' for k in cols)+' WHERE id=%s'
        with conn:
            with conn.cursor() as cur:cur.execute(sql,vals+[submission_id])
        return get_submission(submission_id)
    finally:conn.close()

def _row(r):
    return {'id':str(r[0]),'lat':r[1],'lon':r[2],'building_type':r[3],'note':r[4] or '', 'status':r[5],'created_at':float(r[6]),'assigned_grid_id':r[7],'assigned_address':r[8]}

try:init_submission_store()
except Exception:pass
