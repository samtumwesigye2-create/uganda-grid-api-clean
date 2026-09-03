from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict

from .ugatu_events import build_events, new_id
from .ugatu_models import ExecuteRequest, ExecuteResponse, TransactionRecord
from .ugatu_registry import registry

Handler = Callable[[Dict[str, Any]], Dict[str, Any]]


def passthrough_handler(parameters: Dict[str, Any]) -> Dict[str, Any]:
    return {"accepted": True, "parameters": parameters}


class UGATUEngine:
    def __init__(self):
        self.handlers: Dict[str, Handler] = {}
        self.transactions: Dict[str, TransactionRecord] = {}
        self.events: Dict[str, Any] = {}
        self.idempotency: Dict[str, str] = {}

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

        prior = self.idempotency.get(request.client_request_id)
        if prior:
            tx = self.transactions[prior]
            event_ids = [eid for eid, event in self.events.items() if event.transaction_id == prior]
            return ExecuteResponse(success=True, transaction_id=prior, ucode=tx.ucode, events=event_ids, duplicate=True, result={"status": tx.status})

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
        self.transactions[transaction_id] = tx
        self.idempotency[request.client_request_id] = transaction_id

        event_time = request.device_time or datetime.now(timezone.utc)
        created = build_events(definition.emits_events, transaction_id, request.parameters, event_time)
        for event in created:
            self.events[event.event_id] = event

        return ExecuteResponse(
            success=True,
            transaction_id=transaction_id,
            ucode=definition.ucode,
            events=[e.event_id for e in created],
            result=result,
        )


engine = UGATUEngine()
