"""Vector 5250 user profiles, sign-on identity binding, and authority inquiry."""
import hashlib
import sqlite3
import time
import uuid
from pathlib import Path
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from auth import is_master, require_permission

router=APIRouter(prefix="/vector5250",tags=["Vector 5250 Profiles"])
DB=Path("vector5250.db")
PERM="warehouse:manager"

def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
    c.executescript('''
    CREATE TABLE IF NOT EXISTS vector_profiles(
      id TEXT PRIMARY KEY,user_id TEXT UNIQUE NOT NULL,display_name TEXT NOT NULL,
      role TEXT NOT NULL,authority TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'ACTIVE',
      auth_hash TEXT NOT NULL,created_at REAL NOT NULL,updated_at REAL NOT NULL,last_signon REAL
    );
    CREATE TABLE IF NOT EXISTS vector_profile_audit(
      id TEXT PRIMARY KEY,user_id TEXT NOT NULL,action TEXT NOT NULL,actor TEXT NOT NULL,
      detail TEXT NOT NULL,created_at REAL NOT NULL
    );
    '''); c.commit(); return c

def h(s:str): return hashlib.sha256((s or '').encode()).hexdigest()
def manager(code:str):
    if is_master(code): return
    require_permission(code,PERM)
def audit(c,user,action,actor,detail):
    c.execute("INSERT INTO vector_profile_audit VALUES(?,?,?,?,?,?)",(uuid.uuid4().hex,user,action,actor,detail,time.time()))

class ProfileCreate(BaseModel):
    user_id:str; display_name:str; authorization:str; role:str="MANAGER"; authority:str="MANAGER"
class ProfileUpdate(BaseModel):
    display_name:str|None=None; authorization:str|None=None; role:str|None=None; authority:str|None=None; status:str|None=None
class Signon(BaseModel):
    user_id:str; authorization:str

@router.post('/profiles/bootstrap')
def bootstrap(x_access_code:str=Header(default='')):
    if not is_master(x_access_code): raise HTTPException(403,'Master authorization required')
    c=db(); row=c.execute("SELECT COUNT(*) n FROM vector_profiles").fetchone(); c.close(); return {"profile_count":row['n'],"bootstrap_required":row['n']==0}

@router.get('/profiles')
def list_profiles(x_access_code:str=Header(default='')):
    manager(x_access_code); c=db(); rows=[dict(r) for r in c.execute("SELECT id,user_id,display_name,role,authority,status,created_at,updated_at,last_signon FROM vector_profiles ORDER BY user_id")]; c.close(); return {"count":len(rows),"results":rows}

@router.post('/profiles')
def create_profile(b:ProfileCreate,x_access_code:str=Header(default=''),x_vector_user:str=Header(default='SYSTEM')):
    manager(x_access_code); u=b.user_id.strip().upper()
    if not u or not b.authorization: raise HTTPException(400,'User ID and authorization required')
    c=db()
    try:
      ts=time.time(); c.execute("INSERT INTO vector_profiles VALUES(?,?,?,?,?,?,?,?,?,?)",(uuid.uuid4().hex,u,b.display_name.strip() or u,b.role.upper(),b.authority.upper(),'ACTIVE',h(b.authorization),ts,ts,None)); audit(c,u,'CREATE',x_vector_user,'Vector profile created'); c.commit()
    except sqlite3.IntegrityError: c.close(); raise HTTPException(409,'Vector user ID already exists')
    c.close(); return {"user_id":u,"status":"ACTIVE"}

@router.put('/profiles/{user_id}')
def update_profile(user_id:str,b:ProfileUpdate,x_access_code:str=Header(default=''),x_vector_user:str=Header(default='SYSTEM')):
    manager(x_access_code); u=user_id.upper(); c=db(); r=c.execute("SELECT * FROM vector_profiles WHERE user_id=?",(u,)).fetchone()
    if not r: c.close(); raise HTTPException(404,'Vector profile not found')
    vals={"display_name":b.display_name if b.display_name is not None else r['display_name'],"role":(b.role or r['role']).upper(),"authority":(b.authority or r['authority']).upper(),"status":(b.status or r['status']).upper(),"auth_hash":h(b.authorization) if b.authorization is not None else r['auth_hash']}
    c.execute("UPDATE vector_profiles SET display_name=?,role=?,authority=?,status=?,auth_hash=?,updated_at=? WHERE user_id=?",(vals['display_name'],vals['role'],vals['authority'],vals['status'],vals['auth_hash'],time.time(),u)); audit(c,u,'CHANGE',x_vector_user,'Vector profile changed'); c.commit(); c.close(); return {"user_id":u,"role":vals['role'],"authority":vals['authority'],"status":vals['status']}

@router.post('/signon')
def signon(b:Signon,x_access_code:str=Header(default='')):
    manager(x_access_code); u=b.user_id.strip().upper(); c=db(); r=c.execute("SELECT * FROM vector_profiles WHERE user_id=?",(u,)).fetchone()
    count=c.execute("SELECT COUNT(*) n FROM vector_profiles").fetchone()['n']
    if not r:
      c.close()
      if count==0 and is_master(x_access_code): return {"user_id":u,"display_name":u,"role":"ADMINISTRATOR","authority":"*ALLOBJ","status":"ACTIVE","bootstrap_mode":True}
      raise HTTPException(401,'Vector user profile not found')
    if r['status']!='ACTIVE' or r['auth_hash']!=h(b.authorization): c.close(); raise HTTPException(401,'Invalid Vector user ID or authorization')
    c.execute("UPDATE vector_profiles SET last_signon=?,updated_at=? WHERE user_id=?",(time.time(),time.time(),u)); audit(c,u,'SIGNON',u,'Interactive Vector sign-on'); c.commit(); out={k:r[k] for k in ('user_id','display_name','role','authority','status')}; c.close(); return out

@router.get('/profiles/{user_id}/authority')
def authority(user_id:str,x_access_code:str=Header(default='')):
    manager(x_access_code); c=db(); r=c.execute("SELECT user_id,display_name,role,authority,status,last_signon FROM vector_profiles WHERE user_id=?",(user_id.upper(),)).fetchone(); c.close()
    if not r: raise HTTPException(404,'Vector profile not found')
    return dict(r)
