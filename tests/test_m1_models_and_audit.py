from __future__ import annotations

from unittest.mock import Mock

import pytest

from backend.app.db.base import Base
from backend.app.db.domain_models import load_domain_models
from backend.app.domains.audit import AuditAppendResult, AuditEventInput, AuditWriter
from backend.app.domains.audit.models import AuditEvent
from backend.app.domains.identity.models import IdentityInstanceState, User


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
        "identity_instance_state",
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
    assert record.actor_user_id == "user-001"
    assert record.initiator_user_id is None
    session.commit.assert_not_called()
    assert record.event_metadata == {"roles": ["technician"], "temporaryPassword": "[REDACTED]"}
    assert not hasattr(record, "password_hash")


def test_audit_input_rejects_an_empty_authenticated_actor() -> None:
    with pytest.raises(ValueError, match="不能为空"):
        AuditEventInput(
            actor_user_id=" ",
            action="user.created",
            target_type="user",
            target_id="user-2",
            result="success",
            request_id="request-1",
        )


def test_managed_service_and_audit_schema_are_fail_closed() -> None:
    user_constraints = " ".join(
        str(constraint.sqltext)
        for constraint in User.__table__.constraints
        if hasattr(constraint, "sqltext")
    )

    assert "service" in user_constraints
    assert "service_key" in User.__table__.columns
    assert User.__table__.c.service_key.unique is True
    assert AuditEvent.__table__.c.actor_user_id.nullable is False
    assert AuditEvent.__table__.c.initiator_user_id.nullable is True
    assert IdentityInstanceState.__table__.c.lifecycle.nullable is False
    state_constraints = " ".join(
        str(constraint.sqltext)
        for constraint in IdentityInstanceState.__table__.constraints
        if hasattr(constraint, "sqltext")
    )
    assert "id = 'identity'" in state_constraints
    assert "version >= 1" in state_constraints
    assert "activated_by_user_id IS NOT NULL" in state_constraints
