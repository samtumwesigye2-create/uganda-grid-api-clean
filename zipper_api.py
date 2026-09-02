"""FastAPI router for the active population-balanced ZIPPER layer."""
from __future__ import annotations
import json,os
from functools import lru_cache
from fastapi import APIRouter,HTTPException
from zipper_numbering import numbering_status
from zipper_live_geometry import live_zipper_feature_collection,live_zipper_status
from orders import router as orders_router
from yard import router as yard_router
from analytics import router as analytics_router
from optimization import router as optimization_router
from digital_twin import router as digital_twin_router
from robotics import router as robotics_router
router=APIRouter(tags=['ZIPPER'])
for r in (orders_router,yard_router,analytics_router,optimization_router,digital_twin_router,robotics_router):router.include_router(r)
BASE_DIR=os.path.dirname(os.path.abspath(__file__));ZIPPER_GEOJSON_FILE=os.environ.get('ZIPPER_GEOJSON_FILE',os.path.join(BASE_DIR,'zipper_zones.geojson'))
@lru_cache(maxsize=1)
def _load_artifact():
 if not os.path.exists(ZIPPER_GEOJSON_FILE):raise FileNotFoundError(ZIPPER_GEOJSON_FILE)
 with open(ZIPPER_GEOJSON_FILE,'r',encoding='utf-8') as f:data=json.load(f)
 if data.get('type')!='FeatureCollection':raise ValueError('ZIPPER artifact must be a GeoJSON FeatureCollection')
 return data
def zipper_feature_collection():return _load_artifact() if os.path.exists(ZIPPER_GEOJSON_FILE) else live_zipper_feature_collection()
def clear_zipper_cache():_load_artifact.cache_clear();live_zipper_feature_collection.cache_clear()
@router.get('/geography/zipper')
def geography_zipper():
 try:return zipper_feature_collection()
 except Exception as exc:raise HTTPException(status_code=500,detail=f'ZIPPER geography unavailable: {exc}')
@router.get('/geography/zipper/status')
def geography_zipper_status():
 status=numbering_status();ready=os.path.exists(ZIPPER_GEOJSON_FILE);status.update({'layer':'ZIPPER','active_replacement':True,'artifact':os.path.basename(ZIPPER_GEOJSON_FILE),'artifact_ready':ready,'source':'generated_artifact' if ready else 'district_population_live_fallback'})
 try:
  if ready:status['zones']=len(_load_artifact().get('features',[]));status['ready']=True
  else:status.update(live_zipper_status())
 except Exception as exc:status['ready']=False;status['error']=str(exc)
 return status
