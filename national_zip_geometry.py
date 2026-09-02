"""Compatibility bridge for the active population-balanced ZIPPER system.

The retired national ZIP geometry implementation used fixed regional ZIP pools
and special Entebbe/island geometry. The public app still imports
``zip_feature_collection`` and ``validation_status`` from this module, so those
names now delegate to the active ZIPPER artifact without keeping a second ZIP
layer alive.
"""
from __future__ import annotations

from shapely.geometry import Point, shape

from zipper_api import geography_zipper, geography_zipper_status


def zip_feature_collection():
    """Serve the active ZIPPER GeoJSON through the existing /geography/zips API."""
    return geography_zipper()


def validation_status():
    """Return active ZIPPER status through the existing geography status API."""
    status = geography_zipper_status()
    return {
        **status,
        "method": "population-balanced ZIPPER allocation",
        "retired_legacy_zip_geometry": True,
    }


def zip_for_coordinate(latitude: float, longitude: float, state_code: str = ""):
    """Resolve a coordinate against the generated ZIPPER polygons.

    ``state_code`` is accepted for backward compatibility but the generated
    polygon itself is authoritative.
    """
    point = Point(float(longitude), float(latitude))
    fc = geography_zipper()
    matches = []
    for feature in fc.get("features", []):
        geometry = feature.get("geometry")
        if not geometry:
            continue
        try:
            if shape(geometry).covers(point):
                matches.append(feature)
        except Exception:
            continue
    if not matches:
        return None

    def _code(feature):
        props = feature.get("properties") or {}
        return str(props.get("zipper_id") or props.get("zip_code") or "99999")

    feature = sorted(matches, key=_code)[0]
    props = feature.get("properties") or {}
    code = str(props.get("zipper_id") or props.get("zip_code") or "").zfill(5)
    return {
        "zip_code": code,
        "zipper_id": code,
        "name": props.get("source_parish") or props.get("subcounty") or props.get("district") or "",
        "region": props.get("district") or "",
        "district": props.get("district") or "",
        "state_code": props.get("state_code") or state_code or "",
        "population": props.get("population"),
        "density_class": props.get("density_class"),
        "national_zip": True,
        "zipper": True,
    }
