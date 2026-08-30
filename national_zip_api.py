"""Public API routes for the federal national ZIP registry."""

from fastapi import APIRouter, HTTPException
from national_zip_registry import lookup_zip, state_summary, validate_registry

router = APIRouter(prefix="/zip", tags=["National ZIP"])


@router.get("/{zip_code}")
def get_zip(zip_code: str):
    result = lookup_zip(zip_code)
    if not result:
        raise HTTPException(status_code=404, detail="ZIP code is outside the loaded national ZIP registry")
    return result


@router.get("/state/{state_key}/summary")
def get_state_zip_summary(state_key: str):
    result = state_summary(state_key)
    if not result:
        raise HTTPException(status_code=404, detail="State ZIP block not found")
    return result


@router.get("/registry/status")
def get_registry_status():
    return validate_registry()
