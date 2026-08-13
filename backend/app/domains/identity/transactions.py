from __future__ import annotations

from datetime import datetime

from ...db.session import new_session
from .repository import IdentityRepository, SessionIdentityRecord


class SessionIdentityResolver:
    """Read one complete authorization snapshot in its own short transaction."""

    def __init__(self, repository: IdentityRepository | None = None) -> None:
        self.repository = repository or IdentityRepository()

    def resolve(self, token_digest: str) -> SessionIdentityRecord | None:
        with new_session() as session:
            return self.repository.resolve_session(session, token_digest)


def get_session_identity_resolver() -> SessionIdentityResolver:
    return SessionIdentityResolver()


class SessionActivityRefresher:
    """Refresh idle activity in an independent M0-owned short transaction."""

    def __init__(self, repository: IdentityRepository | None = None) -> None:
        self.repository = repository or IdentityRepository()

    def refresh(
        self,
        *,
        session_id: str,
        now: datetime,
        idle_timeout_minutes: int,
    ) -> bool:
        with new_session() as session:
            return self.repository.refresh_session_activity(
                session,
                session_id=session_id,
                now=now,
                idle_timeout_minutes=idle_timeout_minutes,
            )


def get_session_activity_refresher() -> SessionActivityRefresher:
    return SessionActivityRefresher()
