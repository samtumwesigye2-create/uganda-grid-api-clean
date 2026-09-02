import hashlib,json,os,secrets,sqlite3,time,uuid
from fastapi import APIRouter,File,Form,Header,HTTPException,Query,UploadFile
from pydantic import BaseModel,Field
from auth import require_permission
BASE=os.path.dirname(os.path.abspath(__file__));DB=os.path.join(BASE,'data_hub.db');DOC_DIR=os.path.join(BASE,'uploads','platform-docs');os.makedirs(DOC_DIR,exist_ok=True)
router=APIRouter(prefix='/platform',tags=['platform-services'])
def conn():c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;return c
def read(code):require_permission(code,'shipments:read')
def write(code):require_permission(code,'shipments:write')
def now():return time.time()
def init():
 c=conn();c.executescript('''
 CREATE TABLE IF NOT EXISTS platform_roles(id TEXT PRIMARY KEY,name TEXT UNIQUE NOT NULL,permissions TEXT NOT NULL,attributes TEXT,created_at REAL NOT NULL);
 CREATE TABLE IF NOT EXISTS platform_user_roles(user_id TEXT NOT NULL,role_id TEXT NOT NULL,created_at REAL NOT NULL,PRIMARY KEY(user_id,role_id));
 CREATE TABLE IF NOT EXISTS platform_workflows(id TEXT PRIMARY KEY,name TEXT NOT NULL,steps TEXT NOT NULL,current_step INTEGER NOT NULL DEFAULT 0,status TEXT NOT NULL,assignee TEXT,due_at REAL,context TEXT,created_at REAL NOT NULL,updated_at REAL NOT NULL);
 CREATE TABLE IF NOT EXISTS platform_workflow_history(id TEXT PRIMARY KEY,workflow_id TEXT NOT NULL,event TEXT NOT NULL,actor TEXT,detail TEXT,created_at REAL NOT NULL);
 CREATE TABLE IF NOT EXISTS platform_notification_templates(id TEXT PRIMARY KEY,name TEXT UNIQUE NOT NULL,channel TEXT NOT NULL,subject TEXT,body TEXT NOT NULL,created_at REAL NOT NULL,updated_at REAL NOT NULL);
 CREATE TABLE IF NOT EXISTS platform_notifications(id TEXT PRIMARY KEY,template_id TEXT,channel TEXT NOT NULL,recipient TEXT NOT NULL,subject TEXT,body TEXT NOT NULL,status TEXT NOT NULL,scheduled_at REAL,attempts INTEGER NOT NULL DEFAULT 0,last_error TEXT,created_at REAL NOT NULL,updated_at REAL NOT NULL);
 CREATE TABLE IF NOT EXISTS platform_documents(id TEXT PRIMARY KEY,name TEXT NOT NULL,stored_name TEXT NOT NULL,mime_type TEXT,size INTEGER NOT NULL,version INTEGER NOT NULL DEFAULT 1,tags TEXT,owner TEXT,created_at REAL NOT NULL,updated_at REAL NOT NULL);
 CREATE TABLE IF NOT EXISTS platform_document_versions(id TEXT PRIMARY KEY,document_id TEXT NOT NULL,version INTEGER NOT NULL,stored_name TEXT NOT NULL,size INTEGER NOT NULL,created_at REAL NOT NULL);
 CREATE TABLE IF NOT EXISTS platform_audit(id TEXT PRIMARY KEY,actor TEXT,action TEXT NOT NULL,target TEXT,detail TEXT,result TEXT,created_at REAL NOT NULL);
 CREATE TABLE IF NOT EXISTS platform_mdm(entity_type TEXT NOT NULL,record_key TEXT NOT NULL,data TEXT NOT NULL,source TEXT,updated_at REAL NOT NULL,PRIMARY KEY(entity_type,record_key));
 CREATE TABLE IF NOT EXISTS platform_api_policies(id TEXT PRIMARY KEY,name TEXT NOT NULL,scope TEXT,rate_limit INTEGER,burst INTEGER,is_active INTEGER NOT NULL DEFAULT 1,created_at REAL NOT NULL,updated_at REAL NOT NULL);
 CREATE TABLE IF NOT EXISTS platform_developer_keys(id TEXT PRIMARY KEY,name TEXT NOT NULL,key_hash TEXT NOT NULL,scope TEXT,is_active INTEGER NOT NULL DEFAULT 1,created_at REAL NOT NULL,last_used_at REAL);
 CREATE TABLE IF NOT EXISTS platform_monitoring(id TEXT PRIMARY KEY,status TEXT NOT NULL,metrics TEXT NOT NULL,created_at REAL NOT NULL);
 CREATE TABLE IF NOT EXISTS platform_features(feature_key TEXT PRIMARY KEY,enabled INTEGER NOT NULL DEFAULT 0,rollout_percent INTEGER NOT NULL DEFAULT 0,variant_a INTEGER NOT NULL DEFAULT 50,variant_b INTEGER NOT NULL DEFAULT 50,target_rules TEXT,updated_at REAL NOT NULL);
 ''');c.commit();c.close()
init()
def audit(c,actor,action,target='',detail='',result='ok'):
 c.execute('INSERT INTO platform_audit VALUES (?,?,?,?,?,?,?)',(str(uuid.uuid4()),actor,action,target,detail[:2000],result,now()))
def model(p):return p.model_dump() if hasattr(p,'model_dump') else p.dict()
class RoleIn(BaseModel):name:str;permissions:list[str]=[];attributes:dict={}
class RoleAssign(BaseModel):user_id:str;role_id:str
class WorkflowIn(BaseModel):name:str;steps:list[str];assignee:str='';due_at:float|None=None;context:dict={}
class WorkflowAdvance(BaseModel):action:str='complete_step';actor:str='system';detail:str=''
class TemplateIn(BaseModel):name:str;channel:str;subject:str='';body:str
class NotificationIn(BaseModel):recipient:str;channel:str='in-app';template_id:str='';subject:str='';body:str='';scheduled_at:float|None=None
class MDMIn(BaseModel):entity_type:str;record_key:str;data:dict;source:str='manual'
class APIPolicyIn(BaseModel):name:str;scope:str='read';rate_limit:int=Field(default=120,ge=1);burst:int=Field(default=30,ge=1)
class DeveloperKeyIn(BaseModel):name:str;scope:str='read'
class FeatureIn(BaseModel):feature_key:str;enabled:bool=False;rollout_percent:int=Field(default=0,ge=0,le=100);variant_a:int=Field(default=50,ge=0,le=100);variant_b:int=Field(default=50,ge=0,le=100);target_rules:dict={}
@router.post('/access/roles')
def create_role(p:RoleIn,x_access_code:str=Header(default='')):
 write(x_access_code);c=conn();rid='ROLE-'+uuid.uuid4().hex[:8].upper()
 try:c.execute('INSERT INTO platform_roles VALUES (?,?,?,?,?)',(rid,p.name.strip(),json.dumps(sorted(set(p.permissions))),json.dumps(p.attributes),now()));audit(c,'staff','role.create',rid,p.name);c.commit()
 except sqlite3.IntegrityError:c.close();raise HTTPException(409,'Role already exists')
 c.close();return {'id':rid,'name':p.name,'permissions':p.permissions,'attributes':p.attributes}
@router.get('/access/roles')
def roles(x_access_code:str=Header(default='')):
 read(x_access_code);c=conn();r=[dict(x) for x in c.execute('SELECT * FROM platform_roles ORDER BY name')];c.close()
 for x in r:x['permissions']=json.loads(x['permissions']);x['attributes']=json.loads(x['attributes'] or '{}')
 return {'results':r}
@router.post('/access/assign')
def assign_role(p:RoleAssign,x_access_code:str=Header(default='')):
 write(x_access_code);c=conn()
 if not c.execute('SELECT 1 FROM platform_roles WHERE id=?',(p.role_id,)).fetchone():c.close();raise HTTPException(404,'Role not found')
 c.execute('INSERT OR IGNORE INTO platform_user_roles VALUES (?,?,?)',(p.user_id,p.role_id,now()));audit(c,'staff','role.assign',p.user_id,p.role_id);c.commit();c.close();return {'user_id':p.user_id,'role_id':p.role_id,'assigned':True}
@router.get('/access/effective/{user_id}')
def effective(user_id:str,x_access_code:str=Header(default='')):
 read(x_access_code);c=conn();rs=[dict(x) for x in c.execute('SELECT r.* FROM platform_roles r JOIN platform_user_roles ur ON ur.role_id=r.id WHERE ur.user_id=?',(user_id,))];c.close();perms=sorted({p for r in rs for p in json.loads(r['permissions'])});attrs={}
 for r in rs:attrs.update(json.loads(r['attributes'] or '{}'))
 return {'user_id':user_id,'roles':[r['name'] for r in rs],'permissions':perms,'attributes':attrs}
@router.post('/workflows')
def workflow_create(p:WorkflowIn,x_access_code:str=Header(default='')):
 write(x_access_code)
 if not p.steps:raise HTTPException(400,'At least one workflow step is required')
 c=conn();wid='WF-'+uuid.uuid4().hex[:10].upper();t=now();c.execute('INSERT INTO platform_workflows VALUES (?,?,?,?,?,?,?,?,?,?,?)',(wid,p.name,json.dumps(p.steps),0,'running',p.assignee,p.due_at,json.dumps(p.context),t,t));c.execute('INSERT INTO platform_workflow_history VALUES (?,?,?,?,?,?)',(str(uuid.uuid4()),wid,'created','staff',p.steps[0],t));audit(c,'staff','workflow.create',wid,p.name);c.commit();c.close();return {'id':wid,'name':p.name,'status':'running','current_step':p.steps[0],'steps':p.steps,'assignee':p.assignee,'due_at':p.due_at}
@router.get('/workflows')
def workflow_list(status:str='',x_access_code:str=Header(default='')):
 read(x_access_code);c=conn();q='SELECT * FROM platform_workflows';a=[]
 if status:q+=' WHERE status=?';a.append(status)
 q+=' ORDER BY updated_at DESC';r=[dict(x) for x in c.execute(q,a)];c.close()
 for x in r:x['steps']=json.loads(x['steps']);x['context']=json.loads(x['context'] or '{}');x['overdue']=bool(x['due_at'] and x['due_at']<now() and x['status'] not in ('completed','cancelled'));x['current_step_name']=x['steps'][min(x['current_step'],len(x['steps'])-1)]
 return {'results':r}
@router.post('/workflows/{workflow_id}/advance')
def workflow_advance(workflow_id:str,p:WorkflowAdvance,x_access_code:str=Header(default='')):
 write(x_access_code);c=conn();r=c.execute('SELECT * FROM platform_workflows WHERE id=?',(workflow_id,)).fetchone()
 if not r:c.close();raise HTTPException(404,'Workflow not found')
 steps=json.loads(r['steps']);idx=r['current_step'];status=r['status'];event=p.action
 if p.action=='complete_step':idx+=1;status='completed' if idx>=len(steps) else 'running'
 elif p.action in ('approve','reject','cancel'):status={'approve':'running','reject':'rejected','cancel':'cancelled'}[p.action];idx=idx+1 if p.action=='approve' and idx+1<len(steps) else idx
 else:c.close();raise HTTPException(400,'Unsupported workflow action')
 c.execute('UPDATE platform_workflows SET current_step=?,status=?,updated_at=? WHERE id=?',(min(idx,len(steps)-1),status,now(),workflow_id));c.execute('INSERT INTO platform_workflow_history VALUES (?,?,?,?,?,?)',(str(uuid.uuid4()),workflow_id,event,p.actor,p.detail,now()));audit(c,p.actor,'workflow.'+event,workflow_id,p.detail);c.commit();c.close();return {'id':workflow_id,'status':status,'current_step':None if status=='completed' else steps[min(idx,len(steps)-1)]}
@router.get('/workflows/{workflow_id}')
def workflow_detail(workflow_id:str,x_access_code:str=Header(default='')):
 read(x_access_code);c=conn();r=c.execute('SELECT * FROM platform_workflows WHERE id=?',(workflow_id,)).fetchone()
 if not r:c.close();raise HTTPException(404,'Workflow not found')
 d=dict(r);d['steps']=json.loads(d['steps']);d['context']=json.loads(d['context'] or '{}');d['history']=[dict(x) for x in c.execute('SELECT event,actor,detail,created_at FROM platform_workflow_history WHERE workflow_id=? ORDER BY created_at',(workflow_id,))];c.close();return d
@router.post('/notifications/templates')
def template_create(p:TemplateIn,x_access_code:str=Header(default='')):
 write(x_access_code);c=conn();tid='TPL-'+uuid.uuid4().hex[:8].upper();t=now();c.execute('INSERT OR REPLACE INTO platform_notification_templates VALUES (?,?,?,?,?,?,?)',(tid,p.name,p.channel,p.subject,p.body,t,t));audit(c,'staff','notification.template',tid,p.name);c.commit();c.close();return {'id':tid,'name':p.name,'channel':p.channel}
@router.get('/notifications/templates')
def templates(x_access_code:str=Header(default='')):read(x_access_code);c=conn();r=[dict(x) for x in c.execute('SELECT * FROM platform_notification_templates ORDER BY name')];c.close();return {'results':r}
@router.post('/notifications')
def notification_create(p:NotificationIn,x_access_code:str=Header(default='')):
 write(x_access_code);c=conn();subject=p.subject;body=p.body;channel=p.channel
 if p.template_id:
  t=c.execute('SELECT * FROM platform_notification_templates WHERE id=?',(p.template_id,)).fetchone()
  if not t:c.close();raise HTTPException(404,'Template not found')
  channel=t['channel'];subject=subject or t['subject'];body=body or t['body']
 nid='NTF-'+uuid.uuid4().hex[:10].upper();ts=now();status='scheduled' if p.scheduled_at and p.scheduled_at>ts else 'queued';c.execute('INSERT INTO platform_notifications VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',(nid,p.template_id,channel,p.recipient,subject,body,status,p.scheduled_at,0,'',ts,ts));audit(c,'staff','notification.queue',nid,p.recipient);c.commit();c.close();return {'id':nid,'status':status,'channel':channel,'recipient':p.recipient,'delivery_provider_required':channel in ('email','sms','push')}
@router.get('/notifications')
def notifications(status:str='',x_access_code:str=Header(default='')):
 read(x_access_code);c=conn();q='SELECT * FROM platform_notifications';a=[]
 if status:q+=' WHERE status=?';a.append(status)
 r=[dict(x) for x in c.execute(q+' ORDER BY created_at DESC',a)];c.close();return {'results':r}
@router.post('/documents/upload')
async def document_upload(file:UploadFile=File(...),tags:str=Form(''),owner:str=Form(''),document_id:str=Form(''),x_access_code:str=Header(default='')):
 write(x_access_code);data=await file.read();c=conn();t=now()
 if document_id:
  old=c.execute('SELECT * FROM platform_documents WHERE id=?',(document_id,)).fetchone()
  if not old:c.close();raise HTTPException(404,'Document not found')
  version=old['version']+1;did=document_id
 else:version=1;did='DOC-'+uuid.uuid4().hex[:10].upper()
 stored=f'{did}-v{version}-{uuid.uuid4().hex[:8]}';open(os.path.join(DOC_DIR,stored),'wb').write(data)
 if document_id:c.execute('UPDATE platform_documents SET name=?,stored_name=?,mime_type=?,size=?,version=?,tags=?,owner=?,updated_at=? WHERE id=?',(file.filename,stored,file.content_type or '',len(data),version,tags,owner,t,did))
 else:c.execute('INSERT INTO platform_documents VALUES (?,?,?,?,?,?,?,?,?,?)',(did,file.filename,stored,file.content_type or '',len(data),version,tags,owner,t,t))
 c.execute('INSERT INTO platform_document_versions VALUES (?,?,?,?,?,?)',(str(uuid.uuid4()),did,version,stored,len(data),t));audit(c,owner or 'staff','document.upload',did,file.filename);c.commit();c.close();return {'id':did,'name':file.filename,'version':version,'size':len(data),'tags':tags}
@router.get('/documents')
def document_search(q:str='',x_access_code:str=Header(default='')):
 read(x_access_code);c=conn();term='%'+q+'%';r=[dict(x) for x in c.execute('SELECT * FROM platform_documents WHERE ?="" OR name LIKE ? OR tags LIKE ? OR owner LIKE ? ORDER BY updated_at DESC',(q,term,term,term))];c.close();return {'results':r}
@router.get('/documents/{document_id}/versions')
def document_versions(document_id:str,x_access_code:str=Header(default='')):read(x_access_code);c=conn();r=[dict(x) for x in c.execute('SELECT * FROM platform_document_versions WHERE document_id=? ORDER BY version DESC',(document_id,))];c.close();return {'results':r}
@router.get('/audit')
def audit_log(actor:str='',action:str='',x_access_code:str=Header(default='')):
 read(x_access_code);c=conn();q='SELECT * FROM platform_audit WHERE 1=1';a=[]
 if actor:q+=' AND actor=?';a.append(actor)
 if action:q+=' AND action LIKE ?';a.append('%'+action+'%')
 r=[dict(x) for x in c.execute(q+' ORDER BY created_at DESC LIMIT 500',a)];c.close();return {'results':r}
@router.post('/mdm')
def mdm_upsert(p:MDMIn,x_access_code:str=Header(default='')):
 write(x_access_code);clean={str(k).strip():v.strip() if isinstance(v,str) else v for k,v in p.data.items()};c=conn();c.execute('INSERT OR REPLACE INTO platform_mdm VALUES (?,?,?,?,?)',(p.entity_type.strip().lower(),p.record_key.strip().upper(),json.dumps(clean,sort_keys=True),p.source,now()));audit(c,'staff','mdm.upsert',p.entity_type+':'+p.record_key,p.source);c.commit();c.close();return {'entity_type':p.entity_type,'record_key':p.record_key.upper(),'data':clean}
@router.get('/mdm/{entity_type}')
def mdm_list(entity_type:str,q:str='',x_access_code:str=Header(default='')):
 read(x_access_code);c=conn();r=[dict(x) for x in c.execute('SELECT * FROM platform_mdm WHERE entity_type=? AND (?="" OR record_key LIKE ? OR data LIKE ?) ORDER BY record_key',(entity_type.lower(),q,'%'+q+'%','%'+q+'%'))];c.close()
 for x in r:x['data']=json.loads(x['data'])
 return {'results':r}
@router.post('/api/policies')
def api_policy(p:APIPolicyIn,x_access_code:str=Header(default='')):
 write(x_access_code);c=conn();pid='POL-'+uuid.uuid4().hex[:8].upper();t=now();c.execute('INSERT INTO platform_api_policies VALUES (?,?,?,?,?,?,?,?)',(pid,p.name,p.scope,p.rate_limit,p.burst,1,t,t));audit(c,'staff','api.policy',pid,p.name);c.commit();c.close();return {'id':pid,**model(p),'enforcement':'policy stored; runtime gateway/middleware must consume it'}
@router.post('/api/developer-keys')
def developer_key(p:DeveloperKeyIn,x_access_code:str=Header(default='')):
 write(x_access_code);raw='uga_'+secrets.token_urlsafe(30);h=hashlib.sha256(raw.encode()).hexdigest();kid='KEY-'+uuid.uuid4().hex[:8].upper();c=conn();c.execute('INSERT INTO platform_developer_keys VALUES (?,?,?,?,?,?,?)',(kid,p.name,h,p.scope,1,now(),None));audit(c,'staff','api.key.create',kid,p.name);c.commit();c.close();return {'id':kid,'name':p.name,'scope':p.scope,'key':raw,'note':'Key is shown once; only its hash is stored.'}
@router.get('/api/policies')
def api_policies(x_access_code:str=Header(default='')):read(x_access_code);c=conn();r=[dict(x) for x in c.execute('SELECT * FROM platform_api_policies ORDER BY updated_at DESC')];c.close();return {'results':r}
@router.post('/monitoring/snapshot')
def monitor(x_access_code:str=Header(default='')):
 read(x_access_code);c=conn();tables={r['name']:c.execute('SELECT COUNT(*) n FROM '+r['name']).fetchone()['n'] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'") if r['name'].replace('_','').isalnum()};metrics={'database':'ok','table_count':len(tables),'row_counts':tables,'generated_at':now()};sid='MON-'+uuid.uuid4().hex[:8].upper();c.execute('INSERT INTO platform_monitoring VALUES (?,?,?,?)',(sid,'ok',json.dumps(metrics),now()));c.commit();c.close();return {'id':sid,'status':'ok','metrics':metrics}
@router.get('/monitoring/history')
def monitor_history(x_access_code:str=Header(default='')):read(x_access_code);c=conn();r=[dict(x) for x in c.execute('SELECT * FROM platform_monitoring ORDER BY created_at DESC LIMIT 100')];c.close();return {'results':r}
@router.put('/features/{feature_key}')
def feature_set(feature_key:str,p:FeatureIn,x_access_code:str=Header(default='')):
 write(x_access_code);c=conn();key=feature_key.strip().lower();c.execute('INSERT OR REPLACE INTO platform_features VALUES (?,?,?,?,?,?,?)',(key,int(p.enabled),p.rollout_percent,p.variant_a,p.variant_b,json.dumps(p.target_rules),now()));audit(c,'staff','feature.update',key,json.dumps(model(p)));c.commit();c.close();return {'feature_key':key,**model(p)}
@router.get('/features')
def features(x_access_code:str=Header(default='')):
 read(x_access_code);c=conn();r=[dict(x) for x in c.execute('SELECT * FROM platform_features ORDER BY feature_key')];c.close()
 for x in r:x['enabled']=bool(x['enabled']);x['target_rules']=json.loads(x['target_rules'] or '{}')
 return {'results':r}
@router.get('/features/{feature_key}/evaluate')
def feature_eval(feature_key:str,user_id:str='',x_access_code:str=Header(default='')):
 read(x_access_code);c=conn();r=c.execute('SELECT * FROM platform_features WHERE feature_key=?',(feature_key.lower(),)).fetchone();c.close()
 if not r:return {'feature_key':feature_key,'enabled':False,'reason':'not configured'}
 bucket=int(hashlib.sha256((feature_key+'|'+user_id).encode()).hexdigest()[:8],16)%100;enabled=bool(r['enabled']) and bucket<r['rollout_percent'];variant='A' if bucket<r['variant_a'] else 'B';return {'feature_key':feature_key,'enabled':enabled,'bucket':bucket,'rollout_percent':r['rollout_percent'],'variant':variant,'target_rules':json.loads(r['target_rules'] or '{}')}