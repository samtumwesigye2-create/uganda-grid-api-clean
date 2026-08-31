import os, threading, time

DATABASE_URL=os.environ.get("DATABASE_URL","").strip()
_lock=threading.Lock()
_memory=[]


def _connect():
    if not DATABASE_URL:return None
    import psycopg2
    return psycopg2.connect(DATABASE_URL)


def init_incident_store():
    conn=_connect()
    if not conn:return False
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                CREATE TABLE IF NOT EXISTS ugamap_incidents(
                    id UUID PRIMARY KEY,
                    category VARCHAR(32) NOT NULL,
                    lat DOUBLE PRECISION NOT NULL,
                    lon DOUBLE PRECISION NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    status VARCHAR(24) NOT NULL DEFAULT 'new',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    status_updated_at TIMESTAMPTZ,
                    media_type VARCHAR(96),
                    media_data BYTEA,
                    confirm_yes INTEGER NOT NULL DEFAULT 0,
                    confirm_no INTEGER NOT NULL DEFAULT 0,
                    community_status VARCHAR(24) NOT NULL DEFAULT 'unverified'
                );
                CREATE INDEX IF NOT EXISTS idx_ugamap_incidents_status_created ON ugamap_incidents(status,created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_ugamap_incidents_coords ON ugamap_incidents(lat,lon);
                """)
        return True
    finally:conn.close()


def create_incident(record, media_data=None):
    conn=_connect()
    row=dict(record)
    if not conn:
        row['_media_data']=media_data
        with _lock:_memory.append(row)
        return dict(row)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO ugamap_incidents
                (id,category,lat,lon,note,status,created_at,media_type,media_data,confirm_yes,confirm_no,community_status)
                VALUES(%s,%s,%s,%s,%s,%s,to_timestamp(%s),%s,%s,%s,%s,%s)""",
                (row['id'],row['category'],row['lat'],row['lon'],row.get('note',''),row.get('status','new'),row['created_at'],row.get('media_type'),media_data,row.get('confirm_yes',0),row.get('confirm_no',0),row.get('community_status','unverified')))
        return get_incident(row['id'])
    finally:conn.close()


def list_incidents():
    conn=_connect()
    if not conn:
        with _lock:return [public_row(x) for x in reversed(_memory)]
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT id,category,lat,lon,note,status,EXTRACT(EPOCH FROM created_at),EXTRACT(EPOCH FROM status_updated_at),media_type,(media_data IS NOT NULL),confirm_yes,confirm_no,community_status FROM ugamap_incidents ORDER BY created_at DESC""")
            return [_row(r) for r in cur.fetchall()]
    finally:conn.close()


def get_incident(incident_id):
    conn=_connect()
    if not conn:
        with _lock:
            x=next((x for x in _memory if x['id']==incident_id),None)
            return public_row(x) if x else None
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT id,category,lat,lon,note,status,EXTRACT(EPOCH FROM created_at),EXTRACT(EPOCH FROM status_updated_at),media_type,(media_data IS NOT NULL),confirm_yes,confirm_no,community_status FROM ugamap_incidents WHERE id=%s""",(incident_id,))
            r=cur.fetchone();return _row(r) if r else None
    finally:conn.close()


def update_status(incident_id,status):
    now=time.time();conn=_connect()
    if not conn:
        with _lock:
            for x in _memory:
                if x['id']==incident_id:
                    x['status']=status;x['status_updated_at']=now;return public_row(x)
        return None
    try:
        with conn:
            with conn.cursor() as cur:cur.execute("UPDATE ugamap_incidents SET status=%s,status_updated_at=to_timestamp(%s) WHERE id=%s",(status,now,incident_id))
        return get_incident(incident_id)
    finally:conn.close()


def confirm_incident(incident_id, confirmed):
    conn=_connect()
    if not conn:
        with _lock:
            for x in _memory:
                if x['id']==incident_id:
                    k='confirm_yes' if confirmed else 'confirm_no';x[k]=int(x.get(k,0))+1
                    y,n=int(x.get('confirm_yes',0)),int(x.get('confirm_no',0));x['community_status']='confirmed' if y>=2 and y>n else ('disputed' if n>=2 and n>=y else 'unverified');return public_row(x)
        return None
    try:
        col='confirm_yes' if confirmed else 'confirm_no'
        with conn:
            with conn.cursor() as cur:
                cur.execute(f"UPDATE ugamap_incidents SET {col}={col}+1 WHERE id=%s",(incident_id,))
                cur.execute("""UPDATE ugamap_incidents SET community_status=CASE WHEN confirm_yes>=2 AND confirm_yes>confirm_no THEN 'confirmed' WHEN confirm_no>=2 AND confirm_no>=confirm_yes THEN 'disputed' ELSE 'unverified' END WHERE id=%s""",(incident_id,))
        return get_incident(incident_id)
    finally:conn.close()


def get_media(incident_id):
    conn=_connect()
    if not conn:
        with _lock:
            x=next((x for x in _memory if x['id']==incident_id),None)
            return ((x or {}).get('_media_data'),(x or {}).get('media_type')) if x else (None,None)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT media_data,media_type FROM ugamap_incidents WHERE id=%s",(incident_id,));r=cur.fetchone()
            return (bytes(r[0]) if r and r[0] is not None else None,r[1] if r else None)
    finally:conn.close()


def public_row(x):
    if not x:return None
    r={k:v for k,v in x.items() if not k.startswith('_')}
    if x.get('_media_data') is not None:r['media_url']='/report-media/'+str(x['id'])
    return r


def _row(r):
    out={'id':str(r[0]),'category':r[1],'lat':r[2],'lon':r[3],'note':r[4] or '','status':r[5],'created_at':float(r[6]),'status_updated_at':float(r[7]) if r[7] is not None else None,'media_type':r[8],'confirm_yes':r[10] or 0,'confirm_no':r[11] or 0,'community_status':r[12] or 'unverified'}
    if r[9]:out['media_url']='/report-media/'+out['id']
    return out

try:init_incident_store()
except Exception:pass
