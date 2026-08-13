from __future__ import annotations

import re

from .error_codes import ErrorCode
from .errors import AppError


_VERSION_ETAG_PATTERN = re.compile(r'^"v([1-9][0-9]*)"$')


def etag_for_version(version: int) -> str:
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise ValueError("资源版本必须是正整数")
    return f'"v{version}"'


def parse_if_match(value: str | None) -> int:
    if value is None or not value.strip():
        raise AppError(428, ErrorCode.PRECONDITION_REQUIRED, "该操作必须提供 If-Match 版本条件。")
    match = _VERSION_ETAG_PATTERN.fullmatch(value.strip())
    if match is None:
        raise AppError(
            400,
            ErrorCode.INVALID_PRECONDITION,
            'If-Match 必须使用强版本标签格式，例如 "v3"。',
        )
    return int(match.group(1))


def require_matching_version(value: str | None, current_version: int) -> int:
    requested_version = parse_if_match(value)
    if requested_version != current_version:
        raise AppError(412, ErrorCode.VERSION_CONFLICT, "资源已被其他请求修改，请刷新后重试。")
    return requested_version

