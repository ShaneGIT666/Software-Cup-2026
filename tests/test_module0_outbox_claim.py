from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys
from typing import cast

import pytest

from backend.app.core.ports import (
    OutboxAcknowledgeSuccessInput,
    OutboxAcknowledgeSuccessResult,
    OutboxClaimedEvent,
    OutboxClaimInput,
    OutboxClaimPort,
    OutboxClaimResult,
    OutboxDeadLetterInput,
    OutboxDeadLetterResult,
    OutboxFailure,
    OutboxLease,
    OutboxLeaseRenewalInput,
    OutboxLeaseRenewalResult,
    OutboxOperationStatus,
    OutboxReplayInput,
    OutboxReplayResult,
    OutboxRetryInput,
    OutboxRetryResult,
)


NOW = datetime(2026, 8, 28, 1, 0, tzinfo=timezone.utc)


def _lease(
    *,
    token: str = "lease-001",
    fence: int = 1,
    attempt: int = 1,
    replay_generation: int = 0,
    acquired_at: datetime = NOW,
    expires_at: datetime = NOW + timedelta(minutes=5),
) -> OutboxLease:
    return OutboxLease(
        consumer_id="document-parser.v1",
        event_id="event-001",
        owner_id="worker-instance-001",
        lease_token=token,
        fencing_token=fence,
        delivery_attempt=attempt,
        replay_generation=replay_generation,
        acquired_at=acquired_at,
        expires_at=expires_at,
    )


def _event(payload: dict[str, object] | None = None, *, lease: OutboxLease | None = None) -> OutboxClaimedEvent:
    return OutboxClaimedEvent(
        event_id="event-001",
        event_type="DocumentParseRequested.v1",
        aggregate_type="document",
        aggregate_id="document-001",
        version_id="version-001",
        request_id="request-001",
        occurred_at=NOW - timedelta(minutes=1),
        lease=lease or _lease(),
        payload=payload or {"documentId": "document-001"},
    )


def test_claim_contract_is_immutable_and_deep_freezes_the_delivery_envelope() -> None:
    source_payload: dict[str, object] = {"pages": [1, 2], "options": {"ocr": True}}
    event = _event(source_payload)
    command = OutboxClaimInput(
        consumer_id="document-parser.v1",
        owner_id="worker-instance-001",
        operation_id="operation-claim-001",
        requested_at=NOW,
        lease_duration=timedelta(minutes=5),
        limit=10,
    )
    result = OutboxClaimResult(
        operation_id=command.operation_id,
        consumer_id=command.consumer_id,
        owner_id=command.owner_id,
        status=OutboxOperationStatus.APPLIED,
        claimed_at=NOW,
        events=(event,),
    )

    source_payload["pages"] = [99]
    cast(dict[str, object], source_payload["options"])["ocr"] = False

    assert event.payload["pages"] == (1, 2)
    assert cast(dict[str, object], event.payload["options"])["ocr"] is True
    assert result.events == (event,)
    with pytest.raises(TypeError):
        cast(dict[str, object], event.payload)["new"] = "value"
    with pytest.raises(TypeError):
        cast(dict[str, object], event.payload["options"])["ocr"] = False
    with pytest.raises(FrozenInstanceError):
        command.limit = 20  # type: ignore[misc]


@pytest.mark.parametrize(
    ("changes", "exception_type"),
    [
        ({"consumer_id": " document-parser.v1"}, ValueError),
        ({"operation_id": "contains spaces"}, ValueError),
        ({"requested_at": datetime(2026, 8, 28, 1, 0)}, ValueError),
        ({"lease_duration": timedelta(0)}, ValueError),
        ({"lease_duration": timedelta(days=2)}, ValueError),
        ({"limit": 0}, ValueError),
        ({"limit": 101}, ValueError),
        ({"limit": True}, TypeError),
    ],
)
def test_claim_input_rejects_ambiguous_or_unbounded_values(
    changes: dict[str, object], exception_type: type[Exception]
) -> None:
    values: dict[str, object] = {
        "consumer_id": "document-parser.v1",
        "owner_id": "worker-instance-001",
        "operation_id": "operation-claim-001",
        "requested_at": NOW,
        "lease_duration": timedelta(minutes=5),
        "limit": 10,
    }
    values.update(changes)

    with pytest.raises(exception_type):
        OutboxClaimInput(**values)  # type: ignore[arg-type]


def test_lease_requires_an_owner_token_monotonic_fence_attempt_and_expiry() -> None:
    lease = _lease()

    assert lease.fencing_token == 1
    assert lease.delivery_attempt == 1
    assert lease.expires_at > lease.acquired_at

    with pytest.raises(ValueError, match="expires_at"):
        _lease(expires_at=NOW)
    with pytest.raises(ValueError, match="fencing_token"):
        _lease(fence=0)
    with pytest.raises(TypeError, match="delivery_attempt"):
        _lease(attempt=True)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="replay_generation"):
        _lease(replay_generation=-1)


def test_claim_outcome_distinguishes_idempotent_replay_from_key_conflict() -> None:
    replayed = OutboxClaimResult(
        operation_id="operation-claim-001",
        consumer_id="document-parser.v1",
        owner_id="worker-instance-001",
        status=OutboxOperationStatus.APPLIED,
        claimed_at=NOW,
        events=(_event(),),
        idempotent_replay=True,
    )
    conflict = OutboxClaimResult(
        operation_id="operation-claim-001",
        consumer_id="document-parser.v1",
        owner_id="worker-instance-001",
        status=OutboxOperationStatus.IDEMPOTENCY_CONFLICT,
        claimed_at=NOW,
    )

    assert replayed.idempotent_replay is True
    assert conflict.events == ()
    with pytest.raises(ValueError, match="cannot return claimed events"):
        OutboxClaimResult(
            operation_id="operation-claim-001",
            consumer_id="document-parser.v1",
            owner_id="worker-instance-001",
            status=OutboxOperationStatus.IDEMPOTENCY_CONFLICT,
            claimed_at=NOW,
            events=(_event(),),
        )


def test_heartbeat_renews_only_to_a_typed_lease_and_models_lease_rejections() -> None:
    lease = _lease()
    command = OutboxLeaseRenewalInput(
        lease=lease,
        operation_id="operation-heartbeat-001",
        requested_at=NOW + timedelta(minutes=1),
        lease_duration=timedelta(minutes=5),
    )
    renewed = _lease(expires_at=NOW + timedelta(minutes=6))
    applied = OutboxLeaseRenewalResult(
        operation_id=command.operation_id,
        event_id=lease.event_id,
        consumer_id=lease.consumer_id,
        status=OutboxOperationStatus.APPLIED,
        lease=renewed,
    )
    expired = OutboxLeaseRenewalResult(
        operation_id="operation-heartbeat-002",
        event_id=lease.event_id,
        consumer_id=lease.consumer_id,
        status=OutboxOperationStatus.LEASE_EXPIRED,
    )
    owner_conflict = OutboxLeaseRenewalResult(
        operation_id="operation-heartbeat-003",
        event_id=lease.event_id,
        consumer_id=lease.consumer_id,
        status=OutboxOperationStatus.OWNERSHIP_CONFLICT,
    )

    assert applied.lease == renewed
    assert expired.lease is None
    assert owner_conflict.status is OutboxOperationStatus.OWNERSHIP_CONFLICT
    with pytest.raises(ValueError, match="rejected result"):
        OutboxLeaseRenewalResult(
            operation_id="operation-heartbeat-004",
            event_id=lease.event_id,
            consumer_id=lease.consumer_id,
            status=OutboxOperationStatus.STALE_FENCE,
            lease=renewed,
        )


def test_success_acknowledgement_has_a_terminal_timestamp_or_an_explicit_rejection() -> None:
    lease = _lease()
    command = OutboxAcknowledgeSuccessInput(
        lease=lease,
        operation_id="operation-ack-001",
        acknowledged_at=NOW + timedelta(minutes=2),
    )
    applied = OutboxAcknowledgeSuccessResult(
        operation_id=command.operation_id,
        event_id=lease.event_id,
        consumer_id=lease.consumer_id,
        status=OutboxOperationStatus.APPLIED,
        acknowledged_at=command.acknowledged_at,
    )
    stale = OutboxAcknowledgeSuccessResult(
        operation_id="operation-ack-002",
        event_id=lease.event_id,
        consumer_id=lease.consumer_id,
        status=OutboxOperationStatus.STALE_FENCE,
    )

    assert applied.acknowledged_at == command.acknowledged_at
    assert stale.acknowledged_at is None
    with pytest.raises(ValueError, match="must contain"):
        OutboxAcknowledgeSuccessResult(
            operation_id="operation-ack-003",
            event_id=lease.event_id,
            consumer_id=lease.consumer_id,
            status=OutboxOperationStatus.APPLIED,
        )


def test_retry_carries_explicit_backoff_and_only_safe_failure_metadata() -> None:
    lease = _lease()
    failure = OutboxFailure(code="provider_timeout", diagnostic_id="diag-001")
    retry_at = NOW + timedelta(minutes=10)
    command = OutboxRetryInput(
        lease=lease,
        operation_id="operation-retry-001",
        failed_at=NOW + timedelta(minutes=2),
        available_at=retry_at,
        failure=failure,
    )
    result = OutboxRetryResult(
        operation_id=command.operation_id,
        event_id=lease.event_id,
        consumer_id=lease.consumer_id,
        status=OutboxOperationStatus.APPLIED,
        available_at=retry_at,
        next_delivery_attempt=2,
    )

    assert result.available_at == retry_at
    assert result.next_delivery_attempt == 2
    assert not hasattr(failure, "exception")
    assert not hasattr(failure, "message")
    with pytest.raises(ValueError, match="earlier"):
        OutboxRetryInput(
            lease=lease,
            operation_id="operation-retry-002",
            failed_at=NOW,
            available_at=NOW - timedelta(seconds=1),
            failure=failure,
        )
    with pytest.raises(ValueError, match="both"):
        OutboxRetryResult(
            operation_id="operation-retry-003",
            event_id=lease.event_id,
            consumer_id=lease.consumer_id,
            status=OutboxOperationStatus.APPLIED,
            available_at=retry_at,
        )


def test_dead_letter_token_is_required_for_an_explicit_idempotent_replay() -> None:
    lease = _lease(attempt=5)
    failure = OutboxFailure(code="attempts_exhausted", diagnostic_id="diag-005")
    dead_letter = OutboxDeadLetterInput(
        lease=lease,
        operation_id="operation-dead-001",
        failed_at=NOW + timedelta(minutes=2),
        failure=failure,
    )
    dead_result = OutboxDeadLetterResult(
        operation_id=dead_letter.operation_id,
        event_id=lease.event_id,
        consumer_id=lease.consumer_id,
        status=OutboxOperationStatus.APPLIED,
        dead_letter_id="dead-letter-001",
        dead_lettered_at=dead_letter.failed_at,
    )
    replay = OutboxReplayInput(
        consumer_id=lease.consumer_id,
        event_id=lease.event_id,
        dead_letter_id=cast(str, dead_result.dead_letter_id),
        operation_id="operation-replay-001",
        requested_at=NOW + timedelta(minutes=3),
        available_at=NOW + timedelta(minutes=4),
    )
    replayed = OutboxReplayResult(
        operation_id=replay.operation_id,
        event_id=replay.event_id,
        consumer_id=replay.consumer_id,
        status=OutboxOperationStatus.APPLIED,
        available_at=replay.available_at,
        replay_generation=1,
        idempotent_replay=True,
    )

    assert replay.dead_letter_id == dead_result.dead_letter_id
    assert replayed.replay_generation == 1
    assert replayed.idempotent_replay is True
    with pytest.raises(ValueError, match="earlier"):
        OutboxReplayInput(
            consumer_id=lease.consumer_id,
            event_id=lease.event_id,
            dead_letter_id="dead-letter-001",
            operation_id="operation-replay-002",
            requested_at=NOW,
            available_at=NOW - timedelta(seconds=1),
        )


def test_rejected_mutations_expose_stable_concurrency_outcomes_without_applied_state() -> None:
    expected = {
        "not_found",
        "ownership_conflict",
        "lease_expired",
        "stale_fence",
        "invalid_state",
        "idempotency_conflict",
    }

    assert expected.issubset({status.value for status in OutboxOperationStatus})
    with pytest.raises(ValueError, match="rejected result"):
        OutboxReplayResult(
            operation_id="operation-replay-003",
            event_id="event-001",
            consumer_id="document-parser.v1",
            status=OutboxOperationStatus.INVALID_STATE,
            available_at=NOW,
            replay_generation=2,
        )
    with pytest.raises(ValueError, match="cannot be an idempotent replay"):
        OutboxAcknowledgeSuccessResult(
            operation_id="operation-ack-004",
            event_id="event-001",
            consumer_id="document-parser.v1",
            status=OutboxOperationStatus.LEASE_EXPIRED,
            idempotent_replay=True,
        )


def test_public_port_is_runtime_checkable_and_requires_the_full_state_machine() -> None:
    class FakeClaimAdapter:
        def claim(self, command: OutboxClaimInput) -> OutboxClaimResult:
            raise NotImplementedError

        def renew_lease(self, command: OutboxLeaseRenewalInput) -> OutboxLeaseRenewalResult:
            raise NotImplementedError

        def acknowledge_success(self, command: OutboxAcknowledgeSuccessInput) -> OutboxAcknowledgeSuccessResult:
            raise NotImplementedError

        def schedule_retry(self, command: OutboxRetryInput) -> OutboxRetryResult:
            raise NotImplementedError

        def dead_letter(self, command: OutboxDeadLetterInput) -> OutboxDeadLetterResult:
            raise NotImplementedError

        def replay(self, command: OutboxReplayInput) -> OutboxReplayResult:
            raise NotImplementedError

    class PartialAdapter:
        def claim(self, command: OutboxClaimInput) -> OutboxClaimResult:
            raise NotImplementedError

    assert isinstance(FakeClaimAdapter(), OutboxClaimPort)
    assert not isinstance(PartialAdapter(), OutboxClaimPort)


def test_public_port_package_import_does_not_load_sqlalchemy() -> None:
    project_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import backend.app.core.ports; "
                "print(any(name == 'sqlalchemy' or name.startswith('sqlalchemy.') for name in sys.modules))"
            ),
        ],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "False"
