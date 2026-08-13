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
    actor_user_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

