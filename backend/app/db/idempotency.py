from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..core.error_codes import ErrorCode
from ..core.errors import AppError
from .models import IdempotencyRecord


_IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")


def validate_idempotency_key(value: str | None) -> str:
    """Validate the stable key format accepted by all M0-backed write APIs."""

    if value is None or not _IDEMPOTENCY_KEY_PATTERN.fullmatch(value):
        raise AppError(
            400,
            ErrorCode.IDEMPOTENCY_KEY_REQUIRED,
            "关键写操作必须提供 8 到 128 位的 Idempotency-Key。",
        )
    return value


def request_fingerprint(
    *,
    actor_id: str,
    method: str,
    path: str,
    payload: Mapping[str, Any],
    secret: str,
) -> str:
    """HMAC the logical request without persisting raw credentials or secrets."""

    if not secret:
        raise AppError(
            503,
            ErrorCode.DEPENDENCY_UNAVAILABLE,
            "关键写操作的 APP_IDEMPOTENCY_SECRET 未配置。",
        )

    canonical = json.dumps(
        {
            "actorId": actor_id,
            "method": method.upper(),
            "path": path,
            "payload": payload,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class IdempotencyReplay:
    status_code: int
    data: dict[str, Any]


@dataclass
class IdempotencyReservation:
    """A record reserved inside the caller's current database transaction."""

    record: IdempotencyRecord

    def complete(self, *, status_code: int, data: Mapping[str, Any]) -> None:
        if not 200 <= status_code < 300:
            raise ValueError("幂等记录只能保存成功响应")
        self.record.state = "completed"
        self.record.response_status = status_code
        self.record.response_data = dict(data)
        self.record.completed_at = datetime.now(timezone.utc)


class IdempotencyService:
    """PostgreSQL-backed reservation and replay service shared by domains."""

    def begin(
        self,
        session: Session,
        *,
        scope: str,
        actor_id: str,
        key: str,
        request_hash: str,
    ) -> IdempotencyReservation | IdempotencyReplay:
        validated_key = validate_idempotency_key(key)
        created_id = session.execute(
            insert(IdempotencyRecord)
            .values(
                scope=scope,
                actor_id=actor_id,
                idempotency_key=validated_key,
                request_hash=request_hash,
                state="in_progress",
            )
            .on_conflict_do_nothing(constraint="uq_idempotency_scope_actor_key")
            .returning(IdempotencyRecord.id)
        ).scalar_one_or_none()

        if created_id is not None:
            record = session.get(IdempotencyRecord, created_id)
            assert record is not None
            return IdempotencyReservation(record)

        record = session.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.scope == scope,
                IdempotencyRecord.actor_id == actor_id,
                IdempotencyRecord.idempotency_key == validated_key,
            )
        )
        if record is None:
            raise AppError(409, ErrorCode.REQUEST_IN_PROGRESS, "相同幂等请求正在处理中，请稍后重试。")
        if record.request_hash != request_hash:
            raise AppError(409, ErrorCode.IDEMPOTENCY_CONFLICT, "Idempotency-Key 已用于不同请求。")
        if record.state != "completed" or record.response_status is None or record.response_data is None:
            raise AppError(409, ErrorCode.REQUEST_IN_PROGRESS, "相同幂等请求正在处理中，请稍后重试。")
        return IdempotencyReplay(status_code=record.response_status, data=dict(record.response_data))
