"""FastAPI router for the active ZIPPER layer and standalone UNG-ZIPPER source-of-truth bridge."""
from __future__ import annotations
import json,os
from functools import lru_cache
import requests
from fastapi import APIRouter,HTTPException,Query
from zipper_numbering import numbering_status
from zipper_live_geometry import live_zipper_feature_collection,live_zipper_status
from orders import router as orders_router
from yard import router as yard_router
from analytics import router as analytics_router
from optimization import router as optimization_router
from digital_twin import router as digital_twin_router
from robotics import router as robotics_router
from visibility import router as visibility_router
from platform_services import router as platform_services_router
from notification_runtime import router as notification_runtime_router
from document_runtime import router as document_runtime_router
from audit_runtime import router as audit_runtime_router
from mdm_runtime import router as mdm_runtime_router
from api_management_runtime import router as api_management_runtime_router
from monitoring_runtime import router as monitoring_runtime_router
from feature_management_runtime import router as feature_management_runtime_router
router=APIRouter(tags=['ZIPPER'])
for r in (orders_router,yard_router,analytics_router,optimization_router,digital_twin_router,robotics_router,visibility_router,platform_services_router,notification_runtime_router,document_runtime_router,audit_runtime_router,mdm_runtime_router,api_management_runtime_router,monitoring_runtime_router,feature_management_runtime_router):router.include_router(r)
BASE_DIR=os.path.dirname(os.path.abspath(__file__))
ZIPPER_GEOJSON_FILE=os.environ.get('ZIPPER_GEOJSON_FILE',os.path.join(BASE_DIR,'zipper_zones.geojson'))
ZIPPER_API_URL=os.environ.get('ZIPPER_API_URL','https://ung-zipper-production.up.railway.app').rstrip('/')
ZIPPER_TIMEOUT=float(os.environ.get('ZIPPER_TIMEOUT_SECONDS','8'))

@lru_cache(maxsize=1)
def _load_artifact():
 if not os.path.exists(ZIPPER_GEOJSON_FILE):raise FileNotFoundError(ZIPPER_GEOJSON_FILE)
 with open(ZIPPER_GEOJSON_FILE,'r',encoding='utf-8') as f:data=json.load(f)
 if data.get('type')!='FeatureCollection':raise ValueError('ZIPPER artifact must be a GeoJSON FeatureCollection')
 return data

def zipper_feature_collection():return _load_artifact() if os.path.exists(ZIPPER_GEOJSON_FILE) else live_zipper_feature_collection()
def clear_zipper_cache():_load_artifact.cache_clear();_indexed_zipper_features.cache_clear();live_zipper_feature_collection.cache_clear()

def _zipper_get(path:str):
 try:
  response=requests.get(f'{ZIPPER_API_URL}{path}',timeout=ZIPPER_TIMEOUT)
 except requests.RequestException as exc:
  raise HTTPException(status_code=503,detail=f'UNG-ZIPPER unavailable: {type(exc).__name__}')
 if response.status_code==404:raise HTTPException(status_code=404,detail='ZIP code not found')
 if response.status_code!=200:raise HTTPException(status_code=502,detail=f'UNG-ZIPPER returned HTTP {response.status_code}')
 try:return response.json()
 except ValueError:raise HTTPException(status_code=502,detail='UNG-ZIPPER returned invalid JSON')

@router.get('/integration/zipper/health')
def zipper_integration_health():
 """Live end-to-end acceptance: readiness -> sample -> validation -> resolution."""
 ready=_zipper_get('/ready')
 records=_zipper_get('/zipper/?limit=1')
 if not isinstance(records,list) or not records:
  raise HTTPException(status_code=503,detail='UNG-ZIPPER registry is empty')
 sample=records[0]
 code=str(sample.get('code') or '').strip()
 if not code:
  raise HTTPException(status_code=503,detail='UNG-ZIPPER sample has no code')
 validation=_zipper_get(f'/zipper/validate/{code}')
 resolution=_zipper_get(f'/zipper/{code}')
 if not validation.get('valid') or str(resolution.get('code'))!=code:
  raise HTTPException(status_code=503,detail='UNG-ZIPPER validation/resolution mismatch')
 return {
  'status':'ok',
  'integration':'UGAMAP->UNG-ZIPPER',
  'registry_records':ready.get('records'),
  'sample_code':code,
  'district':resolution.get('district'),
  'area_type':resolution.get('area_type'),
  'population_covered':resolution.get('population_covered'),
  'validation':validation,
  'resolution_ok':True,
 }

@router.get('/zipper/validate/{code}')
def validate_zipper_code(code:str):
 """Authoritative five-digit ZIP validation via standalone UNG-ZIPPER."""
 return _zipper_get(f'/zipper/validate/{code}')

@router.get('/zipper/{code}')
def resolve_zipper_code(code:str):
 """Authoritative destination resolution via standalone UNG-ZIPPER."""
 return _zipper_get(f'/zipper/{code}')

def _geometry_bbox(geometry):
 coords=(geometry or {}).get('coordinates')
 if not coords:return None
 min_lon=min_lat=float('inf');max_lon=max_lat=float('-inf')
 def walk(v):
  nonlocal min_lon,min_lat,max_lon,max_lat
  if isinstance(v,(list,tuple)):
   if len(v)>=2 and isinstance(v[0],(int,float)) and isinstance(v[1],(int,float)):
    lon,lat=float(v[0]),float(v[1]);min_lon=min(min_lon,lon);max_lon=max(max_lon,lon);min_lat=min(min_lat,lat);max_lat=max(max_lat,lat)
   else:
    for x in v:walk(x)
 walk(coords)
 if min_lon==float('inf'):return None
 return min_lon,min_lat,max_lon,max_lat

@lru_cache(maxsize=1)
def _indexed_zipper_features():
 data=zipper_feature_collection();out=[]
 for i,f in enumerate(data.get('features',[])):out.append((i,f,_geometry_bbox(f.get('geometry'))))
 return out

@router.get('/geography/zipper')
def geography_zipper():
 try:return zipper_feature_collection()
 except Exception as exc:raise HTTPException(status_code=500,detail=f'ZIPPER geography unavailable: {exc}')

@router.get('/geography/zipper/viewport')
def geography_zipper_viewport(min_lon:float=Query(...,ge=-180,le=180),min_lat:float=Query(...,ge=-90,le=90),max_lon:float=Query(...,ge=-180,le=180),max_lat:float=Query(...,ge=-90,le=90),limit:int=Query(240,ge=1,le=500)):
 if min_lon>=max_lon or min_lat>=max_lat:raise HTTPException(status_code=400,detail='Invalid viewport bounds')
 try:
  features=[]
  for index,feature,bbox in _indexed_zipper_features():
   if not bbox:continue
   a,b,c,d=bbox
   if c<min_lon or a>max_lon or d<min_lat or b>max_lat:continue
   item=dict(feature);item['__ugamap_index']=index;features.append(item)
   if len(features)>=limit:break
  return {'type':'FeatureCollection','features':features,'viewport':{'min_lon':min_lon,'min_lat':min_lat,'max_lon':max_lon,'max_lat':max_lat},'limited':len(features)>=limit}
 except Exception as exc:raise HTTPException(status_code=500,detail=f'ZIPPER viewport unavailable: {exc}')

@router.get('/geography/zipper/status')
def geography_zipper_status():
 status=numbering_status();ready=os.path.exists(ZIPPER_GEOJSON_FILE);status.update({'layer':'ZIPPER','active_replacement':True,'artifact':os.path.basename(ZIPPER_GEOJSON_FILE),'artifact_ready':ready,'source':'generated_artifact' if ready else 'district_population_live_fallback','registry_url':ZIPPER_API_URL})
 try:
  upstream=requests.get(f'{ZIPPER_API_URL}/health',timeout=ZIPPER_TIMEOUT)
  status['registry_ready']=upstream.status_code==200
 except requests.RequestException:
  status['registry_ready']=False
 try:
  if ready:status['zones']=len(_load_artifact().get('features',[]));status['ready']=True
  else:status.update(live_zipper_status())
 except Exception as exc:status['ready']=False;status['error']=str(exc)
 return status
