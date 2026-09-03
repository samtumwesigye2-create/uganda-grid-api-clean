from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict

from .ugatu_events import build_events, new_id
from .ugatu_models import ExecuteRequest, ExecuteResponse, TransactionRecord
from .ugatu_registry import registry
from .ugatu_store import store

Handler = Callable[[Dict[str, Any]], Dict[str, Any]]


def passthrough_handler(parameters: Dict[str, Any]) -> Dict[str, Any]:
    return {"accepted": True, "parameters": parameters}


def pickup_scan_handler(parameters: Dict[str, Any]) -> Dict[str, Any]:
    package_id = parameters.get("package_id") or parameters.get("freight_id")
    if not package_id:
        raise ValueError("Pickup scan requires package_id or freight_id")
    return {
        "accepted": True,
        "operation": "PICKUP",
        "package_or_freight_id": package_id,
        "custody": "ACQUIRED_BY_DRIVER",
    }


def delivery_scan_handler(parameters: Dict[str, Any]) -> Dict[str, Any]:
    package_id = parameters.get("package_id") or parameters.get("freight_id")
    if not package_id:
        raise ValueError("Delivery scan requires package_id or freight_id")
    return {
        "accepted": True,
        "operation": "DELIVERY",
        "package_or_freight_id": package_id,
        "delivery_scan": "RECORDED",
    }


class UGATUEngine:
    def __init__(self):
        self.handlers: Dict[str, Handler] = {}
        self.register_handler("driver.pickup_scan.v1", pickup_scan_handler)
        self.register_handler("driver.delivery_scan.v1", delivery_scan_handler)

    @property
    def transactions(self):
        return store.memory_transactions

    @property
    def events(self):
        return store.memory_events

    def register_handler(self, name: str, handler: Handler) -> None:
        self.handlers[name] = handler

    def execute(self, request: ExecuteRequest) -> ExecuteResponse:
        definition = registry.get(request.ucode)
        if not definition:
            raise ValueError(f"Unknown U-Code: {request.ucode}")
        if definition.status != "ACTIVE":
            raise ValueError(f"U-Code not active: {definition.ucode}")
        if request.role and definition.roles and request.role.upper() not in definition.roles:
            raise PermissionError(f"Role {request.role} cannot execute {definition.ucode}")
        if request.offline and not definition.can_run_offline:
            raise ValueError(f"{definition.ucode} cannot execute offline")

        prior = store.transaction_for_request(request.client_request_id)
        if prior:
            created = store.events_for_transaction(prior.transaction_id)
            return ExecuteResponse(
                success=True,
                transaction_id=prior.transaction_id,
                ucode=prior.ucode,
                events=[e.event_id for e in created],
                duplicate=True,
                result={"status": prior.status},
            )

        transaction_id = new_id("TXN")
        handler = self.handlers.get(definition.handler, passthrough_handler)
        result = handler(request.parameters)
        tx = TransactionRecord(
            transaction_id=transaction_id,
            ucode=definition.ucode,
            client_request_id=request.client_request_id,
            actor_id=request.actor_id,
            role=request.role,
            device_id=request.device_id,
            parameters=request.parameters,
            status="COMPLETED",
        )
        store.save_transaction(tx)

        event_time = request.device_time or datetime.now(timezone.utc)
        created = build_events(definition.emits_events, transaction_id, request.parameters, event_time)
        for event in created:
            store.save_event(event)

        store.record_recent(request.actor_id, definition.ucode, transaction_id)

        return ExecuteResponse(
            success=True,
            transaction_id=transaction_id,
            ucode=definition.ucode,
            events=[e.event_id for e in created],
            result=result,
        )


engine = UGATUEngine()
