import os,sqlite3,time,uuid
from fastapi import APIRouter,Form,Header,HTTPException,Query
from auth import require_permission
BASE=os.path.dirname(os.path.abspath(__file__));DB=os.path.join(BASE,'data_hub.db');router=APIRouter()
def c():x=sqlite3.connect(DB);x.row_factory=sqlite3.Row;return x
def init():
 x=c();x.execute('''CREATE TABLE IF NOT EXISTS warehouse_carriers(id TEXT PRIMARY KEY,name TEXT NOT NULL,phone TEXT,email TEXT,status TEXT NOT NULL DEFAULT 'active',created_at REAL NOT NULL)''');x.execute('''CREATE TABLE IF NOT EXISTS warehouse_vehicles(id TEXT PRIMARY KEY,carrier_id TEXT,registration_no TEXT UNIQUE NOT NULL,vehicle_type TEXT,capacity REAL NOT NULL DEFAULT 0,status TEXT NOT NULL DEFAULT 'available',created_at REAL NOT NULL)''');x.execute('''CREATE TABLE IF NOT EXISTS warehouse_drivers(id TEXT PRIMARY KEY,carrier_id TEXT,name TEXT NOT NULL,phone TEXT,license_no TEXT,status TEXT NOT NULL DEFAULT 'available',created_at REAL NOT NULL)''');x.execute('''CREATE TABLE IF NOT EXISTS warehouse_docks(id TEXT PRIMARY KEY,warehouse_id TEXT NOT NULL DEFAULT 'main',dock_code TEXT NOT NULL,capacity REAL NOT NULL DEFAULT 1,status TEXT NOT NULL DEFAULT 'available',UNIQUE(warehouse_id,dock_code))''');x.execute('''CREATE TABLE IF NOT EXISTS warehouse_deliveries(id TEXT PRIMARY KEY,delivery_no TEXT UNIQUE NOT NULL,order_id TEXT,carrier_id TEXT,vehicle_id TEXT,driver_id TEXT,warehouse_id TEXT NOT NULL DEFAULT 'main',dock_id TEXT,destination TEXT,tracking_no TEXT,status TEXT NOT NULL DEFAULT 'planned',gate_pass TEXT,loaded_at REAL,departed_at REAL,delivered_at REAL,recipient_name TEXT,proof_note TEXT,created_at REAL NOT NULL,updated_at REAL NOT NULL)''');x.execute('''CREATE TABLE IF NOT EXISTS warehouse_delivery_events(id TEXT PRIMARY KEY,delivery_id TEXT NOT NULL,event_type TEXT NOT NULL,note TEXT,created_at REAL NOT NULL)''');x.commit();x.close()
init()
def auth(k,p):require_permission(k,p)
def num(p):return f'{p}-{time.strftime("%Y%m%d")}-{uuid.uuid4().hex[:6].upper()}'
@router.post('/warehouse/delivery/carriers')
def carrier(name:str=Form(...),phone:str=Form(''),email:str=Form(''),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');x=c();i=str(uuid.uuid4());x.execute('INSERT INTO warehouse_carriers VALUES(?,?,?,?,?,?)',(i,name,phone,email,'active',time.time()));x.commit();r=dict(x.execute('SELECT * FROM warehouse_carriers WHERE id=?',(i,)).fetchone());x.close();return r
@router.post('/warehouse/delivery/vehicles')
def vehicle(registration_no:str=Form(...),carrier_id:str=Form(''),vehicle_type:str=Form('truck'),capacity:float=Form(0),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');x=c();i=str(uuid.uuid4())
 try:x.execute('INSERT INTO warehouse_vehicles VALUES(?,?,?,?,?,?,?)',(i,carrier_id,registration_no.upper(),vehicle_type,capacity,'available',time.time()));x.commit()
 except sqlite3.IntegrityError:x.close();raise HTTPException(409,'Vehicle registration already exists')
 r=dict(x.execute('SELECT * FROM warehouse_vehicles WHERE id=?',(i,)).fetchone());x.close();return r
@router.post('/warehouse/delivery/drivers')
def driver(name:str=Form(...),phone:str=Form(''),license_no:str=Form(''),carrier_id:str=Form(''),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');x=c();i=str(uuid.uuid4());x.execute('INSERT INTO warehouse_drivers VALUES(?,?,?,?,?,?,?)',(i,carrier_id,name,phone,license_no,'available',time.time()));x.commit();r=dict(x.execute('SELECT * FROM warehouse_drivers WHERE id=?',(i,)).fetchone());x.close();return r
@router.post('/warehouse/delivery/docks')
def dock(dock_code:str=Form(...),warehouse_id:str=Form('main'),capacity:float=Form(1),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');x=c();i=str(uuid.uuid4())
 try:x.execute('INSERT INTO warehouse_docks VALUES(?,?,?,?,?)',(i,warehouse_id,dock_code.upper(),capacity,'available'));x.commit()
 except sqlite3.IntegrityError:x.close();raise HTTPException(409,'Dock already exists')
 r=dict(x.execute('SELECT * FROM warehouse_docks WHERE id=?',(i,)).fetchone());x.close();return r
@router.get('/warehouse/delivery/resources')
def resources(warehouse_id:str=Query('main'),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:read');x=c();out={'carriers':[dict(r) for r in x.execute("SELECT * FROM warehouse_carriers WHERE status='active' ORDER BY name")],'vehicles':[dict(r) for r in x.execute("SELECT * FROM warehouse_vehicles WHERE status='available' ORDER BY registration_no")],'drivers':[dict(r) for r in x.execute("SELECT * FROM warehouse_drivers WHERE status='available' ORDER BY name")],'docks':[dict(r) for r in x.execute("SELECT * FROM warehouse_docks WHERE warehouse_id=? ORDER BY dock_code",(warehouse_id,))]};x.close();return out
@router.post('/warehouse/deliveries')
def plan(order_id:str=Form(...),carrier_id:str=Form(''),vehicle_id:str=Form(''),driver_id:str=Form(''),warehouse_id:str=Form('main'),dock_id:str=Form(''),destination:str=Form(''),tracking_no:str=Form(''),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');x=c();o=x.execute('SELECT * FROM warehouse_customer_orders WHERE id=?',(order_id,)).fetchone()
 if not o:x.close();raise HTTPException(404,'Customer order not found')
 if o['status'] not in ('packed','dispatched'):x.close();raise HTTPException(400,'Order must be packed before delivery planning')
 i=str(uuid.uuid4());now=time.time();dn=num('DEL');track=tracking_no or num('TRK');x.execute('INSERT INTO warehouse_deliveries(id,delivery_no,order_id,carrier_id,vehicle_id,driver_id,warehouse_id,dock_id,destination,tracking_no,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(i,dn,order_id,carrier_id,vehicle_id,driver_id,warehouse_id,dock_id,destination or o['delivery_address'],track,'planned',now,now));x.execute('INSERT INTO warehouse_delivery_events VALUES(?,?,?,?,?)',(str(uuid.uuid4()),i,'planned','Delivery planned',now));x.commit();r=dict(x.execute('SELECT * FROM warehouse_deliveries WHERE id=?',(i,)).fetchone());x.close();return r
@router.post('/warehouse/deliveries/{delivery_id}/status')
def status(delivery_id:str,status:str=Form(...),note:str=Form(''),recipient_name:str=Form(''),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');allowed={'loading','loaded','departed','in_transit','delivered','failed','returned'}
 if status not in allowed:raise HTTPException(400,'Invalid delivery status')
 x=c();d=x.execute('SELECT * FROM warehouse_deliveries WHERE id=?',(delivery_id,)).fetchone()
 if not d:x.close();raise HTTPException(404,'Delivery not found')
 now=time.time();sets=['status=?','updated_at=?'];vals=[status,now]
 if status=='loaded':sets+=['loaded_at=?','gate_pass=?'];vals += [now,d['gate_pass'] or num('GATE')]
 if status=='departed':sets+=['departed_at=?'];vals += [now]
 if status=='delivered':sets+=['delivered_at=?','recipient_name=?','proof_note=?'];vals += [now,recipient_name,note]
 vals.append(delivery_id);x.execute('UPDATE warehouse_deliveries SET '+','.join(sets)+' WHERE id=?',vals);x.execute('INSERT INTO warehouse_delivery_events VALUES(?,?,?,?,?)',(str(uuid.uuid4()),delivery_id,status,note,now));x.commit();r=dict(x.execute('SELECT * FROM warehouse_deliveries WHERE id=?',(delivery_id,)).fetchone());x.close();return r
@router.get('/warehouse/deliveries')
def deliveries(status:str=Query(''),warehouse_id:str=Query('main'),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:read');x=c();q='''SELECT d.*,o.order_no,o.customer_name,v.registration_no,dr.name driver_name,ca.name carrier_name,dk.dock_code FROM warehouse_deliveries d LEFT JOIN warehouse_customer_orders o ON o.id=d.order_id LEFT JOIN warehouse_vehicles v ON v.id=d.vehicle_id LEFT JOIN warehouse_drivers dr ON dr.id=d.driver_id LEFT JOIN warehouse_carriers ca ON ca.id=d.carrier_id LEFT JOIN warehouse_docks dk ON dk.id=d.dock_id WHERE d.warehouse_id=?''';a=[warehouse_id]
 if status:q+=' AND d.status=?';a.append(status)
 q+=' ORDER BY d.created_at DESC';rows=[dict(r) for r in x.execute(q,a).fetchall()];x.close();return {'count':len(rows),'results':rows}
@router.get('/warehouse/deliveries/{delivery_id}/events')
def events(delivery_id:str,x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:read');x=c();r=[dict(z) for z in x.execute('SELECT * FROM warehouse_delivery_events WHERE delivery_id=? ORDER BY created_at',(delivery_id,)).fetchall()];x.close();return {'results':r}
