from __future__ import annotations

from backend.app.domains.audit.models import AuditEvent
from backend.app.domains.audit.repository import AuditRepository


def test_audit_repository_exposes_no_mutation_methods() -> None:
    repository = AuditRepository()

    assert hasattr(repository, "list_events")
    assert not hasattr(repository, "update")
    assert not hasattr(repository, "delete")


def test_audit_model_remains_append_only_contract() -> None:
    columns = set(AuditEvent.__table__.columns.keys())

    assert columns == {
        "id",
        "occurred_at",
        "actor_user_id",
        "initiator_user_id",
        "action",
        "target_type",
        "target_id",
        "result",
        "request_id",
        "metadata",
    }
