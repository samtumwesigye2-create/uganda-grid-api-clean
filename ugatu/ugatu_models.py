from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class UCodeDefinition(BaseModel):
    ucode: str
    name: str
    domain: str
    module: str
    description: str = ""
    aliases: List[str] = Field(default_factory=list)
    roles: List[str] = Field(default_factory=list)
    safety_level: int = 1
    can_run_offline: bool = False
    audit_level: str = "STANDARD"
    handler: str
    emits_events: List[str] = Field(default_factory=list)
    status: str = "ACTIVE"
    version: int = 1


class ResolveRequest(BaseModel):
    query: str
    role: Optional[str] = None


class ExecuteRequest(BaseModel):
    ucode: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    client_request_id: str
    actor_id: Optional[str] = None
    role: Optional[str] = None
    device_id: Optional[str] = None
    device_time: Optional[datetime] = None
    offline: bool = False


class TransactionRecord(BaseModel):
    transaction_id: str
    ucode: str
    client_request_id: str
    actor_id: Optional[str] = None
    role: Optional[str] = None
    device_id: Optional[str] = None
    parameters: Dict[str, Any]
    status: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EventRecord(BaseModel):
    event_id: str
    event_type: str
    transaction_id: str
    payload: Dict[str, Any]
    event_time: datetime
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExecuteResponse(BaseModel):
    success: bool
    transaction_id: str
    ucode: str
    events: List[str] = Field(default_factory=list)
    duplicate: bool = False
    result: Dict[str, Any] = Field(default_factory=dict)
