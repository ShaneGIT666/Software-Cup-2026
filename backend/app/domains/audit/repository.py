from __future__ import annotations

from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .models import AuditEvent


class AuditRepository:
    """Read-only keyset access to the append-only audit stream."""

    def list_events(
        self,
        session: Session,
        *,
        limit: int,
        before_occurred_at: datetime | None = None,
        before_id: str | None = None,
        actor_id: str | None = None,
        action: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
    ) -> list[AuditEvent]:
        statement = select(AuditEvent)
        if actor_id:
            statement = statement.where(AuditEvent.actor_user_id == actor_id)
        if action:
            statement = statement.where(AuditEvent.action == action)
        if from_time:
            statement = statement.where(AuditEvent.occurred_at >= from_time)
        if to_time:
            statement = statement.where(AuditEvent.occurred_at <= to_time)
        if before_occurred_at is not None and before_id is not None:
            statement = statement.where(
                or_(
                    AuditEvent.occurred_at < before_occurred_at,
                    (AuditEvent.occurred_at == before_occurred_at) & (AuditEvent.id < before_id),
                )
            )
        return list(
            session.scalars(statement.order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc()).limit(limit)).all()
        )


def audit_event_view(event: AuditEvent) -> dict[str, object]:
    return {
        "id": event.id,
        "occurredAt": event.occurred_at.isoformat(),
        "actorUserId": event.actor_user_id,
        "action": event.action,
        "targetType": event.target_type,
        "targetId": event.target_id,
        "result": event.result,
        "requestId": event.request_id,
        "metadata": event.event_metadata,
    }

