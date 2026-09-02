"""FastAPI router for the active population-balanced ZIPPER layer.

A committed/generated GeoJSON artifact is preferred. Until that finer artifact
exists, UGAMAP serves the live district-population fallback so the map has an
active ZIPPER layer instead of no ZIPPER at all.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache

from fastapi import APIRouter, HTTPException

from zipper_numbering import numbering_status
from zipper_live_geometry import live_zipper_feature_collection, live_zipper_status
from orders import router as orders_router
from yard import router as yard_router

router = APIRouter(tags=["ZIPPER"])
router.include_router(orders_router)
router.include_router(yard_router)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ZIPPER_GEOJSON_FILE = os.environ.get(
    "ZIPPER_GEOJSON_FILE",
    os.path.join(BASE_DIR, "zipper_zones.geojson"),
)


@lru_cache(maxsize=1)
def _load_artifact():
    if not os.path.exists(ZIPPER_GEOJSON_FILE):
        raise FileNotFoundError(ZIPPER_GEOJSON_FILE)
    with open(ZIPPER_GEOJSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    if data.get("type") != "FeatureCollection":
        raise ValueError("ZIPPER artifact must be a GeoJSON FeatureCollection")
    return data


def zipper_feature_collection():
    if os.path.exists(ZIPPER_GEOJSON_FILE):
        return _load_artifact()
    return live_zipper_feature_collection()


def clear_zipper_cache():
    _load_artifact.cache_clear()
    live_zipper_feature_collection.cache_clear()


@router.get("/geography/zipper")
def geography_zipper():
    try:
        return zipper_feature_collection()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"ZIPPER geography unavailable: {exc}")


@router.get("/geography/zipper/status")
def geography_zipper_status():
    status = numbering_status()
    artifact_ready = os.path.exists(ZIPPER_GEOJSON_FILE)
    status.update({
        "layer": "ZIPPER",
        "active_replacement": True,
        "artifact": os.path.basename(ZIPPER_GEOJSON_FILE),
        "artifact_ready": artifact_ready,
        "source": "generated_artifact" if artifact_ready else "district_population_live_fallback",
    })
    try:
        if artifact_ready:
            fc = _load_artifact()
            status["zones"] = len(fc.get("features", []))
            status["ready"] = True
        else:
            status.update(live_zipper_status())
    except Exception as exc:
        status["ready"] = False
        status["error"] = str(exc)
    return status