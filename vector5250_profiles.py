"""Vector 5250 user profiles, sign-on identity binding, and session tokens."""
import hashlib, secrets, sqlite3, time, uuid, threading
from pathlib import Path
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from auth import is_master, require_permission

router=APIRouter(prefix='/vector5250',tags=['Vector 5250 Profiles'])
DB=Path('vector5250.db');PERM='warehouse:manager';SESSION_TTL=8*60*60
_sessions={};_session_lock=threading.Lock()

def db():
    c=sqlite3.connect(DB);c.row_factory=sqlite3.Row
    c.executescript('''CREATE TABLE IF NOT EXISTS vector_profiles(id TEXT PRIMARY KEY,user_id TEXT UNIQUE NOT NULL,display_name TEXT NOT NULL,role TEXT NOT NULL,authority TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'ACTIVE',auth_hash TEXT NOT NULL,created_at REAL NOT NULL,updated_at REAL NOT NULL,last_signon REAL);CREATE TABLE IF NOT EXISTS vector_profile_audit(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,action TEXT NOT NULL,actor TEXT NOT NULL,detail TEXT NOT NULL,created_at REAL NOT NULL);''');c.commit();return c

def h(s:str):return hashlib.sha256((s or '').encode()).hexdigest()
def manager(code:str):
    if is_master(code):return
    require_permission(code,PERM)
def audit(c,user,action,actor,detail):c.execute('INSERT INTO vector_profile_audit VALUES(?,?,?,?,?,?)',(uuid.uuid4().hex,user,action,actor,detail,time.time()))
def _cleanup_sessions():
    now=time.time()
    with _session_lock:
        for token in [k for k,v in _sessions.items() if v['expires_at']<=now]:_sessions.pop(token,None)
def resolve_session_token(token:str):
    _cleanup_sessions()
    with _session_lock:
        s=_sessions.get(token)
        return dict(s) if s else None

def _authenticate(user_id:str,authorization:str,outer_code:str):
    manager(outer_code);u=user_id.strip().upper();c=db();r=c.execute('SELECT * FROM vector_profiles WHERE user_id=?',(u,)).fetchone();count=c.execute('SELECT COUNT(*) n FROM vector_profiles').fetchone()['n']
    if not r:
        c.close()
        if count==0 and outer_code and is_master(outer_code):return {'user_id':u,'display_name':u,'role':'ADMINISTRATOR','authority':'*ALLOBJ','status':'ACTIVE','bootstrap_mode':True}
        raise HTTPException(401,'Vector user profile not found')
    if r['status']!='ACTIVE' or r['auth_hash']!=h(authorization):c.close();raise HTTPException(401,'Invalid Vector user ID or authorization')
    ts=time.time();c.execute('UPDATE vector_profiles SET last_signon=?,updated_at=? WHERE user_id=?',(ts,ts,u));audit(c,u,'SIGNON',u,'Interactive Vector sign-on');c.commit();out={k:r[k] for k in ('user_id','display_name','role','authority','status')};c.close();return out

class ProfileCreate(BaseModel):user_id:str;display_name:str;authorization:str;role:str='MANAGER';authority:str='MANAGER'
class ProfileUpdate(BaseModel):display_name:str|None=None;authorization:str|None=None;role:str|None=None;authority:str|None=None;status:str|None=None
class Signon(BaseModel):user_id:str;authorization:str

@router.post('/profiles/bootstrap')
def bootstrap(x_access_code:str=Header(default='')):
    if not is_master(x_access_code):raise HTTPException(403,'Master authorization required')
    c=db();row=c.execute('SELECT COUNT(*) n FROM vector_profiles').fetchone();c.close();return {'profile_count':row['n'],'bootstrap_required':row['n']==0}
@router.get('/profiles')
def list_profiles(x_access_code:str=Header(default='')):
    manager(x_access_code);c=db();rows=[dict(r) for r in c.execute('SELECT id,user_id,display_name,role,authority,status,created_at,updated_at,last_signon FROM vector_profiles ORDER BY user_id')];c.close();return {'count':len(rows),'results':rows}
@router.post('/profiles')
def create_profile(b:ProfileCreate,x_access_code:str=Header(default=''),x_vector_user:str=Header(default='SYSTEM')):
    manager(x_access_code);u=b.user_id.strip().upper()
    if not u or not b.authorization:raise HTTPException(400,'User ID and authorization required')
    c=db()
    try:
        ts=time.time();c.execute('INSERT INTO vector_profiles VALUES(?,?,?,?,?,?,?,?,?,?)',(uuid.uuid4().hex,u,b.display_name.strip() or u,b.role.upper(),b.authority.upper(),'ACTIVE',h(b.authorization),ts,ts,None));audit(c,u,'CREATE',x_vector_user,'Vector profile created');c.commit()
    except sqlite3.IntegrityError:c.close();raise HTTPException(409,'Vector user ID already exists')
    c.close();return {'user_id':u,'status':'ACTIVE'}
@router.put('/profiles/{user_id}')
def update_profile(user_id:str,b:ProfileUpdate,x_access_code:str=Header(default=''),x_vector_user:str=Header(default='SYSTEM')):
    manager(x_access_code);u=user_id.upper();c=db();r=c.execute('SELECT * FROM vector_profiles WHERE user_id=?',(u,)).fetchone()
    if not r:c.close();raise HTTPException(404,'Vector profile not found')
    vals={'display_name':b.display_name if b.display_name is not None else r['display_name'],'role':(b.role or r['role']).upper(),'authority':(b.authority or r['authority']).upper(),'status':(b.status or r['status']).upper(),'auth_hash':h(b.authorization) if b.authorization is not None else r['auth_hash']};c.execute('UPDATE vector_profiles SET display_name=?,role=?,authority=?,status=?,auth_hash=?,updated_at=? WHERE user_id=?',(vals['display_name'],vals['role'],vals['authority'],vals['status'],vals['auth_hash'],time.time(),u));audit(c,u,'CHANGE',x_vector_user,'Vector profile changed');c.commit();c.close();return {'user_id':u,'role':vals['role'],'authority':vals['authority'],'status':vals['status']}
@router.post('/signon')
def signon(b:Signon,x_access_code:str=Header(default='')):return _authenticate(b.user_id,b.authorization,x_access_code)
@router.post('/session')
def create_session(b:Signon,x_access_code:str=Header(default='')):
    profile=_authenticate(b.user_id,b.authorization,x_access_code);token='v5250_'+secrets.token_urlsafe(32);now=time.time();session={'token':token,'user_id':profile['user_id'],'role':profile['role'],'authority':profile['authority'],'permissions':[PERM],'is_master':bool(is_master(x_access_code)),'created_at':now,'expires_at':now+SESSION_TTL}
    with _session_lock:_sessions[token]=session
    return {**profile,'token':token,'expires_in':SESSION_TTL}
@router.get('/session/current')
def current_session(x_access_code:str=Header(default='')):
    s=resolve_session_token(x_access_code)
    if not s:raise HTTPException(401,'Vector session expired or invalid')
    return {k:s[k] for k in ('user_id','role','authority','created_at','expires_at')}
@router.delete('/session')
def end_session(x_access_code:str=Header(default='')):
    with _session_lock:existed=_sessions.pop(x_access_code,None) is not None
    return {'ended':existed}
@router.get('/profiles/{user_id}/authority')
def authority(user_id:str,x_access_code:str=Header(default='')):
    manager(x_access_code);c=db();r=c.execute('SELECT user_id,display_name,role,authority,status,last_signon FROM vector_profiles WHERE user_id=?',(user_id.upper(),)).fetchone();c.close()
    if not r:raise HTTPException(404,'Vector profile not found')
    return dict(r)
