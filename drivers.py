"""UGAMAP fleet, driver and transport dispatch management."""
import os,sqlite3,time,uuid
from fastapi import APIRouter,Form,Header,HTTPException,Query,UploadFile,File
BASE_DIR=os.path.dirname(os.path.abspath(__file__));DB_PATH=os.path.join(BASE_DIR,'data_hub.db');ADMIN_PASSCODE=os.environ.get('ADMIN_PASSCODE','uganda2026');UPLOADS_DIR=os.path.join(BASE_DIR,'uploads');os.makedirs(UPLOADS_DIR,exist_ok=True)
ALLOWED_PHOTO_TYPES={'image/jpeg','image/png','image/webp'};MAX_PHOTO_BYTES=15*1024*1024;router=APIRouter();TASK_STATUSES=['assigned','en_route_pickup','arrived_pickup','picked_up','en_route_dropoff','arrived_dropoff','dropped_off_customer','dropped_off_warehouse','completed','failed','cancelled'];PHOTO_REQUIRED_STATUSES={'picked_up','dropped_off_customer','dropped_off_warehouse'};DRIVER_STATUSES=['available','on_duty','off_duty'];VEHICLE_STATUSES=['available','in_use','maintenance']
def get_conn():c=sqlite3.connect(DB_PATH);c.row_factory=sqlite3.Row;return c
def init_db():
 c=get_conn();c.execute('CREATE TABLE IF NOT EXISTS vehicles (id TEXT PRIMARY KEY,plate_number TEXT UNIQUE NOT NULL,vehicle_type TEXT NOT NULL,capacity_kg REAL DEFAULT 0,status TEXT NOT NULL DEFAULT "available",created_at REAL NOT NULL)');c.execute('CREATE TABLE IF NOT EXISTS drivers (id TEXT PRIMARY KEY,name TEXT NOT NULL,phone TEXT,passcode TEXT UNIQUE NOT NULL,vehicle_id TEXT,status TEXT NOT NULL DEFAULT "off_duty",current_lat REAL,current_lon REAL,last_ping_at REAL,is_active INTEGER NOT NULL DEFAULT 1,created_at REAL NOT NULL)');c.execute('CREATE TABLE IF NOT EXISTS dispatch_tasks (id TEXT PRIMARY KEY,task_number TEXT UNIQUE NOT NULL,shipment_number TEXT,task_type TEXT NOT NULL,location_text TEXT NOT NULL,latitude REAL,longitude REAL,driver_id TEXT,vehicle_id TEXT,status TEXT NOT NULL DEFAULT "assigned",photo_url TEXT,notes TEXT,scheduled_at REAL,created_at REAL NOT NULL,completed_at REAL)');c.execute('CREATE TABLE IF NOT EXISTS dispatch_task_counter (id INTEGER PRIMARY KEY CHECK(id=1),next_number INTEGER NOT NULL)');c.execute('INSERT OR IGNORE INTO dispatch_task_counter VALUES (1,1)');c.execute('CREATE TABLE IF NOT EXISTS driver_location_pings (id TEXT PRIMARY KEY,driver_id TEXT NOT NULL,latitude REAL NOT NULL,longitude REAL NOT NULL,created_at REAL NOT NULL)');c.execute('CREATE TABLE IF NOT EXISTS dispatch_task_history (id TEXT PRIMARY KEY,task_id TEXT NOT NULL,status TEXT NOT NULL,note TEXT,photo_url TEXT,created_at REAL NOT NULL)');c.commit();c.close()
init_db()
def check_admin(code):
 if code!=ADMIN_PASSCODE:raise HTTPException(401,'Invalid passcode')
def driver_by_code(code):
 if not code:return None
 c=get_conn();r=c.execute('SELECT * FROM drivers WHERE passcode=? AND is_active=1',(code,)).fetchone();c.close();return r
def require_driver(code):
 r=driver_by_code(code)
 if not r:raise HTTPException(401,'Invalid driver passcode')
 return r
def next_task():
 c=get_conn();n=c.execute('SELECT next_number FROM dispatch_task_counter WHERE id=1').fetchone()['next_number'];c.execute('UPDATE dispatch_task_counter SET next_number=? WHERE id=1',(n+1,));c.commit();c.close();return f'UG-TASK-{n:06d}'
def log(c,tid,status,note='',photo=None):c.execute('INSERT INTO dispatch_task_history VALUES (?,?,?,?,?,?)',(str(uuid.uuid4()),tid,status,note,photo,time.time()))
@router.post('/fleet/vehicles')
def create_vehicle(plate_number:str=Form(...),vehicle_type:str=Form(...),capacity_kg:float=Form(0),x_admin_passcode:str=Header(default='')):
 check_admin(x_admin_passcode);c=get_conn()
 if c.execute('SELECT 1 FROM vehicles WHERE plate_number=?',(plate_number,)).fetchone():c.close();raise HTTPException(400,'A vehicle with this plate number already exists')
 vid=str(uuid.uuid4());c.execute('INSERT INTO vehicles VALUES (?,?,?,?,?,?)',(vid,plate_number,vehicle_type,capacity_kg,'available',time.time()));c.commit();c.close();return {'id':vid,'plate_number':plate_number,'vehicle_type':vehicle_type}
@router.get('/fleet/vehicles')
def vehicles(x_admin_passcode:str=Header(default='')):check_admin(x_admin_passcode);c=get_conn();r=c.execute('SELECT * FROM vehicles ORDER BY created_at DESC').fetchall();c.close();return {'count':len(r),'results':[dict(x) for x in r]}
@router.put('/fleet/vehicles/{vehicle_id}')
def vehicle_update(vehicle_id:str,plate_number:str=Form(None),vehicle_type:str=Form(None),capacity_kg:float=Form(None),status:str=Form(None),x_admin_passcode:str=Header(default='')):
 check_admin(x_admin_passcode);c=get_conn();r=c.execute('SELECT * FROM vehicles WHERE id=?',(vehicle_id,)).fetchone()
 if not r:c.close();raise HTTPException(404,'Vehicle not found')
 if status is not None and status not in VEHICLE_STATUSES:c.close();raise HTTPException(400,'Invalid status')
 c.execute('UPDATE vehicles SET plate_number=?,vehicle_type=?,capacity_kg=?,status=? WHERE id=?',(plate_number if plate_number is not None else r['plate_number'],vehicle_type if vehicle_type is not None else r['vehicle_type'],capacity_kg if capacity_kg is not None else r['capacity_kg'],status if status is not None else r['status'],vehicle_id));c.commit();c.close();return {'id':vehicle_id,'updated':True}
@router.delete('/fleet/vehicles/{vehicle_id}')
def vehicle_delete(vehicle_id:str,x_admin_passcode:str=Header(default='')):check_admin(x_admin_passcode);c=get_conn();r=c.execute('DELETE FROM vehicles WHERE id=?',(vehicle_id,));c.commit();c.close();return {'id':vehicle_id,'deleted':bool(r.rowcount)}
@router.post('/fleet/drivers')
def create_driver(name:str=Form(...),phone:str=Form(''),passcode:str=Form(...),vehicle_id:str=Form(''),x_admin_passcode:str=Header(default='')):
 check_admin(x_admin_passcode);c=get_conn()
 if c.execute('SELECT 1 FROM drivers WHERE passcode=?',(passcode,)).fetchone():c.close();raise HTTPException(400,'That passcode is already in use')
 did=str(uuid.uuid4());c.execute('INSERT INTO drivers (id,name,phone,passcode,vehicle_id,status,is_active,created_at) VALUES (?,?,?,?,?,?,?,?)',(did,name,phone,passcode,vehicle_id or None,'off_duty',1,time.time()));c.commit();c.close();return {'id':did,'name':name}
@router.get('/fleet/drivers')
def drivers(x_admin_passcode:str=Header(default='')):check_admin(x_admin_passcode);c=get_conn();r=c.execute('SELECT * FROM drivers ORDER BY created_at DESC').fetchall();c.close();return {'count':len(r),'results':[dict(x) for x in r]}
@router.put('/fleet/drivers/{driver_id}')
def driver_update(driver_id:str,name:str=Form(None),phone:str=Form(None),vehicle_id:str=Form(None),is_active:bool=Form(None),x_admin_passcode:str=Header(default='')):
 check_admin(x_admin_passcode);c=get_conn();r=c.execute('SELECT * FROM drivers WHERE id=?',(driver_id,)).fetchone()
 if not r:c.close();raise HTTPException(404,'Driver not found')
 c.execute('UPDATE drivers SET name=?,phone=?,vehicle_id=?,is_active=? WHERE id=?',(name if name is not None else r['name'],phone if phone is not None else r['phone'],vehicle_id if vehicle_id is not None else r['vehicle_id'],int(is_active) if is_active is not None else r['is_active'],driver_id));c.commit();c.close();return {'id':driver_id,'updated':True}
@router.delete('/fleet/drivers/{driver_id}')
def driver_delete(driver_id:str,x_admin_passcode:str=Header(default='')):check_admin(x_admin_passcode);c=get_conn();r=c.execute('DELETE FROM drivers WHERE id=?',(driver_id,));c.commit();c.close();return {'id':driver_id,'deleted':bool(r.rowcount)}
@router.get('/driver/me')
def me(x_driver_passcode:str=Header(default='')):return dict(require_driver(x_driver_passcode))
@router.post('/driver/location')
def location(latitude:float=Form(...),longitude:float=Form(...),x_driver_passcode:str=Header(default='')):
 d=require_driver(x_driver_passcode);c=get_conn();now=time.time();c.execute('UPDATE drivers SET current_lat=?,current_lon=?,last_ping_at=? WHERE id=?',(latitude,longitude,now,d['id']));c.execute('INSERT INTO driver_location_pings VALUES (?,?,?,?,?)',(str(uuid.uuid4()),d['id'],latitude,longitude,now));c.commit();c.close();return {'status':'ok'}
@router.post('/driver/status')
def driver_status(status:str=Form(...),x_driver_passcode:str=Header(default='')):
 d=require_driver(x_driver_passcode)
 if status not in DRIVER_STATUSES:raise HTTPException(400,'Invalid status')
 c=get_conn();c.execute('UPDATE drivers SET status=? WHERE id=?',(status,d['id']));c.commit();c.close();return {'status':status}
@router.get('/driver/tasks')
def my_tasks(x_driver_passcode:str=Header(default='')):
 d=require_driver(x_driver_passcode);c=get_conn();r=c.execute("SELECT * FROM dispatch_tasks WHERE driver_id=? AND status NOT IN ('completed','cancelled') ORDER BY created_at",(d['id'],)).fetchall();c.close();return {'count':len(r),'results':[dict(x) for x in r]}
@router.post('/dispatch/tasks')
def create_dispatch(task_type:str=Form(...),location_text:str=Form(...),latitude:float=Form(None),longitude:float=Form(None),shipment_number:str=Form(''),driver_id:str=Form(''),vehicle_id:str=Form(''),notes:str=Form(''),scheduled_at:float=Form(None),x_admin_passcode:str=Header(default='')):
 check_admin(x_admin_passcode)
 if task_type not in ('pickup','dropoff_customer','dropoff_warehouse','warehouse_transfer'):raise HTTPException(400,'Invalid task_type')
 tid=str(uuid.uuid4());num=next_task();c=get_conn();c.execute('INSERT INTO dispatch_tasks (id,task_number,shipment_number,task_type,location_text,latitude,longitude,driver_id,vehicle_id,status,notes,scheduled_at,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',(tid,num,shipment_number or None,task_type,location_text,latitude,longitude,driver_id or None,vehicle_id or None,'assigned',notes,scheduled_at,time.time()));log(c,tid,'assigned','Task created');c.commit();c.close();return {'id':tid,'task_number':num,'status':'assigned'}
@router.get('/dispatch/tasks')
def tasks(status:str=Query(default=''),driver_id:str=Query(default=''),x_admin_passcode:str=Header(default='')):
 check_admin(x_admin_passcode);c=get_conn();q='SELECT * FROM dispatch_tasks WHERE 1=1';a=[]
 if status:q+=' AND status=?';a.append(status)
 if driver_id:q+=' AND driver_id=?';a.append(driver_id)
 r=c.execute(q+' ORDER BY created_at DESC',a).fetchall();c.close();return {'count':len(r),'results':[dict(x) for x in r]}
@router.put('/dispatch/tasks/{task_id}/assign')
def assign(task_id:str,driver_id:str=Form(''),vehicle_id:str=Form(''),x_admin_passcode:str=Header(default='')):
 check_admin(x_admin_passcode);c=get_conn();r=c.execute('SELECT * FROM dispatch_tasks WHERE id=?',(task_id,)).fetchone()
 if not r:c.close();raise HTTPException(404,'Task not found')
 c.execute('UPDATE dispatch_tasks SET driver_id=?,vehicle_id=? WHERE id=?',(driver_id or None,vehicle_id or None,task_id));log(c,task_id,r['status'],'Reassigned');c.commit();c.close();return {'id':task_id,'reassigned':True}
@router.post('/dispatch/tasks/{task_id}/status')
async def task_status(task_id:str,status:str=Form(...),note:str=Form(''),photo:UploadFile=File(None),x_driver_passcode:str=Header(default=''),x_admin_passcode:str=Header(default='')):
 driver=None
 if x_admin_passcode!=ADMIN_PASSCODE:driver=require_driver(x_driver_passcode)
 if status not in TASK_STATUSES:raise HTTPException(400,'Invalid status')
 if status in PHOTO_REQUIRED_STATUSES and (photo is None or not photo.filename):raise HTTPException(400,f"A photo is required to mark this task as '{status.replace('_',' ')}'")
 c=get_conn();r=c.execute('SELECT * FROM dispatch_tasks WHERE id=?',(task_id,)).fetchone()
 if not r:c.close();raise HTTPException(404,'Task not found')
 if driver and r['driver_id']!=driver['id']:c.close();raise HTTPException(403,'This task is not assigned to you')
 photo_url=None
 if photo is not None and photo.filename:
  if photo.content_type not in ALLOWED_PHOTO_TYPES:c.close();raise HTTPException(400,'Unsupported photo type')
  data=await photo.read()
  if len(data)>MAX_PHOTO_BYTES:c.close();raise HTTPException(400,'Photo too large (max 15MB)')
  fn=str(uuid.uuid4())+os.path.splitext(photo.filename)[1][:10];open(os.path.join(UPLOADS_DIR,fn),'wb').write(data);photo_url='/uploads/'+fn
 completed=status in ('completed','dropped_off_customer','dropped_off_warehouse');now=time.time();c.execute('UPDATE dispatch_tasks SET status=?,photo_url=COALESCE(?,photo_url),completed_at=? WHERE id=?',(status,photo_url,now if completed else r['completed_at'],task_id));log(c,task_id,status,note,photo_url)
 synchronized={}
 if completed:
  if r['vehicle_id']:c.execute("UPDATE vehicles SET status='available' WHERE id=? AND status!='maintenance'",(r['vehicle_id'],));synchronized['vehicle']='available'
  if r['driver_id']:c.execute("UPDATE drivers SET status='available' WHERE id=? AND is_active=1",(r['driver_id'],));synchronized['driver']='available'
  order=None
  if r['shipment_number']:order=c.execute('SELECT * FROM orders WHERE shipment_number=? ORDER BY updated_at DESC LIMIT 1',(r['shipment_number'],)).fetchone()
  if not order:
   y=c.execute('SELECT order_number FROM yard_units WHERE shipment_number=? ORDER BY updated_at DESC LIMIT 1',(r['shipment_number'],)).fetchone() if r['shipment_number'] else None
   if y and y['order_number']:order=c.execute('SELECT * FROM orders WHERE order_number=?',(y['order_number'],)).fetchone()
  if not order:
   y=c.execute("SELECT order_number FROM yard_units WHERE status='departed' AND notes LIKE ? ORDER BY updated_at DESC LIMIT 1",('%'+str(r['task_number'])+'%',)).fetchone()
   if y and y['order_number']:order=c.execute('SELECT * FROM orders WHERE order_number=?',(y['order_number'],)).fetchone()
  if order and status=='dropped_off_customer':
   c.execute("UPDATE orders SET status='delivered',updated_at=? WHERE id=?",(now,order['id']));c.execute('INSERT INTO order_history VALUES (?,?,?,?,?,?)',(str(uuid.uuid4()),order['id'],'delivered',f"Transport {r['task_number']} completed",'transport-management',now));synchronized['order']=order['order_number'];synchronized['order_status']='delivered'
  if r['shipment_number']:
   try:c.execute("UPDATE shipments SET delivery_status='delivered' WHERE shipment_number=?",(r['shipment_number'],));synchronized['shipment']=r['shipment_number']
   except sqlite3.OperationalError:pass
 c.commit();c.close();return {'id':task_id,'status':status,'photo_url':photo_url,'synchronized':synchronized}
@router.get('/dispatch/tasks/{task_id}/history')
def history(task_id:str,x_admin_passcode:str=Header(default='')):check_admin(x_admin_passcode);c=get_conn();r=c.execute('SELECT * FROM dispatch_task_history WHERE task_id=? ORDER BY created_at',(task_id,)).fetchall();c.close();return {'count':len(r),'results':[dict(x) for x in r]}
@router.get('/dispatch/photo-audit')
def photo_audit(x_admin_passcode:str=Header(default='')):
 check_admin(x_admin_passcode);c=get_conn();r=c.execute("SELECT id,task_number,shipment_number,status,photo_url,completed_at FROM dispatch_tasks WHERE status IN ('picked_up','dropped_off_customer','dropped_off_warehouse') ORDER BY completed_at DESC").fetchall();c.close();return {'count':len(r),'results':[dict(x) for x in r]}