"""Production entrypoint with UGAMAP Core enabled.

This wrapper leaves the existing production entrypoint intact, then attaches
UGAMAP Core and routes public search/address compatibility endpoints through it.
"""

from fastapi import Query

from entrypoint import app, national_search
from main import REPORTS, addresses, prune_reports, get_address as legacy_get_address
from postal_assignment import resolve_zip
from state_geometry import state_for_coordinate
from ugamap_core import configure_core, core_address, core_search, router as ugamap_core_router


def _core_reports_source():
    prune_reports()
    return REPORTS


def _core_search_source(query: str, limit: int):
    payload = national_search(query)
    results = list(payload.get("results") or [])[:limit]
    return {"count": len(results), "results": results}


def _core_address_lookup(grid_id: str):
    return legacy_get_address(grid_id)


configure_core(
    address_source=lambda: addresses,
    state_lookup=state_for_coordinate,
    zip_lookup=resolve_zip,
    reports_source=_core_reports_source,
    search_source=_core_search_source,
    address_lookup=_core_address_lookup,
)

app.include_router(ugamap_core_router)

# Keep the public app's existing contracts while routing them through Core.
for route in list(app.router.routes):
    path = getattr(route, "path", None)
    methods = getattr(route, "methods", set())
    if path == "/search" and "GET" in methods:
        app.router.routes.remove(route)
    elif path == "/address/{grid_id}" and "GET" in methods:
        app.router.routes.remove(route)


@app.get("/search", tags=["UGAMAP Core Compatibility"])
def public_search_via_core(q: str = Query(..., min_length=1)):
    return core_search(q=q, limit=50)


@app.get("/address/{grid_id}", tags=["UGAMAP Core Compatibility"])
def public_address_via_core(grid_id: str):
    return core_address(grid_id)
