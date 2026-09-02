"""UGAMAP API Management runtime: products, developer keys, policies, usage and enforceable gateway checks."""
import hashlib,json,os,secrets,sqlite3,time,uuid
from fastapi import APIRouter,Header,HTTPException,Request
from pydantic import BaseModel,Field
from auth import require_permission
BASE=os.path.dirname(os.path.abspath(__file__));DB=os.path.join(BASE,'data_hub.db');router=APIRouter(prefix='/platform/api-runtime',tags=['platform-api-management'])
def conn():c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;return c
def read(code):require_permission(code,'shipments:read')
def write(code):require_permission(code,'shipments:write')
def now():return time.time()
def init():
 c=conn();c.executescript('''CREATE TABLE IF NOT EXISTS platform_api_products(id TEXT PRIMARY KEY,name TEXT UNIQUE NOT NULL,base_path TEXT NOT NULL,description TEXT,visibility TEXT NOT NULL DEFAULT 'private',is_active INTEGER NOT NULL DEFAULT 1,created_at REAL NOT NULL,updated_at REAL NOT NULL);CREATE TABLE IF NOT EXISTS platform_api_key_bindings(key_id TEXT NOT NULL,product_id TEXT NOT NULL,created_at REAL NOT NULL,PRIMARY KEY(key_id,product_id));CREATE TABLE IF NOT EXISTS platform_api_usage(id TEXT PRIMARY KEY,key_id TEXT,product_id TEXT,path TEXT,method TEXT,status_code INTEGER,latency_ms REAL,allowed INTEGER NOT NULL,reason TEXT,created_at REAL NOT NULL);CREATE INDEX IF NOT EXISTS idx_api_usage_key_time ON platform_api_usage(key_id,created_at);''');c.commit();c.close()
init()
class ProductIn(BaseModel):name:str;base_path:str;description:str='';visibility:str='private'
class PolicyIn(BaseModel):name:str;scope:str='read';rate_limit:int=Field(default=120,ge=1,le=100000);burst:int=Field(default=30,ge=1,le=10000);is_active:bool=True
class KeyIn(BaseModel):name:str;scope:str='read';product_ids:list[str]=[]
class BindIn(BaseModel):key_id:str;product_id:str
class EvaluateIn(BaseModel):api_key:str;product_id:str;path:str='/';method:str='GET'
@router.post('/products')
def product_create(p:ProductIn,x_access_code:str=Header(default='')):
 write(x_access_code);c=conn();pid='API-'+uuid.uuid4().hex[:8].upper();t=now()
 try:c.execute('INSERT INTO platform_api_products VALUES (?,?,?,?,?,?,?,?)',(pid,p.name.strip(),p.base_path.strip(),p.description,p.visibility,1,t,t));c.commit()
 except sqlite3.IntegrityError:c.close();raise HTTPException(409,'API product already exists')
 c.close();return {'id':pid,**p.dict() if hasattr(p,'dict') else p.model_dump(),'active':True}
@router.get('/products')
def products(x_access_code:str=Header(default='')):read(x_access_code);c=conn();r=[dict(x) for x in c.execute('SELECT * FROM platform_api_products ORDER BY name')];c.close();return {'results':r}
@router.post('/policies')
def policy_create(p:PolicyIn,x_access_code:str=Header(default='')):
 write(x_access_code);c=conn();pid='POL-'+uuid.uuid4().hex[:8].upper();t=now();c.execute('INSERT INTO platform_api_policies VALUES (?,?,?,?,?,?,?,?)',(pid,p.name,p.scope,p.rate_limit,p.burst,1 if p.is_active else 0,t,t));c.commit();c.close();return {'id':pid,**(p.model_dump() if hasattr(p,'model_dump') else p.dict())}
@router.get('/policies')
def policies(x_access_code:str=Header(default='')):read(x_access_code);c=conn();r=[dict(x) for x in c.execute('SELECT * FROM platform_api_policies ORDER BY updated_at DESC')];c.close();return {'results':r}
@router.post('/keys')
def key_create(p:KeyIn,x_access_code:str=Header(default='')):
 write(x_access_code);raw='uga_'+secrets.token_urlsafe(30);kh=hashlib.sha256(raw.encode()).hexdigest();kid='KEY-'+uuid.uuid4().hex[:8].upper();c=conn();c.execute('INSERT INTO platform_developer_keys VALUES (?,?,?,?,?,?,?)',(kid,p.name,kh,p.scope,1,now(),None))
 for product_id in p.product_ids:
  if not c.execute('SELECT 1 FROM platform_api_products WHERE id=?',(product_id,)).fetchone():c.rollback();c.close();raise HTTPException(404,f'API product not found: {product_id}')
  c.execute('INSERT OR IGNORE INTO platform_api_key_bindings VALUES (?,?,?)',(kid,product_id,now()))
 c.commit();c.close();return {'id':kid,'name':p.name,'scope':p.scope,'api_key':raw,'warning':'Store this key securely; it is shown only once.'}
@router.get('/keys')
def keys(x_access_code:str=Header(default='')):
 read(x_access_code);c=conn();r=[dict(x) for x in c.execute('SELECT id,name,scope,is_active,created_at,last_used_at FROM platform_developer_keys ORDER BY created_at DESC')]
 for x in r:x['products']=[y['product_id'] for y in c.execute('SELECT product_id FROM platform_api_key_bindings WHERE key_id=?',(x['id'],))]
 c.close();return {'results':r}
@router.post('/bindings')
def bind(p:BindIn,x_access_code:str=Header(default='')):
 write(x_access_code);c=conn()
 if not c.execute('SELECT 1 FROM platform_developer_keys WHERE id=?',(p.key_id,)).fetchone():c.close();raise HTTPException(404,'Developer key not found')
 if not c.execute('SELECT 1 FROM platform_api_products WHERE id=?',(p.product_id,)).fetchone():c.close();raise HTTPException(404,'API product not found')
 c.execute('INSERT OR IGNORE INTO platform_api_key_bindings VALUES (?,?,?)',(p.key_id,p.product_id,now()));c.commit();c.close();return {'bound':True,'key_id':p.key_id,'product_id':p.product_id}
@router.post('/keys/{key_id}/revoke')
def revoke(key_id:str,x_access_code:str=Header(default='')):write(x_access_code);c=conn();n=c.execute('UPDATE platform_developer_keys SET is_active=0 WHERE id=?',(key_id,)).rowcount;c.commit();c.close();return {'revoked':bool(n),'key_id':key_id}
def evaluate_key(c,raw,product_id,path,method):
 kh=hashlib.sha256(raw.encode()).hexdigest();k=c.execute('SELECT * FROM platform_developer_keys WHERE key_hash=?',(kh,)).fetchone()
 if not k or not k['is_active']:return None,False,'invalid_or_revoked_key'
 product=c.execute('SELECT * FROM platform_api_products WHERE id=?',(product_id,)).fetchone()
 if not product or not product['is_active']:return k,False,'inactive_or_unknown_product'
 if not c.execute('SELECT 1 FROM platform_api_key_bindings WHERE key_id=? AND product_id=?',(k['id'],product_id)).fetchone():return k,False,'product_not_authorized'
 policy=c.execute('SELECT * FROM platform_api_policies WHERE is_active=1 AND (scope=? OR scope=? OR scope="all") ORDER BY rate_limit ASC LIMIT 1',(k['scope'],method.lower())).fetchone()
 if policy:
  minute=now()-60;used=c.execute('SELECT COUNT(*) n FROM platform_api_usage WHERE key_id=? AND allowed=1 AND created_at>=?',(k['id'],minute)).fetchone()['n']
  if used>=policy['rate_limit']:return k,False,'rate_limit_exceeded'
 return k,True,'allowed'
@router.post('/evaluate')
def evaluate(p:EvaluateIn,x_access_code:str=Header(default='')):
 read(x_access_code);c=conn();t=now();k,allowed,reason=evaluate_key(c,p.api_key,p.product_id,p.path,p.method);kid=k['id'] if k else None;c.execute('INSERT INTO platform_api_usage VALUES (?,?,?,?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),kid,p.product_id,p.path,p.method,200 if allowed else 429,0,1 if allowed else 0,reason,t));
 if k:c.execute('UPDATE platform_developer_keys SET last_used_at=? WHERE id=?',(t,k['id']))
 c.commit();c.close();return {'allowed':allowed,'reason':reason,'key_id':kid,'product_id':p.product_id}
@router.get('/usage')
def usage(x_access_code:str=Header(default='')):
 read(x_access_code);c=conn();tot=c.execute('SELECT COUNT(*) n,SUM(CASE WHEN allowed=1 THEN 1 ELSE 0 END) ok,SUM(CASE WHEN allowed=0 THEN 1 ELSE 0 END) blocked,AVG(latency_ms) latency FROM platform_api_usage').fetchone();by=[dict(x) for x in c.execute('SELECT product_id,COUNT(*) requests,SUM(CASE WHEN allowed=0 THEN 1 ELSE 0 END) blocked FROM platform_api_usage GROUP BY product_id ORDER BY requests DESC')];recent=[dict(x) for x in c.execute('SELECT key_id,product_id,path,method,status_code,allowed,reason,created_at FROM platform_api_usage ORDER BY created_at DESC LIMIT 100')];c.close();return {'summary':dict(tot),'by_product':by,'recent':recent,'enforcement_endpoint':'/platform/api-runtime/evaluate'}