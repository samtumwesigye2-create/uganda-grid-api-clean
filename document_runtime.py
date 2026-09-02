import json,os,sqlite3,time,uuid
from fastapi import APIRouter,Header,HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from auth import require_permission
BASE=os.path.dirname(os.path.abspath(__file__));DB=os.path.join(BASE,'data_hub.db');DOC_DIR=os.path.join(BASE,'uploads','platform-docs');router=APIRouter(prefix='/platform',tags=['platform-document-runtime'])
def conn():c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;return c
def read(code):require_permission(code,'shipments:read')
def write(code):require_permission(code,'shipments:write')
def now():return time.time()
def init():
 c=conn();c.execute('CREATE TABLE IF NOT EXISTS platform_document_permissions(document_id TEXT NOT NULL,subject TEXT NOT NULL,can_view INTEGER NOT NULL DEFAULT 1,can_download INTEGER NOT NULL DEFAULT 1,can_edit INTEGER NOT NULL DEFAULT 0,can_delete INTEGER NOT NULL DEFAULT 0,updated_at REAL NOT NULL,PRIMARY KEY(document_id,subject))');c.commit();c.close()
init()
class PermissionIn(BaseModel):subject:str='all';can_view:bool=True;can_download:bool=True;can_edit:bool=False;can_delete:bool=False
def get_doc(c,did):
 r=c.execute('SELECT * FROM platform_documents WHERE id=?',(did,)).fetchone()
 if not r:raise HTTPException(404,'Document not found')
 return r
def audit(c,actor,action,target,detail=''):c.execute('INSERT INTO platform_audit VALUES (?,?,?,?,?,?,?)',(str(uuid.uuid4()),actor,action,target,detail,'ok',now()))
@router.get('/documents/{document_id}')
def document_detail(document_id:str,x_access_code:str=Header(default='')):
 read(x_access_code);c=conn();r=get_doc(c,document_id);d=dict(r);d['versions']=[dict(x) for x in c.execute('SELECT id,version,size,created_at FROM platform_document_versions WHERE document_id=? ORDER BY version DESC',(document_id,))];d['permissions']=[dict(x) for x in c.execute('SELECT subject,can_view,can_download,can_edit,can_delete,updated_at FROM platform_document_permissions WHERE document_id=? ORDER BY subject',(document_id,))];c.close();return d
@router.get('/documents/{document_id}/download')
def document_download(document_id:str,version:int|None=None,x_access_code:str=Header(default='')):
 read(x_access_code);c=conn();d=get_doc(c,document_id);stored=d['stored_name'];name=d['name'];ver=d['version']
 if version is not None:
  v=c.execute('SELECT * FROM platform_document_versions WHERE document_id=? AND version=?',(document_id,version)).fetchone()
  if not v:c.close();raise HTTPException(404,'Document version not found')
  stored=v['stored_name'];ver=v['version']
 path=os.path.join(DOC_DIR,stored);c.close()
 if not os.path.isfile(path):raise HTTPException(404,'Stored file is missing')
 return FileResponse(path,filename=name,media_type=d['mime_type'] or 'application/octet-stream',headers={'X-Document-Version':str(ver)})
@router.post('/documents/{document_id}/permissions')
def document_permissions(document_id:str,p:PermissionIn,x_access_code:str=Header(default='')):
 write(x_access_code);c=conn();get_doc(c,document_id);c.execute('INSERT OR REPLACE INTO platform_document_permissions VALUES (?,?,?,?,?,?,?)',(document_id,p.subject,int(p.can_view),int(p.can_download),int(p.can_edit),int(p.can_delete),now()));audit(c,'staff','document.permissions',document_id,p.subject);c.commit();c.close();return {'document_id':document_id,**(p.model_dump() if hasattr(p,'model_dump') else p.dict())}
@router.delete('/documents/{document_id}')
def document_delete(document_id:str,x_access_code:str=Header(default='')):
 write(x_access_code);c=conn();d=get_doc(c,document_id);versions=[dict(x) for x in c.execute('SELECT stored_name FROM platform_document_versions WHERE document_id=?',(document_id,))];c.execute('DELETE FROM platform_document_permissions WHERE document_id=?',(document_id,));c.execute('DELETE FROM platform_document_versions WHERE document_id=?',(document_id,));c.execute('DELETE FROM platform_documents WHERE id=?',(document_id,));audit(c,'staff','document.delete',document_id,d['name']);c.commit();c.close()
 for v in versions:
  try:os.remove(os.path.join(DOC_DIR,v['stored_name']))
  except FileNotFoundError:pass
 return {'id':document_id,'deleted':True,'versions_removed':len(versions)}
@router.get('/documents/summary/runtime')
def document_summary(x_access_code:str=Header(default='')):
 read(x_access_code);c=conn();total=c.execute('SELECT COUNT(*) n FROM platform_documents').fetchone()['n'];versions=c.execute('SELECT COUNT(*) n FROM platform_document_versions').fetchone()['n'];size=c.execute('SELECT COALESCE(SUM(size),0) n FROM platform_documents').fetchone()['n'];c.close();return {'documents':total,'versions':versions,'current_storage_bytes':size}