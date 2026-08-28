from __future__ import annotations

from dataclasses import dataclass

from .error_codes import ErrorCode


INTERNAL_ERROR_MESSAGE = "服务器内部错误"
DEPENDENCY_UNAVAILABLE_MESSAGE = "关键依赖未就绪"


@dataclass(frozen=True)
class PublicServerError:
    """The only fields an explicit v1 server error may expose."""

    status_code: int
    code: str
    message: str
    details: None = None


def normalize_v1_server_error(*, status_code: int, code: str) -> PublicServerError:
    """Fail closed at the public boundary for explicit 5xx exceptions.

    ``DEPENDENCY_UNAVAILABLE/503`` is the sole registered exception.  Its
    message is fixed here and arbitrary exception details are deliberately
    discarded.  The readiness endpoint exposes its separately validated,
    strongly typed detail object without passing through an exception.
    """

    if status_code < 500:
        raise ValueError("server error normalization requires a 5xx status")
    if status_code == 503 and code == ErrorCode.DEPENDENCY_UNAVAILABLE:
        return PublicServerError(
            status_code=503,
            code=ErrorCode.DEPENDENCY_UNAVAILABLE,
            message=DEPENDENCY_UNAVAILABLE_MESSAGE,
        )
    return PublicServerError(
        status_code=500,
        code=ErrorCode.INTERNAL_ERROR,
        message=INTERNAL_ERROR_MESSAGE,
    )
