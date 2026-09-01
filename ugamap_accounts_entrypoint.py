"""Production entrypoint with UGAMAP Core + persistent user accounts."""
from pathlib import Path
from fastapi import Form, Header, HTTPException, UploadFile, File
from fastapi.responses import Response
from ugamap_entrypoint import app, public_report_via_core
from ugamap_accounts import router as ugamap_accounts_router
from ugamap_admin_users import router as ugamap_admin_users_router
from user_profile_store import user_for_token
from incident_records.account_link import attach_reporter, vote_once, list_user_reports
from incident_records.reputation import reputation_for, reputation_for_incident
from backup_monitor import router as backup_monitor_router
from warehouse_ops import router as warehouse_ops_router
from warehouse_inbound import router as warehouse_inbound_router
from warehouse_outbound import router as warehouse_outbound_router
from warehouse_delivery import router as warehouse_delivery_router
import backup_reconcile
app.include_router(ugamap_accounts_router);app.include_router(ugamap_admin_users_router);app.include_router(backup_monitor_router);app.include_router(warehouse_ops_router);app.include_router(warehouse_inbound_router);app.include_router(warehouse_outbound_router);app.include_router(warehouse_delivery_router)
def _account_user(authorization:str):
 value=(authorization or '').strip()
 if not value.lower().startswith('bearer '):raise HTTPException(status_code=401,detail='Sign in to use community incident features')
 user=user_for_token(value[7:].strip())
 if not user:raise HTTPException(status_code=401,detail='Session is invalid or expired')
 return user
for route in list(app.router.routes):
 path=getattr(route,'path',None);methods=getattr(route,'methods',set())
 if path in {'/','/admin','/ship'} and 'GET' in methods:app.router.routes.remove(route)
 if path=='/report' and 'POST' in methods:app.router.routes.remove(route)
 if path=='/reports/{report_id}/confirm' and 'POST' in methods:app.router.routes.remove(route)
@app.get('/',include_in_schema=False)
def ugamap_home_with_accounts():
 source=Path('index.html').read_text(encoding='utf-8')
 if '/boundaries.js' not in source:
  leaflet='<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>';source=source.replace(leaflet,leaflet+'\n<script src="/boundaries.js?v=3"></script>',1)
 scripts='<script src="/assets/ugamap-account-ui.js?v=2"></script>\n<script src="/assets/ugamap-account-incidents.js?v=1"></script>'
 if '/assets/ugamap-account-incidents.js' not in source:source=source.replace('</body>',scripts+'\n</body>') if '</body>' in source else source+scripts
 return Response(source,media_type='text/html',headers={'Cache-Control':'no-cache, no-store, must-revalidate'})
@app.get('/ship',include_in_schema=False)
def ugaship_page():return Response(Path('ship.html').read_text(encoding='utf-8'),media_type='text/html',headers={'Cache-Control':'no-cache, no-store, must-revalidate'})
@app.get('/ship/warehouse',include_in_schema=False)
def ugaship_warehouse_page():
 source=Path('warehouse.html').read_text(encoding='utf-8');needed=['/assets/ugaship-location-manager.js?v=1','/assets/ugaship-lot-allocation.js?v=1','/assets/ugaship-inbound.js?v=1','/assets/ugaship-outbound.js?v=1','/assets/ugaship-delivery.js?v=1'];missing=[f'<script src="{s}"></script>' for s in needed if s.split('?')[0] not in source]
 if missing:source=source.replace('</body>','\n'.join(missing)+'\n</body>') if '</body>' in source else source+'\n'+'\n'.join(missing)
 return Response(source,media_type='text/html',headers={'Cache-Control':'no-cache, no-store, must-revalidate'})
@app.get('/admin',include_in_schema=False)
def ugamap_admin_with_users():
 source=Path('admin.html').read_text(encoding='utf-8');scripts='\n'.join(['<script src="/admin-zip-link.js"></script>','<script src="/assets/admin-report-notifications.js?v=3"></script>','<script src="/assets/admin-user-management.js?v=1"></script>']);source=source.replace('</body>',scripts+'\n</body>') if '</body>' in source else source+scripts;return Response(source,media_type='text/html',headers={'Cache-Control':'no-cache, no-store, must-revalidate'})
@app.post('/report',tags=['UGAMAP Account Incidents'])
async def account_report(category:str=Form(...),lat:float=Form(...),lon:float=Form(...),note:str=Form(''),file:UploadFile=File(None),authorization:str=Header(default='')):
 user=_account_user(authorization);report=await public_report_via_core(category=category,lat=lat,lon=lon,note=note,file=file);attach_reporter(report['id'],user['id']);report['submitted_by_account']=True;report['reporter_reputation']=reputation_for(user['id']);return report
@app.post('/reports/{report_id}/confirm',tags=['UGAMAP Account Incidents'])
def account_confirm_report(report_id:str,vote:str=Form(...),authorization:str=Header(default='')):
 user=_account_user(authorization)
 try:result=vote_once(report_id,user['id'],vote)
 except ValueError as exc:raise HTTPException(status_code=400,detail=str(exc)) from exc
 except PermissionError as exc:raise HTTPException(status_code=403,detail=str(exc)) from exc
 if not result:raise HTTPException(status_code=404,detail='Report not found')
 result['reporter_reputation']=reputation_for_incident(report_id);return result
@app.get('/account/my-reports',tags=['UGAMAP Accounts'])
def account_my_reports(authorization:str=Header(default='')):
 user=_account_user(authorization);rows=list_user_reports(user['id']);return {'count':len(rows),'results':rows,'reputation':reputation_for(user['id'])}
@app.get('/account/reputation',tags=['UGAMAP Accounts'])
def account_reputation(authorization:str=Header(default='')):return reputation_for(_account_user(authorization)['id'])
