from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Mapping

from sqlalchemy.exc import IntegrityError

from ...core.concurrency import require_matching_version
from ...core.error_codes import ErrorCode
from ...core.errors import AppError
from ...db.idempotency import IdempotencyReplay, IdempotencyService
from ...db.session import new_session
from ..audit.contracts import AuditEventInput
from ..audit.writer import AuditWriter
from .contracts import CurrentUser, ROLE_PERMISSIONS, RoleCode
from .models import User
from .passwords import Argon2PasswordHasher, PasswordHasherPort, hash_password
from .repository import IdentityRepository
from .sessions import utc_now
from .usernames import normalize_username


@dataclass(frozen=True)
class WriteResult:
    data: Mapping[str, Any]
    status_code: int
    version: int | None = None


def user_view(user: User, roles: tuple[str, ...] | frozenset[str]) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "displayName": user.display_name,
        "isActive": user.is_active,
        "roles": sorted(roles),
        "mustChangePassword": user.must_change_password,
        "version": user.version,
        "createdAt": user.created_at.isoformat() if user.created_at else None,
        "updatedAt": user.updated_at.isoformat() if user.updated_at else None,
    }


class UserManagementUseCase:
    def __init__(
        self,
        *,
        repository: IdentityRepository | None = None,
        audit_writer: AuditWriter | None = None,
        idempotency: IdempotencyService | None = None,
        password_hasher: PasswordHasherPort | None = None,
    ) -> None:
        self.repository = repository or IdentityRepository()
        self.audit = audit_writer or AuditWriter()
        self.idempotency = idempotency or IdempotencyService()
        self.password_hasher = password_hasher or Argon2PasswordHasher()

    @staticmethod
    def _validate_roles(role_codes: list[str]) -> frozenset[str]:
        if len(role_codes) > len(RoleCode):
            raise AppError(400, ErrorCode.VALIDATION_ERROR, "角色数量超出允许范围。")
        try:
            return frozenset(RoleCode(code).value for code in role_codes)
        except ValueError as exc:
            raise AppError(400, ErrorCode.VALIDATION_ERROR, "包含未知角色代码。") from exc

    def _idempotent_write(
        self,
        *,
        current_user: CurrentUser,
        scope: str,
        key: str,
        request_hash: str,
        operation: Callable[[Any], WriteResult],
    ) -> WriteResult:
        with new_session() as session:
            reservation = self.idempotency.begin(
                session,
                scope=scope,
                actor_id=current_user.id,
                key=key,
                request_hash=request_hash,
            )
            if isinstance(reservation, IdempotencyReplay):
                replay_version = reservation.data.get("version")
                return WriteResult(
                    data=reservation.data,
                    status_code=reservation.status_code,
                    version=replay_version if isinstance(replay_version, int) else None,
                )
            result = operation(session)
            reservation.complete(status_code=result.status_code, data=result.data)
            return result

    def create_user(
        self,
        *,
        current_user: CurrentUser,
        username: str,
        display_name: str,
        initial_password: str,
        role_codes: list[str],
        idempotency_key: str,
        request_hash: str,
        request_id: str,
    ) -> WriteResult:
        normalized = normalize_username(username)
        password_hash = hash_password(initial_password, hasher=self.password_hasher)
        validated_roles = self._validate_roles(role_codes)

        def operation(session):  # type: ignore[no-untyped-def]
            roles = self.repository.roles_by_codes(session, validated_roles)
            if len(roles) != len(validated_roles):
                raise AppError(400, ErrorCode.VALIDATION_ERROR, "包含未知角色代码。")
            user = User(
                username=username.strip(),
                username_normalized=normalized,
                display_name=display_name.strip(),
                password_hash=password_hash,
                auth_source="local",
                is_active=True,
                must_change_password=True,
            )
            session.add(user)
            session.flush()
            self.repository.replace_user_roles(
                session,
                user_id=user.id,
                roles=roles,
                assigned_by_user_id=current_user.id,
            )
            self.audit.append(
                session,
                AuditEventInput(
                    action="user.created",
                    target_type="user",
                    target_id=user.id,
                    result="success",
                    request_id=request_id,
                    actor_user_id=current_user.id,
                    metadata={"roles": sorted(validated_roles)},
                ),
            )
            return WriteResult(data=user_view(user, validated_roles), status_code=201, version=user.version)

        try:
            return self._idempotent_write(
                current_user=current_user,
                scope="identity.user.create",
                key=idempotency_key,
                request_hash=request_hash,
                operation=operation,
            )
        except IntegrityError as exc:
            raise AppError(409, ErrorCode.VALIDATION_ERROR, "用户名已存在。") from exc

    def update_profile(
        self,
        *,
        current_user: CurrentUser,
        user_id: str,
        display_name: str,
        if_match: str | None,
        request_id: str,
    ) -> WriteResult:
        with new_session() as session:
            user = self.repository.lock_user(session, user_id)
            if user is None:
                raise AppError(404, ErrorCode.HTTP_ERROR, "用户不存在。")
            require_matching_version(if_match, user.version)
            user.display_name = display_name.strip()
            user.version += 1
            self.audit.append(
                session,
                AuditEventInput(
                    action="user.updated",
                    target_type="user",
                    target_id=user.id,
                    result="success",
                    request_id=request_id,
                    actor_user_id=current_user.id,
                    metadata={"fields": ["displayName"]},
                ),
            )
            roles = self.repository.role_codes_for_user(session, user.id)
            return WriteResult(data=user_view(user, roles), status_code=200, version=user.version)

    def set_status(
        self,
        *,
        current_user: CurrentUser,
        user_id: str,
        is_active: bool,
        reason: str,
        if_match: str | None,
        idempotency_key: str,
        request_hash: str,
        request_id: str,
        now: datetime,
    ) -> WriteResult:
        if user_id == current_user.id and not is_active:
            raise AppError(403, ErrorCode.FORBIDDEN, "不能禁用当前登录用户。")

        def operation(session):  # type: ignore[no-untyped-def]
            user = self.repository.lock_user(session, user_id)
            if user is None:
                raise AppError(404, ErrorCode.HTTP_ERROR, "用户不存在。")
            require_matching_version(if_match, user.version)
            current_roles = self.repository.role_codes_for_user(session, user.id)
            if not is_active and "system_admin" in current_roles:
                active_admins = self.repository.active_system_admin_ids(session)
                if active_admins == (user.id,):
                    raise AppError(409, ErrorCode.LAST_ADMIN_PROTECTED, "不能禁用最后一个启用的系统管理员。")
            if user.is_active != is_active:
                user.is_active = is_active
                user.auth_version += 1
                user.version += 1
                self.repository.revoke_user_sessions(
                    session,
                    user_id=user.id,
                    now=now,
                    reason="user_status_changed",
                )
            action = "user.enabled" if is_active else "user.disabled"
            self.audit.append(
                session,
                AuditEventInput(
                    action=action,
                    target_type="user",
                    target_id=user.id,
                    result="success",
                    request_id=request_id,
                    actor_user_id=current_user.id,
                    metadata={"reason": reason},
                ),
            )
            return WriteResult(data=user_view(user, current_roles), status_code=200, version=user.version)

        return self._idempotent_write(
            current_user=current_user,
            scope=f"identity.user.status:{user_id}",
            key=idempotency_key,
            request_hash=request_hash,
            operation=operation,
        )

    def set_roles(
        self,
        *,
        current_user: CurrentUser,
        user_id: str,
        role_codes: list[str],
        reason: str,
        if_match: str | None,
        idempotency_key: str,
        request_hash: str,
        request_id: str,
        now: datetime,
    ) -> WriteResult:
        if user_id == current_user.id:
            raise AppError(403, ErrorCode.FORBIDDEN, "不能修改当前登录用户的角色。")
        validated_roles = self._validate_roles(role_codes)

        def operation(session):  # type: ignore[no-untyped-def]
            user = self.repository.lock_user(session, user_id)
            if user is None:
                raise AppError(404, ErrorCode.HTTP_ERROR, "用户不存在。")
            require_matching_version(if_match, user.version)
            existing = self.repository.role_codes_for_user(session, user.id)
            if "system_admin" in existing and "system_admin" not in validated_roles and user.is_active:
                active_admins = self.repository.active_system_admin_ids(session)
                if active_admins == (user.id,):
                    raise AppError(409, ErrorCode.LAST_ADMIN_PROTECTED, "不能移除最后一个启用管理员的系统管理员角色。")
            roles = self.repository.roles_by_codes(session, validated_roles)
            if len(roles) != len(validated_roles):
                raise AppError(400, ErrorCode.VALIDATION_ERROR, "包含未知角色代码。")
            if existing != validated_roles:
                self.repository.replace_user_roles(
                    session,
                    user_id=user.id,
                    roles=roles,
                    assigned_by_user_id=current_user.id,
                )
                user.auth_version += 1
                user.version += 1
                self.repository.revoke_user_sessions(
                    session,
                    user_id=user.id,
                    now=now,
                    reason="roles_changed",
                )
            self.audit.append(
                session,
                AuditEventInput(
                    action="user.roles_changed",
                    target_type="user",
                    target_id=user.id,
                    result="success",
                    request_id=request_id,
                    actor_user_id=current_user.id,
                    metadata={"roles": sorted(validated_roles), "reason": reason},
                ),
            )
            return WriteResult(data=user_view(user, validated_roles), status_code=200, version=user.version)

        return self._idempotent_write(
            current_user=current_user,
            scope=f"identity.user.roles:{user_id}",
            key=idempotency_key,
            request_hash=request_hash,
            operation=operation,
        )

    def reset_password(
        self,
        *,
        current_user: CurrentUser,
        user_id: str,
        temporary_password: str,
        reason: str,
        if_match: str | None,
        idempotency_key: str,
        request_hash: str,
        request_id: str,
        now: datetime,
    ) -> WriteResult:
        if user_id == current_user.id:
            raise AppError(403, ErrorCode.FORBIDDEN, "请通过本人改密接口修改当前账户密码。")
        password_hash = hash_password(temporary_password, hasher=self.password_hasher)

        def operation(session):  # type: ignore[no-untyped-def]
            user = self.repository.lock_user(session, user_id)
            if user is None:
                raise AppError(404, ErrorCode.HTTP_ERROR, "用户不存在。")
            if user.auth_source != "local":
                raise AppError(409, ErrorCode.AUTH_MODE_UNAVAILABLE, "非本地账户不能重置本地密码。")
            require_matching_version(if_match, user.version)
            user.password_hash = password_hash
            user.must_change_password = True
            user.auth_version += 1
            user.version += 1
            self.repository.revoke_user_sessions(
                session,
                user_id=user.id,
                now=now,
                reason="password_reset",
            )
            roles = self.repository.role_codes_for_user(session, user.id)
            self.audit.append(
                session,
                AuditEventInput(
                    action="user.password_reset",
                    target_type="user",
                    target_id=user.id,
                    result="success",
                    request_id=request_id,
                    actor_user_id=current_user.id,
                    metadata={"reason": reason},
                ),
            )
            return WriteResult(data=user_view(user, roles), status_code=200, version=user.version)

        return self._idempotent_write(
            current_user=current_user,
            scope=f"identity.user.password:{user_id}",
            key=idempotency_key,
            request_hash=request_hash,
            operation=operation,
        )


def get_user_management_use_case() -> UserManagementUseCase:
    return UserManagementUseCase()


def role_views() -> list[dict[str, Any]]:
    return [
        {
            "code": role.value,
            "permissions": sorted(permission.value for permission in ROLE_PERMISSIONS[role]),
        }
        for role in RoleCode
    ]
