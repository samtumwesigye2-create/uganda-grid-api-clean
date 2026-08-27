"""Runtime loader/resolver for Uganda National Grid state polygons.

On first use, fetches the pinned public district GeoJSON, runs the strict
136-district reconciliation/dissolve validator, and caches the resulting ten
state geometries in memory. Fails closed if the source or geometry is invalid.
"""
from functools import lru_cache
import requests
from shapely.geometry import Point, shape

from build_state_polygons import build

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


def state_for_coordinate(latitude: float, longitude: float):
    """Return the unique state containing lon/lat, or None outside coverage."""
    point = Point(float(longitude), float(latitude))
    matches = [props for props, geom in _state_geometries() if geom.covers(point)]
    if len(matches) > 1:
        # A point exactly on a shared state boundary is ambiguous by geometry.
        # Do not silently assign it to whichever polygon happens to be first.
        return {"ambiguous": True, "states": matches}
    return matches[0] if matches else None


def geometry_status():
    fc = state_feature_collection()
    return fc["properties"]
