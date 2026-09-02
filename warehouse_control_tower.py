import os,sqlite3,time
from fastapi import APIRouter,Header,Query
from auth import require_permission
DB=os.path.join(os.path.dirname(os.path.abspath(__file__)),'data_hub.db');router=APIRouter()
def db():
 c=sqlite3.connect(DB,timeout=30);c.row_factory=sqlite3.Row;c.execute('PRAGMA busy_timeout=30000');return c
def one(c,q,a=()):return c.execute(q,a).fetchone()
def pct(a,b):return round((float(a or 0)/float(b or 1))*100,1) if b else 0
def exists(c,n):return c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(n,)).fetchone() is not None
def cols(c,n):return {r['name'] for r in c.execute(f'PRAGMA table_info({n})').fetchall()} if exists(c,n) else set()
def safe_count(c,table,where='',args=()):
 if not exists(c,table):return 0
 try:return int(one(c,f'SELECT COUNT(*) n FROM {table}'+((' WHERE '+where) if where else ''),args)['n'] or 0)
 except Exception:return 0
@router.get('/warehouse/dashboard')
def dashboard(warehouse_id:str=Query('main'),x_access_code:str=Header(default='')):
 require_permission(x_access_code,'inventory:read');c=db();today=time.time()-86400
 try:
  def op(name):
   need={'warehouse_id','operation_type','created_at'}
   if not need.issubset(cols(c,'warehouse_operations')):return 0
   return safe_count(c,'warehouse_operations','warehouse_id=? AND operation_type=? AND created_at>=?',(warehouse_id,name,today))
  low=[];sc=cols(c,'stock')
  if {'product_sku','warehouse_id','quantity_on_hand'}.issubset(sc):
   try:low=[dict(r) for r in c.execute('SELECT product_sku,warehouse_id,quantity_on_hand FROM stock WHERE warehouse_id=? AND quantity_on_hand<=5 ORDER BY quantity_on_hand,product_sku LIMIT 100',(warehouse_id,)).fetchall()]
   except Exception:low=[]
  alerts=[]
  if low:alerts.append({'level':'warning','type':'low_stock','message':f'{len(low)} SKUs are at or below low-stock threshold','reference':warehouse_id})
  tc=cols(c,'warehouse_tasks')
  if {'warehouse_id','status'}.issubset(tc):
   n=safe_count(c,'warehouse_tasks',"warehouse_id=? AND status='blocked'",(warehouse_id,))
   if n:alerts.append({'level':'critical','type':'blocked_tasks','message':f'{n} warehouse tasks are blocked','reference':warehouse_id})
  qc=cols(c,'warehouse_quality_holds')
  if {'warehouse_id','status'}.issubset(qc):
   n=safe_count(c,'warehouse_quality_holds',"warehouse_id=? AND status IN ('quarantine','held','open')",(warehouse_id,))
   if n:alerts.append({'level':'warning','type':'quality_hold','message':f'{n} quality holds require attention','reference':warehouse_id})
  dc=cols(c,'warehouse_deliveries')
  if {'warehouse_id','status','updated_at'}.issubset(dc):
   n=safe_count(c,'warehouse_deliveries',"warehouse_id=? AND status='failed' AND updated_at>=?",(warehouse_id,today))
   if n:alerts.append({'level':'critical','type':'delivery_failure','message':f'{n} deliveries failed in the last 24 hours','reference':warehouse_id})
  return {'warehouse_id':warehouse_id,'today':{'receiving':op('receiving'),'picking':op('picking'),'dispatch':op('dispatch'),'putaway':op('putaway')},'low_stock':low,'alerts':alerts,'generated_at':time.time()}
 finally:c.close()
@router.get('/warehouse/control-tower')
def tower(warehouse_id:str=Query('main'),days:int=Query(7,ge=1,le=90),x_access_code:str=Header(default='')):
 require_permission(x_access_code,'inventory:read');c=db();now=time.time();since=now-days*86400;today=now-86400
 try:
  def q(sql,args=(),defaults=None):
   try:return one(c,sql,args)
   except Exception:return defaults or {}
  stock=q('SELECT COUNT(*) skus,COALESCE(SUM(quantity_on_hand),0) units FROM stock WHERE warehouse_id=?',(warehouse_id,),{'skus':0,'units':0});low=q('SELECT COUNT(*) n FROM stock WHERE warehouse_id=? AND quantity_on_hand<=5',(warehouse_id,),{'n':0});lots=q("SELECT COUNT(*) lots,COALESCE(SUM(quantity_available),0) units FROM warehouse_lots WHERE warehouse_id=? AND status='available'",(warehouse_id,),{'lots':0,'units':0});exp=q("SELECT COUNT(*) n,COALESCE(SUM(quantity_available),0) units FROM warehouse_lots WHERE warehouse_id=? AND status='available' AND expiry_date IS NOT NULL AND expiry_date!='' AND date(expiry_date)<=date('now','+30 day')",(warehouse_id,),{'n':0,'units':0});loc=q('SELECT COUNT(*) total,COALESCE(SUM(capacity),0) capacity,COALESCE(SUM(used_capacity),0) used FROM warehouse_locations WHERE warehouse_id=?',(warehouse_id,),{'total':0,'capacity':0,'used':0});orders=q("SELECT COUNT(*) total,SUM(CASE WHEN status='dispatched' THEN 1 ELSE 0 END) dispatched,SUM(CASE WHEN status='partial' THEN 1 ELSE 0 END) partial FROM warehouse_customer_orders WHERE warehouse_id=? AND created_at>=?",(warehouse_id,since),{'total':0,'dispatched':0,'partial':0});deliver=q("SELECT COUNT(*) total,SUM(CASE WHEN status='delivered' THEN 1 ELSE 0 END) delivered,SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) failed FROM warehouse_deliveries WHERE warehouse_id=? AND created_at>=?",(warehouse_id,since),{'total':0,'delivered':0,'failed':0});tasks=q("SELECT COUNT(*) total,SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) completed,SUM(CASE WHEN status='blocked' THEN 1 ELSE 0 END) blocked,COALESCE(SUM(CASE WHEN status='completed' THEN quantity ELSE 0 END),0) units FROM warehouse_tasks WHERE warehouse_id=? AND created_at>=?",(warehouse_id,since),{'total':0,'completed':0,'blocked':0,'units':0});staff=q("SELECT COUNT(*) n FROM warehouse_staff WHERE warehouse_id=? AND status='active'",(warehouse_id,),{'n':0});docks=q("SELECT COUNT(*) n FROM warehouse_docks WHERE warehouse_id=?",(warehouse_id,),{'n':0});dock_use=q("SELECT COUNT(DISTINCT dock_id) n FROM warehouse_deliveries WHERE warehouse_id=? AND created_at>=? AND dock_id IS NOT NULL AND dock_id!=''",(warehouse_id,today),{'n':0})
  try:ops=[dict(r) for r in c.execute('SELECT operation_type,COUNT(*) count,COALESCE(SUM(quantity),0) quantity FROM warehouse_operations WHERE warehouse_id=? AND created_at>=? GROUP BY operation_type ORDER BY count DESC',(warehouse_id,since)).fetchall()]
  except Exception:ops=[]
  alerts=[]
  if low['n']:alerts.append({'level':'warning','type':'low_stock','message':f"{low['n']} SKUs are at or below low-stock threshold"})
  if exp['n']:alerts.append({'level':'warning','type':'expiry','message':f"{exp['n']} lots / {exp['units']} units expire within 30 days"})
  if tasks['blocked']:alerts.append({'level':'critical','type':'blocked_tasks','message':f"{tasks['blocked']} warehouse tasks are blocked"})
  if deliver['failed']:alerts.append({'level':'critical','type':'delivery_failure','message':f"{deliver['failed']} deliveries failed in the last {days} days"})
  return {'period_days':days,'inventory':{'skus':stock['skus'],'units':stock['units'],'low_stock_skus':low['n'],'active_lots':lots['lots'],'lot_units':lots['units'],'expiring_lots':exp['n'],'expiring_units':exp['units']},'space':{'locations':loc['total'],'capacity':loc['capacity'],'used':loc['used'],'utilization_pct':pct(loc['used'],loc['capacity'])},'fulfillment':{'orders':orders['total'] or 0,'dispatched':orders['dispatched'] or 0,'partial':orders['partial'] or 0,'dispatch_rate_pct':pct(orders['dispatched'],orders['total']),'deliveries':deliver['total'] or 0,'delivered':deliver['delivered'] or 0,'failed':deliver['failed'] or 0,'delivery_success_pct':pct(deliver['delivered'],deliver['total'])},'labor':{'active_staff':staff['n'],'tasks':tasks['total'] or 0,'completed':tasks['completed'] or 0,'blocked':tasks['blocked'] or 0,'units_handled':tasks['units'] or 0,'completion_rate_pct':pct(tasks['completed'],tasks['total'])},'dock':{'docks':docks['n'],'used_today':dock_use['n'],'utilization_pct':pct(dock_use['n'],docks['n'])},'operations':ops,'alerts':alerts,'generated_at':now}
 finally:c.close()
