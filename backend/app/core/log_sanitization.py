from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any


_REDACTED = "[REDACTED]"
_REDACTED_EXCEPTION = "[REDACTED_EXCEPTION]"
_REDACTED_LOG_MESSAGE = "log_message_redacted"

_STACK_PATTERN = re.compile(
    r"(?im)(?:traceback \(most recent call last\)|exception group traceback|"
    r"^\s*file\s+[\"'][^\"']+[\"'],\s+line\s+\d+)",
)
_BEARER_PATTERN = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")
_JWT_PATTERN = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
_CONNECTION_URI_PATTERN = re.compile(
    r"(?i)\b(?:postgres(?:ql)?(?:\+[a-z0-9_]+)?|mysql(?:\+[a-z0-9_]+)?|"
    r"mariadb|mongodb(?:\+srv)?|redis|rediss|amqp|amqps|sqlite)://[^\s,;]+",
)
_SENSITIVE_KEY_PATTERN = re.compile(
    r"(?i)(?<![A-Za-z0-9_])[\"']?(authorization|proxy[-_ ]authorization|cookie|"
    r"set[-_ ]cookie|password|passwd|pwd|secret|token|api[-_ ]?key|access[-_ ]?key|"
    r"client[-_ ]?secret|credential|connection(?:[-_ ]string)?|database[-_ ]url|dsn|"
    r"request[-_ ]?(?:body|payload|headers)|body|payload|headers|form[-_ ]?data|path)[\"']?"
    r"\s*[:=]\s*(?:\"[^\"]*\"|'[^']*'|[^\s,]+)",
)
_WINDOWS_PATH_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])(?:[A-Za-z]:[\\/][^\s,;\"'<>|]+|\\\\[^\\\s]+\\[^\s,;\"'<>|]+)",
)
_UNIX_PATH_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_:])/(?:[^/\s,;\"'<>|]+)(?:/[^/\s,;\"'<>|]+)*",
)
_ODBC_CONNECTION_PATTERN = re.compile(
    r"(?i)\b(?:server|data\s+source)\s*=.*?;\s*(?:database|initial\s+catalog|uid|user\s+id|password|pwd)\s*=",
)

_STANDARD_RECORD_FIELDS = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "taskName",
    }
)
_SAFE_EXTRA_FIELDS = frozenset(
    {
        "event",
        "request_id",
        "component",
        "operation",
        "outcome",
        "code",
        "method",
        "status_code",
        "duration_ms",
        "count",
        "attempt",
        "consumer_id",
        "event_id",
        "diagnostic_id",
    }
)


def sanitize_log_text(value: object) -> str:
    """Return one-line ordinary-log text with sensitive diagnostics removed."""

    try:
        text = str(value)
    except Exception:
        return _REDACTED_LOG_MESSAGE
    if (
        _STACK_PATTERN.search(text)
        or _ODBC_CONNECTION_PATTERN.search(text)
        or _SENSITIVE_KEY_PATTERN.search(text)
    ):
        return _REDACTED_LOG_MESSAGE
    text = _BEARER_PATTERN.sub(f"Bearer {_REDACTED}", text)
    text = _JWT_PATTERN.sub(_REDACTED, text)
    text = _CONNECTION_URI_PATTERN.sub(_REDACTED, text)
    text = _WINDOWS_PATH_PATTERN.sub(_REDACTED, text)
    text = _UNIX_PATH_PATTERN.sub(_REDACTED, text)
    return " ".join(text.replace("\x00", " ").splitlines()).strip()


def _safe_format_value(value: Any) -> Any:
    if isinstance(value, BaseException):
        return _REDACTED_EXCEPTION
    if isinstance(value, Mapping):
        return _REDACTED
    if isinstance(value, tuple):
        return tuple(_safe_format_value(item) for item in value)
    if isinstance(value, list):
        return _REDACTED
    return value


def _render_record_message(message: object, arguments: object) -> str:
    safe_message = _safe_format_value(message)
    safe_arguments = _safe_format_value(arguments)
    try:
        rendered = str(safe_message)
        if safe_arguments:
            rendered %= safe_arguments
    except Exception:
        return _REDACTED_LOG_MESSAGE
    return sanitize_log_text(rendered)


def _sanitize_record(record: logging.LogRecord) -> logging.LogRecord:
    record.msg = _render_record_message(record.msg, record.args)
    record.args = ()
    record.exc_info = None
    record.exc_text = None
    record.stack_info = None
    record.pathname = _REDACTED
    for key, value in tuple(record.__dict__.items()):
        if key in _STANDARD_RECORD_FIELDS:
            continue
        if key not in _SAFE_EXTRA_FIELDS:
            record.__dict__[key] = _REDACTED
            continue
        if value is None or isinstance(value, (bool, int, float)):
            continue
        if isinstance(value, str):
            record.__dict__[key] = sanitize_log_text(value)
            continue
        record.__dict__[key] = _REDACTED
    return record


def install_ordinary_log_sanitization() -> None:
    """Install a process-wide boundary after structured ``extra`` is merged."""

    current_make_record = logging.Logger.makeRecord
    if getattr(current_make_record, "_ordinary_log_sanitizer", False):
        return

    def sanitized_make_record(
        logger: logging.Logger,
        *args: Any,
        **kwargs: Any,
    ) -> logging.LogRecord:
        return _sanitize_record(current_make_record(logger, *args, **kwargs))

    setattr(sanitized_make_record, "_ordinary_log_sanitizer", True)
    logging.Logger.makeRecord = sanitized_make_record  # type: ignore[assignment]
