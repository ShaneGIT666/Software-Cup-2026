"""Stable M0 public port for reliable transactional-outbox delivery.

This module deliberately contains no SQLAlchemy or Worker implementation.
M0 owns the eventual adapter and its transactions; M4 owns orchestration and
may depend only on the value objects and :class:`OutboxClaimPort` below.

Concurrency and idempotency semantics frozen by this contract:

* ``claim`` atomically grants each eligible delivery to at most one live
  lease.  Reclaiming an expired delivery creates a new opaque lease token and
  a strictly larger fencing token/delivery attempt.
* Every lease mutation compares consumer, event, owner, lease token and
  fencing token.  The datastore clock decides whether the lease is expired.
  A rejected command never mutates delivery state.
* A renewal is the Worker's heartbeat.  It succeeds only for a current,
  unexpired lease and may extend, but never shorten, that lease.
* Success acknowledgement is terminal.  Retry releases the lease and makes
  the delivery claimable no earlier than ``available_at``.  Dead-lettering is
  terminal until an explicit replay matches the current dead-letter token.
* Replay retains the original event ID and envelope, increments the replay
  generation, and creates new delivery attempts; it never invokes a producer.
* ``operation_id`` is idempotent in the scope
  ``(consumer_id, operation_name, operation_id)``.  Repeating the same
  canonical input returns the stored result with ``idempotent_replay=True``;
  reusing it for different input returns ``IDEMPOTENCY_CONFLICT`` without a
  state change.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Protocol, TypeAlias, runtime_checkable


_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")
_MIN_LEASE_DURATION = timedelta(seconds=1)
_MAX_LEASE_DURATION = timedelta(hours=24)
_MAX_CLAIM_LIMIT = 100

JsonValue: TypeAlias = (
    str | int | float | bool | None | tuple["JsonValue", ...] | Mapping[str, "JsonValue"]
)


def _identifier(name: str, value: str, *, maximum: int = 128) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value or value != value.strip():
        raise ValueError(f"{name} must be non-empty and contain no surrounding whitespace")
    if len(value) > maximum or _IDENTIFIER_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{name} has an invalid format")
    return value


def _utc_datetime(name: str, value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _positive_int(name: str, value: int, *, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 1 or (maximum is not None and value > maximum):
        raise ValueError(f"{name} is outside the allowed range")
    return value


def _lease_duration(value: timedelta) -> timedelta:
    if not isinstance(value, timedelta):
        raise TypeError("lease_duration must be a timedelta")
    if value < _MIN_LEASE_DURATION or value > _MAX_LEASE_DURATION:
        raise ValueError("lease_duration must be between one second and 24 hours")
    return value


def _freeze_json(value: Any, *, path: str = "payload") -> JsonValue:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} contains a non-finite number")
        return value
    if isinstance(value, Mapping):
        frozen: dict[str, JsonValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{path} keys must be strings")
            frozen[key] = _freeze_json(item, path=f"{path}.{key}")
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item, path=f"{path}[]") for item in value)
    raise TypeError(f"{path} contains a value that is not JSON-compatible")


def _frozen_payload(value: Mapping[str, Any]) -> Mapping[str, JsonValue]:
    if not isinstance(value, Mapping):
        raise TypeError("payload must be a mapping")
    frozen = _freeze_json(value)
    if not isinstance(frozen, Mapping):  # pragma: no cover - guarded above
        raise TypeError("payload must be a mapping")
    return frozen


class OutboxOperationStatus(str, Enum):
    """Stable outcome codes returned instead of leaking persistence errors."""

    APPLIED = "applied"
    NOT_FOUND = "not_found"
    OWNERSHIP_CONFLICT = "ownership_conflict"
    LEASE_EXPIRED = "lease_expired"
    STALE_FENCE = "stale_fence"
    INVALID_STATE = "invalid_state"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"


_REJECTED_STATUSES = frozenset(
    {
        OutboxOperationStatus.NOT_FOUND,
        OutboxOperationStatus.OWNERSHIP_CONFLICT,
        OutboxOperationStatus.LEASE_EXPIRED,
        OutboxOperationStatus.STALE_FENCE,
        OutboxOperationStatus.INVALID_STATE,
        OutboxOperationStatus.IDEMPOTENCY_CONFLICT,
    }
)


def _operation_result(
    status: OutboxOperationStatus,
    idempotent_replay: bool,
    *,
    applied_value_present: bool,
) -> None:
    if not isinstance(status, OutboxOperationStatus):
        raise TypeError("status must be an OutboxOperationStatus")
    if not isinstance(idempotent_replay, bool):
        raise TypeError("idempotent_replay must be a boolean")
    if status is OutboxOperationStatus.APPLIED:
        if not applied_value_present:
            raise ValueError("an applied result must contain its resulting state")
    elif status in _REJECTED_STATUSES:
        if applied_value_present:
            raise ValueError("a rejected result cannot contain applied state")
        if idempotent_replay:
            raise ValueError("a rejected result cannot be an idempotent replay")


@dataclass(frozen=True)
class OutboxLease:
    """Opaque ownership proof and monotonic fence for one delivery attempt."""

    consumer_id: str
    event_id: str
    owner_id: str
    lease_token: str
    fencing_token: int
    delivery_attempt: int
    replay_generation: int
    acquired_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        _identifier("consumer_id", self.consumer_id)
        _identifier("event_id", self.event_id)
        _identifier("owner_id", self.owner_id)
        _identifier("lease_token", self.lease_token, maximum=256)
        _positive_int("fencing_token", self.fencing_token)
        _positive_int("delivery_attempt", self.delivery_attempt)
        if isinstance(self.replay_generation, bool) or not isinstance(self.replay_generation, int):
            raise TypeError("replay_generation must be an integer")
        if self.replay_generation < 0:
            raise ValueError("replay_generation cannot be negative")
        acquired_at = _utc_datetime("acquired_at", self.acquired_at)
        expires_at = _utc_datetime("expires_at", self.expires_at)
        if expires_at <= acquired_at:
            raise ValueError("expires_at must be later than acquired_at")
        object.__setattr__(self, "acquired_at", acquired_at)
        object.__setattr__(self, "expires_at", expires_at)


@dataclass(frozen=True)
class OutboxClaimedEvent:
    """Immutable delivery envelope; it is deliberately not an ORM entity."""

    event_id: str
    event_type: str
    aggregate_type: str
    aggregate_id: str
    version_id: str
    request_id: str
    occurred_at: datetime
    lease: OutboxLease
    payload: Mapping[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _identifier("event_id", self.event_id)
        _identifier("event_type", self.event_type)
        _identifier("aggregate_type", self.aggregate_type)
        _identifier("aggregate_id", self.aggregate_id)
        _identifier("version_id", self.version_id)
        _identifier("request_id", self.request_id)
        occurred_at = _utc_datetime("occurred_at", self.occurred_at)
        if not isinstance(self.lease, OutboxLease):
            raise TypeError("lease must be an OutboxLease")
        if self.lease.event_id != self.event_id:
            raise ValueError("lease event_id must match the envelope event_id")
        object.__setattr__(self, "occurred_at", occurred_at)
        object.__setattr__(self, "payload", _frozen_payload(self.payload))


@dataclass(frozen=True)
class OutboxClaimInput:
    consumer_id: str
    owner_id: str
    operation_id: str
    requested_at: datetime
    lease_duration: timedelta
    limit: int = 1

    def __post_init__(self) -> None:
        _identifier("consumer_id", self.consumer_id)
        _identifier("owner_id", self.owner_id)
        _identifier("operation_id", self.operation_id)
        object.__setattr__(self, "requested_at", _utc_datetime("requested_at", self.requested_at))
        _lease_duration(self.lease_duration)
        _positive_int("limit", self.limit, maximum=_MAX_CLAIM_LIMIT)


@dataclass(frozen=True)
class OutboxClaimResult:
    operation_id: str
    consumer_id: str
    owner_id: str
    status: OutboxOperationStatus
    claimed_at: datetime
    events: tuple[OutboxClaimedEvent, ...] = ()
    idempotent_replay: bool = False

    def __post_init__(self) -> None:
        _identifier("operation_id", self.operation_id)
        _identifier("consumer_id", self.consumer_id)
        _identifier("owner_id", self.owner_id)
        claimed_at = _utc_datetime("claimed_at", self.claimed_at)
        if not isinstance(self.events, tuple) or any(not isinstance(event, OutboxClaimedEvent) for event in self.events):
            raise TypeError("events must be a tuple of OutboxClaimedEvent values")
        if not isinstance(self.status, OutboxOperationStatus):
            raise TypeError("status must be an OutboxOperationStatus")
        if not isinstance(self.idempotent_replay, bool):
            raise TypeError("idempotent_replay must be a boolean")
        if self.status not in {OutboxOperationStatus.APPLIED, OutboxOperationStatus.IDEMPOTENCY_CONFLICT}:
            raise ValueError("claim may only be applied or rejected for idempotency conflict")
        if self.status is OutboxOperationStatus.IDEMPOTENCY_CONFLICT and self.events:
            raise ValueError("an idempotency conflict cannot return claimed events")
        if self.status is OutboxOperationStatus.IDEMPOTENCY_CONFLICT and self.idempotent_replay:
            raise ValueError("an idempotency conflict cannot be an idempotent replay")
        identities = {(event.lease.consumer_id, event.event_id) for event in self.events}
        if len(identities) != len(self.events):
            raise ValueError("a claim result cannot contain the same delivery more than once")
        if any(
            event.lease.consumer_id != self.consumer_id or event.lease.owner_id != self.owner_id
            for event in self.events
        ):
            raise ValueError("claimed leases must match the result consumer and owner")
        object.__setattr__(self, "claimed_at", claimed_at)


@dataclass(frozen=True)
class OutboxLeaseRenewalInput:
    lease: OutboxLease
    operation_id: str
    requested_at: datetime
    lease_duration: timedelta

    def __post_init__(self) -> None:
        if not isinstance(self.lease, OutboxLease):
            raise TypeError("lease must be an OutboxLease")
        _identifier("operation_id", self.operation_id)
        object.__setattr__(self, "requested_at", _utc_datetime("requested_at", self.requested_at))
        _lease_duration(self.lease_duration)


@dataclass(frozen=True)
class OutboxLeaseRenewalResult:
    operation_id: str
    event_id: str
    consumer_id: str
    status: OutboxOperationStatus
    lease: OutboxLease | None = None
    idempotent_replay: bool = False

    def __post_init__(self) -> None:
        _identifier("operation_id", self.operation_id)
        _identifier("event_id", self.event_id)
        _identifier("consumer_id", self.consumer_id)
        if self.lease is not None and not isinstance(self.lease, OutboxLease):
            raise TypeError("lease must be an OutboxLease")
        _operation_result(self.status, self.idempotent_replay, applied_value_present=self.lease is not None)
        if self.lease is not None and (
            self.lease.event_id != self.event_id or self.lease.consumer_id != self.consumer_id
        ):
            raise ValueError("renewed lease identity must match the result")


@dataclass(frozen=True)
class OutboxAcknowledgeSuccessInput:
    lease: OutboxLease
    operation_id: str
    acknowledged_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.lease, OutboxLease):
            raise TypeError("lease must be an OutboxLease")
        _identifier("operation_id", self.operation_id)
        object.__setattr__(self, "acknowledged_at", _utc_datetime("acknowledged_at", self.acknowledged_at))


@dataclass(frozen=True)
class OutboxAcknowledgeSuccessResult:
    operation_id: str
    event_id: str
    consumer_id: str
    status: OutboxOperationStatus
    acknowledged_at: datetime | None = None
    idempotent_replay: bool = False

    def __post_init__(self) -> None:
        _identifier("operation_id", self.operation_id)
        _identifier("event_id", self.event_id)
        _identifier("consumer_id", self.consumer_id)
        acknowledged_at = None
        if self.acknowledged_at is not None:
            acknowledged_at = _utc_datetime("acknowledged_at", self.acknowledged_at)
        _operation_result(
            self.status,
            self.idempotent_replay,
            applied_value_present=acknowledged_at is not None,
        )
        object.__setattr__(self, "acknowledged_at", acknowledged_at)


@dataclass(frozen=True)
class OutboxFailure:
    """Allowlisted failure metadata; raw exception text is intentionally absent."""

    code: str
    diagnostic_id: str | None = None

    def __post_init__(self) -> None:
        _identifier("failure code", self.code)
        if self.diagnostic_id is not None:
            _identifier("diagnostic_id", self.diagnostic_id)


@dataclass(frozen=True)
class OutboxRetryInput:
    lease: OutboxLease
    operation_id: str
    failed_at: datetime
    available_at: datetime
    failure: OutboxFailure

    def __post_init__(self) -> None:
        if not isinstance(self.lease, OutboxLease):
            raise TypeError("lease must be an OutboxLease")
        if not isinstance(self.failure, OutboxFailure):
            raise TypeError("failure must be an OutboxFailure")
        _identifier("operation_id", self.operation_id)
        failed_at = _utc_datetime("failed_at", self.failed_at)
        available_at = _utc_datetime("available_at", self.available_at)
        if available_at < failed_at:
            raise ValueError("available_at cannot be earlier than failed_at")
        object.__setattr__(self, "failed_at", failed_at)
        object.__setattr__(self, "available_at", available_at)


@dataclass(frozen=True)
class OutboxRetryResult:
    operation_id: str
    event_id: str
    consumer_id: str
    status: OutboxOperationStatus
    available_at: datetime | None = None
    next_delivery_attempt: int | None = None
    idempotent_replay: bool = False

    def __post_init__(self) -> None:
        _identifier("operation_id", self.operation_id)
        _identifier("event_id", self.event_id)
        _identifier("consumer_id", self.consumer_id)
        available_at = None
        if self.available_at is not None:
            available_at = _utc_datetime("available_at", self.available_at)
        if self.next_delivery_attempt is not None:
            _positive_int("next_delivery_attempt", self.next_delivery_attempt)
        applied_value_present = available_at is not None and self.next_delivery_attempt is not None
        if (available_at is None) != (self.next_delivery_attempt is None):
            raise ValueError("retry result state must include both available_at and next_delivery_attempt")
        _operation_result(self.status, self.idempotent_replay, applied_value_present=applied_value_present)
        object.__setattr__(self, "available_at", available_at)


@dataclass(frozen=True)
class OutboxDeadLetterInput:
    lease: OutboxLease
    operation_id: str
    failed_at: datetime
    failure: OutboxFailure

    def __post_init__(self) -> None:
        if not isinstance(self.lease, OutboxLease):
            raise TypeError("lease must be an OutboxLease")
        if not isinstance(self.failure, OutboxFailure):
            raise TypeError("failure must be an OutboxFailure")
        _identifier("operation_id", self.operation_id)
        object.__setattr__(self, "failed_at", _utc_datetime("failed_at", self.failed_at))


@dataclass(frozen=True)
class OutboxDeadLetterResult:
    operation_id: str
    event_id: str
    consumer_id: str
    status: OutboxOperationStatus
    dead_letter_id: str | None = None
    dead_lettered_at: datetime | None = None
    idempotent_replay: bool = False

    def __post_init__(self) -> None:
        _identifier("operation_id", self.operation_id)
        _identifier("event_id", self.event_id)
        _identifier("consumer_id", self.consumer_id)
        if self.dead_letter_id is not None:
            _identifier("dead_letter_id", self.dead_letter_id, maximum=256)
        dead_lettered_at = None
        if self.dead_lettered_at is not None:
            dead_lettered_at = _utc_datetime("dead_lettered_at", self.dead_lettered_at)
        if (self.dead_letter_id is None) != (dead_lettered_at is None):
            raise ValueError("dead-letter result state must include its token and timestamp")
        _operation_result(
            self.status,
            self.idempotent_replay,
            applied_value_present=self.dead_letter_id is not None,
        )
        object.__setattr__(self, "dead_lettered_at", dead_lettered_at)


@dataclass(frozen=True)
class OutboxReplayInput:
    consumer_id: str
    event_id: str
    dead_letter_id: str
    operation_id: str
    requested_at: datetime
    available_at: datetime

    def __post_init__(self) -> None:
        _identifier("consumer_id", self.consumer_id)
        _identifier("event_id", self.event_id)
        _identifier("dead_letter_id", self.dead_letter_id, maximum=256)
        _identifier("operation_id", self.operation_id)
        requested_at = _utc_datetime("requested_at", self.requested_at)
        available_at = _utc_datetime("available_at", self.available_at)
        if available_at < requested_at:
            raise ValueError("available_at cannot be earlier than requested_at")
        object.__setattr__(self, "requested_at", requested_at)
        object.__setattr__(self, "available_at", available_at)


@dataclass(frozen=True)
class OutboxReplayResult:
    operation_id: str
    event_id: str
    consumer_id: str
    status: OutboxOperationStatus
    available_at: datetime | None = None
    replay_generation: int | None = None
    idempotent_replay: bool = False

    def __post_init__(self) -> None:
        _identifier("operation_id", self.operation_id)
        _identifier("event_id", self.event_id)
        _identifier("consumer_id", self.consumer_id)
        available_at = None
        if self.available_at is not None:
            available_at = _utc_datetime("available_at", self.available_at)
        if self.replay_generation is not None:
            _positive_int("replay_generation", self.replay_generation)
        if (available_at is None) != (self.replay_generation is None):
            raise ValueError("replay result state must include available_at and replay_generation")
        _operation_result(
            self.status,
            self.idempotent_replay,
            applied_value_present=available_at is not None,
        )
        object.__setattr__(self, "available_at", available_at)


@runtime_checkable
class OutboxClaimPort(Protocol):
    """M0-owned atomic persistence boundary used by an M4 Worker."""

    def claim(self, command: OutboxClaimInput) -> OutboxClaimResult:
        """Claim eligible or expired deliveries in one atomic operation."""
        ...

    def renew_lease(self, command: OutboxLeaseRenewalInput) -> OutboxLeaseRenewalResult:
        """Record a heartbeat and renew a current, unexpired lease."""
        ...

    def acknowledge_success(self, command: OutboxAcknowledgeSuccessInput) -> OutboxAcknowledgeSuccessResult:
        """Atomically mark a current leased delivery as succeeded."""
        ...

    def schedule_retry(self, command: OutboxRetryInput) -> OutboxRetryResult:
        """Release a current lease and schedule its bounded-backoff retry."""
        ...

    def dead_letter(self, command: OutboxDeadLetterInput) -> OutboxDeadLetterResult:
        """Move a current leased delivery to its terminal failure state."""
        ...

    def replay(self, command: OutboxReplayInput) -> OutboxReplayResult:
        """Explicitly requeue the current matching dead-letter occurrence."""
        ...


__all__ = [
    "OutboxAcknowledgeSuccessInput",
    "OutboxAcknowledgeSuccessResult",
    "OutboxClaimInput",
    "OutboxClaimPort",
    "OutboxClaimResult",
    "OutboxClaimedEvent",
    "OutboxDeadLetterInput",
    "OutboxDeadLetterResult",
    "OutboxFailure",
    "OutboxLease",
    "OutboxLeaseRenewalInput",
    "OutboxLeaseRenewalResult",
    "OutboxOperationStatus",
    "OutboxReplayInput",
    "OutboxReplayResult",
    "OutboxRetryInput",
    "OutboxRetryResult",
]
