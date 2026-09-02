import json
import os
import sqlite3
import time
import uuid
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field
from auth import require_permission
BASE_DIR=os.path.dirname(os.path.abspath(__file__));DB_PATH=os.path.join(BASE_DIR,'data_hub.db')
router=APIRouter(prefix='/orders',tags=['orders'])
ORDER_STATUSES={'draft','submitted','confirmed','allocated','picking','packed','ready_to_ship','shipped','delivered','cancelled','returned'}
TERMINAL_STATUSES={'delivered','cancelled','returned'}
class OrderLineIn(BaseModel):
 sku:str;name:str='';quantity:float=Field(gt=0);unit_price:float=Field(default=0,ge=0)
class OrderCreate(BaseModel):
 customer_name:str;customer_email:str='';customer_phone:str='';delivery_address:str='';delivery_grid_id:str='';warehouse_id:str='main';currency:str='UGX';notes:str='';items:list[OrderLineIn]
class OrderUpdate(BaseModel):
 customer_name:str|None=None;customer_email:str|None=None;customer_phone:str|None=None;delivery_address:str|None=None;delivery_grid_id:str|None=None;warehouse_id:str|None=None;notes:str|None=None
class StatusUpdate(BaseModel):status:str;note:str=''
class ShipmentLink(BaseModel):shipment_number:str
def conn():
 c=sqlite3.connect(DB_PATH);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys = ON');return c
def init_db():
 c=conn();c.execute('''CREATE TABLE IF NOT EXISTS orders (id TEXT PRIMARY KEY,order_number TEXT UNIQUE NOT NULL,customer_name TEXT NOT NULL,customer_email TEXT,customer_phone TEXT,delivery_address TEXT,delivery_grid_id TEXT,warehouse_id TEXT,currency TEXT NOT NULL DEFAULT 'UGX',subtotal REAL NOT NULL DEFAULT 0,status TEXT NOT NULL,shipment_number TEXT,notes TEXT,created_at REAL NOT NULL,updated_at REAL NOT NULL)''');c.execute('''CREATE TABLE IF NOT EXISTS order_items (id TEXT PRIMARY KEY,order_id TEXT NOT NULL,sku TEXT NOT NULL,name TEXT,quantity REAL NOT NULL,unit_price REAL NOT NULL DEFAULT 0,line_total REAL NOT NULL DEFAULT 0,FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE)''');c.execute('''CREATE TABLE IF NOT EXISTS order_history (id TEXT PRIMARY KEY,order_id TEXT NOT NULL,event TEXT NOT NULL,note TEXT,actor TEXT,created_at REAL NOT NULL,FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE)''');c.execute('CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)');c.execute('CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id)');c.commit();c.close()
init_db()
def access(code,p):require_permission(code,p)
def next_order_number(c):
 today=time.strftime('%Y%m%d',time.gmtime());prefix=f'UG-ORD-{today}-';r=c.execute('SELECT order_number FROM orders WHERE order_number LIKE ? ORDER BY order_number DESC LIMIT 1',(prefix+'%',)).fetchone();n=1
 if r:
  try:n=int(r['order_number'].split('-')[-1])+1
  except:n=1
 return f'{prefix}{n:04d}'
def history(c,oid,event,note='',actor='system'):c.execute('INSERT INTO order_history (id,order_id,event,note,actor,created_at) VALUES (?,?,?,?,?,?)',(str(uuid.uuid4()),oid,event,note[:1000],actor[:120],time.time()))
def row_order(c,row):
 if not row:return None
 d=dict(row);d['items']=[dict(x) for x in c.execute('SELECT id,sku,name,quantity,unit_price,line_total FROM order_items WHERE order_id=? ORDER BY rowid',(d['id'],)).fetchall()];return d
def find_order(c,key):return c.execute('SELECT * FROM orders WHERE id=? OR order_number=?',(key.strip(),key.strip().upper())).fetchone()
@router.post('')
def create_order(payload:OrderCreate,x_access_code:str=Header(default='')):
 access(x_access_code,'shipments:write')
 if not payload.customer_name.strip() or not payload.items:raise HTTPException(400,'Customer name and items are required')
 c=conn();oid=str(uuid.uuid4());number=next_order_number(c);now=time.time();subtotal=sum(float(i.quantity)*float(i.unit_price) for i in payload.items);c.execute('INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(oid,number,payload.customer_name.strip(),payload.customer_email.strip(),payload.customer_phone.strip(),payload.delivery_address.strip(),payload.delivery_grid_id.strip().upper(),payload.warehouse_id.strip() or 'main',payload.currency.strip().upper() or 'UGX',subtotal,'submitted','',payload.notes.strip()[:2000],now,now))
 for i in payload.items:c.execute('INSERT INTO order_items VALUES (?,?,?,?,?,?,?)',(str(uuid.uuid4()),oid,i.sku.strip().upper(),i.name.strip(),i.quantity,i.unit_price,float(i.quantity)*float(i.unit_price)))
 history(c,oid,'submitted','Order created','order-management');c.commit();out=row_order(c,find_order(c,oid));c.close();return out
@router.get('')
def list_orders(status:str=Query(default=''),q:str=Query(default=''),limit:int=Query(default=100,ge=1,le=500),x_access_code:str=Header(default='')):
 access(x_access_code,'shipments:read');c=conn();where=[];args=[]
 if status:where.append('status=?');args.append(status)
 if q.strip():term='%'+q.strip()+'%';where.append('(order_number LIKE ? OR customer_name LIKE ? OR delivery_grid_id LIKE ?)');args += [term,term,term]
 sql='SELECT * FROM orders'+(' WHERE '+' AND '.join(where) if where else '')+' ORDER BY created_at DESC LIMIT ?';args.append(limit);rows=c.execute(sql,args).fetchall();out=[row_order(c,r) for r in rows];c.close();return {'count':len(out),'results':out}
@router.get('/summary')
def summary(x_access_code:str=Header(default='')):
 access(x_access_code,'shipments:read');c=conn();total=c.execute('SELECT COUNT(*) n FROM orders').fetchone()['n'];value=c.execute("SELECT COALESCE(SUM(subtotal),0) v FROM orders WHERE status!='cancelled'").fetchone()['v'];rows=c.execute('SELECT status,COUNT(*) n FROM orders GROUP BY status').fetchall();c.close();return {'total_orders':total,'active_value':value,'by_status':{r['status']:r['n'] for r in rows}}
@router.get('/{order_id}')
def get_order(order_id:str,x_access_code:str=Header(default='')):
 access(x_access_code,'shipments:read');c=conn();r=find_order(c,order_id)
 if not r:c.close();raise HTTPException(404,'Order not found')
 out=row_order(c,r);out['history']=[dict(x) for x in c.execute('SELECT event,note,actor,created_at FROM order_history WHERE order_id=? ORDER BY created_at',(r['id'],)).fetchall()];c.close();return out
@router.put('/{order_id}')
def update_order(order_id:str,payload:OrderUpdate,x_access_code:str=Header(default='')):
 access(x_access_code,'shipments:write');c=conn();r=find_order(c,order_id)
 if not r:c.close();raise HTTPException(404,'Order not found')
 if r['status'] in TERMINAL_STATUSES:c.close();raise HTTPException(409,'Terminal orders cannot be edited')
 data=dict(r);updates=payload.model_dump(exclude_none=True) if hasattr(payload,'model_dump') else payload.dict(exclude_none=True)
 for k,v in updates.items():data[k]=v.strip() if isinstance(v,str) else v
 data['delivery_grid_id']=(data.get('delivery_grid_id') or '').upper();c.execute('UPDATE orders SET customer_name=?,customer_email=?,customer_phone=?,delivery_address=?,delivery_grid_id=?,warehouse_id=?,notes=?,updated_at=? WHERE id=?',(data['customer_name'],data['customer_email'],data['customer_phone'],data['delivery_address'],data['delivery_grid_id'],data['warehouse_id'],data['notes'],time.time(),r['id']));history(c,r['id'],'updated','Order details updated','order-management');c.commit();out=row_order(c,find_order(c,r['id']));c.close();return out
@router.post('/{order_id}/allocate')
def allocate_order(order_id:str,x_access_code:str=Header(default='')):
 access(x_access_code,'shipments:write');access(x_access_code,'inventory:write');c=conn();r=find_order(c,order_id)
 if not r:c.close();raise HTTPException(404,'Order not found')
 if r['status'] in TERMINAL_STATUSES:c.close();raise HTTPException(409,'Terminal order cannot be allocated')
 if r['status'] in {'allocated','picking','packed','ready_to_ship','shipped'}:c.close();raise HTTPException(409,'Order inventory is already allocated')
 items=c.execute('SELECT sku,quantity FROM order_items WHERE order_id=?',(r['id'],)).fetchall();wid=r['warehouse_id'] or 'main';short=[]
 for i in items:
  s=c.execute('SELECT quantity_on_hand FROM stock WHERE product_sku=? AND warehouse_id=?',(i['sku'],wid)).fetchone();available=float(s['quantity_on_hand']) if s else 0
  if available<float(i['quantity']):short.append({'sku':i['sku'],'required':i['quantity'],'available':available})
 if short:c.close();raise HTTPException(409,detail={'message':'Insufficient inventory','shortages':short})
 now=time.time()
 for i in items:
  c.execute('UPDATE stock SET quantity_on_hand=quantity_on_hand-? WHERE product_sku=? AND warehouse_id=?',(i['quantity'],i['sku'],wid));c.execute('INSERT INTO stock_movements (id,product_sku,warehouse_id,movement_type,quantity,note,created_at) VALUES (?,?,?,?,?,?,?)',(str(uuid.uuid4()),i['sku'],wid,'dispatch',i['quantity'],f"Allocated to {r['order_number']}",now))
 c.execute("UPDATE orders SET status='allocated',updated_at=? WHERE id=?",(now,r['id']));history(c,r['id'],'allocated','Inventory reserved and dispatched from warehouse','order-management');c.commit();out=row_order(c,find_order(c,r['id']));c.close();return out
@router.post('/{order_id}/status')
def set_status(order_id:str,payload:StatusUpdate,x_access_code:str=Header(default='')):
 access(x_access_code,'shipments:write');status=payload.status.strip().lower()
 if status not in ORDER_STATUSES:raise HTTPException(400,'Invalid order status')
 if status=='allocated':return allocate_order(order_id,x_access_code)
 c=conn();r=find_order(c,order_id)
 if not r:c.close();raise HTTPException(404,'Order not found')
 if r['status'] in TERMINAL_STATUSES and status!=r['status']:c.close();raise HTTPException(409,'Terminal order status cannot be changed')
 c.execute('UPDATE orders SET status=?,updated_at=? WHERE id=?',(status,time.time(),r['id']));history(c,r['id'],status,payload.note,'order-management');c.commit();out=row_order(c,find_order(c,r['id']));c.close();return out
@router.post('/{order_id}/cancel')
def cancel(order_id:str,x_access_code:str=Header(default='')):return set_status(order_id,StatusUpdate(status='cancelled',note='Order cancelled'),x_access_code)
@router.post('/{order_id}/shipment')
def link_shipment(order_id:str,payload:ShipmentLink,x_access_code:str=Header(default='')):
 access(x_access_code,'shipments:write');c=conn();r=find_order(c,order_id)
 if not r:c.close();raise HTTPException(404,'Order not found')
 ship=payload.shipment_number.strip().upper();exists=c.execute('SELECT shipment_number FROM shipments WHERE shipment_number=?',(ship,)).fetchone()
 if not exists:c.close();raise HTTPException(404,'Shipment not found')
 c.execute("UPDATE orders SET shipment_number=?,status='shipped',updated_at=? WHERE id=?",(ship,time.time(),r['id']));history(c,r['id'],'shipment_linked',ship,'order-management');c.commit();out=row_order(c,find_order(c,r['id']));c.close();return out
@router.get('/{order_id}/export')
def export(order_id:str,x_access_code:str=Header(default='')):return {'format':'json','generated_at':time.time(),'order':get_order(order_id,x_access_code)}