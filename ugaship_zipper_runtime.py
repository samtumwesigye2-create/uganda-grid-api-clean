"""UGASHIP live bridges: UNG-ZIPPER destination resolution and UNG-VECTOR inventory handoff."""
from __future__ import annotations

import os
import requests
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(tags=["UGASHIP integrations"])
ZIPPER_API_URL = os.environ.get("ZIPPER_API_URL", "https://ung-zipper-production.up.railway.app").rstrip("/")
ZIPPER_TIMEOUT = float(os.environ.get("ZIPPER_TIMEOUT_SECONDS", "8"))
VECTOR_API_URL = os.environ.get("VECTOR_API_URL", "https://ung-vector-production.up.railway.app").rstrip("/")
VECTOR_TIMEOUT = float(os.environ.get("VECTOR_TIMEOUT_SECONDS", "8"))


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


def _vector_request(method: str, path: str, authorization: str | None = None, payload: dict | None = None):
    headers = {"Accept": "application/json"}
    if authorization:
        headers["Authorization"] = authorization
    try:
        r = requests.request(method, f"{VECTOR_API_URL}{path}", json=payload, headers=headers, timeout=VECTOR_TIMEOUT)
    except requests.RequestException as exc:
        raise HTTPException(status_code=503, detail=f"UNG-VECTOR unavailable: {type(exc).__name__}")
    try:
        body = r.json()
    except ValueError:
        body = {"detail": "UNG-VECTOR returned invalid JSON"}
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code if r.status_code in {400,401,403,404,409} else 502, detail=body.get("detail", f"UNG-VECTOR HTTP {r.status_code}"))
    return body


@router.get("/ship/destination/{code}")
def resolve_shipping_destination(code: str):
    validation = _get(f"/zipper/validate/{code}")
    if not validation.get("valid"):
        raise HTTPException(status_code=404, detail="ZIP code is not assigned")
    resolution = _get(f"/zipper/{code}")
    return {"status":"ok","source":"UNG-ZIPPER","code":resolution.get("code"),"district":resolution.get("district"),"name":resolution.get("name"),"area_type":resolution.get("area_type"),"population_covered":resolution.get("population_covered"),"latitude":resolution.get("latitude"),"longitude":resolution.get("longitude"),"protected":resolution.get("protected"),"validation":validation}


@router.get("/ship/integration/zipper/health")
def shipping_zipper_health():
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
    return {"status":"ok","integration":"UGASHIP->UNG-ZIPPER","registry_records":ready.get("records"),"sample_code":code,"district":resolution.get("district"),"area_type":resolution.get("area_type"),"population_covered":resolution.get("population_covered"),"latitude":resolution.get("latitude"),"longitude":resolution.get("longitude"),"validation":validation,"resolution_ok":True}


class VectorHandoff(BaseModel):
    shipment_number: str = Field(min_length=1, max_length=80)
    sku: str = Field(min_length=1, max_length=120)
    quantity: int = Field(gt=0)
    movement_type: str
    from_location: str | None = None
    to_location: str | None = None


@router.get("/ship/integration/vector/health")
def shipping_vector_health():
    health = _vector_request("GET", "/health")
    system = _vector_request("GET", "/v1/system")
    if health.get("status") != "ok" or system.get("system_id") != "UNG-VECTOR":
        raise HTTPException(status_code=503, detail="UGASHIP VECTOR acceptance failed")
    return {"status":"ok","integration":"UGASHIP->UNG-VECTOR","vector_health":health.get("status"),"system_id":system.get("system_id"),"capabilities":system.get("capabilities",[]),"mutation_tested":False}


@router.post("/ship/integration/vector/handoff")
def shipping_vector_handoff(body: VectorHandoff, authorization: str | None = Header(default=None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="JANUS bearer token required")
    if body.movement_type not in {"receive","dispatch","transfer","adjust"}:
        raise HTTPException(status_code=400, detail="invalid_movement_type")
    # Preserve the UGASHIP tracking number as VECTOR's cross-system reference.
    # A preflight lookup prevents ordinary client retries from creating duplicate stock movements.
    existing = _vector_request("GET", "/v1/movements", authorization)
    for movement in existing if isinstance(existing, list) else []:
        if str(movement.get("reference") or "") == body.shipment_number and str(movement.get("movement_type") or "") == body.movement_type:
            return {"status":"ok","integration":"UGASHIP->UNG-VECTOR","idempotent_replay":True,"shipment_number":body.shipment_number,"movement":movement}
    payload = {"sku":body.sku,"quantity":body.quantity,"movement_type":body.movement_type,"from_location":body.from_location,"to_location":body.to_location,"reference":body.shipment_number}
    movement = _vector_request("POST", "/v1/movements", authorization, payload)
    return {"status":"ok","integration":"UGASHIP->UNG-VECTOR","idempotent_replay":False,"shipment_number":body.shipment_number,"movement":movement}
