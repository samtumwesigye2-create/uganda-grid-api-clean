"""Production entrypoint with UGAMAP Core enabled."""

from pathlib import Path

from fastapi import Query
from fastapi.responses import Response

from entrypoint import app, national_search
from main import (
    REPORTS,
    addresses,
    prune_reports,
    get_address as legacy_get_address,
    coordinate_lookup as legacy_coordinate_lookup,
)
from postal_assignment import resolve_zip
from state_geometry import state_for_coordinate
from ugamap_core import (
    configure_core,
    core_address,
    core_location,
    core_reports,
    core_search,
    router as ugamap_core_router,
)


def _core_reports_source():
    prune_reports()
    return REPORTS


def _core_search_source(query: str, limit: int):
    payload = national_search(query)
    results = list(payload.get("results") or [])[:limit]
    return {"count": len(results), "results": results}


def _core_address_lookup(grid_id: str):
    return legacy_get_address(grid_id)


def _core_location_lookup(lat: float, lon: float, tolerance_m: float):
    return legacy_coordinate_lookup(lat=lat, lon=lon, tolerance_m=tolerance_m)


configure_core(
    address_source=lambda: addresses,
    state_lookup=state_for_coordinate,
    zip_lookup=resolve_zip,
    reports_source=_core_reports_source,
    search_source=_core_search_source,
    address_lookup=_core_address_lookup,
    location_lookup=_core_location_lookup,
)
app.include_router(ugamap_core_router)

# Preserve public URLs while moving their implementation behind Core.
for route in list(app.router.routes):
    path = getattr(route, "path", None)
    methods = getattr(route, "methods", set())
    if path in {"/", "/search", "/address/{grid_id}", "/coordinates/lookup", "/reports", "/app.js"} and "GET" in methods:
        app.router.routes.remove(route)


@app.get("/", include_in_schema=False)
def public_home_with_boundaries():
    source = Path("index.html").read_text(encoding="utf-8")
    if "/boundaries.js" not in source:
        leaflet = '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>'
        injected = leaflet + '\n<script src="/boundaries.js?v=3"></script>'
        source = source.replace(leaflet, injected, 1)
    return Response(source, media_type="text/html", headers={"Cache-Control": "no-cache"})


@app.get("/search", tags=["UGAMAP Core Compatibility"])
def public_search_via_core(q: str = Query(..., min_length=1)):
    return core_search(q=q, limit=50)


@app.get("/address/{grid_id}", tags=["UGAMAP Core Compatibility"])
def public_address_via_core(grid_id: str):
    return core_address(grid_id)


@app.get("/coordinates/lookup", tags=["UGAMAP Core Compatibility"])
def public_coordinate_lookup_via_core(
    lat: float = Query(...), lon: float = Query(...),
    tolerance_m: float = Query(default=15.0, ge=0.0, le=500.0),
):
    return core_location(lat=lat, lon=lon, tolerance_m=tolerance_m)


@app.get("/reports", tags=["UGAMAP Core Compatibility"])
def public_reports_via_core():
    return core_reports()


@app.get("/app.js", include_in_schema=False)
def public_app_js_via_core():
    """Serve the existing UI with its routing call redirected to /core/route."""
    source = Path("app.js").read_text(encoding="utf-8")
    old_start = "  async function fetchValhalla(payload, attempt = 1) {"
    old_end = "  function decodeShape(str) {"
    start = source.find(old_start)
    end = source.find(old_end, start)
    if start < 0 or end < 0:
        return Response(source, media_type="application/javascript")

    replacement = r'''  async function getRoute(a, b) {
    const params = new URLSearchParams({
      start_lat: String(a.lat), start_lon: String(a.lon),
      dest_lat: String(b.lat), dest_lon: String(b.lon),
      mode: mode.value
    });
    let lastError = null;
    for (const base of apiCandidates()) {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 12000);
        const r = await fetch(base + '/core/route?' + params.toString(), { signal: controller.signal });
        clearTimeout(timeoutId);
        const d = await r.json();
        if (!r.ok) throw new Error((d && d.detail) || ('HTTP ' + r.status));
        const pts = Array.isArray(d.points) ? d.points : [];
        if (pts.length < 2) throw new Error('No route found');
        const cumDist = computeCumDist(pts);
        const maneuvers = parseManeuvers(d.maneuvers || [], pts, cumDist);
        return {
          pts,
          distance: Number(d.distance_m || 0),
          duration: Number(d.duration_s || 0),
          maneuvers,
          cumDist
        };
      } catch (e) {
        lastError = e;
      }
    }
    throw lastError || new Error('UGAMAP routing service unavailable');
  }

'''
    patched = source[:start] + replacement + source[end:]
    return Response(patched, media_type="application/javascript", headers={"Cache-Control": "no-cache"})
