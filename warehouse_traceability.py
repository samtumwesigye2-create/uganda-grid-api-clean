import os,sqlite3,time,uuid
from fastapi import APIRouter,Form,Header,Query
from auth import require_permission
DB=os.path.join(os.path.dirname(os.path.abspath(__file__)),'data_hub.db');router=APIRouter()
def db():c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;return c
def init():
 c=db();c.execute('''CREATE TABLE IF NOT EXISTS warehouse_trace_events(id TEXT PRIMARY KEY,event_no TEXT UNIQUE NOT NULL,sku TEXT NOT NULL,warehouse_id TEXT,lot_no TEXT,batch_no TEXT,serial_no TEXT,event_type TEXT NOT NULL,quantity REAL NOT NULL DEFAULT 0,from_location TEXT,to_location TEXT,reference_type TEXT,reference_no TEXT,actor TEXT,note TEXT,created_at REAL NOT NULL)''');c.execute('CREATE INDEX IF NOT EXISTS idx_trace_sku ON warehouse_trace_events(sku,created_at)');c.execute('CREATE INDEX IF NOT EXISTS idx_trace_lot ON warehouse_trace_events(lot_no,batch_no,created_at)');c.execute('CREATE INDEX IF NOT EXISTS idx_trace_ref ON warehouse_trace_events(reference_no,created_at)');c.commit();c.close()
init()
def auth(k,p):require_permission(k,p)
def eno():return f'TRC-{time.strftime("%Y%m%d")}-{uuid.uuid4().hex[:8].upper()}'
@router.post('/warehouse/trace/events')
def add(sku:str=Form(...),event_type:str=Form(...),warehouse_id:str=Form('main'),quantity:float=Form(0),lot_no:str=Form(''),batch_no:str=Form(''),serial_no:str=Form(''),from_location:str=Form(''),to_location:str=Form(''),reference_type:str=Form(''),reference_no:str=Form(''),actor:str=Form(''),note:str=Form(''),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');c=db();i=str(uuid.uuid4());n=eno();c.execute('INSERT INTO warehouse_trace_events VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(i,n,sku,warehouse_id,lot_no,batch_no,serial_no,event_type,quantity,from_location,to_location,reference_type,reference_no,actor,note,time.time()));c.commit();c.close();return {'id':i,'event_no':n}
@router.get('/warehouse/trace/search')
def search(sku:str=Query(''),lot_no:str=Query(''),batch_no:str=Query(''),serial_no:str=Query(''),reference_no:str=Query(''),warehouse_id:str=Query(''),limit:int=Query(200,ge=1,le=1000),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:read');c=db();q='SELECT * FROM warehouse_trace_events WHERE 1=1';a=[]
 for col,val in [('sku',sku),('lot_no',lot_no),('batch_no',batch_no),('serial_no',serial_no),('reference_no',reference_no),('warehouse_id',warehouse_id)]:
  if val:q+=f' AND {col}=?';a.append(val)
 q+=' ORDER BY created_at ASC LIMIT ?';a.append(limit);rows=[dict(r) for r in c.execute(q,a).fetchall()];c.close();return {'count':len(rows),'results':rows}
@router.get('/warehouse/trace/lot/{lot_no}')
def lot_history(lot_no:str,x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:read');c=db();events=[dict(r) for r in c.execute('SELECT * FROM warehouse_trace_events WHERE lot_no=? ORDER BY created_at',(lot_no,)).fetchall()];lots=[dict(r) for r in c.execute('SELECT * FROM warehouse_lots WHERE lot_no=? ORDER BY received_at',(lot_no,)).fetchall()];c.close();return {'lot_no':lot_no,'lot_records':lots,'events':events}
@router.get('/warehouse/trace/investigate')
def investigate(q:str=Query(...),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:read');c=db();like=f'%{q}%';events=[dict(r) for r in c.execute('''SELECT * FROM warehouse_trace_events WHERE sku LIKE ? OR lot_no LIKE ? OR batch_no LIKE ? OR serial_no LIKE ? OR reference_no LIKE ? OR note LIKE ? ORDER BY created_at DESC LIMIT 300''',(like,like,like,like,like,like)).fetchall()];lots=[dict(r) for r in c.execute('''SELECT * FROM warehouse_lots WHERE sku LIKE ? OR lot_no LIKE ? OR batch_no LIKE ? OR location_code LIKE ? LIMIT 100''',(like,like,like,like)).fetchall()];ops=[dict(r) for r in c.execute('''SELECT * FROM warehouse_operations WHERE sku LIKE ? OR reference_no LIKE ? OR lot_no LIKE ? OR batch_no LIKE ? ORDER BY created_at DESC LIMIT 100''',(like,like,like,like)).fetchall()];c.close();return {'query':q,'trace_events':events,'lots':lots,'operations':ops}
@router.post('/warehouse/trace/snapshot')
def snapshot(warehouse_id:str=Form('main'),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');c=db();created=0
 # Import operational history not yet represented in trace ledger.
 for o in c.execute('SELECT * FROM warehouse_operations WHERE warehouse_id=? ORDER BY created_at',(warehouse_id,)).fetchall():
  ref=o['id'];exists=c.execute("SELECT 1 FROM warehouse_trace_events WHERE reference_type='warehouse_operation' AND reference_no=?",(ref,)).fetchone()
  if exists:continue
  c.execute('INSERT INTO warehouse_trace_events VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),eno(),o['sku'] or 'N/A',warehouse_id,o['lot_no'] or '',o['batch_no'] or '','',o['operation_type'],float(o['quantity'] or 0),'',o['location_code'] or '','warehouse_operation',ref,'system',o['notes'] or '',float(o['created_at'] or time.time())));created+=1
 c.commit();c.close();return {'created':created,'warehouse_id':warehouse_id}
