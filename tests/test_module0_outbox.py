from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import Mock

from backend.app.db import OutboxAppendResult, OutboxEventInput, OutboxWriter
from backend.app.db.models import OutboxEvent


def test_outbox_writer_exposes_only_an_immutable_event_id() -> None:
    session = Mock()
    result = OutboxWriter().append(
        session,
        OutboxEventInput(
            event_type="KnowledgePublished",
            aggregate_type="knowledge",
            aggregate_id="knowledge-001",
            version_id="version-003",
            request_id="request-001",
            occurred_at=datetime(2026, 8, 14, tzinfo=timezone.utc),
            payload={"approved": True},
        ),
    )

    assert isinstance(result, OutboxAppendResult)
    assert not isinstance(result, OutboxEvent)
    assert len(result.event_id) == 36
    record = session.add.call_args.args[0]
    assert isinstance(record, OutboxEvent)
    assert record.id == result.event_id
    assert record.version_id == "version-003"
    assert record.request_id == "request-001"
    assert record.payload == {"approved": True}
    session.commit.assert_not_called()


def test_outbox_model_contains_the_frozen_versioned_event_fields() -> None:
    assert {"version_id", "request_id", "occurred_at"}.issubset(OutboxEvent.__table__.columns.keys())
