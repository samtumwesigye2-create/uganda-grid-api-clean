"""Postal assignment helpers for Uganda National Grid approvals."""

from fastapi import HTTPException
from postal_zones import REGIONS, entebbe_zone_for_coordinates, valid_zip


def resolve_zip(latitude: float, longitude: float, region: str = "", zip_code: str = ""):
    """Resolve an approved address ZIP.

    Entebbe is fully automatic from coordinates. Other regions may supply one
    of that region's five reserved ZIP codes until their polygons are defined.
    """
    ent = entebbe_zone_for_coordinates(latitude, longitude)
    if ent:
        return ent

    region = (region or "").strip().upper()
    zip_code = (zip_code or "").strip()
    if not region and not zip_code:
        return None

    if region not in REGIONS:
        raise HTTPException(status_code=400, detail="Invalid postal region")
    if not zip_code:
        raise HTTPException(status_code=400, detail="ZIP code is required for this region until automatic boundaries are defined")
    if not valid_zip(zip_code) or zip_code not in REGIONS[region]["zip_codes"]:
        raise HTTPException(status_code=400, detail="ZIP code does not belong to the selected postal region")

    return {"zip_code": zip_code, "name": "", "region": region}
