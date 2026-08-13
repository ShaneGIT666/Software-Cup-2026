from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Mapping
from typing import Any

from .error_codes import ErrorCode
from .errors import AppError


_CURSOR_PREFIX = "v1."
_MAX_CURSOR_LENGTH = 2048
_MAX_CURSOR_PAYLOAD_BYTES = 1024


def _invalid_cursor() -> AppError:
    return AppError(400, ErrorCode.INVALID_CURSOR, "分页游标无效或已损坏。")


def encode_cursor(payload: Mapping[str, Any]) -> str:
    """Encode a versioned opaque keyset cursor.

    Cursors are intentionally not authorization tokens. Every consumer must
    reapply identity, status and tenant filters when executing the next page.
    """

    try:
        raw = json.dumps(
            {"version": 1, "payload": dict(payload)},
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("游标 payload 必须可序列化为标准 JSON 对象") from exc
    if len(raw) > _MAX_CURSOR_PAYLOAD_BYTES:
        raise ValueError("游标 payload 过大")
    encoded = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
    return f"{_CURSOR_PREFIX}{encoded}"


def decode_cursor(cursor: str | None) -> dict[str, Any] | None:
    if cursor is None:
        return None
    if not isinstance(cursor, str) or not cursor.startswith(_CURSOR_PREFIX) or len(cursor) > _MAX_CURSOR_LENGTH:
        raise _invalid_cursor()
    encoded = cursor[len(_CURSOR_PREFIX) :]
    if not encoded:
        raise _invalid_cursor()
    padded = encoded + "=" * (-len(encoded) % 4)
    try:
        raw = base64.b64decode(padded.encode("ascii"), altchars=b"-_", validate=True)
        if len(raw) > _MAX_CURSOR_PAYLOAD_BYTES:
            raise _invalid_cursor()
        envelope = json.loads(raw.decode("utf-8"))
    except (UnicodeEncodeError, UnicodeDecodeError, binascii.Error, json.JSONDecodeError):
        raise _invalid_cursor() from None
    if (
        not isinstance(envelope, dict)
        or envelope.get("version") != 1
        or set(envelope) != {"version", "payload"}
        or not isinstance(envelope.get("payload"), dict)
    ):
        raise _invalid_cursor()
    return dict(envelope["payload"])

