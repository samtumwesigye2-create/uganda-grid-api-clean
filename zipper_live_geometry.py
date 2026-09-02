"""Live fallback geometry for the active population-balanced ZIPPER system.

District population determines how many ZIPPER zones each district receives.
Inside each district, geometry is split by area, so population values remain
estimates until finer parish/census population geometry replaces this fallback.
"""
from functools import lru_cache
import requests
from shapely.geometry import box, mapping, shape

from state_geometry import DISTRICT_GEOJSON_URL
from state_district_registry import state_for_district
from district_population import population_for_district
from zipper_numbering import assign_state_block_ids
from zip_population_policy import targets_for


def _district_name(feature):
    p = feature.get("properties") or {}
    for key in ("name", "NAME", "district", "DISTRICT", "District"):
        if p.get(key):
            return str(p[key]).strip()
    return ""


def _bisect(geom):
    minx, miny, maxx, maxy = geom.bounds
    pad = 1.0
    if (maxx - minx) >= (maxy - miny):
        mid = (minx + maxx) / 2
        a = geom.intersection(box(minx - pad, miny - pad, mid, maxy + pad))
        b = geom.intersection(box(mid, miny - pad, maxx + pad, maxy + pad))
    else:
        mid = (miny + maxy) / 2
        a = geom.intersection(box(minx - pad, miny - pad, maxx + pad, mid))
        b = geom.intersection(box(minx - pad, mid, maxx + pad, maxy + pad))
    return a, b


def _split_to_count(geom, count):
    parts = [geom]
    while len(parts) < count:
        idx = max(range(len(parts)), key=lambda i: parts[i].area)
        src = parts.pop(idx)
        a, b = _bisect(src)
        if a.is_empty or b.is_empty:
            parts.append(src)
            break
        parts.extend([a, b])
    return parts


@lru_cache(maxsize=1)
def live_zipper_feature_collection():
    r = requests.get(DISTRICT_GEOJSON_URL, timeout=45)
    r.raise_for_status()
    zones = []

    for feature in r.json().get("features", []):
        district = _district_name(feature)
        if not district or not state_for_district(district):
            continue

        pop = population_for_district(district)
        if pop <= 0:
            continue

        policy = targets_for(district)
        target = policy["target"]
        count = max(1, int(round(pop / target)))
        geom = shape(feature.get("geometry"))
        if geom.is_empty:
            continue

        parts = _split_to_count(geom, count)
        total_area = sum(max(p.area, 0.0) for p in parts) or 1.0
        for part in parts:
            est = max(1, int(round(pop * (part.area / total_area))))
            zones.append({
                "district": district,
                "population": est,
                "population_min": policy["minimum"],
                "population_target": target,
                "population_max": policy["maximum"],
                "density_class": policy["density_class"],
                "geometry_status": "district_population_area_estimate",
                "layer": "ZIPPER",
                "geometry": part,
            })

    zones = assign_state_block_ids(zones)
    features = []
    for z in zones:
        features.append({
            "type": "Feature",
            "properties": {
                "zip_code": z["zipper_id"],
                "zipper_id": z["zipper_id"],
                "district": z["district"],
                "state_code": z["state_code"],
                "population": z["population"],
                "population_min": z["population_min"],
                "population_target": z["population_target"],
                "population_max": z["population_max"],
                "density_class": z["density_class"],
                "geometry_status": z["geometry_status"],
                "layer": "ZIPPER",
            },
            "geometry": mapping(z["geometry"]),
        })

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "layer": "ZIPPER",
            "source": "district_population_live_fallback",
            "population_geometry": "estimated_within_district",
            "policy": "active_replacement",
            "urban_range": [3000, 6000],
            "rural_range": [2000, 4500],
        },
    }


def live_zipper_status():
    fc = live_zipper_feature_collection()
    return {
        "ready": True,
        "zones": len(fc.get("features", [])),
        "source": "district_population_live_fallback",
        "policy": "active_replacement",
    }
