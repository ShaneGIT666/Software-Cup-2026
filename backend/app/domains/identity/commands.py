from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from ...core.config import AppSettings
from ...core.error_codes import ErrorCode
from ...core.errors import AppError
from ...db.idempotency import IdempotencyReplay, IdempotencyService
from ...db.session import new_session
from ..audit.contracts import AuditEventInput
from ..audit.writer import AuditWriter
from .contracts import CurrentUser
from .passwords import Argon2PasswordHasher, PasswordHasherPort, hash_password
from .repository import IdentityRepository


@dataclass(frozen=True)
class PasswordChangeResult:
    data: Mapping[str, object]
    status_code: int = 200


class LogoutUseCase:
    def __init__(
        self,
        *,
        repository: IdentityRepository | None = None,
        audit_writer: AuditWriter | None = None,
    ) -> None:
        self.repository = repository or IdentityRepository()
        self.audit = audit_writer or AuditWriter()

    def execute(self, *, current_user: CurrentUser, request_id: str, now: datetime) -> None:
        with new_session() as session:
            self.repository.revoke_session(
                session,
                session_id=current_user.session_id,
                now=now,
                reason="user_logout",
            )
            self.audit.append(
                session,
                AuditEventInput(
                    action="auth.logout",
                    target_type="session",
                    target_id=current_user.session_id,
                    result="success",
                    request_id=request_id,
                    actor_user_id=current_user.id,
                ),
            )


class PasswordChangeUseCase:
    """Change a password without keeping a transaction open during Argon2."""

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

    def execute(
        self,
        *,
        current_user: CurrentUser,
        current_password: str,
        new_password: str,
        idempotency_key: str,
        request_hash: str,
        request_id: str,
        settings: AppSettings,
        now: datetime,
    ) -> PasswordChangeResult:
        with new_session() as session:
            replay = self.idempotency.lookup(
                session,
                scope="identity.password.change",
                actor_id=current_user.id,
                key=idempotency_key,
                request_hash=request_hash,
            )
        if replay is not None:
            return PasswordChangeResult(data=replay.data, status_code=replay.status_code)

        with new_session() as session:
            credential = self.repository.credential_for_user(session, current_user.id)
        if credential is None or not self.password_hasher.verify(credential.password_hash, current_password):
            raise AppError(401, ErrorCode.INVALID_CREDENTIALS, "当前密码不正确。")
        new_hash = hash_password(new_password, hasher=self.password_hasher)

        with new_session() as session:
            reservation = self.idempotency.begin(
                session,
                scope="identity.password.change",
                actor_id=current_user.id,
                key=idempotency_key,
                request_hash=request_hash,
            )
            if isinstance(reservation, IdempotencyReplay):
                return PasswordChangeResult(data=reservation.data, status_code=reservation.status_code)

            user = self.repository.revalidate_login_candidate(
                session,
                user_id=credential.user_id,
                password_hash=credential.password_hash,
                auth_version=credential.auth_version,
            )
            if user is None:
                raise AppError(409, ErrorCode.VERSION_CONFLICT, "账号安全状态已变化，请重新登录。")

            user.password_hash = new_hash
            user.auth_version += 1
            user.version += 1
            user.must_change_password = False
            preserved = self.repository.preserve_current_session_after_security_change(
                session,
                user_id=user.id,
                current_session_id=current_user.session_id,
                auth_version=user.auth_version,
                now=now,
                reason="password_changed",
            )
            if not preserved:
                raise AppError(409, ErrorCode.SESSION_EXPIRED, "当前会话已失效，请重新登录。")
            self.audit.append(
                session,
                AuditEventInput(
                    action="user.password_changed",
                    target_type="user",
                    target_id=user.id,
                    result="success",
                    request_id=request_id,
                    actor_user_id=user.id,
                ),
            )
            data: dict[str, object] = {
                "changed": True,
                "mustChangePassword": False,
                "reauthenticationRequired": False,
            }
            reservation.complete(status_code=200, data=data)
            return PasswordChangeResult(data=data)


def get_logout_use_case() -> LogoutUseCase:
    return LogoutUseCase()


def get_password_change_use_case() -> PasswordChangeUseCase:
    return PasswordChangeUseCase()
