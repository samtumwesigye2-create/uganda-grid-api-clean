"""Vector 5250 message queues and system operator console."""
import os, sqlite3, time, uuid
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from auth import require_permission, is_master

BASE=os.path.dirname(os.path.abspath(__file__))
DB=os.path.join(BASE,'vector5250.db')
PERM='warehouse:manager'
router=APIRouter(tags=['Vector 5250 Messages'])

def _auth(code):
    if is_master(code): return
    try: require_permission(code,PERM)
    except HTTPException: raise HTTPException(status_code=403,detail='Vector 5250 manager access required')

def _db():
    c=sqlite3.connect(DB);c.row_factory=sqlite3.Row
    c.execute('''CREATE TABLE IF NOT EXISTS vector_message_queues(
      queue_name TEXT PRIMARY KEY, queue_type TEXT NOT NULL, delivery TEXT NOT NULL,
      description TEXT NOT NULL, created_at REAL NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS vector_messages(
      message_id TEXT PRIMARY KEY, queue_name TEXT NOT NULL, severity INTEGER NOT NULL DEFAULT 0,
      message_type TEXT NOT NULL DEFAULT 'INFO', status TEXT NOT NULL DEFAULT 'NEW',
      sender TEXT NOT NULL, text TEXT NOT NULL, reply_text TEXT NOT NULL DEFAULT '',
      created_at REAL NOT NULL, replied_at REAL)''')
    now=time.time()
    seeds=[('QSYSOPR','SYSTEM','BREAK','Vector system operator message queue'),('QVECTOR','APPLICATION','NOTIFY','Vector 5250 application messages'),('QSECURITY','SECURITY','HOLD','Vector security and access messages'),('QBACKUP','SYSTEM','NOTIFY','Backup and resilience messages')]
    for row in seeds:c.execute('INSERT OR IGNORE INTO vector_message_queues VALUES(?,?,?,?,?)',(*row,now))
    c.commit();return c

class MessageIn(BaseModel):
    queue_name:str='QSYSOPR';severity:int=0;message_type:str='INFO';text:str
class ReplyIn(BaseModel): reply_text:str

@router.get('/vector5250/api/message-queues')
def queues(x_access_code:str=Header(default='')):
    _auth(x_access_code);c=_db()
    try:
        rows=[]
        for q in c.execute('SELECT * FROM vector_message_queues ORDER BY queue_name'):
            d=dict(q);d['messages']=c.execute("SELECT count(*) FROM vector_messages WHERE queue_name=? AND status!='REMOVED'",(q['queue_name'],)).fetchone()[0];d['new']=c.execute("SELECT count(*) FROM vector_messages WHERE queue_name=? AND status='NEW'",(q['queue_name'],)).fetchone()[0];rows.append(d)
        return {'count':len(rows),'queues':rows}
    finally:c.close()

@router.get('/vector5250/api/messages')
def messages(queue:str='QSYSOPR',limit:int=100,x_access_code:str=Header(default='')):
    _auth(x_access_code);c=_db()
    try:
        rows=[dict(r) for r in c.execute("SELECT * FROM vector_messages WHERE queue_name=? AND status!='REMOVED' ORDER BY created_at DESC LIMIT ?",(queue.upper(),max(1,min(limit,500)))).fetchall()]
        return {'queue':queue.upper(),'count':len(rows),'messages':rows}
    finally:c.close()

@router.post('/vector5250/api/messages')
def send_message(body:MessageIn,x_access_code:str=Header(default=''),x_vector_user:str=Header(default='SYSTEM')):
    _auth(x_access_code);q=body.queue_name.upper().strip();c=_db()
    try:
        if not c.execute('SELECT 1 FROM vector_message_queues WHERE queue_name=?',(q,)).fetchone(): raise HTTPException(status_code=404,detail='Message queue not found')
        mid='MSG'+uuid.uuid4().hex[:9].upper();now=time.time()
        c.execute('INSERT INTO vector_messages(message_id,queue_name,severity,message_type,status,sender,text,created_at) VALUES(?,?,?,?,?,?,?,?)',(mid,q,max(0,min(body.severity,99)),body.message_type.upper(),'NEW',x_vector_user.upper(),body.text.strip(),now));c.commit()
        return dict(c.execute('SELECT * FROM vector_messages WHERE message_id=?',(mid,)).fetchone())
    finally:c.close()

@router.post('/vector5250/api/messages/{message_id}/reply')
def reply(message_id:str,body:ReplyIn,x_access_code:str=Header(default=''),x_vector_user:str=Header(default='SYSTEM')):
    _auth(x_access_code);c=_db()
    try:
        if not c.execute('SELECT 1 FROM vector_messages WHERE message_id=?',(message_id,)).fetchone(): raise HTTPException(status_code=404,detail='Message not found')
        c.execute("UPDATE vector_messages SET status='REPLIED',reply_text=?,replied_at=? WHERE message_id=?",(body.reply_text.strip(),time.time(),message_id));c.commit()
        return dict(c.execute('SELECT * FROM vector_messages WHERE message_id=?',(message_id,)).fetchone())
    finally:c.close()

@router.post('/vector5250/api/messages/{message_id}/ack')
def acknowledge(message_id:str,x_access_code:str=Header(default='')):
    _auth(x_access_code);c=_db()
    try:
        c.execute("UPDATE vector_messages SET status=CASE WHEN status='NEW' THEN 'ACK' ELSE status END WHERE message_id=?",(message_id,));c.commit();r=c.execute('SELECT * FROM vector_messages WHERE message_id=?',(message_id,)).fetchone()
        if not r: raise HTTPException(status_code=404,detail='Message not found')
        return dict(r)
    finally:c.close()

@router.delete('/vector5250/api/messages/{message_id}')
def remove(message_id:str,x_access_code:str=Header(default='')):
    _auth(x_access_code);c=_db()
    try:
        c.execute("UPDATE vector_messages SET status='REMOVED' WHERE message_id=?",(message_id,));c.commit();return {'removed':True,'message_id':message_id}
    finally:c.close()
