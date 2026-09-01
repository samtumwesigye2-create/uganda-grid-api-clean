import os,sqlite3,time,uuid,json
from fastapi import APIRouter,Form,Header,HTTPException,Query
from auth import require_permission
DB=os.path.join(os.path.dirname(os.path.abspath(__file__)),'data_hub.db');router=APIRouter()
def db():c=sqlite3.connect(DB,timeout=30,isolation_level=None);c.row_factory=sqlite3.Row;c.execute('PRAGMA busy_timeout=30000');return c
def init():
 c=db();c.execute('BEGIN IMMEDIATE');c.execute('''CREATE TABLE IF NOT EXISTS warehouse_approval_requests(id TEXT PRIMARY KEY,request_no TEXT UNIQUE NOT NULL,warehouse_id TEXT NOT NULL,action_type TEXT NOT NULL,reference_no TEXT,requested_by TEXT NOT NULL,requested_by_code TEXT,reason TEXT,payload_json TEXT,status TEXT NOT NULL DEFAULT 'pending',approved_by TEXT,decision_note TEXT,created_at REAL NOT NULL,decided_at REAL)''');
 cols={r['name'] for r in c.execute('PRAGMA table_info(warehouse_approval_requests)').fetchall()}
 if 'consumed_at' not in cols:c.execute('ALTER TABLE warehouse_approval_requests ADD COLUMN consumed_at REAL')
 if 'consumed_reference' not in cols:c.execute('ALTER TABLE warehouse_approval_requests ADD COLUMN consumed_reference TEXT')
 c.execute('''CREATE TABLE IF NOT EXISTS warehouse_security_audit(id TEXT PRIMARY KEY,event_no TEXT UNIQUE NOT NULL,warehouse_id TEXT NOT NULL,event_type TEXT NOT NULL,action_type TEXT,reference_no TEXT,actor TEXT,approval_id TEXT,details TEXT,created_at REAL NOT NULL)''');c.execute('CREATE INDEX IF NOT EXISTS idx_approval_queue ON warehouse_approval_requests(warehouse_id,status,created_at)');c.execute('CREATE INDEX IF NOT EXISTS idx_security_audit ON warehouse_security_audit(warehouse_id,created_at)');c.execute('COMMIT');c.close()
init()
def auth(k,p):require_permission(k,p)
def number(p):return f'{p}-{time.strftime("%Y%m%d")}-{uuid.uuid4().hex[:7].upper()}'
def audit(c,w,event,action='',ref='',actor='',approval='',details=''):c.execute('INSERT INTO warehouse_security_audit VALUES(?,?,?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),number('AUD'),w,event,action,ref,actor,approval,details,time.time()))
def consume_approval(c,approval_id,action_type,reference_no,warehouse_id='main',actor='system'):
 if not approval_id:raise HTTPException(403,f'Approved {action_type} authorization required')
 r=c.execute('SELECT * FROM warehouse_approval_requests WHERE id=?',(approval_id,)).fetchone()
 if not r:raise HTTPException(403,'Approval not found')
 if r['status']!='approved':raise HTTPException(403,'Approval is not approved')
 if r['action_type']!=action_type:raise HTTPException(403,'Approval action does not match operation')
 if r['warehouse_id']!=warehouse_id:raise HTTPException(403,'Approval warehouse does not match operation')
 if r['reference_no'] and r['reference_no']!=reference_no:raise HTTPException(403,'Approval reference does not match operation')
 if r['consumed_at']:raise HTTPException(409,'Approval has already been consumed')
 c.execute('UPDATE warehouse_approval_requests SET consumed_at=?,consumed_reference=? WHERE id=?',(time.time(),reference_no,approval_id));audit(c,warehouse_id,'approval_consumed',action_type,reference_no,actor,approval_id,'Sensitive operation authorized and approval consumed');return r
SENSITIVE={'inventory_adjustment','stock_writeoff','destroy_inventory','return_supplier','dispatch_release','recall_close','quality_release','transfer_ship','purchase_approval'}
@router.post('/warehouse/approvals')
def request(action_type:str=Form(...),warehouse_id:str=Form('main'),reference_no:str=Form(''),requested_by:str=Form(...),reason:str=Form(...),payload_json:str=Form('{}'),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write')
 if action_type not in SENSITIVE:raise HTTPException(400,'Unsupported sensitive action')
 try:json.loads(payload_json or '{}')
 except:raise HTTPException(400,'Invalid action payload')
 c=db();c.execute('BEGIN IMMEDIATE');i=str(uuid.uuid4());n=number('APR');c.execute('INSERT INTO warehouse_approval_requests(id,request_no,warehouse_id,action_type,reference_no,requested_by,requested_by_code,reason,payload_json,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(i,n,warehouse_id,action_type,reference_no,requested_by,'authenticated',reason,payload_json,'pending',time.time()));audit(c,warehouse_id,'approval_requested',action_type,reference_no,requested_by,i,reason);c.execute('COMMIT');c.close();return {'id':i,'request_no':n,'status':'pending'}
@router.get('/warehouse/approvals')
def queue(warehouse_id:str=Query('main'),status:str=Query('pending'),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:read');c=db();r=[dict(x) for x in c.execute('SELECT * FROM warehouse_approval_requests WHERE warehouse_id=? AND status=? ORDER BY created_at',(warehouse_id,status)).fetchall()];c.close();return {'results':r}
@router.post('/warehouse/approvals/{approval_id}/decision')
def decision(approval_id:str,decision:str=Form(...),approved_by:str=Form(...),decision_note:str=Form(''),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write')
 if decision not in {'approved','rejected'}:raise HTTPException(400,'Decision must be approved or rejected')
 c=db();c.execute('BEGIN IMMEDIATE');r=c.execute('SELECT * FROM warehouse_approval_requests WHERE id=?',(approval_id,)).fetchone()
 if not r:c.execute('ROLLBACK');c.close();raise HTTPException(404,'Approval request not found')
 if r['status']!='pending':c.execute('ROLLBACK');c.close();raise HTTPException(400,'Approval already decided')
 if approved_by.strip().lower()==r['requested_by'].strip().lower():c.execute('ROLLBACK');c.close();raise HTTPException(403,'Separation of duties: requester cannot approve own action')
 c.execute('UPDATE warehouse_approval_requests SET status=?,approved_by=?,decision_note=?,decided_at=? WHERE id=?',(decision,approved_by,decision_note,time.time(),approval_id));audit(c,r['warehouse_id'],'approval_decision',r['action_type'],r['reference_no'],approved_by,approval_id,decision+': '+decision_note);c.execute('COMMIT');c.close();return {'id':approval_id,'status':decision}
@router.get('/warehouse/approvals/{approval_id}/authorize')
def authorize(approval_id:str,action_type:str=Query(...),reference_no:str=Query(''),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');c=db();r=c.execute('SELECT * FROM warehouse_approval_requests WHERE id=?',(approval_id,)).fetchone();ok=bool(r and r['status']=='approved' and not r['consumed_at'] and r['action_type']==action_type and (not reference_no or not r['reference_no'] or r['reference_no']==reference_no));c.close();return {'authorized':ok,'approval_id':approval_id,'consumed':bool(r and r['consumed_at'])}
@router.post('/warehouse/security/audit')
def log(event_type:str=Form(...),action_type:str=Form(''),warehouse_id:str=Form('main'),reference_no:str=Form(''),actor:str=Form(''),approval_id:str=Form(''),details:str=Form(''),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');c=db();c.execute('BEGIN IMMEDIATE');audit(c,warehouse_id,event_type,action_type,reference_no,actor,approval_id,details);c.execute('COMMIT');c.close();return {'logged':True}
@router.get('/warehouse/security/audit')
def audit_log(warehouse_id:str=Query('main'),limit:int=Query(200,ge=1,le=1000),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:read');c=db();r=[dict(x) for x in c.execute('SELECT * FROM warehouse_security_audit WHERE warehouse_id=? ORDER BY created_at DESC LIMIT ?',(warehouse_id,limit)).fetchall()];c.close();return {'results':r}
