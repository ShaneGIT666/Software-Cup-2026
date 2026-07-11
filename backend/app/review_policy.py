from __future__ import annotations

from typing import Any


APPROVED = "approved"
UNKNOWN = "unknown"
REPLACED = "replaced"


def normalize_review_status(value: Any) -> str:
    status = str(value or "").strip().lower()
    return status or UNKNOWN


def is_explicitly_approved(item: dict[str, Any], field: str = "review_status") -> bool:
    return normalize_review_status(item.get(field)) == APPROVED


def is_current_approved_chunk(chunk: dict[str, Any]) -> bool:
    if not is_explicitly_approved(chunk):
        return False
    if normalize_review_status(chunk.get("review_status")) == REPLACED:
        return False
    if chunk.get("replaced_by"):
        return False
    return chunk.get("is_current", True) is not False


def is_approved_case(item: dict[str, Any]) -> bool:
    return is_explicitly_approved(item, field="status")
