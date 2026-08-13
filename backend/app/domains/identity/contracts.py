from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RoleCode(str, Enum):
    TECHNICIAN = "technician"
    REVIEWER = "reviewer"
    KNOWLEDGE_MANAGER = "knowledge_manager"
    SYSTEM_ADMIN = "system_admin"
    AUDITOR = "auditor"


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

