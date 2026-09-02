"""Lookup API for the active five-digit ZIPPER geography."""
from functools import lru_cache

from fastapi import APIRouter, HTTPException
from shapely.geometry import shape

from zipper_live_geometry import live_zipper_feature_collection

router = APIRouter(tags=["ZIPPER Search"])


@lru_cache(maxsize=1)
def _lookup_index():
    index = {}
    fc = live_zipper_feature_collection()
    for feature in fc.get("features", []):
        props = feature.get("properties") or {}
        code = str(props.get("zipper_id") or props.get("zip_code") or "").strip()
        if len(code) != 5 or not code.isdigit():
            continue
        geom = shape(feature.get("geometry"))
        if geom.is_empty:
            continue
        point = geom.representative_point()
        index[code] = {
            "zipper_id": code,
            "zip_code": code,
            "grid_id": code,
            "district": props.get("district") or "",
            "state_code": props.get("state_code") or "",
            "population": props.get("population"),
            "latitude": float(point.y),
            "longitude": float(point.x),
            "address": "ZIPPER " + code + (" — " + str(props.get("district")) if props.get("district") else ""),
        }
    return index


@router.get("/zipper/lookup/{code}")
def lookup_zipper(code: str):
    value = str(code or "").strip()
    if len(value) != 5 or not value.isdigit():
        raise HTTPException(status_code=400, detail="ZIPPER must be exactly five digits")
    item = _lookup_index().get(value)
    if not item:
        raise HTTPException(status_code=404, detail="ZIPPER not found")
    return item


@router.get("/zipper/search")
def search_zipper(q: str):
    value = str(q or "").strip()
    if len(value) != 5 or not value.isdigit():
        return {"count": 0, "results": []}
    item = _lookup_index().get(value)
    return {"count": 1 if item else 0, "results": [item] if item else []}
