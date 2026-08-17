from __future__ import annotations

import argparse
import getpass
from collections.abc import Sequence
from uuid import uuid4

from sqlalchemy import select

from ...core.config import get_settings
from ...db.session import new_session
from ..audit.contracts import AuditEventInput
from ..audit.writer import AuditWriter
from .models import Role, User, UserRole
from .passwords import hash_password
from .repository import IdentityRepository
from .runtime import validate_identity_runtime_settings
from .service_accounts import BOOTSTRAP_SERVICE
from .usernames import normalize_username


def bootstrap_system_admin(
    *,
    username: str,
    display_name: str,
    password: str,
    repository: IdentityRepository | None = None,
    audit_writer: AuditWriter | None = None,
) -> str:
    settings = get_settings()
    validate_identity_runtime_settings(settings)
    normalized = normalize_username(username)
    password_hash = hash_password(password)

    identity = repository or IdentityRepository()
    audit = audit_writer or AuditWriter()
    with new_session() as session:
        # The singleton lifecycle row serializes concurrent bootstrap attempts.
        state = identity.lock_instance_state(session)
        if state is None:
            raise RuntimeError("身份实例状态不存在，请先执行最新数据库迁移。")
        if state.lifecycle != "uninitialized":
            raise RuntimeError("身份实例已经引导或激活，拒绝再次执行初始管理员引导。")
        role = session.scalar(select(Role).where(Role.code == "system_admin"))
        if role is None:
            raise RuntimeError("system_admin 种子角色不存在，请先执行数据库迁移。")
        service_user = identity.managed_service_user(
            session,
            service_key=BOOTSTRAP_SERVICE.key.value,
        )
        if service_user is None or service_user.id != BOOTSTRAP_SERVICE.user_id:
            raise RuntimeError("bootstrap 受管服务用户不存在，请先执行最新数据库迁移。")
        if identity.interactive_user_count(session) != 0:
            raise RuntimeError("用户库非空，拒绝再次执行初始管理员引导。")
        user = User(
            id=str(uuid4()),
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
        session.add(UserRole(user_id=user.id, role_id=role.id, assigned_by_user_id=service_user.id))
        state.lifecycle = "bootstrapped"
        state.version += 1
        audit.append(
            session,
            AuditEventInput(
                action="user.bootstrap_admin_created",
                target_type="user",
                target_id=user.id,
                result="success",
                request_id=f"bootstrap-cli:{uuid4().hex}",
                actor_user_id=service_user.id,
                metadata={"roles": ["system_admin"], "lifecycle": "bootstrapped"},
            ),
        )
        return user.id


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="创建空用户库中的首个系统管理员")
    parser.add_argument("--username", required=True)
    parser.add_argument("--display-name", required=True)
    args = parser.parse_args(argv)
    password = getpass.getpass("初始管理员密码: ")
    confirmation = getpass.getpass("再次输入密码: ")
    if password != confirmation:
        parser.error("两次密码输入不一致")
    user_id = bootstrap_system_admin(username=args.username, display_name=args.display_name, password=password)
    print(f"初始系统管理员已创建：{user_id}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
