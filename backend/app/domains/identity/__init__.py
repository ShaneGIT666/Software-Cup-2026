"""M1 identity domain public surface."""

from .authorization import ensure_not_self_review, permissions_for_roles
from .contracts import CurrentUser, Permission, RoleCode

__all__ = [
    "CurrentUser",
    "Permission",
    "RoleCode",
    "ensure_not_self_review",
    "permissions_for_roles",
]
