import os, json, threading

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
                    status VARCHAR(24) NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    assigned_grid_id VARCHAR(64),
                    assigned_address TEXT,
                    assigned_zip_code VARCHAR(16),
                    confidence_score INTEGER,
                    confidence_decision VARCHAR(24),
                    confidence_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
                    gps_accuracy_m DOUBLE PRECISION,
                    approval_method VARCHAR(24),
                    reviewed_at TIMESTAMPTZ
                );
                ALTER TABLE address_applications ADD COLUMN IF NOT EXISTS assigned_zip_code VARCHAR(16);
                ALTER TABLE address_applications ADD COLUMN IF NOT EXISTS confidence_score INTEGER;
                ALTER TABLE address_applications ADD COLUMN IF NOT EXISTS confidence_decision VARCHAR(24);
                ALTER TABLE address_applications ADD COLUMN IF NOT EXISTS confidence_reasons JSONB NOT NULL DEFAULT '[]'::jsonb;
                ALTER TABLE address_applications ADD COLUMN IF NOT EXISTS gps_accuracy_m DOUBLE PRECISION;
                ALTER TABLE address_applications ADD COLUMN IF NOT EXISTS approval_method VARCHAR(24);
                ALTER TABLE address_applications ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ;
                CREATE INDEX IF NOT EXISTS idx_address_applications_status_created ON address_applications(status,created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_address_applications_coords ON address_applications(lat,lon);
                CREATE INDEX IF NOT EXISTS idx_address_applications_confidence ON address_applications(confidence_decision,confidence_score);
                """)
        return True
    finally:conn.close()

def create_submission(record):
    conn=_connect()
    if not conn:
        with _lock:_memory.append(dict(record))
        return dict(record)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO address_applications
                (id,lat,lon,building_type,note,status,created_at,gps_accuracy_m,confidence_score,confidence_decision,confidence_reasons,approval_method)
                VALUES(%s,%s,%s,%s,%s,%s,to_timestamp(%s),%s,%s,%s,%s::jsonb,%s)""",
                (record['id'],record['lat'],record['lon'],record['building_type'],record.get('note',''),record.get('status','pending'),record['created_at'],record.get('gps_accuracy_m'),record.get('confidence_score'),record.get('confidence_decision'),json.dumps(record.get('confidence_reasons',[])),record.get('approval_method')))
        return dict(record)
    finally:conn.close()

def list_submissions(status=''):
    conn=_connect()
    if not conn:
        with _lock:rows=[dict(x) for x in _memory if not status or x.get('status')==status]
        return list(reversed(rows))
    try:
        with conn.cursor() as cur:
            q="""SELECT id,lat,lon,building_type,note,status,EXTRACT(EPOCH FROM created_at),assigned_grid_id,assigned_address,assigned_zip_code,confidence_score,confidence_decision,confidence_reasons,gps_accuracy_m,approval_method,EXTRACT(EPOCH FROM reviewed_at) FROM address_applications"""
            if status:cur.execute(q+" WHERE status=%s ORDER BY created_at DESC",(status,))
            else:cur.execute(q+" ORDER BY created_at DESC")
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
            cur.execute("""SELECT id,lat,lon,building_type,note,status,EXTRACT(EPOCH FROM created_at),assigned_grid_id,assigned_address,assigned_zip_code,confidence_score,confidence_decision,confidence_reasons,gps_accuracy_m,approval_method,EXTRACT(EPOCH FROM reviewed_at) FROM address_applications WHERE id=%s""",(submission_id,))
            r=cur.fetchone();return _row(r) if r else None
    finally:conn.close()

def update_submission(submission_id, **changes):
    allowed={'status','assigned_grid_id','assigned_address','assigned_zip_code','confidence_score','confidence_decision','confidence_reasons','gps_accuracy_m','approval_method','reviewed_at'}
    changes={k:v for k,v in changes.items() if k in allowed}
    if not changes:return get_submission(submission_id)
    conn=_connect()
    if not conn:
        with _lock:
            for x in _memory:
                if x['id']==submission_id:x.update(changes);return dict(x)
        return None
    try:
        cols=list(changes);vals=[];sets=[]
        for k in cols:
            if k=='confidence_reasons':sets.append(k+'=%s::jsonb');vals.append(json.dumps(changes[k] or []))
            elif k=='reviewed_at':sets.append(k+'=to_timestamp(%s)');vals.append(changes[k])
            else:sets.append(k+'=%s');vals.append(changes[k])
        with conn:
            with conn.cursor() as cur:cur.execute('UPDATE address_applications SET '+','.join(sets)+' WHERE id=%s',vals+[submission_id])
        return get_submission(submission_id)
    finally:conn.close()

def _row(r):
    return {'id':str(r[0]),'lat':r[1],'lon':r[2],'building_type':r[3],'note':r[4] or '', 'status':r[5],'created_at':float(r[6]),'assigned_grid_id':r[7],'assigned_address':r[8],'assigned_zip_code':r[9],'confidence_score':r[10],'confidence_decision':r[11],'confidence_reasons':r[12] or [],'gps_accuracy_m':r[13],'approval_method':r[14],'reviewed_at':float(r[15]) if r[15] is not None else None}

try:init_submission_store()
except Exception:pass
