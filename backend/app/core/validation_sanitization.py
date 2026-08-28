from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from typing import Final

from .contracts import ValidationIssue, ValidationIssueContext
from .log_sanitization import sanitize_log_text


VALIDATION_ERROR_MESSAGE: Final = "请求参数校验失败"
VALIDATION_ISSUE_MESSAGE: Final = "请求参数不符合要求"

_MAX_ISSUES = 32
_MAX_LOCATION_PARTS = 16
_MAX_LOCATION_TEXT = 64
_MAX_ERROR_TYPE = 96
_MAX_LIMIT_TEXT = 64
_LOCATION_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]{0,63}$")
_ERROR_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,95}$")
_LIMIT_TEXT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:+-]{0,63}$")
_SENSITIVE_LIMIT_MARKERS = ("password", "passwd", "secret", "token", "cookie", "bearer", "api_key", "api-key")
_INVALID = object()


def _public_location(raw_location: object) -> list[str | int]:
    if not isinstance(raw_location, (list, tuple)):
        return ["request"]
    if not raw_location or len(raw_location) > _MAX_LOCATION_PARTS:
        return ["request"]

    location: list[str | int] = []
    for part in raw_location:
        if isinstance(part, bool):
            return ["request"]
        if isinstance(part, int):
            if part < 0 or part > 1_000_000:
                return ["request"]
            location.append(part)
            continue
        if not isinstance(part, str):
            return ["request"]
        if len(part) > _MAX_LOCATION_TEXT or not _LOCATION_PATTERN.fullmatch(part):
            return ["request"]
        location.append(part)
    return location


def _public_error_type(raw_type: object) -> str:
    if not isinstance(raw_type, str):
        return "validation_error"
    if len(raw_type) > _MAX_ERROR_TYPE or not _ERROR_TYPE_PATTERN.fullmatch(raw_type):
        return "validation_error"
    return raw_type


def _public_limit_value(raw_value: object) -> object:
    if raw_value is None:
        return None
    if isinstance(raw_value, bool):
        return _INVALID
    if isinstance(raw_value, int):
        return raw_value if -(2**53) <= raw_value <= 2**53 else _INVALID
    if isinstance(raw_value, float):
        return raw_value if math.isfinite(raw_value) else _INVALID
    if not isinstance(raw_value, str):
        return _INVALID
    if len(raw_value) > _MAX_LIMIT_TEXT or not _LIMIT_TEXT_PATTERN.fullmatch(raw_value):
        return _INVALID
    folded = raw_value.casefold()
    if any(marker in folded for marker in _SENSITIVE_LIMIT_MARKERS):
        return _INVALID
    if sanitize_log_text(raw_value) != raw_value:
        return _INVALID
    return raw_value


def _public_context(raw_context: object) -> ValidationIssueContext | None:
    if not isinstance(raw_context, Mapping) or "limit_value" not in raw_context:
        return None
    limit_value = _public_limit_value(raw_context["limit_value"])
    if limit_value is _INVALID:
        return None
    return ValidationIssueContext(limit_value=limit_value)


def public_validation_issues(errors: Sequence[object]) -> list[ValidationIssue]:
    """Map framework validation errors into the closed public issue model."""

    issues: list[ValidationIssue] = []
    for raw_error in errors[:_MAX_ISSUES]:
        if not isinstance(raw_error, Mapping):
            issues.append(
                ValidationIssue(
                    loc=["request"],
                    msg=VALIDATION_ISSUE_MESSAGE,
                    type="validation_error",
                )
            )
            continue
        issues.append(
            ValidationIssue(
                loc=_public_location(raw_error.get("loc")),
                msg=VALIDATION_ISSUE_MESSAGE,
                type=_public_error_type(raw_error.get("type")),
                ctx=_public_context(raw_error.get("ctx")),
            )
        )
    return issues
