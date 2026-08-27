"""Locality-based national ZIP geometry.

Each state is divided into ten compact zones using district polygons as the
primary building blocks. States with more than ten districts merge neighboring
districts; states with fewer than ten districts subdivide their largest local
areas. This avoids state-wide longitude strips.

Entebbe is a protected postal enclave inside Kampala Metropolitan. Its existing
21401-21405 classifier is rendered separately and removed from Kampala's 20xxx
state ZIP polygons, so those codes are never mixed into another state.
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


def _district_name(feature):
    p = feature.get("properties") or {}
    for key in ("name", "NAME", "district", "DISTRICT", "District"):
        if p.get(key): return str(p[key]).strip()
    raise ValueError("District feature has no recognized name property")


@lru_cache(maxsize=1)
def _district_geometries():
    r = requests.get(DISTRICT_GEOJSON_URL, timeout=30)
    r.raise_for_status()
    result = []
    for f in r.json().get("features", []):
        name = _district_name(f)
        code = DISTRICT_TO_STATE.get(name)
        if code:
            result.append((name, code, shape(f["geometry"])))
    return result


def _distance(a, b):
    return a.representative_point().distance(b.representative_point())


def _merge_to_ten(geoms):
    clusters = list(geoms)
    while len(clusters) > 10:
        best = None
        # Prefer true neighbors so merged ZIPs follow district/local boundaries.
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                a, b = clusters[i], clusters[j]
                touching = a.touches(b) or a.intersects(b) or a.distance(b) < 1e-8
                score = (0 if touching else 1, _distance(a, b), a.area + b.area)
                if best is None or score < best[0]:
                    best = (score, i, j)
        _, i, j = best
        merged = unary_union([clusters[i], clusters[j]])
        clusters = [g for k, g in enumerate(clusters) if k not in (i, j)] + [merged]
    return clusters


def _bisect(geom):
    minx, miny, maxx, maxy = geom.bounds
    pad = 2.0
    # Split along the longer geographic axis, producing exactly two groups.
    if (maxx - minx) >= (maxy - miny):
        mid = (minx + maxx) / 2.0
        a = geom.intersection(box(minx - pad, miny - pad, mid, maxy + pad))
        b = geom.intersection(box(mid, miny - pad, maxx + pad, maxy + pad))
    else:
        mid = (miny + maxy) / 2.0
        a = geom.intersection(box(minx - pad, miny - pad, maxx + pad, mid))
        b = geom.intersection(box(minx - pad, mid, maxx + pad, maxy + pad))
    if a.is_empty or b.is_empty:
        # Orthogonal fallback.
        mid = (minx + maxx) / 2.0
        a = geom.intersection(box(minx - pad, miny - pad, mid, maxy + pad))
        b = geom.intersection(box(mid, miny - pad, maxx + pad, maxy + pad))
    if a.is_empty or b.is_empty:
        raise ValueError("Unable to subdivide local ZIP geometry")
    return a, b


def _expand_to_ten(clusters):
    clusters = list(clusters)
    while len(clusters) < 10:
        idx = max(range(len(clusters)), key=lambda i: clusters[i].area)
        target = clusters.pop(idx)
        a, b = _bisect(target)
        clusters.extend([a, b])
    return clusters


def _sort_local(zones):
    # Stable north-to-south, then west-to-east numbering.
    return sorted(zones, key=lambda g: (-g.representative_point().y, g.representative_point().x))


def _entebbe_clip(kmp_geom):
    b = ENTEBBE_BOUNDS
    return kmp_geom.intersection(box(b["min_lon"], b["min_lat"], b["max_lon"], b["max_lat"]))


def _entebbe_zones(kmp_geom):
    enclave = _entebbe_clip(kmp_geom)
    if enclave.is_empty: return []
    b = ENTEBBE_BOUNDS
    west = enclave.intersection(box(b["min_lon"] - 1, b["min_lat"] - 1, 32.445000, b["max_lat"] + 1))
    katabi = enclave.intersection(box(32.445000, b["min_lat"] - 1, 32.460001, 0.103221))
    kigungu = enclave.intersection(box(32.460001, b["min_lat"] - 1, b["max_lon"] + 1, 0.044999))
    central = enclave.intersection(box(32.460001, 0.044999, 32.500006, 0.090002))
    used = unary_union([g for g in (west, katabi, kigungu, central) if not g.is_empty])
    airport = enclave.difference(used)
    return [("21401", central), ("21402", west), ("21403", airport), ("21404", katabi), ("21405", kigungu)]


@lru_cache(maxsize=1)
def _zones():
    state_geoms = {props["state_code"]: (props, geom) for props, geom in _state_geometries()}
    districts = _district_geometries()
    result = {}

    for state_code, (props, state_geom) in state_geoms.items():
        postal_region = STATE_TO_POSTAL[state_code]
        zip_codes = REGIONS[postal_region]["zip_codes"]
        district_parts = [g for _, code, g in districts if code == state_code]

        working_state = state_geom
        if state_code == "KMP":
            enclave = _entebbe_clip(state_geom)
            working_state = state_geom.difference(enclave)
            district_parts = [g.difference(enclave) for g in district_parts]
            district_parts = [g for g in district_parts if not g.is_empty]

        clusters = _merge_to_ten(district_parts) if len(district_parts) > 10 else district_parts
        clusters = _expand_to_ten(clusters) if len(clusters) < 10 else clusters
        clusters = _sort_local(clusters)

        # Force exact state coverage and remove numerical overlaps sequentially.
        assigned = []
        covered = None
        for geom in clusters:
            clipped = geom.intersection(working_state)
            if covered is not None:
                clipped = clipped.difference(covered)
            if not clipped.is_empty:
                assigned.append(clipped)
                covered = clipped if covered is None else unary_union([covered, clipped])
        if len(assigned) != 10:
            raise ValueError(f"Expected 10 ZIP zones for {state_code}, got {len(assigned)}")
        union = unary_union(assigned)
        remainder = working_state.difference(union)
        if not remainder.is_empty and remainder.area > 1e-12:
            # Attach tiny topology remnants to nearest local zone.
            rp = remainder.representative_point()
            nearest = min(range(10), key=lambda i: assigned[i].distance(rp))
            assigned[nearest] = unary_union([assigned[nearest], remainder])
            union = unary_union(assigned)
        if working_state.difference(union).area > 1e-10:
            raise ValueError(f"ZIP coverage gap remains in {state_code}")

        result[state_code] = {
            "postal_region": postal_region,
            "state": props,
            "zones": list(zip(zip_codes, assigned)),
        }
    return result


def zip_for_coordinate(latitude: float, longitude: float, state_code: str):
    point = Point(float(longitude), float(latitude))
    state = _zones().get(state_code)
    if not state: return None
    matches = [z for z, g in state["zones"] if g.covers(point)]
    if not matches: return None
    return {"zip_code": sorted(matches)[0], "region": state["postal_region"], "name": ""}


def zip_feature_collection():
    features = []
    kmp_geom = dict((p["state_code"], g) for p, g in _state_geometries()).get("KMP")
    if kmp_geom is not None:
        for zip_code, geom in _entebbe_zones(kmp_geom):
            if geom.is_empty: continue
            features.append({"type":"Feature","properties":{"zip_code":zip_code,"postal_region":"ENT","state_code":"KMP","state_name":"Entebbe protected postal enclave","protected":True},"geometry":mapping(geom)})

    for state_code, state in _zones().items():
        props = state["state"]
        for zip_code, geom in state["zones"]:
            features.append({"type":"Feature","properties":{"zip_code":zip_code,"postal_region":state["postal_region"],"state_code":state_code,"state_name":props["state_name"],"protected":False},"geometry":mapping(geom)})
    return {"type":"FeatureCollection","features":features}


def validation_status():
    zones = _zones()
    return {
        "state_count": len(zones),
        "state_zip_zone_count": sum(len(v["zones"]) for v in zones.values()),
        "protected_entebbe_zone_count": 5,
        "display_zone_count": 105,
        "zones_per_state": {k: len(v["zones"]) for k,v in zones.items()},
        "method": "district/locality-based; no state-wide longitude strips",
    }
