"""UGAMAP Master Data Management runtime: canonical records, source links, quality and duplicate controls."""
import json,os,sqlite3,time,uuid,re
from fastapi import APIRouter,Header,HTTPException,Query
from pydantic import BaseModel
from auth import require_permission
BASE=os.path.dirname(os.path.abspath(__file__));DB=os.path.join(BASE,'data_hub.db');router=APIRouter(prefix='/platform/mdm-runtime',tags=['platform-mdm'])
def conn():c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;return c
def read(code):require_permission(code,'shipments:read')
def write(code):require_permission(code,'shipments:write')
def now():return time.time()
def clean_value(v):
 if isinstance(v,str):return re.sub(r'\s+',' ',v).strip()
 if isinstance(v,dict):return {str(k).strip().lower():clean_value(x) for k,x in v.items()}
 if isinstance(v,list):return [clean_value(x) for x in v]
 return v
def init():
 c=conn();c.executescript('''CREATE TABLE IF NOT EXISTS platform_mdm_sources(id TEXT PRIMARY KEY,entity_type TEXT NOT NULL,record_key TEXT NOT NULL,source_system TEXT NOT NULL,source_id TEXT,priority INTEGER NOT NULL DEFAULT 100,last_seen_at REAL NOT NULL,UNIQUE(entity_type,record_key,source_system,source_id));CREATE TABLE IF NOT EXISTS platform_mdm_history(id TEXT PRIMARY KEY,entity_type TEXT NOT NULL,record_key TEXT NOT NULL,data TEXT NOT NULL,source TEXT,changed_by TEXT,created_at REAL NOT NULL);CREATE TABLE IF NOT EXISTS platform_mdm_quality(id TEXT PRIMARY KEY,entity_type TEXT NOT NULL,record_key TEXT NOT NULL,score INTEGER NOT NULL,issues TEXT NOT NULL,checked_at REAL NOT NULL);CREATE TABLE IF NOT EXISTS platform_mdm_aliases(entity_type TEXT NOT NULL,alias_key TEXT NOT NULL,canonical_key TEXT NOT NULL,created_at REAL NOT NULL,PRIMARY KEY(entity_type,alias_key));''');c.commit();c.close()
init()
class Record(BaseModel):entity_type:str;record_key:str;data:dict;source:str='manual';source_id:str='';priority:int=100;changed_by:str='staff'
class Merge(BaseModel):entity_type:str;canonical_key:str;duplicate_keys:list[str];changed_by:str='staff'
class Link(BaseModel):entity_type:str;record_key:str;source_system:str;source_id:str='';priority:int=100

def quality(data):
 issues=[]
 if not data:issues.append('empty record')
 for k,v in data.items():
  if v is None or (isinstance(v,str) and not v.strip()):issues.append(f'missing:{k}')
  if isinstance(v,str) and len(v)>500:issues.append(f'oversized:{k}')
 score=max(0,100-min(80,len(issues)*15));return score,issues
@router.post('/records')
def upsert(p:Record,x_access_code:str=Header(default='')):
 write(x_access_code);et=p.entity_type.strip().lower();rk=p.record_key.strip().upper();data=clean_value(p.data);score,issues=quality(data);c=conn();old=c.execute('SELECT * FROM platform_mdm WHERE entity_type=? AND record_key=?',(et,rk)).fetchone()
 if old:c.execute('INSERT INTO platform_mdm_history VALUES (?,?,?,?,?,?,?)',(str(uuid.uuid4()),et,rk,old['data'],old['source'],p.changed_by,now()))
 c.execute('INSERT OR REPLACE INTO platform_mdm VALUES (?,?,?,?,?)',(et,rk,json.dumps(data,sort_keys=True),p.source,now()));c.execute('INSERT OR REPLACE INTO platform_mdm_sources VALUES (?,?,?,?,?,?,?)',(str(uuid.uuid4()),et,rk,p.source,p.source_id,p.priority,now()));c.execute('INSERT INTO platform_mdm_quality VALUES (?,?,?,?,?,?)',(str(uuid.uuid4()),et,rk,score,json.dumps(issues),now()));c.commit();c.close();return {'entity_type':et,'record_key':rk,'data':data,'quality_score':score,'issues':issues,'canonical':True}
@router.get('/records/{entity_type}')
def records(entity_type:str,q:str='',x_access_code:str=Header(default='')):
 read(x_access_code);c=conn();term='%'+q+'%';rows=[dict(x) for x in c.execute('SELECT * FROM platform_mdm WHERE entity_type=? AND (?="" OR record_key LIKE ? OR data LIKE ?) ORDER BY record_key',(entity_type.lower(),q,term,term))]
 for r in rows:r['data']=json.loads(r['data']);r['sources']=[dict(x) for x in c.execute('SELECT source_system,source_id,priority,last_seen_at FROM platform_mdm_sources WHERE entity_type=? AND record_key=? ORDER BY priority',(entity_type.lower(),r['record_key']))]
 c.close();return {'results':rows}
@router.get('/record/{entity_type}/{record_key}')
def detail(entity_type:str,record_key:str,x_access_code:str=Header(default='')):
 read(x_access_code);c=conn();et=entity_type.lower();rk=record_key.upper();alias=c.execute('SELECT canonical_key FROM platform_mdm_aliases WHERE entity_type=? AND alias_key=?',(et,rk)).fetchone();rk=alias['canonical_key'] if alias else rk;r=c.execute('SELECT * FROM platform_mdm WHERE entity_type=? AND record_key=?',(et,rk)).fetchone()
 if not r:c.close();raise HTTPException(404,'Master record not found')
 d=dict(r);d['data']=json.loads(d['data']);d['sources']=[dict(x) for x in c.execute('SELECT * FROM platform_mdm_sources WHERE entity_type=? AND record_key=? ORDER BY priority',(et,rk))];d['history']=[dict(x) for x in c.execute('SELECT source,changed_by,created_at FROM platform_mdm_history WHERE entity_type=? AND record_key=? ORDER BY created_at DESC LIMIT 50',(et,rk))];q=c.execute('SELECT score,issues,checked_at FROM platform_mdm_quality WHERE entity_type=? AND record_key=? ORDER BY checked_at DESC LIMIT 1',(et,rk)).fetchone();d['quality']=dict(q) if q else None;c.close();return d
@router.post('/link-source')
def link_source(p:Link,x_access_code:str=Header(default='')):
 write(x_access_code);c=conn();et=p.entity_type.lower();rk=p.record_key.upper()
 if not c.execute('SELECT 1 FROM platform_mdm WHERE entity_type=? AND record_key=?',(et,rk)).fetchone():c.close();raise HTTPException(404,'Master record not found')
 c.execute('INSERT OR REPLACE INTO platform_mdm_sources VALUES (?,?,?,?,?,?,?)',(str(uuid.uuid4()),et,rk,p.source_system,p.source_id,p.priority,now()));c.commit();c.close();return {'linked':True,'entity_type':et,'record_key':rk,'source_system':p.source_system}
@router.get('/duplicates/{entity_type}')
def duplicates(entity_type:str,x_access_code:str=Header(default='')):
 read(x_access_code);c=conn();rows=[dict(x) for x in c.execute('SELECT record_key,data FROM platform_mdm WHERE entity_type=?',(entity_type.lower(),))];c.close();groups={}
 for r in rows:
  d=json.loads(r['data']);sig='|'.join(str(d.get(k,'')).lower().strip() for k in ('name','email','phone','sku','code') if d.get(k))
  if sig:groups.setdefault(sig,[]).append(r['record_key'])
 return {'duplicates':[{'signature':k,'record_keys':v} for k,v in groups.items() if len(v)>1]}
@router.post('/merge')
def merge(p:Merge,x_access_code:str=Header(default='')):
 write(x_access_code);et=p.entity_type.lower();ck=p.canonical_key.upper();c=conn();base=c.execute('SELECT * FROM platform_mdm WHERE entity_type=? AND record_key=?',(et,ck)).fetchone()
 if not base:c.close();raise HTTPException(404,'Canonical record not found')
 data=json.loads(base['data'])
 for key in p.duplicate_keys:
  dk=key.upper()
  if dk==ck:continue
  r=c.execute('SELECT * FROM platform_mdm WHERE entity_type=? AND record_key=?',(et,dk)).fetchone()
  if not r:continue
  other=json.loads(r['data']);data={**other,**{k:v for k,v in data.items() if v not in ('',None)}};c.execute('INSERT OR REPLACE INTO platform_mdm_aliases VALUES (?,?,?,?)',(et,dk,ck,now()));c.execute('UPDATE platform_mdm_sources SET record_key=? WHERE entity_type=? AND record_key=?',(ck,et,dk));c.execute('DELETE FROM platform_mdm WHERE entity_type=? AND record_key=?',(et,dk))
 c.execute('UPDATE platform_mdm SET data=?,source=?,updated_at=? WHERE entity_type=? AND record_key=?',(json.dumps(clean_value(data),sort_keys=True),'merged',now(),et,ck));c.commit();c.close();return {'merged':True,'canonical_key':ck,'aliases':[x.upper() for x in p.duplicate_keys]}
@router.get('/quality')
def quality_summary(entity_type:str='',x_access_code:str=Header(default='')):
 read(x_access_code);c=conn();q='SELECT entity_type,COUNT(*) records FROM platform_mdm';a=[]
 if entity_type:q+=' WHERE entity_type=?';a.append(entity_type.lower())
 q+=' GROUP BY entity_type';counts=[dict(x) for x in c.execute(q,a)];latest=[dict(x) for x in c.execute('SELECT entity_type,record_key,score,issues,MAX(checked_at) checked_at FROM platform_mdm_quality GROUP BY entity_type,record_key ORDER BY score ASC LIMIT 100')];c.close()
 for x in latest:x['issues']=json.loads(x['issues'])
 return {'record_counts':counts,'quality':latest,'single_source_of_truth':True}