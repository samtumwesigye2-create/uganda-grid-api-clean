"""Production application entrypoint.

Extends the existing Uganda National Grid FastAPI application with the finalized
national ZIP registry, ZIP-aware search, and district-grounded coordinate lookup.
Legacy 00xxx special ZIP assignments remain stored for history/admin migration but
are not exposed as active address ZIPs because 00000-09999 is permanently reserved.
"""

from fastapi import Query
from main import app, addresses
from national_zip_api import router as national_zip_router
from national_zip_registry import lookup_zip
from national_zip_coordinate import district_allocation_for_coordinate

app.include_router(national_zip_router)


def _zip_search_result(query: str):
    q = str(query or "").strip()
    if not q.isdigit() or len(q) > 5:
        return None
    result = lookup_zip(q.zfill(5))
    if not result:
        return None
    return {
        "grid_id": result["zip_code"],
        "zip_code": result["zip_code"],
        "address": result.get("district") or "Reserved ZIP range",
        "display_name": (
            f"{result.get('district')}, {result.get('state_name')} — ZIP {result['zip_code']}"
            if result.get("district")
            else f"Reserved ZIP {result['zip_code']}"
        ),
        "state_name": result.get("state_name"),
        "political_region": result.get("political_region"),
        "district": result.get("district"),
        "reserved": result.get("reserved", False),
        "reservation": result.get("reservation"),
        "national_zip": True,
        "data_gap": result.get("data_gap", False),
        "county_subsplit_flag": result.get("county_subsplit_flag", False),
    }


# Replace only GET /search with the finalized registry-aware implementation.
for route in list(app.router.routes):
    if getattr(route, "path", None) == "/search" and "GET" in getattr(route, "methods", set()):
        app.router.routes.remove(route)


@app.get("/search")
def national_search(q: str = Query(..., min_length=1)):
    x = q.strip().lower()
    results = []

    zip_result = _zip_search_result(q)
    if zip_result:
        results.append(zip_result)

    # Legacy 00xxx special assignments are intentionally excluded from active search.
    normal = [
        a for a in addresses
        if x in str(a.get("grid_id", "")).lower()
        or x in str(a.get("address", "")).lower()
        or x in str(a.get("zip_code", "")).lower()
    ]

    seen = set()
    merged = []
    for item in results + normal:
        key = (str(item.get("grid_id", "")), str(item.get("zip_code", "")), str(item.get("address", "")))
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
        if len(merged) >= 50:
            break

    return {"count": len(merged), "results": merged}


@app.get("/coordinates/national-zip")
def national_zip_for_coordinates(lat: float = Query(...), lon: float = Query(...)):
    result = district_allocation_for_coordinate(lat, lon)
    if result is None:
        return {
            "latitude": lat,
            "longitude": lon,
            "matched": False,
            "assignment_ready": False,
            "detail": "Coordinates did not match a loaded Uganda district polygon",
        }
    return {"latitude": lat, "longitude": lon, "matched": True, **result}
