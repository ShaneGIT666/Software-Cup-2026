from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class AuditEventInput:
    action: str
    target_type: str
    target_id: str
    result: str
    request_id: str
    actor_user_id: str
    initiator_user_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        required = {
            "action": self.action,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "result": self.result,
            "request_id": self.request_id,
            "actor_user_id": self.actor_user_id,
        }
        if any(not value.strip() for value in required.values()):
            raise ValueError("审计事件必填标识不能为空")
        if self.initiator_user_id is not None and not self.initiator_user_id.strip():
            raise ValueError("审计事件发起用户标识不能为空字符串")


@dataclass(frozen=True)
class AuditAppendResult:
    event_id: str
