"""UGAMAP integration and operational data-flow smoke tests."""
from __future__ import annotations
import asyncio,json,os,sys,uuid
from urllib.parse import urlsplit
os.environ.setdefault('ADMIN_PASSCODE','ugamap-smoke-test-only')
from main import app
PASSCODE=os.environ['ADMIN_PASSCODE']
async def req(method,path,headers=None,payload=None):
 parts=urlsplit(path);sent=[];done=False;body=json.dumps(payload).encode() if payload is not None else b''
 async def receive():
  nonlocal done
  if done:return {'type':'http.disconnect'}
  done=True;return {'type':'http.request','body':body,'more_body':False}
 async def send(m):sent.append(m)
 hs=[(k.lower().encode(),str(v).encode()) for k,v in (headers or {}).items()]
 if body:hs += [(b'content-type',b'application/json'),(b'content-length',str(len(body)).encode())]
 scope={'type':'http','asgi':{'version':'3.0'},'http_version':'1.1','method':method,'scheme':'http','path':parts.path,'raw_path':parts.path.encode(),'query_string':parts.query.encode(),'headers':hs,'client':('127.0.0.1',1),'server':('test',80),'root_path':''}
 await app(scope,receive,send);start=next(m for m in sent if m['type']=='http.response.start');raw=b''.join(m.get('body',b'') for m in sent if m['type']=='http.response.body')
 try:data=json.loads(raw or b'{}')
 except:data=raw.decode(errors='replace')
 return start['status'],data
def routes():return {getattr(r,'path','') for r in app.routes}
async def main():
 failures=[];checks=0;h={'x-access-code':PASSCODE,'x-admin-passcode':PASSCODE};paths=routes()
 required=['/health','/orders/summary','/inventory/products','/fleet/vehicles','/yard/summary','/analytics/summary','/optimization/summary','/digital-twin/snapshot','/robotics/summary','/visibility/summary','/geography/zipper/status','/platform/mdm-runtime/quality','/platform/api-runtime/usage','/platform/monitoring-runtime/dashboard','/platform/feature-runtime/summary']
 for p in required:
  checks+=1
  if p not in paths:failures.append('missing '+p);print('FAIL route',p)
  else:print('PASS route',p)
 pages=['extended-applications','platform-services','transport-management','order-management','warehouse-control','yard-management','ai-ml-analytics','optimization-engine','digital-twin','robotics-orchestration','supply-chain-visibility']
 for name in pages:
  checks+=1;s,_=await req('GET',f'/assets/{name}.html')
  if s!=200:failures.append(f'page {name} {s}');print('FAIL page',name,s)
  else:print('PASS page',name)
 reads=['/orders/summary','/inventory/products','/fleet/vehicles','/yard/summary','/analytics/summary?window_days=14','/optimization/summary','/digital-twin/snapshot','/robotics/summary','/visibility/summary','/platform/mdm-runtime/quality','/platform/api-runtime/usage','/platform/monitoring-runtime/dashboard','/platform/feature-runtime/summary']
 for p in reads:
  checks+=1;s,d=await req('GET',p,h)
  if s>=400:failures.append(f'{p} {s} {d}');print('FAIL API',p,s)
  else:print('PASS API',p)
 suffix=uuid.uuid4().hex[:7].upper();sku='CI-'+suffix;bot='CI Robot '+suffix
 # Inventory endpoints are form-based, so the integration audit deliberately avoids pretending JSON writes validate them.
 flow=[('register robot','POST','/robotics/robots',{'name':bot,'robot_type':'mobile','warehouse_id':'main'})]
 created={}
 for label,m,p,b in flow:
  checks+=1;s,d=await req(m,p,h,b)
  if s>=400:failures.append(f'{label} {s} {d}');print('FAIL',label,s,d)
  else:created[label]=d;print('PASS',label)
 rid=(created.get('register robot') or {}).get('id')
 if rid:
  checks+=1;s,d=await req('POST','/robotics/missions',h,{'robot_id':rid,'mission_type':'move','reference':sku,'source_location':'RECEIVING','destination_location':'STORAGE','priority':'normal'})
  if s>=400:failures.append(f'robot mission {s} {d}');print('FAIL robot mission',s,d)
  else:print('PASS robot mission')
 # Exercise the four newest Platform Services runtimes with isolated CI records.
 mdm={'entity_type':'ci_test','record_key':suffix,'data':{'name':'Integration '+suffix,'code':suffix},'source':'ci','source_id':suffix,'priority':1,'changed_by':'ci'}
 checks+=1;s,d=await req('POST','/platform/mdm-runtime/records',h,mdm);print(('PASS' if s<400 else 'FAIL'),'MDM record',s)
 if s>=400:failures.append(f'MDM write {s} {d}')
 flag='ci-'+suffix.lower();checks+=1;s,d=await req('POST','/platform/feature-runtime/flags',h,{'feature_key':flag,'enabled':True,'rollout_percent':100,'variant_a':50,'variant_b':50,'target_rules':{}});print(('PASS' if s<400 else 'FAIL'),'feature flag',s)
 if s>=400:failures.append(f'feature write {s} {d}')
 checks+=1;s,d=await req('POST','/platform/feature-runtime/evaluate',h,{'feature_key':flag,'subject_key':'ci-user','context':{}});print(('PASS' if s<400 else 'FAIL'),'feature evaluate',s)
 if s>=400 or not d.get('enabled'):failures.append(f'feature evaluate {s} {d}')
 checks+=1;s,d=await req('POST','/platform/monitoring-runtime/services',h,{'name':'CI '+suffix,'kind':'test','target':'internal'});print(('PASS' if s<400 else 'FAIL'),'monitor service',s)
 if s>=400:failures.append(f'monitor write {s} {d}')
 downstream=['/digital-twin/snapshot','/optimization/summary','/analytics/summary?window_days=14','/visibility/network','/robotics/summary']
 for p in downstream:
  checks+=1;s,d=await req('GET',p,h)
  if s>=400:failures.append(f'downstream {p} {s} {d}');print('FAIL downstream',p,s)
  else:print('PASS downstream',p)
 for p in ['/analytics/summary','/optimization/summary','/robotics/summary','/visibility/summary','/platform/mdm-runtime/quality','/platform/api-runtime/usage','/platform/monitoring-runtime/dashboard','/platform/feature-runtime/summary']:
  checks+=1;s,_=await req('GET',p)
  if s not in (401,403):failures.append(f'auth {p} returned {s}');print('FAIL auth',p,s)
  else:print('PASS auth',p,s)
 print(f'\nUGAMAP integration audit: {checks-len(failures)}/{checks} checks passed')
 if failures:
  for f in failures:print(' -',f)
  return 1
 return 0
if __name__=='__main__':sys.exit(asyncio.run(main()))
