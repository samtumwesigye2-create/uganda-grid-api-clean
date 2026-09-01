import os,sqlite3,time,uuid,json
from fastapi import APIRouter,Form,Header,HTTPException,Query
from auth import require_permission
BASE=os.path.dirname(os.path.abspath(__file__));DB=os.path.join(BASE,'data_hub.db');router=APIRouter()
def conn():c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;return c
def init():
 c=conn();c.execute('''CREATE TABLE IF NOT EXISTS warehouse_customer_orders(id TEXT PRIMARY KEY,order_no TEXT UNIQUE NOT NULL,customer_name TEXT NOT NULL,customer_phone TEXT,delivery_address TEXT,warehouse_id TEXT NOT NULL DEFAULT 'main',priority INTEGER NOT NULL DEFAULT 100,status TEXT NOT NULL DEFAULT 'open',created_at REAL NOT NULL,updated_at REAL NOT NULL)''');c.execute('''CREATE TABLE IF NOT EXISTS warehouse_order_lines(id TEXT PRIMARY KEY,order_id TEXT NOT NULL,sku TEXT NOT NULL,quantity REAL NOT NULL,reserved_qty REAL NOT NULL DEFAULT 0,picked_qty REAL NOT NULL DEFAULT 0,packed_qty REAL NOT NULL DEFAULT 0,dispatched_qty REAL NOT NULL DEFAULT 0,status TEXT NOT NULL DEFAULT 'open')''');c.execute('''CREATE TABLE IF NOT EXISTS warehouse_pick_waves(id TEXT PRIMARY KEY,wave_no TEXT UNIQUE NOT NULL,warehouse_id TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'open',strategy TEXT NOT NULL DEFAULT 'fefo',created_at REAL NOT NULL,completed_at REAL)''');c.execute('''CREATE TABLE IF NOT EXISTS warehouse_wave_lines(id TEXT PRIMARY KEY,wave_id TEXT NOT NULL,order_id TEXT NOT NULL,order_line_id TEXT NOT NULL,sku TEXT NOT NULL,quantity REAL NOT NULL,location_code TEXT,lot_no TEXT,batch_no TEXT,expiry_date TEXT,status TEXT NOT NULL DEFAULT 'allocated')''');c.execute('CREATE INDEX IF NOT EXISTS idx_order_status ON warehouse_customer_orders(warehouse_id,status,priority)');c.commit();c.close()
init()
def auth(code,p):require_permission(code,p)
def no(prefix):return f'{prefix}-{time.strftime("%Y%m%d")}-{uuid.uuid4().hex[:6].upper()}'
def available(c,sku,w):
 s=c.execute('SELECT quantity_on_hand FROM stock WHERE product_sku=? AND warehouse_id=?',(sku,w)).fetchone();on=float(s['quantity_on_hand']) if s else 0;r=c.execute("SELECT COALESCE(SUM(l.reserved_qty-l.picked_qty),0) q FROM warehouse_order_lines l JOIN warehouse_customer_orders o ON o.id=l.order_id WHERE l.sku=? AND o.warehouse_id=? AND o.status NOT IN ('cancelled','dispatched')",(sku,w)).fetchone();return max(0,on-float(r['q'] or 0))
@router.post('/warehouse/outbound/orders')
def create_order(customer_name:str=Form(...),customer_phone:str=Form(''),delivery_address:str=Form(''),warehouse_id:str=Form('main'),priority:int=Form(100),lines_json:str=Form('[]'),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write')
 try:lines=json.loads(lines_json)
 except:raise HTTPException(400,'Invalid order lines')
 if not lines:raise HTTPException(400,'Order requires at least one line')
 c=conn();oid=str(uuid.uuid4());now=time.time();order_no=no('ORD');c.execute('INSERT INTO warehouse_customer_orders VALUES(?,?,?,?,?,?,?,?,?,?)',(oid,order_no,customer_name,customer_phone,delivery_address,warehouse_id,priority,'open',now,now))
 for x in lines:
  sku=str(x.get('sku','')).strip();q=float(x.get('quantity',0));
  if not sku or q<=0:c.rollback();c.close();raise HTTPException(400,'Every line requires SKU and quantity')
  c.execute('INSERT INTO warehouse_order_lines(id,order_id,sku,quantity,status) VALUES(?,?,?,?,?)',(str(uuid.uuid4()),oid,sku,q,'open'))
 c.commit();out=dict(c.execute('SELECT * FROM warehouse_customer_orders WHERE id=?',(oid,)).fetchone());c.close();return out
@router.get('/warehouse/outbound/orders')
def orders(status:str=Query(''),warehouse_id:str=Query('main'),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:read');c=conn();q='SELECT * FROM warehouse_customer_orders WHERE warehouse_id=?';a=[warehouse_id]
 if status:q+=' AND status=?';a.append(status)
 q+=' ORDER BY priority,created_at';rows=[dict(r) for r in c.execute(q,a).fetchall()]
 for o in rows:o['lines']=[dict(x) for x in c.execute('SELECT * FROM warehouse_order_lines WHERE order_id=?',(o['id'],)).fetchall()]
 c.close();return {'count':len(rows),'results':rows}
@router.post('/warehouse/outbound/orders/{order_id}/reserve')
def reserve(order_id:str,x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');c=conn();o=c.execute('SELECT * FROM warehouse_customer_orders WHERE id=?',(order_id,)).fetchone()
 if not o:c.close();raise HTTPException(404,'Order not found')
 shortages=[]
 for l in c.execute('SELECT * FROM warehouse_order_lines WHERE order_id=?',(order_id,)).fetchall():
  need=float(l['quantity'])-float(l['reserved_qty']);take=min(need,available(c,l['sku'],o['warehouse_id']))
  if take>0:c.execute('UPDATE warehouse_order_lines SET reserved_qty=reserved_qty+?,status=? WHERE id=?',(take,'reserved' if take>=need else 'partial',l['id']))
  if take<need:shortages.append({'sku':l['sku'],'short':need-take})
 c.execute('UPDATE warehouse_customer_orders SET status=?,updated_at=? WHERE id=?',('reserved' if not shortages else 'partial',time.time(),order_id));c.commit();c.close();return {'order_id':order_id,'reserved':not shortages,'shortages':shortages}
@router.post('/warehouse/outbound/waves')
def create_wave(warehouse_id:str=Form('main'),strategy:str=Form('fefo'),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');c=conn();orders=c.execute("SELECT * FROM warehouse_customer_orders WHERE warehouse_id=? AND status IN ('reserved','partial') ORDER BY priority,created_at",(warehouse_id,)).fetchall()
 if not orders:c.close();raise HTTPException(400,'No reserved orders available for a pick wave')
 wid=str(uuid.uuid4());wn=no('WAVE');c.execute('INSERT INTO warehouse_pick_waves(id,wave_no,warehouse_id,status,strategy,created_at) VALUES(?,?,?,?,?,?)',(wid,wn,warehouse_id,'open',strategy,time.time()))
 for o in orders:
  for l in c.execute('SELECT * FROM warehouse_order_lines WHERE order_id=? AND reserved_qty>picked_qty',(o['id'],)).fetchall():
   need=float(l['reserved_qty'])-float(l['picked_qty']);order="CASE WHEN expiry_date IS NULL OR expiry_date='' THEN 1 ELSE 0 END,expiry_date,received_at" if strategy=='fefo' else 'received_at';lots=c.execute(f"SELECT * FROM warehouse_lots WHERE sku=? AND warehouse_id=? AND status='available' AND quantity_available>0 ORDER BY {order}",(l['sku'],warehouse_id)).fetchall()
   for lot in lots:
    if need<=0:break
    take=min(need,float(lot['quantity_available']));c.execute('INSERT INTO warehouse_wave_lines VALUES(?,?,?,?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),wid,o['id'],l['id'],l['sku'],take,lot['location_code'],lot['lot_no'],lot['batch_no'],lot['expiry_date'],'allocated'));need-=take
 c.commit();lines=[dict(x) for x in c.execute('SELECT * FROM warehouse_wave_lines WHERE wave_id=? ORDER BY location_code,sku',(wid,)).fetchall()];c.close();return {'id':wid,'wave_no':wn,'strategy':strategy.upper(),'lines':lines}
@router.get('/warehouse/outbound/waves')
def waves(x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:read');c=conn();rows=[dict(r) for r in c.execute('SELECT * FROM warehouse_pick_waves ORDER BY created_at DESC LIMIT 50').fetchall()]
 for w in rows:w['lines']=[dict(x) for x in c.execute('SELECT * FROM warehouse_wave_lines WHERE wave_id=? ORDER BY location_code',(w['id'],)).fetchall()]
 c.close();return {'results':rows}
@router.post('/warehouse/outbound/waves/{wave_id}/complete')
def complete_wave(wave_id:str,x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');c=conn();lines=c.execute("SELECT * FROM warehouse_wave_lines WHERE wave_id=? AND status='allocated'",(wave_id,)).fetchall()
 if not lines:c.close();raise HTTPException(404,'Open wave not found or already completed')
 for x in lines:c.execute('UPDATE warehouse_order_lines SET picked_qty=picked_qty+?,status=\'picked\' WHERE id=?',(x['quantity'],x['order_line_id']));c.execute('UPDATE warehouse_wave_lines SET status=\'picked\' WHERE id=?',(x['id'],))
 ids={x['order_id'] for x in lines}
 for oid in ids:c.execute("UPDATE warehouse_customer_orders SET status='picked',updated_at=? WHERE id=?",(time.time(),oid))
 c.execute("UPDATE warehouse_pick_waves SET status='completed',completed_at=? WHERE id=?",(time.time(),wave_id));c.commit();c.close();return {'wave_id':wave_id,'status':'completed','picked_lines':len(lines)}
@router.post('/warehouse/outbound/orders/{order_id}/pack')
def pack(order_id:str,x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');c=conn();ls=c.execute('SELECT * FROM warehouse_order_lines WHERE order_id=?',(order_id,)).fetchall()
 if not ls:c.close();raise HTTPException(404,'Order not found')
 for l in ls:c.execute('UPDATE warehouse_order_lines SET packed_qty=picked_qty,status=\'packed\' WHERE id=?',(l['id'],))
 c.execute("UPDATE warehouse_customer_orders SET status='packed',updated_at=? WHERE id=?",(time.time(),order_id));c.commit();c.close();return {'order_id':order_id,'status':'packed'}
@router.post('/warehouse/outbound/orders/{order_id}/dispatch')
def dispatch_order(order_id:str,x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');c=conn();o=c.execute('SELECT * FROM warehouse_customer_orders WHERE id=?',(order_id,)).fetchone()
 if not o:c.close();raise HTTPException(404,'Order not found')
 if o['status']!='packed':c.close();raise HTTPException(400,'Order must be packed before dispatch')
 ls=c.execute('SELECT * FROM warehouse_order_lines WHERE order_id=?',(order_id,)).fetchall()
 for l in ls:
  q=float(l['packed_qty']);s=c.execute('SELECT quantity_on_hand FROM stock WHERE product_sku=? AND warehouse_id=?',(l['sku'],o['warehouse_id'])).fetchone();on=float(s['quantity_on_hand']) if s else 0
  if on<q:c.rollback();c.close();raise HTTPException(400,f'Insufficient stock for {l["sku"]}')
  c.execute('UPDATE stock SET quantity_on_hand=quantity_on_hand-? WHERE product_sku=? AND warehouse_id=?',(q,l['sku'],o['warehouse_id']));c.execute('UPDATE warehouse_order_lines SET dispatched_qty=?,status=\'dispatched\' WHERE id=?',(q,l['id']))
 c.execute("UPDATE warehouse_customer_orders SET status='dispatched',updated_at=? WHERE id=?",(time.time(),order_id));c.commit();c.close();return {'order_no':o['order_no'],'status':'dispatched','gate_pass':no('GATE')}
