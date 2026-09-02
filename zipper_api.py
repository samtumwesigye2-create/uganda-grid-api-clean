"""FastAPI router for the active population-balanced ZIPPER layer.

The production map should serve a pre-generated GeoJSON file rather than
recomputing thousands of polygons on every request. This router deliberately
fails clearly when the generated artifact is not present yet.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache

from fastapi import APIRouter, HTTPException

from zipper_numbering import numbering_status

router = APIRouter(tags=["ZIPPER"])
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ZIPPER_GEOJSON_FILE = os.environ.get(
    "ZIPPER_GEOJSON_FILE",
    os.path.join(BASE_DIR, "zipper_zones.geojson"),
)


@lru_cache(maxsize=1)
def _load_zipper_geojson():
    if not os.path.exists(ZIPPER_GEOJSON_FILE):
        raise FileNotFoundError(ZIPPER_GEOJSON_FILE)
    with open(ZIPPER_GEOJSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    if data.get("type") != "FeatureCollection":
        raise ValueError("ZIPPER artifact must be a GeoJSON FeatureCollection")
    return data


def clear_zipper_cache():
    _load_zipper_geojson.cache_clear()


@router.get("/geography/zipper")
def geography_zipper():
    """Return the active replacement ZIPPER layer."""
    try:
        return _load_zipper_geojson()
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="ZIPPER geography has not been generated yet",
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail=f"Invalid ZIPPER geography: {exc}")


@router.get("/geography/zipper/status")
def geography_zipper_status():
    status = numbering_status()
    status.update({
        "layer": "ZIPPER",
        "active_replacement": True,
        "artifact": os.path.basename(ZIPPER_GEOJSON_FILE),
        "artifact_ready": os.path.exists(ZIPPER_GEOJSON_FILE),
    })
    if status["artifact_ready"]:
        try:
            fc = _load_zipper_geojson()
            status["zones"] = len(fc.get("features", []))
        except Exception as exc:
            status["artifact_valid"] = False
            status["error"] = str(exc)
        else:
            status["artifact_valid"] = True
    return status
