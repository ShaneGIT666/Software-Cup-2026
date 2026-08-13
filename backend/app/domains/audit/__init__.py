"""M1 append-only audit domain public surface."""

from .contracts import AuditEventInput
from .writer import AuditWriter

__all__ = ["AuditEventInput", "AuditWriter"]
