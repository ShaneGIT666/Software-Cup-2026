from __future__ import annotations

from unittest.mock import Mock

from backend.app.db.base import Base
from backend.app.db.domain_models import load_domain_models
from backend.app.domains.audit import AuditAppendResult, AuditEventInput, AuditWriter
from backend.app.domains.audit.models import AuditEvent


def test_m1_domain_models_are_discovered_by_m0() -> None:
    load_domain_models()

    assert {
        "users",
        "roles",
        "user_roles",
        "auth_sessions",
        "login_throttles",
        "login_throttle_buckets",
        "audit_events",
    }.issubset(
        Base.metadata.tables
    )


def test_audit_writer_appends_to_the_callers_transaction() -> None:
    session = Mock()
    event = AuditEventInput(
        actor_user_id="user-001",
        action="user.created",
        target_type="user",
        target_id="user-002",
        result="success",
        request_id="request-001",
        metadata={"roles": ["technician"], "temporaryPassword": "NeverPersistThis!"},
    )

    result = AuditWriter().append(session, event)

    assert isinstance(result, AuditAppendResult)
    assert not isinstance(result, AuditEvent)
    record = session.add.call_args.args[0]
    assert isinstance(record, AuditEvent)
    assert record.id == result.event_id
    session.commit.assert_not_called()
    assert record.event_metadata == {"roles": ["technician"], "temporaryPassword": "[REDACTED]"}
    assert not hasattr(record, "password_hash")
