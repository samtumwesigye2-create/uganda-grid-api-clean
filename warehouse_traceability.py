import os,sqlite3,time,uuid,hashlib,json
from fastapi import APIRouter,Form,Header,Query,HTTPException
from auth import require_permission
DB=os.path.join(os.path.dirname(os.path.abspath(__file__)),'data_hub.db');router=APIRouter()
def db():c=sqlite3.connect(DB,timeout=30,isolation_level=None);c.row_factory=sqlite3.Row;c.execute('PRAGMA busy_timeout=30000');return c
def cols(c,t):return {x['name'] for x in c.execute('PRAGMA table_info('+t+')').fetchall()}
def init():
 c=db();c.execute('BEGIN IMMEDIATE');c.execute('''CREATE TABLE IF NOT EXISTS warehouse_trace_events(id TEXT PRIMARY KEY,event_no TEXT UNIQUE NOT NULL,sku TEXT NOT NULL,warehouse_id TEXT,lot_no TEXT,batch_no TEXT,serial_no TEXT,event_type TEXT NOT NULL,quantity REAL NOT NULL DEFAULT 0,from_location TEXT,to_location TEXT,reference_type TEXT,reference_no TEXT,actor TEXT,note TEXT,created_at REAL NOT NULL)''');
 for n,t in [('previous_hash','TEXT'),('event_hash','TEXT'),('source_key','TEXT')]:
  if n not in cols(c,'warehouse_trace_events'):c.execute(f'ALTER TABLE warehouse_trace_events ADD COLUMN {n} {t}')
 c.execute('''CREATE TABLE IF NOT EXISTS warehouse_trace_sources(source_key TEXT PRIMARY KEY,event_id TEXT NOT NULL,created_at REAL NOT NULL)''');c.execute('CREATE INDEX IF NOT EXISTS idx_trace_sku ON warehouse_trace_events(sku,created_at)');c.execute('CREATE INDEX IF NOT EXISTS idx_trace_lot ON warehouse_trace_events(lot_no,batch_no,created_at)');c.execute('CREATE INDEX IF NOT EXISTS idx_trace_ref ON warehouse_trace_events(reference_no,created_at)');c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_trace_source_key ON warehouse_trace_events(source_key) WHERE source_key IS NOT NULL AND source_key!=""');c.execute('COMMIT');c.close()
init()
def auth(k,p):require_permission(k,p)
def eno():return f'TRC-{time.strftime("%Y%m%d")}-{uuid.uuid4().hex[:8].upper()}'
def has_table(c,n):return c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(n,)).fetchone() is not None
def digest(v):return hashlib.sha256(json.dumps(v,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def emit(c,key,sku,event_type,warehouse_id='',quantity=0,lot_no='',batch_no='',serial_no='',from_location='',to_location='',reference_type='',reference_no='',actor='system',note='',created_at=None):
 old=c.execute('SELECT event_id FROM warehouse_trace_sources WHERE source_key=?',(key,)).fetchone()
 if old:return False
 i=str(uuid.uuid4());n=eno();ts=float(created_at or time.time());prev=c.execute("SELECT event_hash FROM warehouse_trace_events WHERE event_hash IS NOT NULL AND event_hash!='' ORDER BY rowid DESC LIMIT 1").fetchone();ph=prev['event_hash'] if prev else ''
 payload=[i,n,sku or 'N/A',warehouse_id or '',lot_no or '',batch_no or '',serial_no or '',event_type,float(quantity or 0),from_location or '',to_location or '',reference_type or '',reference_no or '',actor or 'system',note or '',ts,ph,key];eh=digest(payload)
 c.execute('''INSERT INTO warehouse_trace_events(id,event_no,sku,warehouse_id,lot_no,batch_no,serial_no,event_type,quantity,from_location,to_location,reference_type,reference_no,actor,note,created_at,previous_hash,event_hash,source_key) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(*payload[:-2],ph,eh,key));c.execute('INSERT INTO warehouse_trace_sources VALUES(?,?,?)',(key,i,time.time()));return True
@router.post('/warehouse/trace/events')
def add(sku:str=Form(...),event_type:str=Form(...),warehouse_id:str=Form('main'),quantity:float=Form(0),lot_no:str=Form(''),batch_no:str=Form(''),serial_no:str=Form(''),from_location:str=Form(''),to_location:str=Form(''),reference_type:str=Form(''),reference_no:str=Form(''),actor:str=Form(''),note:str=Form(''),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');c=db();c.execute('BEGIN IMMEDIATE')
 try:key='manual:'+str(uuid.uuid4());emit(c,key,sku,event_type,warehouse_id,quantity,lot_no,batch_no,serial_no,from_location,to_location,reference_type,reference_no,actor or 'staff',note,time.time());r=c.execute('SELECT id,event_no,event_hash FROM warehouse_trace_events WHERE source_key=?',(key,)).fetchone();c.execute('COMMIT');return dict(r)
 except Exception:c.execute('ROLLBACK');raise
 finally:c.close()
@router.get('/warehouse/trace/search')
def search(sku:str=Query(''),lot_no:str=Query(''),batch_no:str=Query(''),serial_no:str=Query(''),reference_no:str=Query(''),warehouse_id:str=Query(''),limit:int=Query(200,ge=1,le=1000),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:read');c=db();q='SELECT * FROM warehouse_trace_events WHERE 1=1';a=[]
 for col,val in [('sku',sku),('lot_no',lot_no),('batch_no',batch_no),('serial_no',serial_no),('reference_no',reference_no),('warehouse_id',warehouse_id)]:
  if val:q+=f' AND {col}=?';a.append(val)
 q+=' ORDER BY created_at ASC,rowid ASC LIMIT ?';a.append(limit);rows=[dict(r) for r in c.execute(q,a).fetchall()];c.close();return {'count':len(rows),'results':rows}
@router.get('/warehouse/trace/verify')
def verify(x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:read');c=db();rows=c.execute("SELECT rowid,* FROM warehouse_trace_events WHERE event_hash IS NOT NULL AND event_hash!='' ORDER BY rowid").fetchall();prev='';bad=[]
 for r in rows:
  payload=[r['id'],r['event_no'],r['sku'],r['warehouse_id'] or '',r['lot_no'] or '',r['batch_no'] or '',r['serial_no'] or '',r['event_type'],float(r['quantity'] or 0),r['from_location'] or '',r['to_location'] or '',r['reference_type'] or '',r['reference_no'] or '',r['actor'] or 'system',r['note'] or '',float(r['created_at']),r['previous_hash'] or '',r['source_key'] or ''];expected=digest(payload)
  if (r['previous_hash'] or '')!=prev or r['event_hash']!=expected:bad.append({'event_no':r['event_no'],'reason':'hash_chain_mismatch'})
  prev=r['event_hash']
 c.close();return {'verified':not bad,'hashed_events':len(rows),'problems':bad[:100]}
@router.get('/warehouse/trace/lot/{lot_no}')
def lot_history(lot_no:str,x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:read');c=db();events=[dict(r) for r in c.execute('SELECT * FROM warehouse_trace_events WHERE lot_no=? ORDER BY created_at,rowid',(lot_no,)).fetchall()];lots=[dict(r) for r in c.execute('SELECT * FROM warehouse_lots WHERE lot_no=? ORDER BY received_at',(lot_no,)).fetchall()];c.close();return {'lot_no':lot_no,'lot_records':lots,'events':events}
@router.get('/warehouse/trace/investigate')
def investigate(q:str=Query(...),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:read');c=db();like=f'%{q}%';events=[dict(r) for r in c.execute('''SELECT * FROM warehouse_trace_events WHERE sku LIKE ? OR lot_no LIKE ? OR batch_no LIKE ? OR serial_no LIKE ? OR reference_no LIKE ? OR note LIKE ? ORDER BY created_at DESC LIMIT 300''',(like,like,like,like,like,like)).fetchall()];lots=[dict(r) for r in c.execute('''SELECT * FROM warehouse_lots WHERE sku LIKE ? OR lot_no LIKE ? OR batch_no LIKE ? OR location_code LIKE ? LIMIT 100''',(like,like,like,like)).fetchall()];ops=[dict(r) for r in c.execute('''SELECT * FROM warehouse_operations WHERE sku LIKE ? OR reference_no LIKE ? OR lot_no LIKE ? OR batch_no LIKE ? ORDER BY created_at DESC LIMIT 100''',(like,like,like,like)).fetchall()] if has_table(c,'warehouse_operations') else [];c.close();return {'query':q,'trace_events':events,'lots':lots,'operations':ops}
@router.post('/warehouse/trace/snapshot')
def snapshot(warehouse_id:str=Form('main'),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');c=db();c.execute('BEGIN IMMEDIATE');created=0
 try:
  if has_table(c,'warehouse_operations'):
   for o in c.execute('SELECT * FROM warehouse_operations WHERE warehouse_id=? ORDER BY created_at',(warehouse_id,)).fetchall():created+=emit(c,'op:'+o['id'],o['sku'],o['operation_type'],warehouse_id,o['quantity'],o['lot_no'],o['batch_no'],'','',o['location_code'],'warehouse_operation',o['reference_no'] or o['id'],'system',o['note'] or '',o['created_at'])
  if has_table(c,'warehouse_lot_reservations'):
   for r in c.execute('SELECT r.*,l.lot_no,l.batch_no FROM warehouse_lot_reservations r LEFT JOIN warehouse_lots l ON l.id=r.lot_id WHERE r.warehouse_id=? ORDER BY r.created_at',(warehouse_id,)).fetchall():created+=emit(c,'reservation:'+r['id'],r['sku'],'inventory_'+r['status'],warehouse_id,r['quantity'],r['lot_no'],r['batch_no'],'',r['location_code'],'','customer_order',r['order_id'],'system','Lot-linked outbound reservation',r['created_at'])
  if has_table(c,'warehouse_dispatch_ledger'):
   for d in c.execute('SELECT * FROM warehouse_dispatch_ledger WHERE warehouse_id=? ORDER BY created_at',(warehouse_id,)).fetchall():
    for r in c.execute("SELECT r.*,l.lot_no,l.batch_no FROM warehouse_lot_reservations r LEFT JOIN warehouse_lots l ON l.id=r.lot_id WHERE r.order_id=? AND r.status='dispatched'",(d['order_id'],)).fetchall():created+=emit(c,'dispatch:'+d['id']+':'+r['id'],r['sku'],'dispatch',warehouse_id,-float(r['quantity']),r['lot_no'],r['batch_no'],'',r['location_code'],'','customer_order',d['order_no'],'system','Gate pass '+d['gate_pass'],d['created_at'])
  if has_table(c,'warehouse_transfer_lots'):
   for z in c.execute('''SELECT z.*,t.transfer_no,t.from_warehouse,t.to_warehouse FROM warehouse_transfer_lots z JOIN warehouse_transfer_orders t ON t.id=z.transfer_id WHERE t.from_warehouse=? OR t.to_warehouse=? ORDER BY z.created_at''',(warehouse_id,warehouse_id)).fetchall():
    created+=emit(c,'transfer-reserve:'+z['id'],z['sku'],'transfer_reserved',z['from_warehouse'],z['quantity'],z['lot_no'],z['batch_no'],'',z['source_location'],'','transfer',z['transfer_no'],'system','Inventory reserved for inter-warehouse transfer',z['created_at'])
    if z['shipped_at']:created+=emit(c,'transfer-ship:'+z['id'],z['sku'],'transfer_shipped',z['from_warehouse'],-float(z['quantity']),z['lot_no'],z['batch_no'],'',z['source_location'],'in_transit','transfer',z['transfer_no'],'system','Lot departed source warehouse',z['shipped_at'])
    if z['received_at']:created+=emit(c,'transfer-receive:'+z['id'],z['sku'],'transfer_received',z['to_warehouse'],z['quantity'],z['lot_no'],z['batch_no'],'','in_transit',z['destination_location'],'transfer',z['transfer_no'],'system','Lot received at destination warehouse',z['received_at'])
  if has_table(c,'warehouse_quality_hold_lots'):
   for z in c.execute('''SELECT q.*,h.hold_no,h.sku,h.warehouse_id,h.status,h.reason,l.lot_no,l.batch_no,l.location_code FROM warehouse_quality_hold_lots q JOIN warehouse_quality_holds h ON h.id=q.hold_id JOIN warehouse_lots l ON l.id=q.lot_id WHERE h.warehouse_id=? ORDER BY q.created_at''',(warehouse_id,)).fetchall():
    created+=emit(c,'quality-hold:'+z['id'],z['sku'],'quarantine_hold',warehouse_id,z['quantity'],z['lot_no'],z['batch_no'],'',z['location_code'],'QUARANTINE','quality_hold',z['hold_no'],'system',z['reason'],z['created_at'])
    if z['resolved_at']:created+=emit(c,'quality-resolve:'+z['id'],z['sku'],'quality_'+z['status'],warehouse_id,-float(z['quantity']) if z['status'] in ('destroyed','return_supplier') else z['quantity'],z['lot_no'],z['batch_no'],'','QUARANTINE',z['location_code'] if z['status']=='released' else '','quality_hold',z['hold_no'],'system','Quality hold resolved: '+z['status'],z['resolved_at'])
  if has_table(c,'warehouse_recalls'):
   for r in c.execute("SELECT * FROM warehouse_recalls WHERE status IN ('open','closed') ORDER BY created_at").fetchall():
    created+=emit(c,'recall:'+r['id'],r['sku'],'recall_opened','',0,r['lot_no'],r['batch_no'],'','','','','recall',r['recall_no'],'system',r['reason'],r['created_at'])
    if r['closed_at']:created+=emit(c,'recall-close:'+r['id'],r['sku'],'recall_closed','',0,r['lot_no'],r['batch_no'],'','','','','recall',r['recall_no'],'system','Recall closed',r['closed_at'])
  if has_table(c,'warehouse_deliveries'):
   for d in c.execute('SELECT * FROM warehouse_deliveries WHERE warehouse_id=? ORDER BY created_at',(warehouse_id,)).fetchall():
    if d['departed_at']:created+=emit(c,'delivery-depart:'+d['id'],'N/A','delivery_departed',warehouse_id,0,'','','','dock:'+str(d['dock_id'] or ''),'vehicle:'+str(d['vehicle_id'] or ''),'delivery',d['delivery_no'],'system','Gate pass '+str(d['gate_pass'] or ''),d['departed_at'])
    if d['delivered_at']:created+=emit(c,'delivery-complete:'+d['id'],'N/A','delivery_completed',warehouse_id,0,'','','','vehicle:'+str(d['vehicle_id'] or ''),'customer','delivery',d['delivery_no'],'system','Recipient '+str(d['recipient_name'] or ''),d['delivered_at'])
  c.execute('COMMIT');return {'created':created,'warehouse_id':warehouse_id,'tamper_evident':True,'sources':'operations,reservations,dispatch,transfers,quality,recalls,delivery'}
 except Exception:c.execute('ROLLBACK');raise
 finally:c.close()
