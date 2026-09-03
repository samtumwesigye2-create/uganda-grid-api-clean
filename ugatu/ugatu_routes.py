from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query

from .ugatu_context import driver_home_actions, resolve_scan_ucode
from .ugatu_engine import engine
from .ugatu_models import ExecuteRequest, ResolveRequest
from .ugatu_registry import registry
from .ugatu_store import store

router = APIRouter(prefix="/api/ugatu", tags=["UGATU"])


@router.get("/health")
def health():
    return {
        "ok": True,
        "registry_version": registry.version,
        "codes": len(registry.codes),
        "persistence": "postgres" if store.postgres_enabled else "memory",
    }


@router.get("/codes")
def list_codes(role: str | None = Query(default=None), domain: str | None = Query(default=None)):
    return {"registry_version": registry.version, "codes": [x.model_dump() for x in registry.list(role=role, domain=domain)]}


@router.get("/codes/{ucode}")
def get_code(ucode: str):
    item = registry.get(ucode)
    if not item:
        raise HTTPException(status_code=404, detail="U-Code not found")
    return item.model_dump()


@router.post("/resolve")
def resolve_command(request: ResolveRequest):
    item = registry.resolve(request.query, role=request.role)
    if not item:
        raise HTTPException(status_code=404, detail="No authorized UGATU command matched")
    return item.model_dump()


@router.post("/context/scan")
def resolve_scan(context: Dict[str, Any]):
    ucode = resolve_scan_ucode(context)
    item = registry.get(ucode)
    if not item:
        raise HTTPException(status_code=404, detail=f"Context resolved to unavailable command {ucode}")
    return {"ucode": ucode, "command": item.model_dump()}


@router.post("/context/driver-home")
def driver_home(context: Dict[str, Any]):
    actions = []
    for action in driver_home_actions(context):
        item = registry.get(action["ucode"])
        if item:
            actions.append({**action, "name": item.name})
    return {"actions": actions}


@router.post("/execute")
def execute_command(request: ExecuteRequest):
    try:
        return engine.execute(request).model_dump()
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/transactions/{transaction_id}")
def get_transaction(transaction_id: str):
    item = store.get_transaction(transaction_id)
    if not item:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return item.model_dump()


@router.get("/events/{event_id}")
def get_event(event_id: str):
    item = store.get_event(event_id)
    if not item:
        raise HTTPException(status_code=404, detail="Event not found")
    return item.model_dump()


@router.get("/favorites/{actor_id}")
def get_favorites(actor_id: str):
    codes = store.favorites(actor_id)
    return {"actor_id": actor_id, "favorites": [registry.get(c).model_dump() for c in codes if registry.get(c)]}


@router.put("/favorites/{actor_id}")
def put_favorites(actor_id: str, ucodes: List[str]):
    normalized = []
    for value in ucodes:
        item = registry.get(value)
        if not item:
            raise HTTPException(status_code=400, detail=f"Unknown U-Code: {value}")
        normalized.append(item.ucode)
    saved = store.set_favorites(actor_id, normalized)
    return {"actor_id": actor_id, "ucodes": saved}


@router.get("/recent/{actor_id}")
def get_recent(actor_id: str, limit: int = Query(default=10, ge=1, le=50)):
    codes = store.recent(actor_id, limit)
    return {"actor_id": actor_id, "recent": [registry.get(c).model_dump() for c in codes if registry.get(c)]}
