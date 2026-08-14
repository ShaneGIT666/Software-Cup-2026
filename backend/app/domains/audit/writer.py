from __future__ import annotations

from sqlalchemy.orm import Session
from uuid import uuid4

from .contracts import AuditAppendResult, AuditEventInput
from .models import AuditEvent


_SENSITIVE_KEY_PARTS = ("password", "secret", "token", "authorization", "cookie", "api_key", "apikey")


def _sanitize_metadata(value: object) -> object:
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]"
            if any(part in str(key).lower() for part in _SENSITIVE_KEY_PARTS)
            else _sanitize_metadata(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_sanitize_metadata(item) for item in value]
    return value


class AuditWriter:
    """Append an audit event to the caller-owned database transaction."""

    def append(self, session: Session, event: AuditEventInput) -> AuditAppendResult:
        event_id = str(uuid4())
        record = AuditEvent(
            id=event_id,
            actor_user_id=event.actor_user_id,
            action=event.action,
            target_type=event.target_type,
            target_id=event.target_id,
            result=event.result,
            request_id=event.request_id,
            event_metadata=_sanitize_metadata(dict(event.metadata)),
        )
        session.add(record)
        return AuditAppendResult(event_id=event_id)
