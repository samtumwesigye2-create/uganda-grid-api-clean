"""Postal assignment helpers for Uganda National Grid approvals."""

from fastapi import HTTPException
from postal_zones import REGIONS, entebbe_zone_for_coordinates, valid_zip
from state_geometry import state_for_coordinate
from national_zip_geometry import zip_for_coordinate


def resolve_zip(latitude: float, longitude: float, region: str = "", zip_code: str = ""):
    """Resolve an approved address ZIP from its coordinates.

    Existing Entebbe 21401-21405 assignments always take precedence. Outside
    the calibrated Entebbe envelope, the coordinate is resolved to one of the
    ten state polygons and then to one of that state's five ZIP sub-polygons.

    Explicit region/ZIP values remain supported only as a validated fallback.
    """
    ent = entebbe_zone_for_coordinates(latitude, longitude)
    if ent:
        return ent

    state = state_for_coordinate(latitude, longitude)
    if state and state.get("ambiguous"):
        raise HTTPException(status_code=409, detail="Coordinate lies on an ambiguous state boundary")
    if state:
        automatic = zip_for_coordinate(latitude, longitude, state["state_code"])
        if automatic:
            automatic["state_code"] = state["state_code"]
            automatic["state_name"] = state["state_name"]
            return automatic

    region = (region or "").strip().upper()
    zip_code = (zip_code or "").strip()
    if not region and not zip_code:
        return None

    if region not in REGIONS:
        raise HTTPException(status_code=400, detail="Invalid postal region")
    if not zip_code:
        raise HTTPException(status_code=400, detail="ZIP code is required")
    if not valid_zip(zip_code) or zip_code not in REGIONS[region]["zip_codes"]:
        raise HTTPException(status_code=400, detail="ZIP code does not belong to the selected postal region")

    return {"zip_code": zip_code, "name": "", "region": region}
