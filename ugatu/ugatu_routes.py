from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .ugatu_engine import engine
from .ugatu_models import ExecuteRequest, ResolveRequest
from .ugatu_registry import registry

router = APIRouter(prefix="/api/ugatu", tags=["UGATU"])


@router.get("/health")
def health():
    return {"ok": True, "registry_version": registry.version, "codes": len(registry.codes)}


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
    item = engine.transactions.get(transaction_id)
    if not item:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return item.model_dump()


@router.get("/events/{event_id}")
def get_event(event_id: str):
    item = engine.events.get(event_id)
    if not item:
        raise HTTPException(status_code=404, detail="Event not found")
    return item.model_dump()
