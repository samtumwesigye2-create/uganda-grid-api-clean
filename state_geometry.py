"""Runtime loader/resolver for Uganda National Grid state polygons.

On first use, fetches the pinned public district GeoJSON, runs the strict
136-district reconciliation/dissolve validator, and caches the resulting ten
state geometries in memory. Fails closed if the source or geometry is invalid.

Manual ZIP polygons created by an authorized admin are authoritative overrides:
coordinates inside one are treated as belonging to the state selected on that
manual assignment, even when the base dissolved geometry says otherwise.
"""
from functools import lru_cache
import requests
from shapely.geometry import Point, shape

from build_state_polygons import build
from manual_zip_assignments import match_point as match_manual_zip
from state_regions import STATE_REGIONS

DISTRICT_GEOJSON_URL = (
    "https://raw.githubusercontent.com/kakandemanwell/uganda/"
    "master/dist/geo/districts.geojson"
)


@lru_cache(maxsize=1)
def state_feature_collection():
    response = requests.get(DISTRICT_GEOJSON_URL, timeout=30)
    response.raise_for_status()
    return build(response.json())


@lru_cache(maxsize=1)
def _state_geometries():
    fc = state_feature_collection()
    return [(f["properties"], shape(f["geometry"])) for f in fc["features"]]


def _manual_override_state(latitude: float, longitude: float):
    item = match_manual_zip(latitude, longitude)
    if not item:
        return None
    code = str(item.get("state_code", "")).strip().upper()
    meta = STATE_REGIONS.get(code)
    if not meta:
        return None
    return {
        "state_code": code,
        "state_name": meta["name"],
        "grid_prefix": meta["grid_prefix"],
        "postal_prefix": meta["postal_prefix"],
        "postal_center": meta["postal_center"],
        "manual_override": True,
        "override_zip_code": item.get("zip_code"),
        "override_postal_region": item.get("postal_region"),
        "override_name": item.get("name", ""),
    }


def state_for_coordinate(latitude: float, longitude: float):
    """Return the effective state for lon/lat.

    Authorized manual ZIP polygons take precedence over the base state geometry.
    """
    override = _manual_override_state(latitude, longitude)
    if override:
        return override

    point = Point(float(longitude), float(latitude))
    matches = [props for props, geom in _state_geometries() if geom.covers(point)]
    if len(matches) > 1:
        return {"ambiguous": True, "states": matches}
    return matches[0] if matches else None


def geometry_status():
    fc = state_feature_collection()
    return fc["properties"]
