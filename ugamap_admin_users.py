import os
from fastapi import APIRouter, Form, Header, HTTPException
from main import check_admin

DATABASE_URL=os.environ.get('DATABASE_URL','').strip()
router=APIRouter(prefix='/admin/users',tags=['UGAMAP Admin Users'])

def _connect():
    if not DATABASE_URL: raise RuntimeError('Permanent user storage unavailable')
    import psycopg2
    return psycopg2.connect(DATABASE_URL)

def init_admin_users():
    conn=_connect()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""ALTER TABLE ugamap_users ADD COLUMN IF NOT EXISTS account_status VARCHAR(16) NOT NULL DEFAULT 'active';
                CREATE TABLE IF NOT EXISTS ugamap_admin_user_actions(action_id BIGSERIAL PRIMARY KEY,user_id UUID NOT NULL,action VARCHAR(24) NOT NULL,reason TEXT,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
                CREATE INDEX IF NOT EXISTS idx_admin_user_actions_user ON ugamap_admin_user_actions(user_id,created_at DESC);""")
    finally: conn.close()

def _admin(passcode):
    try: check_admin(passcode)
    except Exception: raise HTTPException(status_code=401,detail='Admin authorization required')

def _row(r):
    return {'id':str(r[0]),'email':r[1],'phone':r[2],'account_status':r[3] or 'active','created_at':float(r[4]),'score':r[5] if r[5] is not None else 50,'trust_level':r[6] or 'standard','flagged':bool(r[7]),'reports_total':r[8] or 0,'confirmed_reports':r[9] or 0,'disputed_reports':r[10] or 0}

@router.get('')
def list_users(x_admin_passcode:str=Header(default='')):
    _admin(x_admin_passcode); conn=_connect()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT u.id,u.email,u.phone,u.account_status,EXTRACT(EPOCH FROM u.created_at),r.score,r.trust_level,r.flagged,r.reports_total,r.confirmed_reports,r.disputed_reports FROM ugamap_users u LEFT JOIN ugamap_reporter_reputation r ON r.user_id=u.id ORDER BY COALESCE(r.flagged,FALSE) DESC,u.created_at DESC LIMIT 500""")
            rows=[_row(r) for r in cur.fetchall()]
        return {'count':len(rows),'results':rows}
    finally: conn.close()

@router.get('/flagged')
def flagged_users(x_admin_passcode:str=Header(default='')):
    _admin(x_admin_passcode); conn=_connect()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT u.id,u.email,u.phone,u.account_status,EXTRACT(EPOCH FROM u.created_at),r.score,r.trust_level,r.flagged,r.reports_total,r.confirmed_reports,r.disputed_reports FROM ugamap_users u JOIN ugamap_reporter_reputation r ON r.user_id=u.id WHERE r.flagged=TRUE ORDER BY r.score ASC""")
            rows=[_row(r) for r in cur.fetchall()]
        return {'count':len(rows),'results':rows}
    finally: conn.close()

@router.post('/{user_id}/status')
def set_status(user_id:str,status:str=Form(...),reason:str=Form(''),x_admin_passcode:str=Header(default='')):
    _admin(x_admin_passcode); value=status.strip().lower()
    if value not in {'active','suspended'}: raise HTTPException(status_code=400,detail='Status must be active or suspended')
    conn=_connect()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute('UPDATE ugamap_users SET account_status=%s,updated_at=NOW() WHERE id=%s',(value,user_id))
                if cur.rowcount==0: raise HTTPException(status_code=404,detail='User not found')
                cur.execute('INSERT INTO ugamap_admin_user_actions(user_id,action,reason) VALUES(%s,%s,%s)',(user_id,'suspend' if value=='suspended' else 'reinstate',reason or None))
                if value=='suspended': cur.execute('UPDATE ugamap_user_sessions SET revoked_at=NOW() WHERE user_id=%s AND revoked_at IS NULL',(user_id,))
        return {'id':user_id,'account_status':value,'ok':True}
    finally: conn.close()

@router.get('/{user_id}/audit')
def user_audit(user_id:str,x_admin_passcode:str=Header(default='')):
    _admin(x_admin_passcode); conn=_connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT action,reason,EXTRACT(EPOCH FROM created_at) FROM ugamap_admin_user_actions WHERE user_id=%s ORDER BY created_at DESC LIMIT 100",(user_id,))
            rows=[{'action':r[0],'reason':r[1] or '','created_at':float(r[2])} for r in cur.fetchall()]
        return {'count':len(rows),'results':rows}
    finally: conn.close()

try:
    if DATABASE_URL:init_admin_users()
except Exception: pass
