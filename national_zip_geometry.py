"""Locality-based national ZIP geometry with variable regional capacity.

Dense state regions receive 25 ZIP zones; standard regions receive 15. The
protected 21xxx postal region contains Entebbe plus Lake Victoria islands and
has 10 total ZIP zones. Existing Entebbe 21401-21405 assignments stay fixed;
21406-21410 cover island localities.
"""
from functools import lru_cache
import requests
from shapely.geometry import box, Point, mapping, shape
from shapely.ops import unary_union

from state_geometry import _state_geometries, DISTRICT_GEOJSON_URL
from state_district_registry import DISTRICT_TO_STATE
from postal_zones import REGIONS, ENTEBBE_BOUNDS

STATE_TO_POSTAL = {
    "KMP": "KLA", "LKV": "MSK", "NIL": "JIN", "WHS": "MBA", "ELG": "MBL",
    "NSV": "GUL", "WNL": "ARU", "EPL": "SOR", "KRM": "MOR", "ALB": "HOI",
}
ISLAND_DISTRICTS = {"Kalangala", "Buvuma"}


def _district_name(feature):
    p = feature.get("properties") or {}
    for key in ("name", "NAME", "district", "DISTRICT", "District"):
        if p.get(key): return str(p[key]).strip()
    raise ValueError("District feature has no recognized name property")

@lru_cache(maxsize=1)
def _district_geometries():
    r = requests.get(DISTRICT_GEOJSON_URL, timeout=30); r.raise_for_status()
    out = []
    for f in r.json().get("features", []):
        name = _district_name(f); code = DISTRICT_TO_STATE.get(name)
        if code: out.append((name, code, shape(f["geometry"])))
    return out


def _distance(a, b): return a.representative_point().distance(b.representative_point())

def _merge_to_target(geoms, target):
    clusters = list(geoms)
    while len(clusters) > target:
        best = None
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                a, b = clusters[i], clusters[j]
                touching = a.touches(b) or a.intersects(b) or a.distance(b) < 1e-8
                score = (0 if touching else 1, _distance(a, b), a.area + b.area)
                if best is None or score < best[0]: best = (score, i, j)
        _, i, j = best
        merged = unary_union([clusters[i], clusters[j]])
        clusters = [g for k, g in enumerate(clusters) if k not in (i, j)] + [merged]
    return clusters


def _bisect(geom):
    minx, miny, maxx, maxy = geom.bounds; pad = 2.0
    if (maxx-minx) >= (maxy-miny):
        mid=(minx+maxx)/2; a=geom.intersection(box(minx-pad,miny-pad,mid,maxy+pad)); b=geom.intersection(box(mid,miny-pad,maxx+pad,maxy+pad))
    else:
        mid=(miny+maxy)/2; a=geom.intersection(box(minx-pad,miny-pad,maxx+pad,mid)); b=geom.intersection(box(minx-pad,mid,maxx+pad,maxy+pad))
    if a.is_empty or b.is_empty: raise ValueError("Unable to subdivide local ZIP geometry")
    return a,b


def _expand_to_target(clusters, target):
    clusters=list(clusters)
    while len(clusters)<target:
        idx=max(range(len(clusters)), key=lambda i: clusters[i].area)
        a,b=_bisect(clusters.pop(idx)); clusters.extend([a,b])
    return clusters


def _sort_local(zones): return sorted(zones,key=lambda g:(-g.representative_point().y,g.representative_point().x))

def _entebbe_clip(kmp_geom):
    b=ENTEBBE_BOUNDS
    return kmp_geom.intersection(box(b["min_lon"],b["min_lat"],b["max_lon"],b["max_lat"]))

def _entebbe_city_zones(kmp_geom):
    enclave=_entebbe_clip(kmp_geom)
    if enclave.is_empty:return []
    b=ENTEBBE_BOUNDS
    west=enclave.intersection(box(b["min_lon"]-1,b["min_lat"]-1,32.445000,b["max_lat"]+1))
    katabi=enclave.intersection(box(32.445000,b["min_lat"]-1,32.460001,0.103221))
    kigungu=enclave.intersection(box(32.460001,b["min_lat"]-1,b["max_lon"]+1,0.044999))
    central=enclave.intersection(box(32.460001,0.044999,32.500006,0.090002))
    used=unary_union([g for g in (west,katabi,kigungu,central) if not g.is_empty]); airport=enclave.difference(used)
    return [("21401",central),("21402",west),("21403",airport),("21404",katabi),("21405",kigungu)]


def _island_zones(districts):
    islands=[g for name,_,g in districts if name in ISLAND_DISTRICTS]
    if not islands:return []
    clusters=_expand_to_target(islands,5) if len(islands)<5 else _merge_to_target(islands,5)
    clusters=_sort_local(clusters)
    return list(zip(REGIONS["ENT"]["zip_codes"][5:],clusters))

@lru_cache(maxsize=1)
def _zones():
    state_geoms={p["state_code"]:(p,g) for p,g in _state_geometries()}; districts=_district_geometries(); result={}
    island_union=unary_union([g for name,_,g in districts if name in ISLAND_DISTRICTS])
    for state_code,(props,state_geom) in state_geoms.items():
        region=STATE_TO_POSTAL[state_code]; zip_codes=REGIONS[region]["zip_codes"]; target=len(zip_codes)
        parts=[g for name,code,g in districts if code==state_code and name not in ISLAND_DISTRICTS]
        working=state_geom.difference(island_union)
        if state_code=="KMP":
            enclave=_entebbe_clip(state_geom); working=working.difference(enclave); parts=[g.difference(enclave) for g in parts]; parts=[g for g in parts if not g.is_empty]
        clusters=_merge_to_target(parts,target) if len(parts)>target else parts
        clusters=_expand_to_target(clusters,target) if len(clusters)<target else clusters
        clusters=_sort_local(clusters)
        assigned=[]; covered=None
        for geom in clusters:
            clipped=geom.intersection(working)
            if covered is not None: clipped=clipped.difference(covered)
            if not clipped.is_empty:
                assigned.append(clipped); covered=clipped if covered is None else unary_union([covered,clipped])
        if len(assigned)!=target: raise ValueError(f"Expected {target} ZIP zones for {state_code}, got {len(assigned)}")
        remainder=working.difference(unary_union(assigned))
        if not remainder.is_empty and remainder.area>1e-12:
            rp=remainder.representative_point(); nearest=min(range(target),key=lambda i:assigned[i].distance(rp)); assigned[nearest]=unary_union([assigned[nearest],remainder])
        result[state_code]={"postal_region":region,"state":props,"zones":list(zip(zip_codes,assigned))}
    return result


def zip_for_coordinate(latitude:float, longitude:float, state_code:str):
    point=Point(float(longitude),float(latitude))
    # Entebbe protected city first.
    for z,g in _entebbe_city_zones(dict((p["state_code"],g) for p,g in _state_geometries()).get("KMP")):
        if g.covers(point): return {"zip_code":z,"region":"ENT","name":""}
    # Lake Victoria islands share the Entebbe 21 prefix.
    for z,g in _island_zones(_district_geometries()):
        if g.covers(point): return {"zip_code":z,"region":"ENT","name":"Lake Victoria Islands"}
    state=_zones().get(state_code)
    if not state:return None
    matches=[z for z,g in state["zones"] if g.covers(point)]
    if not matches:return None
    return {"zip_code":sorted(matches)[0],"region":state["postal_region"],"name":""}


def zip_feature_collection():
    features=[]; kmp=dict((p["state_code"],g) for p,g in _state_geometries()).get("KMP")
    for z,g in _entebbe_city_zones(kmp):
        if not g.is_empty: features.append({"type":"Feature","properties":{"zip_code":z,"postal_region":"ENT","state_code":"KMP","state_name":"Entebbe","protected":True},"geometry":mapping(g)})
    for z,g in _island_zones(_district_geometries()):
        features.append({"type":"Feature","properties":{"zip_code":z,"postal_region":"ENT","state_code":"ISLANDS","state_name":"Lake Victoria Islands","protected":True},"geometry":mapping(g)})
    for state_code,state in _zones().items():
        p=state["state"]
        for z,g in state["zones"]: features.append({"type":"Feature","properties":{"zip_code":z,"postal_region":state["postal_region"],"state_code":state_code,"state_name":p["state_name"],"protected":False},"geometry":mapping(g)})
    return {"type":"FeatureCollection","features":features}


def validation_status():
    zones=_zones(); ent_count=len(_entebbe_city_zones(dict((p["state_code"],g) for p,g in _state_geometries()).get("KMP")))+len(_island_zones(_district_geometries()))
    return {"state_count":len(zones),"state_zip_zone_count":sum(len(v["zones"]) for v in zones.values()),"entebbe_islands_zone_count":ent_count,"display_zone_count":sum(len(v["zones"]) for v in zones.values())+ent_count,"zones_per_state":{k:len(v["zones"]) for k,v in zones.items()},"method":"district/locality-based variable density allocation"}
