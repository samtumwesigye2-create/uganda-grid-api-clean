"""Provider-neutral payment adapter."""
from typing import Any

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field

from auth import require_permission
from integration_gateway import queue_event

router = APIRouter(prefix="/integration/payments", tags=["Payment Integration"])


class PaymentRequest(BaseModel):
    connector_id: str
    payment_reference: str
    order_number: str
    amount: float = Field(gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    customer_name: str
    customer_email: str = ""
    customer_phone: str = ""
    return_url: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class RefundRequest(BaseModel):
    connector_id: str
    payment_reference: str
    refund_reference: str
    amount: float = Field(gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    reason: str


class VerifyRequest(BaseModel):
    connector_id: str
    payment_reference: str


@router.post("/requests")
def request_payment(body:PaymentRequest,x_access_code:str=Header(default=""),x_idempotency_key:str=Header(default="")):
    require_permission(x_access_code,"commercial:write")
    payload=body.model_dump();connector_id=payload.pop("connector_id")
    row,created=queue_event(connector_id,"payment.request.create",payload,x_idempotency_key.strip() or f"payment:{body.payment_reference}")
    return {"event_id":row["id"],"payment_reference":body.payment_reference,"status":row["status"],"duplicate":not created}


@router.post("/verify")
def verify_payment(body:VerifyRequest,x_access_code:str=Header(default=""),x_idempotency_key:str=Header(default="")):
    require_permission(x_access_code,"commercial:read")
    payload=body.model_dump();connector_id=payload.pop("connector_id")
    row,created=queue_event(connector_id,"payment.status.verify",payload,x_idempotency_key.strip() or f"payment-verify:{body.payment_reference}")
    return {"event_id":row["id"],"payment_reference":body.payment_reference,"status":row["status"],"duplicate":not created}


@router.post("/refunds")
def refund_payment(body:RefundRequest,x_access_code:str=Header(default=""),x_idempotency_key:str=Header(default="")):
    require_permission(x_access_code,"commercial:write")
    payload=body.model_dump();connector_id=payload.pop("connector_id")
    row,created=queue_event(connector_id,"payment.refund.create",payload,x_idempotency_key.strip() or f"refund:{body.refund_reference}")
    return {"event_id":row["id"],"refund_reference":body.refund_reference,"status":row["status"],"duplicate":not created}
