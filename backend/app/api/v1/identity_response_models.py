from __future__ import annotations

from datetime import datetime
from typing import Literal

from ...core.contracts import V1ContractModel, V1PageResponse, V1Response
from ...domains.identity.contracts import Permission, RoleCode


class IdentityUserData(V1ContractModel):
    id: str
    displayName: str
    roles: list[RoleCode]
    permissions: list[Permission]
    mustChangePassword: bool


class IdentitySessionData(V1ContractModel):
    expiresAt: datetime
    idleExpiresAt: datetime


class MeData(V1ContractModel):
    user: IdentityUserData
    session: IdentitySessionData


class LoginData(MeData):
    csrfToken: str


class LoginResponse(V1Response[LoginData]):
    pass


class MeResponse(V1Response[MeData]):
    pass


class LogoutData(V1ContractModel):
    loggedOut: Literal[True] = True


class LogoutResponse(V1Response[LogoutData]):
    pass


class CsrfData(V1ContractModel):
    csrfToken: str


class CsrfResponse(V1Response[CsrfData]):
    pass


class PasswordChangeData(V1ContractModel):
    changed: Literal[True] = True
    mustChangePassword: Literal[False] = False
    reauthenticationRequired: Literal[False] = False


class PasswordChangeResponse(V1Response[PasswordChangeData]):
    pass


class UserData(V1ContractModel):
    id: str
    username: str
    displayName: str
    isActive: bool
    roles: list[RoleCode]
    mustChangePassword: bool
    version: int
    createdAt: datetime | None
    updatedAt: datetime | None


class UserResponse(V1Response[UserData]):
    pass


class UserListResponse(V1PageResponse[UserData]):
    pass


class RoleData(V1ContractModel):
    code: RoleCode
    permissions: list[Permission]


class RolesResponse(V1Response[list[RoleData]]):
    pass


class AuditMetadataData(V1ContractModel):
    roles: list[RoleCode] | None = None
    fields: list[Literal["displayName"]] | None = None
    reason: str | None = None
    lifecycle: Literal["bootstrapped", "active"] | None = None
    sourceHmac: str | None = None


class AuditEventData(V1ContractModel):
    id: str
    occurredAt: datetime
    actorUserId: str
    initiatorUserId: str | None
    action: str
    targetType: str
    targetId: str
    result: Literal["success", "denied"]
    requestId: str
    metadata: AuditMetadataData


class AuditEventListResponse(V1PageResponse[AuditEventData]):
    pass
