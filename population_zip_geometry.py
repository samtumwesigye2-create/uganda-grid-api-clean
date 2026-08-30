"""Population ZIP geometry registry for UGAMAP.

Only publishes cluster geometry when real source geometry has been supplied.
Population-only clustering must never fabricate map boundaries.
"""
import json
import os
from functools import lru_cache
from shapely.geometry import Point, shape

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "population_zip_clusters.geojson")


def _empty():
    return {"type": "FeatureCollection", "features": []}


@lru_cache(maxsize=1)
def population_zip_feature_collection():
    if not os.path.exists(DATA_FILE):
        return _empty()
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return _empty()
    if data.get("type") != "FeatureCollection":
        return _empty()
    features = []
    for feature in data.get("features", []):
        props = feature.get("properties") or {}
        geom = feature.get("geometry")
        zip_code = str(props.get("zip_code", "")).zfill(5)
        population = props.get("population")
        if not geom or len(zip_code) != 5 or not zip_code.isdigit():
            continue
        if population is None:
            continue
        feature = dict(feature)
        feature["properties"] = {**props, "zip_code": zip_code, "geometry_source": "population_cluster"}
        features.append(feature)
    return {"type": "FeatureCollection", "features": features}


def population_zip_for_coordinate(latitude: float, longitude: float):
    point = Point(float(longitude), float(latitude))
    matches = []
    for feature in population_zip_feature_collection()["features"]:
        try:
            if shape(feature["geometry"]).covers(point):
                matches.append(feature["properties"])
        except Exception:
            continue
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        return {"ambiguous": True, "matches": matches}
    return None


def status():
    fc = population_zip_feature_collection()
    population = sum(int((f.get("properties") or {}).get("population", 0)) for f in fc["features"])
    return {"geometry_ready": bool(fc["features"]), "cluster_polygons": len(fc["features"]), "population_covered": population, "source": "population_zip_clusters.geojson"}
