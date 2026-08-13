from __future__ import annotations

import pytest

from backend.app.core.error_codes import ErrorCode
from backend.app.core.errors import AppError
from backend.app.domains.identity.authorization import (
    ensure_not_self_review,
    permissions_for_roles,
    require_permission_set,
)
from backend.app.domains.identity.contracts import CurrentUser, Permission, RoleCode


def _user(*, user_id: str = "user-001", roles: set[str], permissions: set[str]) -> CurrentUser:
    return CurrentUser(
        id=user_id,
        roles=frozenset(roles),
        permissions=frozenset(permissions),
        session_id="session-001",
    )


def test_system_admin_does_not_inherit_review_or_business_read() -> None:
    permissions = permissions_for_roles([RoleCode.SYSTEM_ADMIN])

    assert Permission.IAM_USERS_WRITE.value in permissions
    assert Permission.KNOWLEDGE_READ.value not in permissions
    assert Permission.KNOWLEDGE_REVIEW.value not in permissions


def test_auditor_needs_an_explicit_business_role() -> None:
    audit_only = permissions_for_roles([RoleCode.AUDITOR])
    combined = permissions_for_roles([RoleCode.AUDITOR, RoleCode.TECHNICIAN])

    assert audit_only == frozenset({Permission.AUDIT_READ.value, Permission.OPS_READ.value})
    assert Permission.KNOWLEDGE_READ.value not in audit_only
    assert Permission.KNOWLEDGE_READ.value in combined


def test_unknown_role_grants_no_permissions() -> None:
    assert permissions_for_roles(["unknown-role"]) == frozenset()


def test_permission_check_and_self_review_are_server_side() -> None:
    current_user = _user(
        roles={RoleCode.REVIEWER.value},
        permissions={Permission.KNOWLEDGE_REVIEW.value},
    )
    require_permission_set(current_user, Permission.KNOWLEDGE_REVIEW)

    with pytest.raises(AppError) as permission_error:
        require_permission_set(current_user, Permission.IAM_USERS_WRITE)
    assert permission_error.value.code == ErrorCode.FORBIDDEN

    with pytest.raises(AppError) as self_review_error:
        ensure_not_self_review(current_user, "user-001")
    assert self_review_error.value.code == ErrorCode.SELF_REVIEW_FORBIDDEN

