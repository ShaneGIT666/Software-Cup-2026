from __future__ import annotations

import argparse
import getpass
from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import uuid4

from ...core.config import get_settings
from ...db.session import new_session
from ..audit.contracts import AuditEventInput
from ..audit.writer import AuditWriter
from .passwords import Argon2PasswordHasher, PasswordHasherPort
from .repository import IdentityRepository
from .runtime import validate_identity_runtime_settings
from .usernames import normalize_username


def activate_identity_instance(
    *,
    username: str,
    password: str,
    repository: IdentityRepository | None = None,
    audit_writer: AuditWriter | None = None,
    password_hasher: PasswordHasherPort | None = None,
    now: datetime | None = None,
) -> str:
    """Activate a bootstrapped instance after the first admin changed its password."""

    settings = get_settings()
    validate_identity_runtime_settings(settings)
    identity = repository or IdentityRepository()
    audit = audit_writer or AuditWriter()
    hasher = password_hasher or Argon2PasswordHasher()
    normalized = normalize_username(username)

    # Password verification intentionally occurs outside the activation write transaction.
    with new_session() as session:
        credential = identity.credential_for_login(session, normalized)
    if credential is None or not hasher.verify(credential.password_hash, password):
        raise RuntimeError("管理员凭据无效，实例未激活。")

    activated_at = now or datetime.now(timezone.utc)
    with new_session() as session:
        state = identity.lock_instance_state(session)
        if state is None:
            raise RuntimeError("身份实例状态不存在，请先执行最新数据库迁移。")
        if state.lifecycle != "bootstrapped":
            raise RuntimeError("身份实例不处于可激活的 bootstrapped 状态。")
        user = identity.revalidate_login_candidate(
            session,
            user_id=credential.user_id,
            password_hash=credential.password_hash,
            auth_version=credential.auth_version,
        )
        if user is None:
            raise RuntimeError("管理员安全状态已经变化，实例未激活。")
        if user.must_change_password:
            raise RuntimeError("初始管理员必须先修改临时密码。")
        if "system_admin" not in identity.role_codes_for_user(session, user.id):
            raise RuntimeError("只有系统管理员能够激活实例。")

        state.lifecycle = "active"
        state.version += 1
        state.activated_at = activated_at
        state.activated_by_user_id = user.id
        audit.append(
            session,
            AuditEventInput(
                action="identity.instance_activated",
                target_type="identity_instance",
                target_id=state.id,
                result="success",
                request_id=f"activation-cli:{uuid4().hex}",
                actor_user_id=user.id,
                metadata={"lifecycle": "active"},
            ),
        )
        return user.id


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="激活已经完成初始管理员改密的身份实例")
    parser.add_argument("--username", required=True)
    args = parser.parse_args(argv)
    password = getpass.getpass("系统管理员密码: ")
    user_id = activate_identity_instance(username=args.username, password=password)
    print(f"身份实例已激活：{user_id}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
