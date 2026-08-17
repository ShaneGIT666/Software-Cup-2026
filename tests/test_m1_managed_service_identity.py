from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from backend.app.core.config import AppSettings
from backend.app.domains.identity.activation import activate_identity_instance
from backend.app.domains.identity.contracts import AuthenticatedActor, ActorKind, ManagedServiceKey
from backend.app.domains.identity.login import LoginUseCase
from backend.app.domains.identity.readiness import IdentityReadinessContributor
from backend.app.domains.identity.repository import LoginThrottleSnapshot
from backend.app.domains.identity.service import LoginVerification
from backend.app.domains.identity.service_accounts import (
    AUTHENTICATION_SERVICE,
    BOOTSTRAP_SERVICE,
    MANAGED_SERVICE_ACCOUNTS,
    WORKER_SERVICE,
)


NOW = datetime(2026, 8, 17, 8, 0, tzinfo=timezone.utc)


def _settings(*, environment: str = "test") -> AppSettings:
    return AppSettings(
        environment=environment,
        database_url="postgresql+psycopg://test:test@localhost/identity_test",
        database_required=True,
        application_name="managed-service-test",
        trusted_origins=("https://repair.example.com",),
        idempotency_secret="i" * 32,
        auth_mode="local",
        auth_secret="a" * 32,
        session_cookie_name="__Host-repair_session" if environment == "production" else "repair_session",
        session_cookie_secure=environment == "production",
        session_ttl_minutes=480,
        session_idle_timeout_minutes=30,
        auth_max_login_failures=5,
        auth_login_window_seconds=900,
        auth_lock_seconds=900,
        legacy_surface_mode="disabled" if environment == "production" else "enabled",
    )


@contextmanager
def _session_context(session):  # type: ignore[no-untyped-def]
    yield session


def test_managed_service_accounts_are_stable_noninteractive_actors() -> None:
    assert {account.key for account in MANAGED_SERVICE_ACCOUNTS} == {
        ManagedServiceKey.AUTHENTICATION,
        ManagedServiceKey.BOOTSTRAP,
        ManagedServiceKey.WORKER,
    }
    assert len({account.user_id for account in MANAGED_SERVICE_ACCOUNTS}) == 3
    assert len({account.username for account in MANAGED_SERVICE_ACCOUNTS}) == 3
    assert AUTHENTICATION_SERVICE.actor().kind is ActorKind.SERVICE
    assert BOOTSTRAP_SERVICE.actor().initiator_user_id is None
    assert WORKER_SERVICE.actor(initiator_user_id="user-1").initiator_user_id == "user-1"


def test_authenticated_actor_rejects_ambiguous_or_empty_identity() -> None:
    with pytest.raises(ValueError, match="交互用户不能"):
        AuthenticatedActor(
            user_id="user-1",
            kind=ActorKind.INTERACTIVE,
            initiator_user_id="user-2",
        )
    with pytest.raises(ValueError, match="不能为空"):
        AuthenticatedActor(user_id=" ", kind=ActorKind.SERVICE)
    with pytest.raises(ValueError, match="类型无效"):
        AuthenticatedActor(user_id="user-1", kind="service")  # type: ignore[arg-type]


def test_failed_login_is_audited_by_the_authentication_service_user(monkeypatch) -> None:
    read_session = Mock()
    write_session = Mock()
    sessions = iter((read_session, write_session))
    monkeypatch.setattr(
        "backend.app.domains.identity.login.new_session",
        lambda: _session_context(next(sessions)),
    )
    repository = Mock()
    repository.credential_for_login.return_value = None
    throttles = Mock()
    throttles.get_states.return_value = LoginThrottleSnapshot(subject=None, source=None)
    identity = Mock()
    identity._throttle_subject.return_value = ("alice", "alice")
    identity.verify_login_candidate.return_value = LoginVerification(
        user_id=None,
        password_hash=None,
        auth_version=None,
        subject_hmac="s" * 64,
        source_hmac="i" * 64,
        locked=False,
    )
    audit = Mock()
    use_case = LoginUseCase(
        repository=repository,
        throttle_repository=throttles,
        identity_service=identity,
        audit_writer=audit,
    )

    result = use_case.authenticate(
        username="Alice",
        password="wrong-password",
        source_address="192.0.2.8",
        settings=_settings(),
        request_id="login-failed-1",
        now=NOW,
    )

    assert result.authenticated is False
    identity.record_failed_login.assert_called_once()
    event = audit.append.call_args.args[1]
    assert event.action == "auth.login_failed"
    assert event.actor_user_id == AUTHENTICATION_SERVICE.user_id
    assert event.initiator_user_id is None


def test_activation_requires_changed_admin_password_and_records_the_actor(monkeypatch) -> None:
    read_session = Mock()
    write_session = Mock()
    sessions = iter((read_session, write_session))
    monkeypatch.setattr(
        "backend.app.domains.identity.activation.new_session",
        lambda: _session_context(next(sessions)),
    )
    monkeypatch.setattr("backend.app.domains.identity.activation.get_settings", lambda: _settings())
    monkeypatch.setattr(
        "backend.app.domains.identity.activation.validate_identity_runtime_settings",
        lambda settings: None,
    )
    credential = SimpleNamespace(user_id="admin-1", password_hash="argon2", auth_version=3)
    state = SimpleNamespace(
        id="identity",
        lifecycle="bootstrapped",
        version=2,
        activated_at=None,
        activated_by_user_id=None,
    )
    user = SimpleNamespace(id="admin-1", must_change_password=False)
    repository = Mock()
    repository.credential_for_login.return_value = credential
    repository.lock_instance_state.return_value = state
    repository.revalidate_login_candidate.return_value = user
    repository.role_codes_for_user.return_value = frozenset({"system_admin"})
    hasher = Mock()
    hasher.verify.return_value = True
    audit = Mock()

    actor_id = activate_identity_instance(
        username="Admin.User",
        password="changed-password",
        repository=repository,
        audit_writer=audit,
        password_hasher=hasher,
        now=NOW,
    )

    assert actor_id == "admin-1"
    assert state.lifecycle == "active"
    assert state.version == 3
    assert state.activated_at == NOW
    assert state.activated_by_user_id == "admin-1"
    event = audit.append.call_args.args[1]
    assert event.actor_user_id == "admin-1"
    assert event.action == "identity.instance_activated"
    assert event.request_id.startswith("activation-cli:")


def test_activation_rejects_an_unchanged_bootstrap_password(monkeypatch) -> None:
    sessions = iter((Mock(), Mock()))
    monkeypatch.setattr(
        "backend.app.domains.identity.activation.new_session",
        lambda: _session_context(next(sessions)),
    )
    monkeypatch.setattr("backend.app.domains.identity.activation.get_settings", lambda: _settings())
    monkeypatch.setattr(
        "backend.app.domains.identity.activation.validate_identity_runtime_settings",
        lambda settings: None,
    )
    repository = Mock()
    repository.credential_for_login.return_value = SimpleNamespace(
        user_id="admin-1",
        password_hash="argon2",
        auth_version=1,
    )
    repository.lock_instance_state.return_value = SimpleNamespace(
        lifecycle="bootstrapped",
        version=2,
    )
    repository.revalidate_login_candidate.return_value = SimpleNamespace(
        id="admin-1",
        must_change_password=True,
    )
    hasher = Mock()
    hasher.verify.return_value = True

    with pytest.raises(RuntimeError, match="必须先修改临时密码"):
        activate_identity_instance(
            username="Admin.User",
            password="initial-password",
            repository=repository,
            audit_writer=Mock(),
            password_hasher=hasher,
            now=NOW,
        )


@pytest.mark.parametrize(
    ("lifecycle", "healthy"),
    (("bootstrapped", False), ("active", True)),
)
def test_production_identity_readiness_requires_explicit_activation(
    monkeypatch,
    lifecycle: str,
    healthy: bool,
) -> None:
    session = Mock()
    repository = Mock()
    repository.instance_state.return_value = SimpleNamespace(lifecycle=lifecycle)
    monkeypatch.setattr(
        "backend.app.domains.identity.readiness.new_session",
        lambda: _session_context(session),
    )
    monkeypatch.setattr(
        "backend.app.domains.identity.readiness.IdentityRepository",
        lambda: repository,
    )

    probe = IdentityReadinessContributor().check(_settings(environment="production"))

    assert probe.healthy is healthy
    assert probe.reason == ("" if healthy else "身份实例尚未激活")
