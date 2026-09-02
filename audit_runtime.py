import hashlib,json,os,sqlite3,time,uuid
from fastapi import APIRouter,Header,HTTPException,Query
from pydantic import BaseModel
from auth import require_permission
BASE=os.path.dirname(os.path.abspath(__file__));DB=os.path.join(BASE,'data_hub.db');router=APIRouter(prefix='/platform/audit',tags=['platform-audit-compliance'])
def conn():c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;return c
def read(code):require_permission(code,'shipments:read')
def write(code):require_permission(code,'shipments:write')
def now():return time.time()
def init():
 c=conn();c.executescript('''
 CREATE TABLE IF NOT EXISTS platform_compliance_controls(id TEXT PRIMARY KEY,framework TEXT NOT NULL,control_key TEXT NOT NULL,title TEXT NOT NULL,status TEXT NOT NULL,evidence TEXT,owner TEXT,review_due_at REAL,created_at REAL NOT NULL,updated_at REAL NOT NULL);
 CREATE TABLE IF NOT EXISTS platform_audit_snapshots(id TEXT PRIMARY KEY,from_ts REAL,to_ts REAL,event_count INTEGER NOT NULL,digest TEXT NOT NULL,created_at REAL NOT NULL);
 CREATE TABLE IF NOT EXISTS platform_compliance_reviews(id TEXT PRIMARY KEY,framework TEXT NOT NULL,summary TEXT NOT NULL,status TEXT NOT NULL,created_at REAL NOT NULL);
 ''');c.commit();c.close()
init()
class ControlIn(BaseModel):framework:str='UGAMAP';control_key:str;title:str;status:str='review';evidence:str='';owner:str='';review_due_at:float|None=None
class ReviewIn(BaseModel):framework:str='UGAMAP';summary:str;status:str='open'
class AuditEventIn(BaseModel):actor:str='staff';action:str;target:str='';detail:str='';result:str='ok'
def add_audit(c,actor,action,target='',detail='',result='ok'):
 c.execute('INSERT INTO platform_audit VALUES (?,?,?,?,?,?,?)',(str(uuid.uuid4()),actor,action,target,detail[:2000],result,now()))
@router.post('/events')
def create_event(p:AuditEventIn,x_access_code:str=Header(default='')):
 write(x_access_code);c=conn();add_audit(c,p.actor,p.action,p.target,p.detail,p.result);c.commit();c.close();return {'recorded':True,'actor':p.actor,'action':p.action,'result':p.result}
@router.get('/events')
def events(actor:str='',action:str='',result:str='',limit:int=Query(default=200,ge=1,le=1000),x_access_code:str=Header(default='')):
 read(x_access_code);c=conn();q='SELECT * FROM platform_audit WHERE 1=1';a=[]
 if actor:q+=' AND actor LIKE ?';a.append('%'+actor+'%')
 if action:q+=' AND action LIKE ?';a.append('%'+action+'%')
 if result:q+=' AND result=?';a.append(result)
 a.append(limit);r=[dict(x) for x in c.execute(q+' ORDER BY created_at DESC LIMIT ?',a)];c.close();return {'count':len(r),'results':r}
@router.post('/snapshot')
def snapshot(x_access_code:str=Header(default='')):
 write(x_access_code);c=conn();rows=[dict(x) for x in c.execute('SELECT * FROM platform_audit ORDER BY created_at,id')];payload=json.dumps(rows,sort_keys=True,separators=(',',':')).encode();digest=hashlib.sha256(payload).hexdigest();sid='AUDSNAP-'+uuid.uuid4().hex[:10].upper();start=rows[0]['created_at'] if rows else None;end=rows[-1]['created_at'] if rows else None;c.execute('INSERT INTO platform_audit_snapshots VALUES (?,?,?,?,?,?)',(sid,start,end,len(rows),digest,now()));add_audit(c,'system','audit.snapshot',sid,'SHA-256 evidence snapshot created');c.commit();c.close();return {'id':sid,'event_count':len(rows),'sha256':digest,'from_ts':start,'to_ts':end,'integrity':'tamper-evident snapshot; not WORM/immutable storage'}
@router.get('/snapshots')
def snapshots(x_access_code:str=Header(default='')):
 read(x_access_code);c=conn();r=[dict(x) for x in c.execute('SELECT * FROM platform_audit_snapshots ORDER BY created_at DESC LIMIT 100')];c.close();return {'results':r}
@router.post('/controls')
def save_control(p:ControlIn,x_access_code:str=Header(default='')):
 write(x_access_code);c=conn();old=c.execute('SELECT id FROM platform_compliance_controls WHERE framework=? AND control_key=?',(p.framework,p.control_key)).fetchone();t=now();cid=old['id'] if old else 'CTL-'+uuid.uuid4().hex[:10].upper()
 if old:c.execute('UPDATE platform_compliance_controls SET title=?,status=?,evidence=?,owner=?,review_due_at=?,updated_at=? WHERE id=?',(p.title,p.status,p.evidence,p.owner,p.review_due_at,t,cid))
 else:c.execute('INSERT INTO platform_compliance_controls VALUES (?,?,?,?,?,?,?,?,?,?)',(cid,p.framework,p.control_key,p.title,p.status,p.evidence,p.owner,p.review_due_at,t,t))
 add_audit(c,'staff','compliance.control.update',cid,p.framework+':'+p.control_key,p.status);c.commit();c.close();payload=p.model_dump() if hasattr(p,'model_dump') else p.dict();return {'id':cid,**payload}
@router.get('/controls')
def controls(framework:str='',status:str='',x_access_code:str=Header(default='')):
 read(x_access_code);c=conn();q='SELECT * FROM platform_compliance_controls WHERE 1=1';a=[]
 if framework:q+=' AND framework=?';a.append(framework)
 if status:q+=' AND status=?';a.append(status)
 r=[dict(x) for x in c.execute(q+' ORDER BY framework,control_key',a)];c.close();return {'results':r}
@router.post('/reviews')
def review(p:ReviewIn,x_access_code:str=Header(default='')):
 write(x_access_code);c=conn();rid='REV-'+uuid.uuid4().hex[:10].upper();c.execute('INSERT INTO platform_compliance_reviews VALUES (?,?,?,?,?)',(rid,p.framework,p.summary,p.status,now()));add_audit(c,'staff','compliance.review',rid,p.summary,p.status);c.commit();c.close();return {'id':rid,'framework':p.framework,'status':p.status}
@router.get('/reviews')
def reviews(x_access_code:str=Header(default='')):
 read(x_access_code);c=conn();r=[dict(x) for x in c.execute('SELECT * FROM platform_compliance_reviews ORDER BY created_at DESC LIMIT 200')];c.close();return {'results':r}
@router.get('/anomalies')
def anomalies(x_access_code:str=Header(default='')):
 read(x_access_code);c=conn();failed=[dict(x) for x in c.execute("SELECT * FROM platform_audit WHERE result NOT IN ('ok','success','completed','delivered') ORDER BY created_at DESC LIMIT 100")];denied=[dict(x) for x in c.execute("SELECT * FROM platform_audit WHERE lower(action) LIKE '%deny%' OR lower(action) LIKE '%unauthor%' ORDER BY created_at DESC LIMIT 100")];repeat={};
 for x in failed:repeat[x['actor']]=repeat.get(x['actor'],0)+1
 c.close();return {'failed_or_exception_events':failed,'denied_access_events':denied,'actors_with_repeated_failures':[{'actor':k,'count':v} for k,v in repeat.items() if v>=3]}
@router.get('/summary')
def summary(x_access_code:str=Header(default='')):
 read(x_access_code);c=conn();events=c.execute('SELECT COUNT(*) n FROM platform_audit').fetchone()['n'];controls=c.execute('SELECT COUNT(*) n FROM platform_compliance_controls').fetchone()['n'];open_controls=c.execute("SELECT COUNT(*) n FROM platform_compliance_controls WHERE status NOT IN ('passed','compliant','closed')").fetchone()['n'];snapshots=c.execute('SELECT COUNT(*) n FROM platform_audit_snapshots').fetchone()['n'];reviews=c.execute('SELECT COUNT(*) n FROM platform_compliance_reviews').fetchone()['n'];c.close();return {'audit_events':events,'compliance_controls':controls,'open_controls':open_controls,'evidence_snapshots':snapshots,'reviews':reviews,'note':'Controls and evidence tracking support compliance work; they do not by themselves establish legal certification.'}