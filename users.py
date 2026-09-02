"""User account registration, login, session, profile and password management."""
import hashlib,hmac,os,re,secrets,sqlite3,time
from fastapi import APIRouter,Header,HTTPException,Request
from pydantic import BaseModel
BASE_DIR=os.path.dirname(os.path.abspath(__file__));DB_PATH=os.path.join(BASE_DIR,'data_hub.db');ADMIN_PASSCODE=os.environ.get('ADMIN_PASSCODE','uganda2026');router=APIRouter();EMAIL_RE=re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');PBKDF2_ITERATIONS=260000
def get_conn():c=sqlite3.connect(DB_PATH);c.row_factory=sqlite3.Row;return c
def init_db():
 c=get_conn();c.execute('CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY,name TEXT NOT NULL,email TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,password_salt TEXT NOT NULL,phone TEXT,address TEXT,created_at REAL NOT NULL)');c.execute('CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY,user_id TEXT NOT NULL,created_at REAL NOT NULL)');c.commit();c.close()
init_db()
def hash_password(password,salt=None):
 salt=salt or secrets.token_hex(16);digest=hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),PBKDF2_ITERATIONS).hex();return digest,salt
def verify_password(password,stored_hash,salt):check,_=hash_password(password,salt);return hmac.compare_digest(check,stored_hash)
def create_session(user_id):
 token=secrets.token_urlsafe(32);c=get_conn();c.execute('INSERT INTO sessions VALUES (?,?,?)',(token,user_id,time.time()));c.commit();c.close();return token
def get_user_by_token(token):
 if not token:return None
 c=get_conn();r=c.execute('SELECT users.* FROM sessions JOIN users ON users.id=sessions.user_id WHERE sessions.token=?',(token,)).fetchone();c.close();return r
def user_to_dict(r):return {'id':r['id'],'name':r['name'],'email':r['email'],'phone':r['phone'] or '','address':r['address'] or ''}
class SignupBody(BaseModel):name:str;email:str;password:str;phone:str='';address:str=''
class LoginBody(BaseModel):email:str;password:str
class ProfileBody(BaseModel):token:str;name:str='';phone:str='';address:str=''
class PasswordChangeBody(BaseModel):token:str;current_password:str;new_password:str
class AdminPasswordResetBody(BaseModel):email:str;new_password:str
@router.post('/auth/signup')
def signup(body:SignupBody):
 email=body.email.strip().lower()
 if not EMAIL_RE.match(email):raise HTTPException(400,'Invalid email address')
 if len(body.password)<6:raise HTTPException(400,'Password must be at least 6 characters')
 if not body.name.strip():raise HTTPException(400,'Name is required')
 c=get_conn()
 if c.execute('SELECT id FROM users WHERE email=?',(email,)).fetchone():c.close();raise HTTPException(400,'An account with this email already exists')
 ph,salt=hash_password(body.password);uid=secrets.token_hex(16);c.execute('INSERT INTO users VALUES (?,?,?,?,?,?,?,?)',(uid,body.name.strip(),email,ph,salt,body.phone.strip(),body.address.strip(),time.time()));c.commit();c.close();token=create_session(uid);return {'token':token,'id':uid,'name':body.name.strip(),'email':email,'phone':body.phone.strip(),'address':body.address.strip()}
@router.post('/auth/login')
def login(body:LoginBody):
 email=body.email.strip().lower();c=get_conn();r=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone();c.close()
 if not r or not verify_password(body.password,r['password_hash'],r['password_salt']):raise HTTPException(401,'Invalid email or password')
 return {'token':create_session(r['id']),**user_to_dict(r)}
@router.get('/auth/me')
def me(token:str=''):
 r=get_user_by_token(token)
 if not r:raise HTTPException(401,'Invalid or expired session')
 return user_to_dict(r)
@router.post('/auth/logout')
async def logout(request:Request):
 form=await request.form();token=form.get('token','');c=get_conn()
 if token:c.execute('DELETE FROM sessions WHERE token=?',(token,));c.commit()
 c.close();return {'status':'logged_out'}
@router.post('/profile')
def profile(body:ProfileBody):
 r=get_user_by_token(body.token)
 if not r:raise HTTPException(401,'Invalid or expired session')
 name=body.name.strip() or r['name'];c=get_conn();c.execute('UPDATE users SET name=?,phone=?,address=? WHERE id=?',(name,body.phone.strip(),body.address.strip(),r['id']));c.commit();c.close();return {'id':r['id'],'name':name,'email':r['email'],'phone':body.phone.strip(),'address':body.address.strip()}
@router.post('/auth/password/change')
def change_password(body:PasswordChangeBody):
 r=get_user_by_token(body.token)
 if not r:raise HTTPException(401,'Invalid or expired session')
 if not verify_password(body.current_password,r['password_hash'],r['password_salt']):raise HTTPException(401,'Current password is incorrect')
 if len(body.new_password)<8:raise HTTPException(400,'New password must be at least 8 characters')
 ph,salt=hash_password(body.new_password);c=get_conn();c.execute('UPDATE users SET password_hash=?,password_salt=? WHERE id=?',(ph,salt,r['id']));c.execute('DELETE FROM sessions WHERE user_id=?',(r['id'],));c.commit();c.close();return {'status':'password_changed','sessions_revoked':True}
@router.post('/auth/password/admin-reset')
def admin_reset(body:AdminPasswordResetBody,x_admin_passcode:str=Header(default='')):
 if x_admin_passcode!=ADMIN_PASSCODE:raise HTTPException(401,'Master admin passcode required')
 if len(body.new_password)<8:raise HTTPException(400,'New password must be at least 8 characters')
 email=body.email.strip().lower();c=get_conn();r=c.execute('SELECT id FROM users WHERE email=?',(email,)).fetchone()
 if not r:c.close();raise HTTPException(404,'User not found')
 ph,salt=hash_password(body.new_password);c.execute('UPDATE users SET password_hash=?,password_salt=? WHERE id=?',(ph,salt,r['id']));c.execute('DELETE FROM sessions WHERE user_id=?',(r['id'],));c.commit();c.close();return {'status':'password_reset','email':email,'sessions_revoked':True}