"""Provider-neutral shipping carrier adapter."""
import uuid
from typing import Any

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field

from auth import require_permission
from integration_gateway import queue_event

router = APIRouter(prefix="/integration/carriers", tags=["Carrier Integration"])


class Address(BaseModel):
    name: str
    phone: str = ""
    line1: str
    line2: str = ""
    city: str
    state_region: str = ""
    postal_code: str = ""
    country_code: str = Field(min_length=2, max_length=2)


class Parcel(BaseModel):
    weight_kg: float = Field(gt=0)
    length_cm: float = Field(gt=0)
    width_cm: float = Field(gt=0)
    height_cm: float = Field(gt=0)
    description: str = "Goods"
    declared_value: float = Field(default=0, ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)


class ShipmentRequest(BaseModel):
    connector_id: str
    shipment_number: str
    service_level: str = "standard"
    sender: Address
    recipient: Address
    parcels: list[Parcel] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TrackingRequest(BaseModel):
    connector_id: str
    tracking_number: str


class CancelRequest(BaseModel):
    connector_id: str
    shipment_number: str
    tracking_number: str = ""
    reason: str


@router.post("/shipments")
def create_carrier_shipment(body:ShipmentRequest,x_access_code:str=Header(default=""),x_idempotency_key:str=Header(default="")):
    require_permission(x_access_code,"shipments:write")
    payload=body.model_dump();connector_id=payload.pop("connector_id")
    row,created=queue_event(connector_id,"carrier.shipment.create",payload,x_idempotency_key.strip() or f"carrier-create:{body.shipment_number}")
    return {"event_id":row["id"],"shipment_number":body.shipment_number,"status":row["status"],"duplicate":not created}


@router.post("/tracking/refresh")
def refresh_tracking(body:TrackingRequest,x_access_code:str=Header(default=""),x_idempotency_key:str=Header(default="")):
    require_permission(x_access_code,"shipments:read")
    payload=body.model_dump();connector_id=payload.pop("connector_id")
    row,created=queue_event(connector_id,"carrier.tracking.refresh",payload,x_idempotency_key.strip() or f"tracking:{body.tracking_number}:{uuid.uuid4()}")
    return {"event_id":row["id"],"tracking_number":body.tracking_number,"status":row["status"],"duplicate":not created}


@router.post("/shipments/cancel")
def cancel_carrier_shipment(body:CancelRequest,x_access_code:str=Header(default=""),x_idempotency_key:str=Header(default="")):
    require_permission(x_access_code,"shipments:write")
    payload=body.model_dump();connector_id=payload.pop("connector_id")
    row,created=queue_event(connector_id,"carrier.shipment.cancel",payload,x_idempotency_key.strip() or f"carrier-cancel:{body.shipment_number}")
    return {"event_id":row["id"],"shipment_number":body.shipment_number,"status":row["status"],"duplicate":not created}
