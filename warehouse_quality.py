import os,sqlite3,time,uuid
from fastapi import APIRouter,Form,Header,HTTPException,Query
from auth import require_permission
DB=os.path.join(os.path.dirname(os.path.abspath(__file__)),'data_hub.db');router=APIRouter()
def db():c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;return c
def init():
 c=db();c.execute('''CREATE TABLE IF NOT EXISTS warehouse_quality_holds(id TEXT PRIMARY KEY,hold_no TEXT UNIQUE NOT NULL,sku TEXT NOT NULL,warehouse_id TEXT NOT NULL,lot_no TEXT,batch_no TEXT,quantity REAL NOT NULL DEFAULT 0,reason TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'quarantine',quarantine_location TEXT,inspection_result TEXT,authorized_by TEXT,created_at REAL NOT NULL,resolved_at REAL)''');c.execute('''CREATE TABLE IF NOT EXISTS warehouse_recalls(id TEXT PRIMARY KEY,recall_no TEXT UNIQUE NOT NULL,title TEXT NOT NULL,sku TEXT NOT NULL,lot_no TEXT,batch_no TEXT,reason TEXT NOT NULL,severity TEXT NOT NULL DEFAULT 'high',status TEXT NOT NULL DEFAULT 'open',created_at REAL NOT NULL,closed_at REAL)''');c.execute('''CREATE TABLE IF NOT EXISTS warehouse_recall_actions(id TEXT PRIMARY KEY,recall_id TEXT NOT NULL,action_type TEXT NOT NULL,reference_no TEXT,customer_name TEXT,quantity REAL NOT NULL DEFAULT 0,status TEXT NOT NULL DEFAULT 'identified',note TEXT,created_at REAL NOT NULL,updated_at REAL NOT NULL)''');c.execute('CREATE INDEX IF NOT EXISTS idx_qhold ON warehouse_quality_holds(warehouse_id,status,sku,lot_no)');c.execute('CREATE INDEX IF NOT EXISTS idx_recall ON warehouse_recalls(status,sku,lot_no)');c.commit();c.close()
init()
def auth(k,p):require_permission(k,p)
def num(prefix):return f'{prefix}-{time.strftime("%Y%m%d")}-{uuid.uuid4().hex[:6].upper()}'
@router.post('/warehouse/quality/holds')
def hold(sku:str=Form(...),warehouse_id:str=Form('main'),lot_no:str=Form(''),batch_no:str=Form(''),quantity:float=Form(0),reason:str=Form(...),quarantine_location:str=Form('QUARANTINE'),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');c=db();i=str(uuid.uuid4());n=num('QH');c.execute('INSERT INTO warehouse_quality_holds(id,hold_no,sku,warehouse_id,lot_no,batch_no,quantity,reason,status,quarantine_location,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(i,n,sku,warehouse_id,lot_no,batch_no,quantity,reason,'quarantine',quarantine_location,time.time()));
 if lot_no:c.execute("UPDATE warehouse_lots SET status='quarantine',updated_at=? WHERE warehouse_id=? AND sku=? AND lot_no=?",(time.time(),warehouse_id,sku,lot_no))
 c.commit();c.close();return {'id':i,'hold_no':n,'status':'quarantine'}
@router.get('/warehouse/quality/holds')
def holds(warehouse_id:str=Query('main'),status:str=Query(''),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:read');c=db();q='SELECT * FROM warehouse_quality_holds WHERE warehouse_id=?';a=[warehouse_id]
 if status:q+=' AND status=?';a.append(status)
 q+=' ORDER BY created_at DESC';r=[dict(x) for x in c.execute(q,a).fetchall()];c.close();return {'results':r}
@router.post('/warehouse/quality/holds/{hold_id}/resolve')
def resolve(hold_id:str,decision:str=Form(...),inspection_result:str=Form(''),authorized_by:str=Form(...),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write')
 if decision not in {'release','reject','destroy','return_supplier'}:raise HTTPException(400,'Invalid quality decision')
 c=db();h=c.execute('SELECT * FROM warehouse_quality_holds WHERE id=?',(hold_id,)).fetchone()
 if not h:c.close();raise HTTPException(404,'Quality hold not found')
 if h['status']!='quarantine':c.close();raise HTTPException(400,'Hold already resolved')
 status={'release':'released','reject':'rejected','destroy':'destroyed','return_supplier':'return_supplier'}[decision];c.execute('UPDATE warehouse_quality_holds SET status=?,inspection_result=?,authorized_by=?,resolved_at=? WHERE id=?',(status,inspection_result,authorized_by,time.time(),hold_id))
 if h['lot_no']:c.execute('UPDATE warehouse_lots SET status=?,updated_at=? WHERE warehouse_id=? AND sku=? AND lot_no=?',('available' if decision=='release' else status,time.time(),h['warehouse_id'],h['sku'],h['lot_no']))
 c.commit();c.close();return {'id':hold_id,'status':status}
@router.post('/warehouse/recalls')
def recall(title:str=Form(...),sku:str=Form(...),lot_no:str=Form(''),batch_no:str=Form(''),reason:str=Form(...),severity:str=Form('high'),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');c=db();i=str(uuid.uuid4());n=num('RCL');c.execute('INSERT INTO warehouse_recalls VALUES(?,?,?,?,?,?,?,?,?,?,?)',(i,n,title,sku,lot_no,batch_no,reason,severity,'open',time.time(),None));
 # Immediately quarantine matching warehouse lots.
 if lot_no:c.execute("UPDATE warehouse_lots SET status='recall_hold',updated_at=? WHERE sku=? AND lot_no=?",(time.time(),sku,lot_no))
 elif batch_no:c.execute("UPDATE warehouse_lots SET status='recall_hold',updated_at=? WHERE sku=? AND batch_no=?",(time.time(),sku,batch_no))
 # Identify affected outbound orders from lot-linked wave lines.
 rows=c.execute('''SELECT DISTINCT o.order_no,o.customer_name,w.quantity FROM warehouse_wave_lines w JOIN warehouse_customer_orders o ON o.id=w.order_id WHERE w.sku=? AND (?='' OR w.lot_no=?) AND (?='' OR w.batch_no=?)''',(sku,lot_no,lot_no,batch_no,batch_no)).fetchall()
 for r in rows:c.execute('INSERT INTO warehouse_recall_actions VALUES(?,?,?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),i,'customer_order',r['order_no'],r['customer_name'],r['quantity'],'identified','Affected outbound allocation',time.time(),time.time()))
 c.commit();c.close();return {'id':i,'recall_no':n,'affected_orders':len(rows),'status':'open'}
@router.get('/warehouse/recalls')
def recalls(status:str=Query('open'),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:read');c=db();rs=[dict(x) for x in c.execute('SELECT * FROM warehouse_recalls WHERE status=? ORDER BY created_at DESC',(status,)).fetchall()]
 for r in rs:r['actions']=[dict(x) for x in c.execute('SELECT * FROM warehouse_recall_actions WHERE recall_id=? ORDER BY created_at',(r['id'],)).fetchall()]
 c.close();return {'results':rs}
@router.post('/warehouse/recalls/{recall_id}/actions/{action_id}')
def action(recall_id:str,action_id:str,status:str=Form(...),note:str=Form(''),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write')
 if status not in {'identified','notified','return_requested','returned','closed'}:raise HTTPException(400,'Invalid recall action status')
 c=db();c.execute('UPDATE warehouse_recall_actions SET status=?,note=?,updated_at=? WHERE id=? AND recall_id=?',(status,note,time.time(),action_id,recall_id));c.commit();c.close();return {'id':action_id,'status':status}
@router.post('/warehouse/recalls/{recall_id}/close')
def close(recall_id:str,x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');c=db();open_actions=c.execute("SELECT COUNT(*) n FROM warehouse_recall_actions WHERE recall_id=? AND status NOT IN ('returned','closed')",(recall_id,)).fetchone()['n']
 if open_actions:c.close();raise HTTPException(400,f'{open_actions} recall actions remain open')
 c.execute("UPDATE warehouse_recalls SET status='closed',closed_at=? WHERE id=?",(time.time(),recall_id));c.commit();c.close();return {'id':recall_id,'status':'closed'}
