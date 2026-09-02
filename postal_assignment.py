"""Postal assignment helpers for the finalized Uganda National Grid ZIP plan."""

from fastapi import HTTPException
from manual_zip_assignments import match_point as match_manual_zip
from national_zip_coordinate import district_allocation_for_coordinate
from national_zip_registry import lookup_zip

try:
    from national_zip_clusters import cluster_zip_for_coordinate
except ModuleNotFoundError:
    def cluster_zip_for_coordinate(latitude, longitude):
        return None


def _manual_result(manual):
    code = str(manual.get("zip_code", "")).strip().zfill(5)
    canonical = lookup_zip(code)
    if not canonical or canonical.get("reserved"):
        raise HTTPException(status_code=409, detail="Manual ZIP override uses a code that is not active in the finalized national registry")
    return {
        "zip_code": code,
        "name": manual.get("name", ""),
        "region": canonical.get("state_name", ""),
        "state_name": canonical.get("state_name"),
        "state_key": canonical.get("state_key"),
        "district": canonical.get("district"),
        "manual_override": True,
        "forced_override": True,
        "national_zip": True,
    }


def resolve_zip(latitude: float, longitude: float, region: str = "", zip_code: str = ""):
    manual = match_manual_zip(latitude, longitude)
    if manual:
        return _manual_result(manual)

    allocation = district_allocation_for_coordinate(latitude, longitude)
    if allocation and allocation.get("ambiguous"):
        raise HTTPException(status_code=409, detail=allocation.get("detail", "Ambiguous district boundary"))

    requested = str(zip_code or "").strip()
    if requested:
        if not requested.isdigit() or len(requested) > 5:
            raise HTTPException(status_code=400, detail="ZIP code must be five numeric text characters")
        requested = requested.zfill(5)
        canonical = lookup_zip(requested)
        if not canonical:
            raise HTTPException(status_code=400, detail="ZIP code is outside the finalized national registry")
        if canonical.get("reserved"):
            raise HTTPException(status_code=400, detail="Reserved ZIP codes cannot be assigned to addresses")
        candidates = (allocation or {}).get("candidates", [])
        if candidates and not any(c["zip_start"] <= requested <= c["zip_end"] for c in candidates):
            raise HTTPException(status_code=400, detail="ZIP code does not belong to the coordinate's district allocation")
        return {
            "zip_code": requested,
            "name": canonical.get("district", ""),
            "region": canonical.get("state_name", ""),
            "state_name": canonical.get("state_name"),
            "state_key": canonical.get("state_key"),
            "district": canonical.get("district"),
            "national_zip": True,
            "validated_against_coordinates": bool(candidates),
        }

    cluster_result = cluster_zip_for_coordinate(latitude, longitude)
    if cluster_result:
        return cluster_result
    if not allocation:
        return None
    candidates = allocation.get("candidates", [])
    return {
        "zip_code": "",
        "name": candidates[0]["district"] if len(candidates) == 1 else "",
        "region": candidates[0]["state_name"] if len(candidates) == 1 else "",
        "national_zip": True,
        "assignment_pending": True,
        "exact_zip_ready": False,
        "source_district": allocation.get("source_district"),
        "district_range_resolved": allocation.get("district_range_resolved", False),
        "candidates": candidates,
        "detail": allocation.get("detail"),
    }
