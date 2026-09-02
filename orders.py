import os,sqlite3,time,uuid
from fastapi import APIRouter,Header,HTTPException,Query
from pydantic import BaseModel,Field
from auth import require_permission
BASE_DIR=os.path.dirname(os.path.abspath(__file__));DB_PATH=os.path.join(BASE_DIR,'data_hub.db');router=APIRouter(prefix='/orders',tags=['orders'])
ORDER_STATUSES={'draft','submitted','confirmed','allocated','picking','packed','ready_to_ship','shipped','delivered','cancelled','returned'};TERMINAL_STATUSES={'delivered','cancelled','returned'}
class OrderLineIn(BaseModel):sku:str;name:str='';quantity:float=Field(gt=0);unit_price:float=Field(default=0,ge=0)
class OrderCreate(BaseModel):customer_name:str;customer_email:str='';customer_phone:str='';delivery_address:str='';delivery_grid_id:str='';warehouse_id:str='main';currency:str='UGX';notes:str='';items:list[OrderLineIn]
class OrderUpdate(BaseModel):customer_name:str|None=None;customer_email:str|None=None;customer_phone:str|None=None;delivery_address:str|None=None;delivery_grid_id:str|None=None;warehouse_id:str|None=None;notes:str|None=None
class StatusUpdate(BaseModel):status:str;note:str=''
class ShipmentLink(BaseModel):shipment_number:str
class YardHandoff(BaseModel):unit_number:str;unit_type:str='trailer';carrier:str='';plate_number:str='';shipment_number:str='';appointment_time:float|None=None;notes:str=''
def conn():c=sqlite3.connect(DB_PATH);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');return c
def init_db():
 c=conn();c.execute("CREATE TABLE IF NOT EXISTS orders (id TEXT PRIMARY KEY,order_number TEXT UNIQUE NOT NULL,customer_name TEXT NOT NULL,customer_email TEXT,customer_phone TEXT,delivery_address TEXT,delivery_grid_id TEXT,warehouse_id TEXT,currency TEXT NOT NULL DEFAULT 'UGX',subtotal REAL NOT NULL DEFAULT 0,status TEXT NOT NULL,shipment_number TEXT,notes TEXT,created_at REAL NOT NULL,updated_at REAL NOT NULL)");c.execute('CREATE TABLE IF NOT EXISTS order_items (id TEXT PRIMARY KEY,order_id TEXT NOT NULL,sku TEXT NOT NULL,name TEXT,quantity REAL NOT NULL,unit_price REAL NOT NULL DEFAULT 0,line_total REAL NOT NULL DEFAULT 0,FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE)');c.execute('CREATE TABLE IF NOT EXISTS order_history (id TEXT PRIMARY KEY,order_id TEXT NOT NULL,event TEXT NOT NULL,note TEXT,actor TEXT,created_at REAL NOT NULL,FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE)');c.commit();c.close()
init_db()
def access(code,p):require_permission(code,p)
def find(c,key):return c.execute('SELECT * FROM orders WHERE id=? OR order_number=?',(key.strip(),key.strip().upper())).fetchone()
def hist(c,oid,event,note='',actor='order-management'):c.execute('INSERT INTO order_history VALUES (?,?,?,?,?,?)',(str(uuid.uuid4()),oid,event,note[:1000],actor,time.time()))
def out(c,r):
 if not r:return None
 d=dict(r);d['items']=[dict(x) for x in c.execute('SELECT id,sku,name,quantity,unit_price,line_total FROM order_items WHERE order_id=? ORDER BY rowid',(r['id'],)).fetchall()];return d
def nextnum(c):
 prefix='UG-ORD-'+time.strftime('%Y%m%d',time.gmtime())+'-';r=c.execute('SELECT order_number FROM orders WHERE order_number LIKE ? ORDER BY order_number DESC LIMIT 1',(prefix+'%',)).fetchone();n=1
 if r:
  try:n=int(r['order_number'].split('-')[-1])+1
  except:n=1
 return f'{prefix}{n:04d}'
@router.post('')
def create(payload:OrderCreate,x_access_code:str=Header(default='')):
 access(x_access_code,'shipments:write')
 if not payload.customer_name.strip() or not payload.items:raise HTTPException(400,'Customer name and items are required')
 c=conn();oid=str(uuid.uuid4());num=nextnum(c);now=time.time();sub=sum(i.quantity*i.unit_price for i in payload.items);c.execute('INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(oid,num,payload.customer_name.strip(),payload.customer_email.strip(),payload.customer_phone.strip(),payload.delivery_address.strip(),payload.delivery_grid_id.strip().upper(),payload.warehouse_id.strip() or 'main',payload.currency.strip().upper() or 'UGX',sub,'submitted','',payload.notes.strip()[:2000],now,now))
 for i in payload.items:c.execute('INSERT INTO order_items VALUES (?,?,?,?,?,?,?)',(str(uuid.uuid4()),oid,i.sku.strip().upper(),i.name.strip(),i.quantity,i.unit_price,i.quantity*i.unit_price))
 hist(c,oid,'submitted','Order created');c.commit();d=out(c,find(c,oid));c.close();return d
@router.get('')
def listing(status:str=Query(default=''),q:str=Query(default=''),limit:int=Query(default=100,ge=1,le=500),x_access_code:str=Header(default='')):
 access(x_access_code,'shipments:read');c=conn();w=[];a=[]
 if status:w.append('status=?');a.append(status)
 if q.strip():t='%'+q.strip()+'%';w.append('(order_number LIKE ? OR customer_name LIKE ? OR delivery_grid_id LIKE ?)');a += [t,t,t]
 a.append(limit);rows=c.execute('SELECT * FROM orders'+(' WHERE '+' AND '.join(w) if w else '')+' ORDER BY created_at DESC LIMIT ?',a).fetchall();r=[out(c,x) for x in rows];c.close();return {'count':len(r),'results':r}
@router.get('/summary')
def summary(x_access_code:str=Header(default='')):
 access(x_access_code,'shipments:read');c=conn();total=c.execute('SELECT COUNT(*) n FROM orders').fetchone()['n'];value=c.execute("SELECT COALESCE(SUM(subtotal),0) v FROM orders WHERE status!='cancelled'").fetchone()['v'];rows=c.execute('SELECT status,COUNT(*) n FROM orders GROUP BY status').fetchall();c.close();return {'total_orders':total,'active_value':value,'by_status':{r['status']:r['n'] for r in rows}}
@router.get('/{order_id}')
def detail(order_id:str,x_access_code:str=Header(default='')):
 access(x_access_code,'shipments:read');c=conn();r=find(c,order_id)
 if not r:c.close();raise HTTPException(404,'Order not found')
 d=out(c,r);d['history']=[dict(x) for x in c.execute('SELECT event,note,actor,created_at FROM order_history WHERE order_id=? ORDER BY created_at',(r['id'],)).fetchall()];c.close();return d
@router.put('/{order_id}')
def update(order_id:str,payload:OrderUpdate,x_access_code:str=Header(default='')):
 access(x_access_code,'shipments:write');c=conn();r=find(c,order_id)
 if not r:c.close();raise HTTPException(404,'Order not found')
 if r['status'] in TERMINAL_STATUSES:c.close();raise HTTPException(409,'Terminal orders cannot be edited')
 d=dict(r);u=payload.model_dump(exclude_none=True) if hasattr(payload,'model_dump') else payload.dict(exclude_none=True)
 for k,v in u.items():d[k]=v.strip() if isinstance(v,str) else v
 c.execute('UPDATE orders SET customer_name=?,customer_email=?,customer_phone=?,delivery_address=?,delivery_grid_id=?,warehouse_id=?,notes=?,updated_at=? WHERE id=?',(d['customer_name'],d['customer_email'],d['customer_phone'],d['delivery_address'],(d['delivery_grid_id'] or '').upper(),d['warehouse_id'],d['notes'],time.time(),r['id']));hist(c,r['id'],'updated','Order details updated');c.commit();z=out(c,find(c,r['id']));c.close();return z
@router.post('/{order_id}/allocate')
def allocate(order_id:str,x_access_code:str=Header(default='')):
 access(x_access_code,'shipments:write');access(x_access_code,'inventory:write');c=conn();r=find(c,order_id)
 if not r:c.close();raise HTTPException(404,'Order not found')
 if r['status'] in TERMINAL_STATUSES or r['status'] in {'allocated','picking','packed','ready_to_ship','shipped'}:c.close();raise HTTPException(409,'Order cannot be allocated from its current status')
 items=c.execute('SELECT sku,quantity FROM order_items WHERE order_id=?',(r['id'],)).fetchall();wid=r['warehouse_id'] or 'main';short=[]
 for i in items:
  s=c.execute('SELECT quantity_on_hand FROM stock WHERE product_sku=? AND warehouse_id=?',(i['sku'],wid)).fetchone();av=float(s['quantity_on_hand']) if s else 0
  if av<float(i['quantity']):short.append({'sku':i['sku'],'required':i['quantity'],'available':av})
 if short:c.close();raise HTTPException(409,detail={'message':'Insufficient inventory','shortages':short})
 now=time.time()
 for i in items:c.execute('UPDATE stock SET quantity_on_hand=quantity_on_hand-? WHERE product_sku=? AND warehouse_id=?',(i['quantity'],i['sku'],wid));c.execute('INSERT INTO stock_movements VALUES (?,?,?,?,?,?,?)',(str(uuid.uuid4()),i['sku'],wid,'dispatch',i['quantity'],f"Allocated to {r['order_number']}",now))
 c.execute("UPDATE orders SET status='allocated',updated_at=? WHERE id=?",(now,r['id']));hist(c,r['id'],'allocated','Inventory allocated from warehouse');c.commit();z=out(c,find(c,r['id']));c.close();return z
def transition(order_id,target,allowed,code,note):
 access(code,'shipments:write');c=conn();r=find(c,order_id)
 if not r:c.close();raise HTTPException(404,'Order not found')
 if r['status'] not in allowed:c.close();raise HTTPException(409,f"Order must be in {sorted(allowed)} before {target}")
 c.execute('UPDATE orders SET status=?,updated_at=? WHERE id=?',(target,time.time(),r['id']));hist(c,r['id'],target,note);c.commit();z=out(c,find(c,r['id']));c.close();return z
@router.post('/{order_id}/pick')
def pick(order_id:str,x_access_code:str=Header(default='')):return transition(order_id,'picking',{'allocated'},x_access_code,'Warehouse picking started')
@router.post('/{order_id}/pack')
def pack(order_id:str,x_access_code:str=Header(default='')):return transition(order_id,'packed',{'picking'},x_access_code,'Warehouse picking completed and order packed')
@router.post('/{order_id}/ready')
def ready(order_id:str,x_access_code:str=Header(default='')):return transition(order_id,'ready_to_ship',{'packed'},x_access_code,'Packed order released to outbound staging')
@router.post('/{order_id}/yard-handoff')
def yard_handoff(order_id:str,payload:YardHandoff,x_access_code:str=Header(default='')):
 access(x_access_code,'shipments:write');c=conn();r=find(c,order_id)
 if not r:c.close();raise HTTPException(404,'Order not found')
 if r['status']!='ready_to_ship':c.close();raise HTTPException(409,'Order must be ready_to_ship before yard handoff')
 number=payload.unit_number.strip().upper()
 if not number:c.close();raise HTTPException(400,'Unit number is required')
 if c.execute('SELECT 1 FROM yard_units WHERE unit_number=?',(number,)).fetchone():c.close();raise HTTPException(409,'Yard unit already exists')
 uid=str(uuid.uuid4());now=time.time();ship=(payload.shipment_number or r['shipment_number'] or '').strip().upper();c.execute('INSERT INTO yard_units (id,unit_number,unit_type,carrier,plate_number,shipment_number,order_number,appointment_time,status,bay_id,gate_id,checked_in_at,departed_at,notes,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(uid,number,payload.unit_type.strip().lower() or 'trailer',payload.carrier.strip(),payload.plate_number.strip().upper(),ship,r['order_number'],payload.appointment_time,'expected','','',None,None,payload.notes.strip()[:2000],now,now));c.execute('INSERT INTO yard_history VALUES (?,?,?,?,?)',(str(uuid.uuid4()),uid,'expected',f"Outbound order {r['order_number']} handed to yard",now));hist(c,r['id'],'yard_handoff',number);c.commit();unit=dict(c.execute('SELECT * FROM yard_units WHERE id=?',(uid,)).fetchone());c.close();return {'order_number':r['order_number'],'yard_unit':unit}
@router.post('/{order_id}/status')
def status(order_id:str,payload:StatusUpdate,x_access_code:str=Header(default='')):
 target=payload.status.strip().lower()
 if target not in ORDER_STATUSES:raise HTTPException(400,'Invalid order status')
 if target=='allocated':return allocate(order_id,x_access_code)
 return transition(order_id,target,ORDER_STATUSES-{target},x_access_code,payload.note or f'Status changed to {target}')
@router.post('/{order_id}/cancel')
def cancel(order_id:str,x_access_code:str=Header(default='')):return status(order_id,StatusUpdate(status='cancelled',note='Order cancelled'),x_access_code)
@router.post('/{order_id}/shipment')
def shipment(order_id:str,payload:ShipmentLink,x_access_code:str=Header(default='')):
 access(x_access_code,'shipments:write');c=conn();r=find(c,order_id)
 if not r:c.close();raise HTTPException(404,'Order not found')
 ship=payload.shipment_number.strip().upper()
 if not c.execute('SELECT 1 FROM shipments WHERE shipment_number=?',(ship,)).fetchone():c.close();raise HTTPException(404,'Shipment not found')
 c.execute("UPDATE orders SET shipment_number=?,status='shipped',updated_at=? WHERE id=?",(ship,time.time(),r['id']));hist(c,r['id'],'shipment_linked',ship);c.commit();z=out(c,find(c,r['id']));c.close();return z
@router.get('/{order_id}/export')
def export(order_id:str,x_access_code:str=Header(default='')):return {'format':'json','generated_at':time.time(),'order':detail(order_id,x_access_code)}