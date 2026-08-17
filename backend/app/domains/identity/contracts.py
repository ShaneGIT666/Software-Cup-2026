from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class RoleCode(str, Enum):
    TECHNICIAN = "technician"
    REVIEWER = "reviewer"
    KNOWLEDGE_MANAGER = "knowledge_manager"
    SYSTEM_ADMIN = "system_admin"
    AUDITOR = "auditor"


class ActorKind(str, Enum):
    INTERACTIVE = "interactive"
    SERVICE = "service"


class ManagedServiceKey(str, Enum):
    AUTHENTICATION = "authentication"
    BOOTSTRAP = "bootstrap"
    WORKER = "worker"


class Permission(str, Enum):
    KNOWLEDGE_READ = "knowledge:read"
    WORKFLOW_READ = "workflow:read"
    CASE_CREATE = "case:create"
    FEEDBACK_CREATE = "feedback:create"
    KNOWLEDGE_REVIEW = "knowledge:review"
    WORKFLOW_REVIEW = "workflow:review"
    CASE_REVIEW = "case:review"
    FEEDBACK_REVIEW = "feedback:review"
    DOCUMENT_WRITE = "document:write"
    KNOWLEDGE_WRITE = "knowledge:write"
    WORKFLOW_WRITE = "workflow:write"
    IAM_USERS_READ = "iam:users:read"
    IAM_USERS_WRITE = "iam:users:write"
    IAM_ROLES_WRITE = "iam:roles:write"
    OPS_READ = "ops:read"
    AUDIT_READ = "audit:read"


ROLE_PERMISSIONS: dict[RoleCode, frozenset[Permission]] = {
    RoleCode.TECHNICIAN: frozenset(
        {
            Permission.KNOWLEDGE_READ,
            Permission.WORKFLOW_READ,
            Permission.CASE_CREATE,
            Permission.FEEDBACK_CREATE,
        }
    ),
    RoleCode.REVIEWER: frozenset(
        {
            Permission.KNOWLEDGE_READ,
            Permission.WORKFLOW_READ,
            Permission.KNOWLEDGE_REVIEW,
            Permission.WORKFLOW_REVIEW,
            Permission.CASE_REVIEW,
            Permission.FEEDBACK_REVIEW,
        }
    ),
    RoleCode.KNOWLEDGE_MANAGER: frozenset(
        {
            Permission.KNOWLEDGE_READ,
            Permission.WORKFLOW_READ,
            Permission.DOCUMENT_WRITE,
            Permission.KNOWLEDGE_WRITE,
            Permission.WORKFLOW_WRITE,
        }
    ),
    RoleCode.SYSTEM_ADMIN: frozenset(
        {
            Permission.IAM_USERS_READ,
            Permission.IAM_USERS_WRITE,
            Permission.IAM_ROLES_WRITE,
            Permission.OPS_READ,
        }
    ),
    RoleCode.AUDITOR: frozenset({Permission.AUDIT_READ, Permission.OPS_READ}),
}


@dataclass(frozen=True)
class CurrentUser:
    """M1-owned identity port consumed by business modules."""

    id: str
    roles: frozenset[str]
    permissions: frozenset[str]
    session_id: str


@dataclass(frozen=True)
class AuthenticatedActor:
    """Auditable principal for an interactive or managed internal write."""

    user_id: str
    kind: ActorKind
    initiator_user_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ActorKind):
            raise ValueError("审计主体类型无效")
        if not self.user_id.strip():
            raise ValueError("审计主体用户标识不能为空")
        if self.initiator_user_id is not None and not self.initiator_user_id.strip():
            raise ValueError("发起用户标识不能为空字符串")
        if self.kind == ActorKind.INTERACTIVE and self.initiator_user_id is not None:
            raise ValueError("交互用户不能另行声明发起用户")


@dataclass(frozen=True)
class ResolvedIdentity:
    """M1-private request identity with session/profile details for auth APIs."""

    current_user: CurrentUser
    display_name: str
    must_change_password: bool
    expires_at: datetime
    idle_expires_at: datetime
    csrf_digest: str
