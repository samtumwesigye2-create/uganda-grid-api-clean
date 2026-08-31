"""Production entrypoint with UGAMAP Core enabled.

This wrapper leaves the existing production entrypoint intact, then attaches
UGAMAP Core and routes the public search compatibility endpoint through it.
"""

from fastapi import Query

from entrypoint import app, national_search
from main import REPORTS, addresses, prune_reports
from postal_assignment import resolve_zip
from state_geometry import state_for_coordinate
from ugamap_core import configure_core, core_search, router as ugamap_core_router


def _core_reports_source():
    prune_reports()
    return REPORTS


def _core_search_source(query: str, limit: int):
    payload = national_search(query)
    results = list(payload.get("results") or [])[:limit]
    return {"count": len(results), "results": results}


configure_core(
    address_source=lambda: addresses,
    state_lookup=state_for_coordinate,
    zip_lookup=resolve_zip,
    reports_source=_core_reports_source,
    search_source=_core_search_source,
)

app.include_router(ugamap_core_router)

# Keep the public app's existing /search contract, but make UGAMAP Core the
# single backend path. This lets us migrate safely without changing app.js yet.
for route in list(app.router.routes):
    if getattr(route, "path", None) == "/search" and "GET" in getattr(route, "methods", set()):
        app.router.routes.remove(route)


@app.get("/search", tags=["UGAMAP Core Compatibility"])
def public_search_via_core(q: str = Query(..., min_length=1)):
    return core_search(q=q, limit=50)
