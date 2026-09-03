from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List
from uuid import uuid4

from .ugatu_models import EventRecord


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:16].upper()}"


def build_events(event_types: Iterable[str], transaction_id: str, payload: Dict[str, Any], event_time=None) -> List[EventRecord]:
    when = event_time or datetime.now(timezone.utc)
    return [
        EventRecord(
            event_id=new_id("EVT"),
            event_type=event_type,
            transaction_id=transaction_id,
            payload=dict(payload),
            event_time=when,
        )
        for event_type in event_types
    ]
