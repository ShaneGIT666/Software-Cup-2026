"""M1 identity domain public surface."""

from .authorization import ensure_not_self_review, permissions_for_roles
from .contracts import ActorKind, AuthenticatedActor, CurrentUser, ManagedServiceKey, Permission, RoleCode
from .runtime import validate_identity_runtime_settings

__all__ = [
    "ActorKind",
    "AuthenticatedActor",
    "CurrentUser",
    "ManagedServiceKey",
    "Permission",
    "RoleCode",
    "ensure_not_self_review",
    "permissions_for_roles",
    "validate_identity_runtime_settings",
]
