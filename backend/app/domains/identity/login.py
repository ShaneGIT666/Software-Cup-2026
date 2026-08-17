from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ...core.config import AppSettings
from ...db.session import new_session
from ..audit.contracts import AuditEventInput
from ..audit.writer import AuditWriter
from .repository import IdentityRepository, LoginThrottleRepository, login_throttle_digests
from .service_accounts import AUTHENTICATION_SERVICE
from .service import CreatedSession, IdentityService


@dataclass(frozen=True)
class LoginAttemptResult:
    created_session: CreatedSession | None
    locked: bool

    @property
    def authenticated(self) -> bool:
        return self.created_session is not None


class LoginUseCase:
    """Own the short transactions around transaction-free Argon2 verification."""

    def __init__(
        self,
        *,
        repository: IdentityRepository | None = None,
        throttle_repository: LoginThrottleRepository | None = None,
        identity_service: IdentityService | None = None,
        audit_writer: AuditWriter | None = None,
    ) -> None:
        self.repository = repository or IdentityRepository()
        self.throttles = throttle_repository or LoginThrottleRepository()
        self.identity = identity_service or IdentityService(
            repository=self.repository,
            throttle_repository=self.throttles,
        )
        self.audit = audit_writer or AuditWriter()

    def authenticate(
        self,
        *,
        username: str,
        password: str,
        source_address: str,
        settings: AppSettings,
        request_id: str,
        now: datetime,
    ) -> LoginAttemptResult:
        throttle_subject, normalized = self.identity._throttle_subject(username)
        subject_hmac, source_hmac = login_throttle_digests(
            normalized_username=throttle_subject,
            source_address=source_address,
            secret=settings.auth_secret,
        )
        with new_session() as session:
            throttles = self.throttles.get_states(
                session,
                subject_hmac=subject_hmac,
                source_hmac=source_hmac,
            )
            credential = self.repository.credential_for_login(session, normalized) if normalized is not None else None

        verification = self.identity.verify_login_candidate(
            username=username,
            password=password,
            source_address=source_address,
            settings=settings,
            now=now,
            credential=credential,
            throttle_snapshot=throttles,
        )

        with new_session() as session:
            if not verification.authenticated:
                self.identity.record_failed_login(session, verification=verification, settings=settings, now=now)
                self.audit.append(
                    session,
                    AuditEventInput(
                        action="auth.login_failed",
                        target_type="login_subject",
                        target_id=verification.subject_hmac,
                        result="denied",
                        request_id=request_id,
                        actor_user_id=AUTHENTICATION_SERVICE.user_id,
                        metadata={"sourceHmac": verification.source_hmac},
                    ),
                )
                return LoginAttemptResult(created_session=None, locked=verification.locked)
            try:
                created = self.identity.create_authenticated_session(
                    session,
                    verification=verification,
                    settings=settings,
                    now=now,
                )
            except ValueError:
                self.identity.record_failed_login(session, verification=verification, settings=settings, now=now)
                self.audit.append(
                    session,
                    AuditEventInput(
                        action="auth.login_failed",
                        target_type="login_subject",
                        target_id=verification.subject_hmac,
                        result="denied",
                        request_id=request_id,
                        actor_user_id=AUTHENTICATION_SERVICE.user_id,
                        metadata={"sourceHmac": verification.source_hmac, "reason": "security_state_changed"},
                    ),
                )
                return LoginAttemptResult(created_session=None, locked=False)
            if verification.user_id is None:
                raise RuntimeError("认证成功结果缺少用户标识")
            self.audit.append(
                session,
                AuditEventInput(
                    action="auth.login_succeeded",
                    target_type="user",
                    target_id=verification.user_id or "unknown",
                    result="success",
                    request_id=request_id,
                    actor_user_id=verification.user_id,
                    metadata={"sourceHmac": verification.source_hmac},
                ),
            )
            return LoginAttemptResult(created_session=created, locked=False)


def get_login_use_case() -> LoginUseCase:
    return LoginUseCase()
