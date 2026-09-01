import os,sqlite3,time,uuid
from fastapi import APIRouter,Form,Header,Query
from auth import require_permission
DB=os.path.join(os.path.dirname(os.path.abspath(__file__)),'data_hub.db');router=APIRouter()
def db():c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;return c
def init():
 c=db();c.execute('''CREATE TABLE IF NOT EXISTS warehouse_exceptions(id TEXT PRIMARY KEY,exception_key TEXT UNIQUE NOT NULL,warehouse_id TEXT NOT NULL,exception_type TEXT NOT NULL,severity TEXT NOT NULL,title TEXT NOT NULL,reference_no TEXT,sku TEXT,status TEXT NOT NULL DEFAULT 'open',task_id TEXT,details TEXT,first_seen REAL NOT NULL,last_seen REAL NOT NULL,resolved_at REAL)''');c.execute('CREATE INDEX IF NOT EXISTS idx_wex ON warehouse_exceptions(warehouse_id,status,severity,last_seen)');c.commit();c.close()
init()
def auth(k,p):require_permission(k,p)
def up(c,w,typ,key,severity,title,ref='',sku='',details=''):
 now=time.time();eid=str(uuid.uuid4());c.execute('''INSERT INTO warehouse_exceptions(id,exception_key,warehouse_id,exception_type,severity,title,reference_no,sku,status,details,first_seen,last_seen) VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(exception_key) DO UPDATE SET severity=excluded.severity,title=excluded.title,details=excluded.details,last_seen=excluded.last_seen,status=CASE WHEN warehouse_exceptions.status='resolved' THEN 'open' ELSE warehouse_exceptions.status END,resolved_at=NULL''',(eid,key,w,typ,severity,title,ref,sku,'open',details,now,now));return key
def task(c,e):
 if e['task_id']:return e['task_id']
 staff=c.execute("SELECT id FROM warehouse_staff WHERE warehouse_id=? AND status='active' ORDER BY id LIMIT 1",(e['warehouse_id'],)).fetchone();tid=str(uuid.uuid4());tn=f'AUTO-{uuid.uuid4().hex[:8].upper()}';c.execute('''INSERT INTO warehouse_tasks(id,task_no,task_type,title,staff_id,warehouse_id,reference_no,priority,status,quantity,created_at,note) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',(tid,tn,'exception',e['title'],staff['id'] if staff else None,e['warehouse_id'],e['reference_no'] or e['exception_key'],'critical' if e['severity']=='critical' else 'high','assigned',0,time.time(),e['details'] or 'Automatically created by warehouse exception engine'));c.execute('UPDATE warehouse_exceptions SET task_id=? WHERE id=?',(tid,e['id']));return tid
@router.post('/warehouse/exceptions/scan')
def scan(warehouse_id:str=Form('main'),auto_tasks:int=Form(1),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');c=db();active=set();now=time.time()
 for r in c.execute('SELECT product_sku,quantity_on_hand FROM stock WHERE warehouse_id=? AND quantity_on_hand<=5',(warehouse_id,)).fetchall():active.add(up(c,warehouse_id,'low_stock',f'low:{warehouse_id}:{r["product_sku"]}','warning',f'Low stock: {r["product_sku"]}',sku=r['product_sku'],details=f'On hand {r["quantity_on_hand"]}'))
 for r in c.execute("SELECT id,sku,lot_no,expiry_date FROM warehouse_lots WHERE warehouse_id=? AND status='available' AND expiry_date!='' AND date(expiry_date)<=date('now','+30 day')",(warehouse_id,)).fetchall():active.add(up(c,warehouse_id,'expiry',f'exp:{r["id"]}','warning',f'Inventory expiring: {r["sku"]}',r['lot_no'],r['sku'],f'Expiry {r["expiry_date"]}'))
 for r in c.execute("SELECT id,task_no,title FROM warehouse_tasks WHERE warehouse_id=? AND status='blocked'",(warehouse_id,)).fetchall():active.add(up(c,warehouse_id,'blocked_task',f'blocked:{r["id"]}','critical',f'Blocked task: {r["title"]}',r['task_no']))
 for r in c.execute("SELECT id,transfer_no FROM warehouse_transfer_orders WHERE status='in_transit' AND (from_warehouse=? OR to_warehouse=?) AND shipped_at<?",(warehouse_id,warehouse_id,now-2*86400)).fetchall():active.add(up(c,warehouse_id,'delayed_transfer',f'trf:{r["id"]}','warning',f'Delayed transfer: {r["transfer_no"]}',r['transfer_no'],details='In transit over 48 hours'))
 for r in c.execute("SELECT id,delivery_no FROM warehouse_deliveries WHERE warehouse_id=? AND status='failed'",(warehouse_id,)).fetchall():active.add(up(c,warehouse_id,'failed_delivery',f'del:{r["id"]}','critical',f'Failed delivery: {r["delivery_no"]}',r['delivery_no']))
 for r in c.execute("SELECT id,hold_no,sku,reason FROM warehouse_quality_holds WHERE warehouse_id=? AND status='quarantine'",(warehouse_id,)).fetchall():active.add(up(c,warehouse_id,'quality_hold',f'q:{r["id"]}','warning',f'Quality hold: {r["sku"]}',r['hold_no'],r['sku'],r['reason']))
 for r in c.execute("SELECT id,recall_no,sku,title,severity FROM warehouse_recalls WHERE status='open'",()).fetchall():active.add(up(c,warehouse_id,'recall',f'recall:{r["id"]}', 'critical' if r['severity'] in ('high','critical') else 'warning',f'Recall: {r["title"]}',r['recall_no'],r['sku']))
 # Auto-resolve exceptions no longer detected.
 openrows=c.execute("SELECT * FROM warehouse_exceptions WHERE warehouse_id=? AND status IN ('open','acknowledged')",(warehouse_id,)).fetchall()
 for e in openrows:
  if e['exception_key'] not in active:c.execute("UPDATE warehouse_exceptions SET status='resolved',resolved_at=? WHERE id=?",(now,e['id']))
 c.commit();created=0
 if auto_tasks:
  for e in c.execute("SELECT * FROM warehouse_exceptions WHERE warehouse_id=? AND status='open' AND task_id IS NULL AND severity IN ('warning','critical')",(warehouse_id,)).fetchall():task(c,e);created+=1
 c.commit();count=c.execute("SELECT COUNT(*) n FROM warehouse_exceptions WHERE warehouse_id=? AND status='open'",(warehouse_id,)).fetchone()['n'];c.close();return {'open_exceptions':count,'tasks_created':created,'detected':len(active)}
@router.get('/warehouse/exceptions')
def list_ex(warehouse_id:str=Query('main'),status:str=Query('open'),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:read');c=db();r=[dict(x) for x in c.execute('SELECT * FROM warehouse_exceptions WHERE warehouse_id=? AND status=? ORDER BY CASE severity WHEN "critical" THEN 0 ELSE 1 END,last_seen DESC',(warehouse_id,status)).fetchall()];c.close();return {'results':r}
@router.post('/warehouse/exceptions/{exception_id}/acknowledge')
def ack(exception_id:str,x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');c=db();c.execute("UPDATE warehouse_exceptions SET status='acknowledged' WHERE id=? AND status='open'",(exception_id,));c.commit();c.close();return {'id':exception_id,'status':'acknowledged'}
