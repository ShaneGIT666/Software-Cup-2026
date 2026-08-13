from __future__ import annotations

from collections.abc import Iterable

from ...core.error_codes import ErrorCode
from ...core.errors import AppError
from .contracts import CurrentUser, Permission, ROLE_PERMISSIONS, RoleCode


def permissions_for_roles(roles: Iterable[str | RoleCode]) -> frozenset[str]:
    permissions: set[str] = set()
    for role in roles:
        try:
            role_code = role if isinstance(role, RoleCode) else RoleCode(role)
        except ValueError:
            continue
        permissions.update(permission.value for permission in ROLE_PERMISSIONS[role_code])
    return frozenset(permissions)


def require_permission_set(current_user: CurrentUser, *permissions: str | Permission) -> None:
    required = {permission.value if isinstance(permission, Permission) else permission for permission in permissions}
    if not required.issubset(current_user.permissions):
        raise AppError(403, ErrorCode.FORBIDDEN, "当前用户没有执行该操作的权限。")


def ensure_not_self_review(current_user: CurrentUser, submitter_user_id: str) -> None:
    if current_user.id == submitter_user_id:
        raise AppError(403, ErrorCode.SELF_REVIEW_FORBIDDEN, "提交人不能审核自己的内容。")

