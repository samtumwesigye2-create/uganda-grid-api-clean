"""Persistent manual ZIP polygons created from the admin map editor.

Manual geometry is authoritative for *where* a ZIP applies, but ZIP ownership is
not arbitrary: every postal region belongs to exactly one state. Admin drawing
can override automatic ZIP/state geometry inside the polygon, but it cannot move
a ZIP into another state's namespace.
"""
import json, os
from shapely.geometry import shape, mapping, Point
from postal_zones import REGIONS

BASE_DIR=os.path.dirname(os.path.abspath(__file__))
STORE=os.path.join(BASE_DIR,"manual_zip_assignments.json")

# Canonical ownership. ENT is a protected postal enclave geographically inside
# Kampala Metropolitan, so all 21xxx Entebbe reserve ZIPs remain owned by KMP.
REGION_TO_STATE={
    "KLA":"KMP",
    "JIN":"NIL",
    "MBA":"WHS",
    "MBL":"ELG",
    "GUL":"NSV",
    "ARU":"WNL",
    "SOR":"EPL",
    "MOR":"KRM",
    "HOI":"ALB",
    "MSK":"LKV",
    "ENT":"KMP",
}

def canonical_state_for_region(region):
    return REGION_TO_STATE.get(str(region or "").strip().upper())

def _canonicalize_item(item):
    x=dict(item)
    region=str(x.get("postal_region","")).strip().upper()
    owner=canonical_state_for_region(region)
    if owner:
        x["postal_region"]=region
        x["state_code"]=owner
        x["state_forced_by_zip"]=True
    return x

def _load():
    try:
        with open(STORE,"r",encoding="utf-8") as f:
            return [_canonicalize_item(x) for x in json.load(f)]
    except Exception:return []

def _save(items):
    with open(STORE,"w",encoding="utf-8") as f:json.dump([_canonicalize_item(x) for x in items],f,ensure_ascii=False,indent=2)

def list_assignments(): return _load()

def available_reserves(region):
    region=str(region or "").strip().upper()
    r=REGIONS.get(region)
    if not r:return []
    used={x.get("zip_code") for x in _load()}
    return [z for z in r.get("reserve_zip_codes",[]) if z not in used]

def create_assignment(zip_code,region,state_code,name,geometry):
    region=str(region or "").strip().upper()
    zip_code=str(zip_code or "").strip()
    r=REGIONS.get(region)
    if not r or zip_code not in r.get("reserve_zip_codes",[]):
        raise ValueError("ZIP is not a reserve code for this region")
    if zip_code not in available_reserves(region):
        raise ValueError("Reserve ZIP already assigned")

    owner=canonical_state_for_region(region)
    if not owner:
        raise ValueError("Postal region has no registered state owner")

    supplied=str(state_code or "").strip().upper()
    if supplied and supplied!=owner:
        raise ValueError(f"ZIP {zip_code} belongs to state {owner} and cannot be assigned to {supplied}")

    geom=shape(geometry)
    if geom.is_empty or not geom.is_valid or geom.geom_type not in {"Polygon","MultiPolygon"}:
        raise ValueError("Valid polygon geometry required")

    item={
        "zip_code":zip_code,
        "postal_region":region,
        "state_code":owner,
        "name":name.strip() or zip_code,
        "geometry":mapping(geom),
        "manual":True,
        "state_forced_by_zip":True,
    }
    items=_load();items.append(item);_save(items);return item

def delete_assignment(zip_code):
    items=_load();new=[x for x in items if x.get("zip_code")!=zip_code]
    if len(new)==len(items):return False
    _save(new);return True

def match_point(latitude,longitude):
    p=Point(float(longitude),float(latitude))
    for item in reversed(_load()):
        try:
            if shape(item["geometry"]).covers(p):return _canonicalize_item(item)
        except Exception:pass
    return None

def feature_collection():
    return {"type":"FeatureCollection","features":[{"type":"Feature","properties":{k:v for k,v in x.items() if k!="geometry"},"geometry":x["geometry"]} for x in _load()]}
