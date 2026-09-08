"""Map/search bridge for the active five-digit UNG-ZIPPER registry."""
from __future__ import annotations

import os
import requests
from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["ZIPPER Search"])
ZIPPER_API_URL = os.environ.get("ZIPPER_API_URL", "https://ung-zipper-production.up.railway.app").rstrip("/")
ZIPPER_TIMEOUT = float(os.environ.get("ZIPPER_TIMEOUT_SECONDS", "8"))


def _state_code(flag: str | None) -> str:
    for part in str(flag or "").split(";"):
        part = part.strip()
        if part.startswith("state:"):
            return part.split(":", 1)[1].strip()
    return ""


def _resolve_remote(code: str) -> dict:
    try:
        r = requests.get(f"{ZIPPER_API_URL}/zipper/{code}", timeout=ZIPPER_TIMEOUT, headers={"Accept": "application/json"})
    except requests.RequestException as exc:
        raise HTTPException(status_code=503, detail=f"UNG-ZIPPER unavailable: {type(exc).__name__}")
    if r.status_code == 404:
        raise HTTPException(status_code=404, detail="ZIPPER not found")
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"UNG-ZIPPER returned HTTP {r.status_code}")
    try:
        record = r.json()
    except ValueError:
        raise HTTPException(status_code=502, detail="UNG-ZIPPER returned invalid JSON")

    lat = record.get("latitude")
    lon = record.get("longitude")
    if lat is None or lon is None:
        raise HTTPException(status_code=502, detail="ZIPPER has no map coordinates")

    district = str(record.get("district") or record.get("name") or "")
    return {
        "zipper_id": str(record.get("code") or code).zfill(5),
        "zip_code": str(record.get("code") or code).zfill(5),
        "grid_id": str(record.get("code") or code).zfill(5),
        "district": district,
        "state_code": _state_code(record.get("flag")),
        "population": record.get("population_covered"),
        "latitude": float(lat),
        "longitude": float(lon),
        "address": "ZIPPER " + str(record.get("code") or code).zfill(5) + (" — " + district if district else ""),
        "source": "UNG-ZIPPER",
    }


def _clean_code(value: str) -> str:
    code = str(value or "").strip()
    if len(code) != 5 or not code.isdigit():
        raise HTTPException(status_code=400, detail="ZIPPER must be exactly five digits")
    return code


@router.get("/zipper/lookup/{code}")
def lookup_zipper(code: str):
    return _resolve_remote(_clean_code(code))


@router.get("/zipper/search")
def search_zipper(q: str):
    value = str(q or "").strip()
    if len(value) != 5 or not value.isdigit():
        return {"count": 0, "results": []}
    try:
        item = _resolve_remote(value)
    except HTTPException as exc:
        if exc.status_code == 404:
            return {"count": 0, "results": []}
        raise
    return {"count": 1, "results": [item]}


@router.get("/integration/map-zipper/health")
def map_zipper_health():
    sample = _resolve_remote("10000")
    return {
        "status": "ok",
        "integration": "UGAMAP-MAP->UNG-ZIPPER",
        "sample_code": sample["zipper_id"],
        "district": sample["district"],
        "latitude": sample["latitude"],
        "longitude": sample["longitude"],
        "source": sample["source"],
        "search_ready": True,
    }
