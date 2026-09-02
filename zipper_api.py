"""FastAPI router for the active population-balanced ZIPPER layer."""
from __future__ import annotations
import json,os
from functools import lru_cache
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
from data_relay_runtime import router as data_relay_runtime_router
from data_relay_audit import router as data_relay_audit_router
router=APIRouter(tags=['ZIPPER'])
for r in (orders_router,yard_router,analytics_router,optimization_router,digital_twin_router,robotics_router,visibility_router,platform_services_router,notification_runtime_router,document_runtime_router,audit_runtime_router,mdm_runtime_router,api_management_runtime_router,monitoring_runtime_router,feature_management_runtime_router,data_relay_runtime_router,data_relay_audit_router):router.include_router(r)
BASE_DIR=os.path.dirname(os.path.abspath(__file__));ZIPPER_GEOJSON_FILE=os.environ.get('ZIPPER_GEOJSON_FILE',os.path.join(BASE_DIR,'zipper_zones.geojson'))
@lru_cache(maxsize=1)
def _load_artifact():
 if not os.path.exists(ZIPPER_GEOJSON_FILE):raise FileNotFoundError(ZIPPER_GEOJSON_FILE)
 with open(ZIPPER_GEOJSON_FILE,'r',encoding='utf-8') as f:data=json.load(f)
 if data.get('type')!='FeatureCollection':raise ValueError('ZIPPER artifact must be a GeoJSON FeatureCollection')
 return data
def zipper_feature_collection():return _load_artifact() if os.path.exists(ZIPPER_GEOJSON_FILE) else live_zipper_feature_collection()
def clear_zipper_cache():_load_artifact.cache_clear();_indexed_zipper_features.cache_clear();live_zipper_feature_collection.cache_clear()

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
def geography_zipper_viewport(
 min_lon:float=Query(...,ge=-180,le=180),min_lat:float=Query(...,ge=-90,le=90),
 max_lon:float=Query(...,ge=-180,le=180),max_lat:float=Query(...,ge=-90,le=90),
 limit:int=Query(240,ge=1,le=500)
):
 """Return only ZIPPER polygons intersecting the current map viewport."""
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
 status=numbering_status();ready=os.path.exists(ZIPPER_GEOJSON_FILE);status.update({'layer':'ZIPPER','active_replacement':True,'artifact':os.path.basename(ZIPPER_GEOJSON_FILE),'artifact_ready':ready,'source':'generated_artifact' if ready else 'district_population_live_fallback'})
 try:
  if ready:status['zones']=len(_load_artifact().get('features',[]));status['ready']=True
  else:status.update(live_zipper_status())
 except Exception as exc:status['ready']=False;status['error']=str(exc)
 return status