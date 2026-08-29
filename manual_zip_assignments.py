"""Persistent manual ZIP polygons created from the admin map editor."""
import json, os
from shapely.geometry import shape, mapping, Point
from postal_zones import REGIONS
from state_regions import STATE_REGIONS

BASE_DIR=os.path.dirname(os.path.abspath(__file__))
STORE=os.path.join(BASE_DIR,"manual_zip_assignments.json")

def _load():
    try:
        with open(STORE,"r",encoding="utf-8") as f:return json.load(f)
    except Exception:return []

def _save(items):
    with open(STORE,"w",encoding="utf-8") as f:json.dump(items,f,ensure_ascii=False,indent=2)

def list_assignments(): return _load()

def available_reserves(region):
    r=REGIONS.get(region)
    if not r:return []
    used={x.get("zip_code") for x in _load()}
    return [z for z in r.get("reserve_zip_codes",[]) if z not in used]

def create_assignment(zip_code,region,state_code,name,geometry):
    r=REGIONS.get(region)
    state_code=str(state_code or "").strip().upper()
    if not r or zip_code not in r.get("reserve_zip_codes",[]): raise ValueError("ZIP is not a reserve code for this region")
    if state_code not in STATE_REGIONS: raise ValueError("Invalid state code for manual ZIP override")
    if zip_code not in available_reserves(region): raise ValueError("Reserve ZIP already assigned")
    geom=shape(geometry)
    if geom.is_empty or not geom.is_valid or geom.geom_type not in {"Polygon","MultiPolygon"}: raise ValueError("Valid polygon geometry required")
    item={"zip_code":zip_code,"postal_region":region,"state_code":state_code,"name":name.strip() or zip_code,"geometry":mapping(geom),"manual":True,"forced_override":True}
    items=_load();items.append(item);_save(items);return item

def delete_assignment(zip_code):
    items=_load();new=[x for x in items if x.get("zip_code")!=zip_code]
    if len(new)==len(items):return False
    _save(new);return True

def match_point(latitude,longitude):
    p=Point(float(longitude),float(latitude))
    for item in reversed(_load()):
        try:
            if shape(item["geometry"]).covers(p):return item
        except Exception:pass
    return None

def feature_collection():
    return {"type":"FeatureCollection","features":[{"type":"Feature","properties":{k:v for k,v in x.items() if k!="geometry"},"geometry":x["geometry"]} for x in _load()]}
