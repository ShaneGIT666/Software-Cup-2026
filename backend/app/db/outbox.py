from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping
from uuid import uuid4

from sqlalchemy.orm import Session

from .models import OutboxEvent


@dataclass(frozen=True)
class OutboxEventInput:
    event_type: str
    aggregate_type: str
    aggregate_id: str
    version_id: str
    request_id: str
    occurred_at: datetime
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OutboxAppendResult:
    event_id: str


class OutboxWriter:
    """Append a versioned event to the caller-owned transaction."""

    def append(self, session: Session, event: OutboxEventInput) -> OutboxAppendResult:
        event_id = str(uuid4())
        session.add(
            OutboxEvent(
                id=event_id,
                event_type=event.event_type,
                aggregate_type=event.aggregate_type,
                aggregate_id=event.aggregate_id,
                version_id=event.version_id,
                request_id=event.request_id,
                occurred_at=event.occurred_at,
                payload=dict(event.payload),
                status="pending",
                attempt_count=0,
            )
        )
        return OutboxAppendResult(event_id=event_id)
