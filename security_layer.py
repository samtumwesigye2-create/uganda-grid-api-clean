"""Central security controls for the production FastAPI application."""
import base64,hashlib,hmac,json,os,secrets,sqlite3,struct,threading,time,uuid
from collections import defaultdict,deque
from urllib.parse import quote
from cryptography.fernet import Fernet,InvalidToken
from fastapi import APIRouter,Form,Header,HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from auth import get_conn,is_master,require_permission

DB=os.path.join(os.path.dirname(os.path.abspath(__file__)),"data_hub.db")
MAX_BODY=max(65536,int(os.environ.get("SECURITY_MAX_BODY_BYTES","2097152")))
RATE=max(10,int(os.environ.get("SECURITY_RATE_LIMIT_PER_MINUTE","120")))
AUTH_RATE=max(3,int(os.environ.get("SECURITY_AUTH_RATE_PER_MINUTE","10")))
MFA_TTL=max(60,min(3600,int(os.environ.get("SECURITY_MFA_GRANT_SECONDS","900"))))
ENFORCE_MFA=os.environ.get("SECURITY_ENFORCE_MFA","0").lower() in ("1","true","yes")
router=APIRouter(prefix="/security",tags=["Security"]);_hits=defaultdict(deque);_lock=threading.Lock()
SENSITIVE_PREFIXES=("/admin","/staff","/warehouse","/integration","/inventory","/ship/admin","/security")
AUTH_PATHS=("/account/login","/account/signup","/auth/login","/auth/signup","/security/mfa/verify")
BAD=("<script","javascript:"," union select "," sleep("," benchmark(","${jndi:","../..")

def conn():c=sqlite3.connect(DB,timeout=30);c.row_factory=sqlite3.Row;return c
def init():
 c=conn();c.execute('''CREATE TABLE IF NOT EXISTS security_mfa(subject_hash TEXT PRIMARY KEY,secret_encrypted TEXT NOT NULL,confirmed INTEGER NOT NULL DEFAULT 0,created_at REAL NOT NULL,updated_at REAL NOT NULL)''');c.execute('''CREATE TABLE IF NOT EXISTS security_mfa_grants(token_hash TEXT PRIMARY KEY,subject_hash TEXT NOT NULL,expires_at REAL NOT NULL,created_at REAL NOT NULL)''');c.execute('''CREATE TABLE IF NOT EXISTS security_audit(id TEXT PRIMARY KEY,event_type TEXT NOT NULL,severity TEXT NOT NULL,ip_hash TEXT,path TEXT,subject_hash TEXT,detail TEXT,created_at REAL NOT NULL)''');c.execute('CREATE INDEX IF NOT EXISTS idx_security_audit_time ON security_audit(created_at)');c.commit();c.close()
def key():
 raw=os.environ.get("SECURITY_DATA_KEY","").strip()
 if not raw:raise HTTPException(503,"SECURITY_DATA_KEY is not configured")
 try:Fernet(raw);return raw.encode()
 except Exception:raise HTTPException(503,"SECURITY_DATA_KEY must be a Fernet key")
def subject(code):return hashlib.sha256(("staff:"+code).encode()).hexdigest()
def token_hash(token):return hashlib.sha256(token.encode()).hexdigest()
def ip_hash(ip):return hashlib.sha256((os.environ.get("SECURITY_AUDIT_SALT","uga-security")+ip).encode()).hexdigest()[:24]
def audit(event,severity="info",ip="",path="",sub="",detail=""):
 try:
  c=conn();c.execute('INSERT INTO security_audit VALUES(?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),event,severity,ip_hash(ip) if ip else "",path,sub,detail[:800],time.time()));c.commit();c.close()
 except Exception:pass
def totp(secret,at=None):
 counter=int((at or time.time())//30);secret_bytes=base64.b32decode(secret+"="*((8-len(secret)%8)%8));digest=hmac.new(secret_bytes,struct.pack(">Q",counter),hashlib.sha1).digest();offset=digest[-1]&15;return str((struct.unpack(">I",digest[offset:offset+4])[0]&0x7fffffff)%1000000).zfill(6)
def valid_totp(secret,code):return any(hmac.compare_digest(totp(secret,time.time()+step*30),str(code).zfill(6)) for step in (-1,0,1))
def allowed(ip,path):
 limit=AUTH_RATE if path in AUTH_PATHS else RATE;bucket=(ip,path if path in AUTH_PATHS else "global");now=time.time()
 with _lock:
  q=_hits[bucket]
  while q and q[0]<now-60:q.popleft()
  if len(q)>=limit:return False
  q.append(now);return True
def grant_valid(token,code):
 if not token or not code:return False
 c=conn();r=c.execute('SELECT expires_at,subject_hash FROM security_mfa_grants WHERE token_hash=?',(token_hash(token),)).fetchone();c.close();return bool(r and r['expires_at']>time.time() and r['subject_hash']==subject(code))
def require_identity(code):
 if is_master(code):return
 if not code:raise HTTPException(401,'Access code required')
 c=get_conn();row=c.execute('SELECT id FROM staff WHERE passcode=? AND is_active=1',(code,)).fetchone();c.close()
 if not row:raise HTTPException(401,'Invalid access code')

class SecurityMiddleware(BaseHTTPMiddleware):
 async def dispatch(self,request,call_next):
  path=request.url.path;ip=(request.headers.get("x-forwarded-for","").split(",")[0].strip() or (request.client.host if request.client else "unknown"))
  if request.headers.get("content-length","").isdigit() and int(request.headers["content-length"])>MAX_BODY:audit("request_blocked_size","warning",ip,path);return JSONResponse({"detail":"Request body too large"},413)
  if any(x in (str(request.url).lower()) for x in BAD):audit("request_blocked_payload","critical",ip,path);return JSONResponse({"detail":"Request rejected"},400)
  if not allowed(ip,path):audit("rate_limit","warning",ip,path);return JSONResponse({"detail":"Too many requests"},429,headers={"Retry-After":"60"})
  if ENFORCE_MFA and request.method not in ("GET","HEAD","OPTIONS") and path.startswith(SENSITIVE_PREFIXES) and path not in ("/security/mfa/enroll","/security/mfa/verify"):
   if not grant_valid(request.headers.get("x-mfa-token",""),request.headers.get("x-access-code","") or request.headers.get("x-admin-passcode","")):audit("mfa_required","warning",ip,path);return JSONResponse({"detail":"Valid MFA grant required"},401)
  response=await call_next(request)
  response.headers["X-Content-Type-Options"]="nosniff";response.headers["X-Frame-Options"]="DENY";response.headers["Referrer-Policy"]="strict-origin-when-cross-origin";response.headers["Permissions-Policy"]="camera=(self), geolocation=(self), microphone=()";response.headers["Strict-Transport-Security"]="max-age=31536000; includeSubDomains"
  response.headers["Content-Security-Policy"]="default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline' https:; script-src 'self' 'unsafe-inline' https://unpkg.com; connect-src 'self' https:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
  if path.startswith(("/account","/auth","/admin","/staff","/security")):response.headers["Cache-Control"]="no-store"
  if response.status_code in (400,401,403,422):audit("request_denied","warning",ip,path,detail=str(response.status_code))
  return response

@router.post('/mfa/enroll')
def enroll(x_access_code:str=Header(default="")):
 require_identity(x_access_code);sub=subject(x_access_code);secret=base64.b32encode(secrets.token_bytes(20)).decode().rstrip('=');encrypted=Fernet(key()).encrypt(secret.encode()).decode();c=conn();c.execute('INSERT INTO security_mfa(subject_hash,secret_encrypted,confirmed,created_at,updated_at) VALUES(?,?,0,?,?) ON CONFLICT(subject_hash) DO UPDATE SET secret_encrypted=excluded.secret_encrypted,confirmed=0,updated_at=excluded.updated_at',(sub,encrypted,time.time(),time.time()));c.commit();c.close();audit('mfa_enrolled','info',sub=sub);label=quote('UGA Systems');return {'secret':secret,'provisioning_uri':f'otpauth://totp/{label}?secret={secret}&issuer={label}&digits=6&period=30','confirmation_required':True}
@router.post('/mfa/verify')
def verify(code:str=Form(...),x_access_code:str=Header(default="")):
 require_identity(x_access_code);sub=subject(x_access_code);c=conn();r=c.execute('SELECT secret_encrypted FROM security_mfa WHERE subject_hash=?',(sub,)).fetchone()
 if not r:c.close();raise HTTPException(404,'MFA enrollment not found')
 try:secret=Fernet(key()).decrypt(r['secret_encrypted'].encode()).decode()
 except InvalidToken:c.close();raise HTTPException(503,'MFA encryption key mismatch')
 if not valid_totp(secret,code):c.close();audit('mfa_failed','warning',sub=sub);raise HTTPException(401,'Invalid MFA code')
 token=secrets.token_urlsafe(48);expires=time.time()+MFA_TTL;c.execute('UPDATE security_mfa SET confirmed=1,updated_at=? WHERE subject_hash=?',(time.time(),sub));c.execute('DELETE FROM security_mfa_grants WHERE subject_hash=? OR expires_at<=?',(sub,time.time()));c.execute('INSERT INTO security_mfa_grants VALUES(?,?,?,?)',(token_hash(token),sub,expires,time.time()));c.commit();c.close();audit('mfa_verified','info',sub=sub);return {'mfa_token':token,'expires_at':expires,'expires_in':MFA_TTL}
@router.get('/status')
def status(x_access_code:str=Header(default="")):
 require_permission(x_access_code,'inventory:read');c=conn();events=c.execute('SELECT COUNT(*) n FROM security_audit WHERE created_at>=?',(time.time()-86400,)).fetchone()['n'];enrolled=c.execute('SELECT COUNT(*) n FROM security_mfa WHERE confirmed=1').fetchone()['n'];c.close();return {'security_layer':'active','mfa_enforced':ENFORCE_MFA,'mfa_enrolled':enrolled,'security_events_24h':events,'rate_limit_per_minute':RATE,'auth_rate_limit_per_minute':AUTH_RATE,'max_body_bytes':MAX_BODY,'encryption_key_configured':bool(os.environ.get('SECURITY_DATA_KEY'))}
init()
