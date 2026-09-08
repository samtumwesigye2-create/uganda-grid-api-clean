"""UGASHIP -> UNG-ZIPPER live destination bridge."""
from __future__ import annotations

import os
import requests
from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["UGASHIP ZIPPER"])
ZIPPER_API_URL = os.environ.get("ZIPPER_API_URL", "https://ung-zipper-production.up.railway.app").rstrip("/")
ZIPPER_TIMEOUT = float(os.environ.get("ZIPPER_TIMEOUT_SECONDS", "8"))


def _get(path: str):
    try:
        r = requests.get(f"{ZIPPER_API_URL}{path}", timeout=ZIPPER_TIMEOUT)
    except requests.RequestException as exc:
        raise HTTPException(status_code=503, detail=f"UNG-ZIPPER unavailable: {type(exc).__name__}")
    if r.status_code == 404:
        raise HTTPException(status_code=404, detail="ZIP code not found")
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"UNG-ZIPPER returned HTTP {r.status_code}")
    try:
        return r.json()
    except ValueError:
        raise HTTPException(status_code=502, detail="UNG-ZIPPER returned invalid JSON")


@router.get("/ship/destination/{code}")
def resolve_shipping_destination(code: str):
    """Resolve a five-digit shipping destination from the national ZIP registry."""
    validation = _get(f"/zipper/validate/{code}")
    if not validation.get("valid"):
        raise HTTPException(status_code=404, detail="ZIP code is not assigned")
    resolution = _get(f"/zipper/{code}")
    return {
        "status": "ok",
        "source": "UNG-ZIPPER",
        "code": resolution.get("code"),
        "district": resolution.get("district"),
        "name": resolution.get("name"),
        "area_type": resolution.get("area_type"),
        "population_covered": resolution.get("population_covered"),
        "latitude": resolution.get("latitude"),
        "longitude": resolution.get("longitude"),
        "protected": resolution.get("protected"),
        "validation": validation,
    }


@router.get("/ship/integration/zipper/health")
def shipping_zipper_health():
    """End-to-end acceptance for UGASHIP -> UNG-ZIPPER destination resolution."""
    ready = _get("/ready")
    rows = _get("/zipper/?limit=1")
    if not isinstance(rows, list) or not rows:
        raise HTTPException(status_code=503, detail="UNG-ZIPPER registry is empty")
    code = str(rows[0].get("code") or "").strip()
    if not code:
        raise HTTPException(status_code=503, detail="UNG-ZIPPER sample has no code")
    validation = _get(f"/zipper/validate/{code}")
    resolution = _get(f"/zipper/{code}")
    if not validation.get("valid") or str(resolution.get("code")) != code:
        raise HTTPException(status_code=503, detail="UGASHIP ZIP validation/resolution mismatch")
    return {
        "status": "ok",
        "integration": "UGASHIP->UNG-ZIPPER",
        "registry_records": ready.get("records"),
        "sample_code": code,
        "district": resolution.get("district"),
        "area_type": resolution.get("area_type"),
        "population_covered": resolution.get("population_covered"),
        "latitude": resolution.get("latitude"),
        "longitude": resolution.get("longitude"),
        "validation": validation,
        "resolution_ok": True,
    }
