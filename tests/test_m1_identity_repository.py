from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.dialects import postgresql

from backend.app.core.config import AppSettings
from backend.app.domains.identity.models import User
from backend.app.domains.identity.repository import (
    IdentityRepository,
    LoginCredentialRecord,
    LoginThrottleRepository,
    LoginThrottleSnapshot,
    LoginThrottleState,
    login_throttle_digests,
)
from backend.app.domains.identity.service import IdentityService, LoginVerification
from backend.app.domains.identity.sessions import issue_session_secrets
from backend.app.domains.identity.usernames import normalize_username


NOW = datetime(2026, 8, 13, 8, 0, tzinfo=timezone.utc)


def _settings() -> AppSettings:
    return AppSettings(
        environment="test",
        database_url="postgresql+psycopg://test:test@localhost/test",
        database_required=True,
        application_name="m1-test",
        trusted_origins=("http://localhost:5173",),
        idempotency_secret="i" * 32,
        auth_mode="local",
        auth_secret="a" * 32,
        session_cookie_name="repair_session",
        session_cookie_secure=False,
        session_ttl_minutes=480,
        session_idle_timeout_minutes=30,
        auth_max_login_failures=5,
        auth_login_window_seconds=900,
        auth_lock_seconds=900,
    )


class _ExecuteResult:
    def __init__(self, *, row: tuple[int, datetime | None] | None = None, rowcount: int = 0) -> None:
        self._row = row
        self.rowcount = rowcount

    def one(self) -> tuple[int, datetime | None]:
        assert self._row is not None
        return self._row


class _RecordingSession:
    def __init__(self, result: _ExecuteResult | None = None) -> None:
        self.result = result or _ExecuteResult()
        self.statements: list[object] = []
        self.added: list[object] = []

    def execute(self, statement: object) -> _ExecuteResult:
        self.statements.append(statement)
        return self.result

    def add(self, record: object) -> None:
        self.added.append(record)


def test_username_normalization_is_single_canonical_policy() -> None:
    assert normalize_username("  Ａlice.Example  ") == "alice.example"
    assert normalize_username("维修员01") == "维修员01"
    for invalid in ("ab", ".alice", "alice-", "alice smith", "a" * 129):
        with pytest.raises(ValueError):
            normalize_username(invalid)


def test_login_throttle_hmacs_are_stable_separated_and_do_not_store_plaintext() -> None:
    first = login_throttle_digests(
        normalized_username="alice",
        source_address="192.0.2.8",
        secret="a" * 32,
    )
    second = login_throttle_digests(
        normalized_username="alice",
        source_address="192.0.2.8",
        secret="a" * 32,
    )
    assert first == second
    assert first[0] != first[1]
    assert all(len(value) == 64 for value in first)
    assert "alice" not in first[0]
    assert "192.0.2.8" not in first[1]


def test_repository_assigns_session_id_before_flush_and_never_commits() -> None:
    session = _RecordingSession()
    secrets = issue_session_secrets(
        secret="a" * 32,
        ttl_minutes=480,
        idle_timeout_minutes=30,
        now=NOW,
    )

    record = IdentityRepository().create_session(
        session,  # type: ignore[arg-type]
        user_id="user-1",
        auth_version=2,
        secrets=secrets,
        now=NOW,
    )

    assert record.id
    assert session.added == [record]
    assert not hasattr(session, "commit")


def test_session_identity_resolution_uses_one_aggregate_statement() -> None:
    repository = IdentityRepository()
    session = Mock()
    session.execute.return_value.one_or_none.return_value = None

    assert repository.resolve_session(session, "d" * 64) is None

    session.execute.assert_called_once()
    sql = str(session.execute.call_args.args[0].compile(dialect=postgresql.dialect())).lower()
    assert "array_agg" in sql
    assert "auth_sessions" in sql
    assert "users" in sql
    assert "user_roles" in sql


def test_session_activity_refresh_is_conditional_and_never_shortens_idle_expiry() -> None:
    session = _RecordingSession(_ExecuteResult(rowcount=1))

    changed = IdentityRepository().refresh_session_activity(
        session,  # type: ignore[arg-type]
        session_id="session-1",
        now=NOW,
        idle_timeout_minutes=30,
    )

    sql = str(session.statements[0].compile(dialect=postgresql.dialect())).lower()
    assert changed is True
    assert "last_activity_at <=" in sql
    assert "least(" in sql
    assert "greatest(" in sql


def test_login_failure_updates_independent_subject_and_source_buckets() -> None:
    expected_lock = NOW + timedelta(minutes=15)
    session = _RecordingSession(_ExecuteResult(row=(5, expected_lock)))

    state = LoginThrottleRepository().record_failure(
        session,  # type: ignore[arg-type]
        subject_hmac="s" * 64,
        source_hmac="i" * 64,
        now=NOW,
        max_failures=5,
        window_seconds=900,
        lock_seconds=900,
    )

    sql = str(session.statements[0].compile(dialect=postgresql.dialect())).lower()
    assert "on conflict on constraint uq_login_throttle_buckets_type_hmac do update" in sql
    assert "returning login_throttle_buckets.failure_count, login_throttle_buckets.locked_until" in sql
    assert len(session.statements) == 2
    assert state == LoginThrottleSnapshot(
        subject=LoginThrottleState(failure_count=5, locked_until=expected_lock),
        source=LoginThrottleState(failure_count=5, locked_until=expected_lock),
    )


def test_missing_user_still_runs_dummy_argon2_path_and_is_throttled() -> None:
    repository = Mock()
    throttles = Mock()
    hasher = Mock()
    hasher.verify.return_value = False
    service = IdentityService(
        repository=repository,
        throttle_repository=throttles,
        password_hasher=hasher,
    )

    verification = service.verify_login_candidate(
        username="missing-user",
        password="not-the-password",
        source_address="192.0.2.8",
        settings=_settings(),
        now=NOW,
        credential=None,
        throttle_snapshot=LoginThrottleSnapshot(subject=None, source=None),
    )

    assert verification.authenticated is False
    hasher.verify.assert_called_once()
    service.record_failed_login(Mock(), verification=verification, settings=_settings(), now=NOW)
    throttles.record_failure.assert_called_once()


def test_successful_login_creation_uses_one_caller_owned_transaction() -> None:
    user = User(
        id="user-1",
        username="Alice",
        username_normalized="alice",
        display_name="Alice",
        password_hash="hash",
        auth_source="local",
        is_active=True,
        auth_version=3,
    )
    repository = Mock()
    repository.create_session.return_value = SimpleNamespace(id="session-1")
    throttles = Mock()
    service = IdentityService(repository=repository, throttle_repository=throttles, password_hasher=Mock())
    verification = LoginVerification(
        user_id=user.id,
        password_hash=user.password_hash,
        auth_version=user.auth_version,
        subject_hmac="s" * 64,
        source_hmac="i" * 64,
        locked=False,
    )
    session = Mock()
    repository.revalidate_login_candidate.return_value = user
    throttles.get_states.return_value = LoginThrottleSnapshot(subject=None, source=None)

    created = service.create_authenticated_session(
        session,
        verification=verification,
        settings=_settings(),
        now=NOW,
    )

    assert created.session_id == "session-1"
    repository.create_session.assert_called_once()
    throttles.clear_subject.assert_called_once()
    session.commit.assert_not_called()


def test_session_issuance_rechecks_throttle_after_password_verification() -> None:
    repository = Mock()
    throttles = Mock()
    throttles.get_states.return_value = LoginThrottleSnapshot(
        subject=LoginThrottleState(failure_count=5, locked_until=NOW + timedelta(minutes=15)),
        source=None,
    )
    service = IdentityService(repository=repository, throttle_repository=throttles, password_hasher=Mock())
    verification = LoginVerification(
        user_id="user-1",
        password_hash="hash",
        auth_version=3,
        subject_hmac="s" * 64,
        source_hmac="i" * 64,
        locked=False,
    )

    with pytest.raises(ValueError, match="限流状态"):
        service.create_authenticated_session(Mock(), verification=verification, settings=_settings(), now=NOW)

    repository.revalidate_login_candidate.assert_not_called()
