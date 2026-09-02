"""Population ZIP geometry registry for UGAMAP."""
import json, os
from functools import lru_cache
from shapely.geometry import Point, shape
BASE_DIR=os.path.dirname(os.path.abspath(__file__))
DATA_FILE=os.path.join(BASE_DIR,"population_zip_clusters.geojson")
def _empty():return {"type":"FeatureCollection","features":[]}
@lru_cache(maxsize=1)
def population_zip_feature_collection():
 if not os.path.exists(DATA_FILE):return _empty()
 try:
  with open(DATA_FILE,"r",encoding="utf-8") as f:data=json.load(f)
 except Exception:return _empty()
 if data.get("type")!="FeatureCollection":return _empty()
 out=[]
 for feature in data.get("features",[]):
  p=feature.get("properties") or {};g=feature.get("geometry");z=str(p.get("zip_code","")).zfill(5)
  if not g or not z.isdigit() or len(z)!=5 or p.get("population") is None:continue
  item=dict(feature);item["properties"]={**p,"zip_code":z,"geometry_source":"population_cluster"};out.append(item)
 return {"type":"FeatureCollection","features":out}
def population_zip_for_coordinate(latitude,longitude):
 pt=Point(float(longitude),float(latitude));matches=[]
 for f in population_zip_feature_collection()["features"]:
  try:
   if shape(f["geometry"]).covers(pt):matches.append(f["properties"])
  except Exception:pass
 return matches[0] if len(matches)==1 else ({"ambiguous":True,"matches":matches} if len(matches)>1 else None)
def status():
 fc=population_zip_feature_collection();return {"geometry_ready":bool(fc["features"]),"cluster_polygons":len(fc["features"]),"population_covered":sum(int((f.get("properties") or {}).get("population",0)) for f in fc["features"]),"source":"population_zip_clusters.geojson"}
