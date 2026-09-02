import os,sqlite3,time,uuid
from fastapi import APIRouter,Header,HTTPException
from pydantic import BaseModel
from auth import require_permission
BASE=os.path.dirname(os.path.abspath(__file__));DB=os.path.join(BASE,'data_hub.db');router=APIRouter(prefix='/platform/notifications',tags=['platform-notifications'])
def conn():c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;return c
def read(code):require_permission(code,'shipments:read')
def write(code):require_permission(code,'shipments:write')
class StatusIn(BaseModel):status:str;error:str=''
@router.get('/summary')
def summary(x_access_code:str=Header(default='')):
 read(x_access_code);c=conn();rows=c.execute('SELECT status,COUNT(*) n FROM platform_notifications GROUP BY status').fetchall();channels=c.execute('SELECT channel,COUNT(*) n FROM platform_notifications GROUP BY channel').fetchall();due=c.execute("SELECT COUNT(*) n FROM platform_notifications WHERE status='scheduled' AND scheduled_at<=?",(time.time(),)).fetchone()['n'];c.close();return {'by_status':{r['status']:r['n'] for r in rows},'by_channel':{r['channel']:r['n'] for r in channels},'due_now':due}
@router.post('/process-due')
def process_due(x_access_code:str=Header(default='')):
 write(x_access_code);c=conn();ts=time.time();rows=c.execute("SELECT * FROM platform_notifications WHERE (status='scheduled' AND scheduled_at<=?) OR status='queued' ORDER BY created_at LIMIT 200",(ts,)).fetchall();processed=[]
 for r in rows:
  ch=(r['channel'] or '').lower();new='delivered' if ch=='in-app' else 'provider_required';err='' if ch=='in-app' else f'{ch} provider not configured';c.execute('UPDATE platform_notifications SET status=?,attempts=attempts+1,last_error=?,updated_at=? WHERE id=?',(new,err,ts,r['id']));processed.append({'id':r['id'],'channel':ch,'status':new})
 c.commit();c.close();return {'processed':len(processed),'results':processed,'note':'In-app messages complete internally. Email/SMS/push require configured delivery providers.'}
@router.post('/{notification_id}/status')
def set_status(notification_id:str,p:StatusIn,x_access_code:str=Header(default='')):
 write(x_access_code);allowed={'queued','scheduled','provider_required','sent','delivered','failed','cancelled'};s=p.status.strip().lower()
 if s not in allowed:raise HTTPException(400,'Invalid notification status')
 c=conn();r=c.execute('SELECT * FROM platform_notifications WHERE id=?',(notification_id,)).fetchone()
 if not r:c.close();raise HTTPException(404,'Notification not found')
 c.execute('UPDATE platform_notifications SET status=?,last_error=?,updated_at=? WHERE id=?',(s,p.error[:1000],time.time(),notification_id));c.execute('INSERT INTO platform_audit VALUES (?,?,?,?,?,?,?)',(str(uuid.uuid4()),'staff','notification.status',notification_id,s,'ok',time.time()));c.commit();c.close();return {'id':notification_id,'status':s}
@router.post('/{notification_id}/retry')
def retry(notification_id:str,x_access_code:str=Header(default='')):
 write(x_access_code);c=conn();r=c.execute('SELECT * FROM platform_notifications WHERE id=?',(notification_id,)).fetchone()
 if not r:c.close();raise HTTPException(404,'Notification not found')
 c.execute("UPDATE platform_notifications SET status='queued',last_error='',updated_at=? WHERE id=?",(time.time(),notification_id));c.execute('INSERT INTO platform_audit VALUES (?,?,?,?,?,?,?)',(str(uuid.uuid4()),'staff','notification.retry',notification_id,'manual retry','ok',time.time()));c.commit();c.close();return {'id':notification_id,'status':'queued'}