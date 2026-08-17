from __future__ import annotations

from dataclasses import dataclass

from .contracts import ActorKind, AuthenticatedActor, ManagedServiceKey


@dataclass(frozen=True)
class ManagedServiceAccount:
    key: ManagedServiceKey
    user_id: str
    username: str
    display_name: str

    def actor(self, *, initiator_user_id: str | None = None) -> AuthenticatedActor:
        return AuthenticatedActor(
            user_id=self.user_id,
            kind=ActorKind.SERVICE,
            initiator_user_id=initiator_user_id,
        )


AUTHENTICATION_SERVICE = ManagedServiceAccount(
    key=ManagedServiceKey.AUTHENTICATION,
    user_id="20000000-0000-0000-0000-000000000001",
    username="__service_authentication__",
    display_name="认证子系统服务用户",
)
BOOTSTRAP_SERVICE = ManagedServiceAccount(
    key=ManagedServiceKey.BOOTSTRAP,
    user_id="20000000-0000-0000-0000-000000000002",
    username="__service_bootstrap__",
    display_name="实例引导服务用户",
)
WORKER_SERVICE = ManagedServiceAccount(
    key=ManagedServiceKey.WORKER,
    user_id="20000000-0000-0000-0000-000000000003",
    username="__service_worker__",
    display_name="后台任务服务用户",
)

MANAGED_SERVICE_ACCOUNTS = (
    AUTHENTICATION_SERVICE,
    BOOTSTRAP_SERVICE,
    WORKER_SERVICE,
)
MANAGED_SERVICE_BY_KEY = {account.key: account for account in MANAGED_SERVICE_ACCOUNTS}


def managed_service_account(key: ManagedServiceKey) -> ManagedServiceAccount:
    return MANAGED_SERVICE_BY_KEY[key]
