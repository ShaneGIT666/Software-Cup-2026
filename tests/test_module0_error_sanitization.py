from __future__ import annotations

import logging

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from backend.app.core.error_codes import ErrorCode
from backend.app.core.errors import AppError
from backend.app.core.request_context import RequestContextMiddleware
from backend.app.main import (
    app_error_handler,
    http_exception_handler,
    request_validation_exception_handler,
    unhandled_exception_handler,
)


def _client_raising(error: Exception) -> TestClient:
    isolated_app = FastAPI()
    isolated_app.add_middleware(RequestContextMiddleware)
    isolated_app.add_exception_handler(HTTPException, http_exception_handler)
    isolated_app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    isolated_app.add_exception_handler(AppError, app_error_handler)
    isolated_app.add_exception_handler(Exception, unhandled_exception_handler)

    @isolated_app.get("/api/v1/explode")
    def explode() -> None:
        raise error

    return TestClient(isolated_app, raise_server_exceptions=False)


@pytest.mark.parametrize(
    "error",
    [
        HTTPException(
            status_code=500,
            detail="postgresql://admin:secret@db.internal/app",
        ),
        HTTPException(
            status_code=503,
            detail={"password": "do-not-leak", "path": r"C:\private\service.py"},
        ),
        AppError(
            500,
            ErrorCode.HTTP_ERROR,
            "token=do-not-leak",
            details={"traceback": "private stack"},
        ),
        AppError(
            502,
            ErrorCode.DEPENDENCY_UNAVAILABLE,
            "password=do-not-leak",
            details={"dsn": "postgresql://admin:secret@db.internal/app"},
        ),
    ],
)
def test_explicit_v1_5xx_errors_are_normalized_to_internal_error(error: Exception) -> None:
    response = _client_raising(error).get(
        "/api/v1/explode",
        headers={"X-Request-ID": "explicit-5xx-test"},
    )

    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == "explicit-5xx-test"
    assert response.json() == {
        "success": False,
        "data": None,
        "error": {
            "code": ErrorCode.INTERNAL_ERROR,
            "message": "服务器内部错误",
            "details": None,
        },
        "meta": {"requestId": "explicit-5xx-test"},
    }
    for forbidden in ("do-not-leak", "postgresql://", "C:\\private", "private stack"):
        assert forbidden not in response.text


def test_only_dependency_unavailable_app_error_keeps_503_with_fixed_public_fields() -> None:
    response = _client_raising(
        AppError(
            503,
            ErrorCode.DEPENDENCY_UNAVAILABLE,
            "APP_DATABASE_URL=postgresql://admin:secret@db.internal/app",
            details={"password": "do-not-leak", "serverPath": r"C:\private\service.py"},
        )
    ).get(
        "/api/v1/explode",
        headers={"X-Request-ID": "dependency-503-test"},
    )

    assert response.status_code == 503
    assert response.headers["X-Request-ID"] == "dependency-503-test"
    assert response.json() == {
        "success": False,
        "data": None,
        "error": {
            "code": ErrorCode.DEPENDENCY_UNAVAILABLE,
            "message": "关键依赖未就绪",
            "details": None,
        },
        "meta": {"requestId": "dependency-503-test"},
    }
    assert "admin:secret" not in response.text
    assert "do-not-leak" not in response.text
    assert "C:\\private" not in response.text


def test_v1_client_errors_never_expose_unregistered_details() -> None:
    response = _client_raising(
        AppError(
            409,
            ErrorCode.IDEMPOTENCY_CONFLICT,
            "Idempotency-Key 已用于不同请求。",
            details={
                "request_payload": "payload-secret",
                "path": "/workspace/private/command.py",
            },
        )
    ).get(
        "/api/v1/explode",
        headers={"X-Request-ID": "client-error-details-test"},
    )

    assert response.status_code == 409
    assert response.json()["error"] == {
        "code": ErrorCode.IDEMPOTENCY_CONFLICT,
        "message": "Idempotency-Key 已用于不同请求。",
        "details": None,
    }
    assert "payload-secret" not in response.text
    assert "/workspace/private" not in response.text


def test_v1_validation_error_uses_closed_safe_issue_details() -> None:
    response = _client_raising(
        RequestValidationError(
            [
                {
                    "loc": ("body", "password"),
                    "msg": "token=validator-secret at C:\\private\\validator.py",
                    "type": "value_error.any_str.max_length",
                    "ctx": {
                        "limit_value": 128,
                        "error": ValueError("ctx-exception-secret"),
                        "token": "ctx-token-secret",
                    },
                    "input": "request-input-secret",
                    "url": "https://internal.example/errors/secret",
                },
                {
                    "loc": ("body", "x" * 200, {"password": "location-secret"}),
                    "msg": "password=second-validator-secret",
                    "type": "value_error." + "x" * 200,
                    "ctx": {
                        "limit_value": "token-limit-secret",
                        "private": "arbitrary-context-secret",
                    },
                    "input": {"cookie": "input-cookie-secret"},
                },
            ],
            body={"password": "request-body-secret"},
        )
    ).get(
        "/api/v1/explode",
        headers={"X-Request-ID": "validation-sanitization-test"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "success": False,
        "data": None,
        "error": {
            "code": ErrorCode.VALIDATION_ERROR,
            "message": "请求参数校验失败",
            "details": [
                {
                    "loc": ["body", "password"],
                    "msg": "请求参数不符合要求",
                    "type": "value_error.any_str.max_length",
                    "ctx": {"limit_value": 128},
                },
                {
                    "loc": ["request"],
                    "msg": "请求参数不符合要求",
                    "type": "validation_error",
                    "ctx": None,
                },
            ],
        },
        "meta": {"requestId": "validation-sanitization-test"},
    }
    for forbidden in (
        "validator-secret",
        "ctx-exception-secret",
        "ctx-token-secret",
        "request-input-secret",
        "internal.example",
        "location-secret",
        "second-validator-secret",
        "token-limit-secret",
        "arbitrary-context-secret",
        "input-cookie-secret",
        "request-body-secret",
        "C:\\private",
    ):
        assert forbidden not in response.text


def test_unhandled_error_ordinary_log_has_no_exception_or_stack(caplog: pytest.LogCaptureFixture) -> None:
    error = RuntimeError(
        "password=do-not-leak postgresql://admin:secret@db.internal/app "
        r"C:\private\service.py"
    )

    with caplog.at_level(logging.ERROR, logger="backend.app.main"):
        response = _client_raising(error).get(
            "/api/v1/explode",
            headers={"X-Request-ID": "unhandled-log-test"},
        )

    assert response.status_code == 500
    records = [record for record in caplog.records if record.name == "backend.app.main"]
    assert records
    assert all(record.exc_info is None for record in records)
    assert all(record.stack_info is None for record in records)
    assert "unhandled-log-test" in caplog.text
    for forbidden in (
        "do-not-leak",
        "admin:secret",
        "postgresql://",
        "C:\\private",
        "Traceback",
        "RuntimeError:",
    ):
        assert forbidden not in caplog.text


def test_central_ordinary_log_sanitizer_cleans_arguments_and_exc_info(
    caplog: pytest.LogCaptureFixture,
) -> None:
    ordinary_logger = logging.getLogger("backend.app.tests.ordinary_log")

    with caplog.at_level(logging.WARNING, logger=ordinary_logger.name):
        ordinary_logger.warning(
            "provider_failure error=%s token=%s cookie=%s connection=%s path=%s",
            RuntimeError("raw exception password=exception-secret"),
            "token-secret",
            "session=very-secret",
            "postgresql://admin:database-secret@db.internal/app",
            r"C:\private\provider.py",
        )
        try:
            raise ValueError("stack-secret")
        except ValueError:
            ordinary_logger.exception("provider_failure request_id=ordinary-log-test")
        ordinary_logger.warning(
            "provider_headers request_id=ordinary-log-test headers=%s unix_path=%s",
            {
                "Authorization": "Bearer auth-secret",
                "Cookie": "session=cookie-secret; csrf=csrf-secret",
                "password": "mapping-secret",
            },
            "/srv/private/provider.py",
        )
        ordinary_logger.warning(
            "request_body=%s payload=%s password=%s path=%s",
            "plain body secret words",
            "plain payload secret words",
            "this is my secret passphrase",
            "/app/private/provider.py",
        )
        ordinary_logger.warning(
            "event=structured_extra_test request_id=ordinary-log-test",
            extra={
                "authorization": "Bearer extra-auth-secret",
                "request_payload": "extra-payload-secret",
                "request_id": "ordinary-log-test",
            },
        )

    records = [record for record in caplog.records if record.name == ordinary_logger.name]
    assert len(records) == 5
    assert all(record.exc_info is None for record in records)
    assert all(record.stack_info is None for record in records)
    structured_record = records[-1]
    assert structured_record.__dict__["authorization"] == "[REDACTED]"
    assert structured_record.__dict__["request_payload"] == "[REDACTED]"
    assert structured_record.__dict__["request_id"] == "ordinary-log-test"
    assert "ordinary-log-test" in caplog.text
    for forbidden in (
        "raw exception",
        "exception-secret",
        "token-secret",
        "very-secret",
        "database-secret",
        "postgresql://",
        "C:\\private",
        "stack-secret",
        "auth-secret",
        "cookie-secret",
        "csrf-secret",
        "mapping-secret",
        "plain body secret words",
        "plain payload secret words",
        "this is my secret passphrase",
        "extra-auth-secret",
        "extra-payload-secret",
        "/app/private",
        "/srv/private",
        "Traceback",
    ):
        assert forbidden not in caplog.text
