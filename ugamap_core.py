from __future__ import annotations

from typing import Any, Callable, Iterable, Optional

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/core", tags=["UGAMAP Core"])

_address_source: Callable[[], Iterable[dict[str, Any]]] = lambda: []
_state_lookup: Optional[Callable[[float, float], Any]] = None
_zip_lookup: Optional[Callable[[float, float], Any]] = None
_reports_source: Optional[Callable[[], Iterable[dict[str, Any]]]] = None
_search_source: Optional[Callable[[str, int], Any]] = None
_address_lookup: Optional[Callable[[str], Any]] = None


def configure_core(
    *,
    address_source: Callable[[], Iterable[dict[str, Any]]],
    state_lookup: Optional[Callable[[float, float], Any]] = None,
    zip_lookup: Optional[Callable[[float, float], Any]] = None,
    reports_source: Optional[Callable[[], Iterable[dict[str, Any]]]] = None,
    search_source: Optional[Callable[[str, int], Any]] = None,
    address_lookup: Optional[Callable[[str], Any]] = None,
) -> None:
    """Connect UGAMAP Core to the application's existing data/services."""
    global _address_source, _state_lookup, _zip_lookup, _reports_source, _search_source, _address_lookup
    _address_source = address_source
    _state_lookup = state_lookup
    _zip_lookup = zip_lookup
    _reports_source = reports_source
    _search_source = search_source
    _address_lookup = address_lookup


def _addresses() -> list[dict[str, Any]]:
    return list(_address_source() or [])


def _normalized_address(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "grid_id": record.get("grid_id", ""),
        "address": record.get("address") or record.get("display_name") or record.get("grid_id", ""),
        "display_name": record.get("display_name") or record.get("address") or record.get("grid_id", ""),
        "latitude": record.get("latitude"),
        "longitude": record.get("longitude"),
        "zip_code": record.get("zip_code"),
        "state_code": record.get("state_code"),
        "state_name": record.get("state_name"),
        "address_type": record.get("address_type"),
        **{k: v for k, v in record.items() if k not in {
            "grid_id", "address", "display_name", "latitude", "longitude",
            "zip_code", "state_code", "state_name", "address_type"
        }},
    }


@router.get("/status")
def core_status() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "UGAMAP Core",
        "version": "1.2",
        "records": len(_addresses()),
        "capabilities": ["address", "search", "location", "reports"],
    }


@router.get("/address/{grid_id}")
def core_address(grid_id: str) -> dict[str, Any]:
    key = grid_id.strip()
    if _address_lookup:
        try:
            record = _address_lookup(key)
        except HTTPException:
            raise
        if record:
            return _normalized_address(dict(record))
        raise HTTPException(status_code=404, detail="UGAMAP location not found")

    lowered = key.lower()
    for record in _addresses():
        if str(record.get("grid_id", "")).strip().lower() == lowered:
            return _normalized_address(record)
    raise HTTPException(status_code=404, detail="UGAMAP location not found")


@router.get("/search")
def core_search(q: str = Query(..., min_length=1), limit: int = Query(20, ge=1, le=50)) -> dict[str, Any]:
    if _search_source:
        payload = _search_source(q.strip(), limit)
        if isinstance(payload, dict):
            results = list(payload.get("results") or [])[:limit]
            return {"count": len(results), "results": results}
        results = list(payload or [])[:limit]
        return {"count": len(results), "results": results}

    key = q.strip().lower()
    matches: list[dict[str, Any]] = []
    for record in _addresses():
        searchable = " ".join(
            str(record.get(field, ""))
            for field in ("grid_id", "address", "display_name", "zip_code", "state_name")
        ).lower()
        if key in searchable:
            matches.append(_normalized_address(record))
            if len(matches) >= limit:
                break
    return {"count": len(matches), "results": matches}


@router.get("/location")
def core_location(lat: float = Query(...), lon: float = Query(...)) -> dict[str, Any]:
    state = _state_lookup(lat, lon) if _state_lookup else None
    postal = _zip_lookup(lat, lon) if _zip_lookup else None
    return {
        "latitude": lat,
        "longitude": lon,
        "state": state,
        "postal": postal,
    }


@router.get("/reports")
def core_reports() -> dict[str, Any]:
    results = list(_reports_source() or []) if _reports_source else []
    return {"count": len(results), "results": results}
