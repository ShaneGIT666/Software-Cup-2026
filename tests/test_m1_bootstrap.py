from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from backend.app.domains.audit.models import AuditEvent
from backend.app.domains.identity.bootstrap import bootstrap_system_admin
from backend.app.domains.identity.models import User, UserRole
from backend.app.domains.identity.service_accounts import BOOTSTRAP_SERVICE


@contextmanager
def _session_context(session):  # type: ignore[no-untyped-def]
    yield session


def test_bootstrap_creates_admin_role_and_audit_in_one_owned_transaction(monkeypatch) -> None:
    role = SimpleNamespace(id="role-admin")
    state = SimpleNamespace(lifecycle="uninitialized", version=1)
    service_user = SimpleNamespace(id=BOOTSTRAP_SERVICE.user_id)
    repository = Mock()
    repository.lock_instance_state.return_value = state
    repository.managed_service_user.return_value = service_user
    repository.interactive_user_count.return_value = 0
    session = Mock()
    session.scalar.return_value = role
    added: list[object] = []
    session.add.side_effect = added.append
    monkeypatch.setattr("backend.app.domains.identity.bootstrap.new_session", lambda: _session_context(session))
    monkeypatch.setattr("backend.app.domains.identity.bootstrap.get_settings", lambda: Mock())
    monkeypatch.setattr("backend.app.domains.identity.bootstrap.validate_identity_runtime_settings", lambda settings: None)
    monkeypatch.setattr("backend.app.domains.identity.bootstrap.hash_password", lambda password: "argon2-hash")

    user_id = bootstrap_system_admin(
        username="Admin.User",
        display_name="管理员",
        password="password",
        repository=repository,
    )

    assert user_id
    assert isinstance(added[0], User)
    assert isinstance(added[1], UserRole)
    assert isinstance(added[2], AuditEvent)
    assert added[0].password_hash == "argon2-hash"
    assert added[0].must_change_password is True
    assert added[1].assigned_by_user_id == BOOTSTRAP_SERVICE.user_id
    assert added[2].actor_user_id == BOOTSTRAP_SERVICE.user_id
    assert added[2].request_id.startswith("bootstrap-cli:")
    assert state.lifecycle == "bootstrapped"
    assert state.version == 2
    session.commit.assert_not_called()


def test_bootstrap_rejects_a_nonempty_user_database(monkeypatch) -> None:
    repository = Mock()
    repository.lock_instance_state.return_value = SimpleNamespace(lifecycle="uninitialized", version=1)
    repository.managed_service_user.return_value = SimpleNamespace(id=BOOTSTRAP_SERVICE.user_id)
    repository.interactive_user_count.return_value = 1
    session = Mock()
    session.scalar.return_value = SimpleNamespace(id="role-admin")
    monkeypatch.setattr("backend.app.domains.identity.bootstrap.new_session", lambda: _session_context(session))
    monkeypatch.setattr("backend.app.domains.identity.bootstrap.get_settings", lambda: Mock())
    monkeypatch.setattr("backend.app.domains.identity.bootstrap.validate_identity_runtime_settings", lambda settings: None)
    monkeypatch.setattr("backend.app.domains.identity.bootstrap.hash_password", lambda password: "argon2-hash")

    with pytest.raises(RuntimeError, match="用户库非空"):
        bootstrap_system_admin(
            username="Admin.User",
            display_name="管理员",
            password="password",
            repository=repository,
        )


def test_bootstrap_rejects_an_already_bootstrapped_instance(monkeypatch) -> None:
    repository = Mock()
    repository.lock_instance_state.return_value = SimpleNamespace(lifecycle="bootstrapped", version=2)
    session = Mock()
    monkeypatch.setattr("backend.app.domains.identity.bootstrap.new_session", lambda: _session_context(session))
    monkeypatch.setattr("backend.app.domains.identity.bootstrap.get_settings", lambda: Mock())
    monkeypatch.setattr("backend.app.domains.identity.bootstrap.validate_identity_runtime_settings", lambda settings: None)
    monkeypatch.setattr("backend.app.domains.identity.bootstrap.hash_password", lambda password: "argon2-hash")

    with pytest.raises(RuntimeError, match="已经引导或激活"):
        bootstrap_system_admin(
            username="Admin.User",
            display_name="管理员",
            password="password",
            repository=repository,
        )

    repository.interactive_user_count.assert_not_called()
