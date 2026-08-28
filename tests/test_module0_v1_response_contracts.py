from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from pydantic import ValidationError
from starlette.requests import Request

from backend.app.api.v1.identity_response_models import (
    AuditEventListResponse,
    CsrfResponse,
    LoginResponse,
    LogoutResponse,
    MeResponse,
    PasswordChangeResponse,
    RolesResponse,
    UserListResponse,
    UserResponse,
)
from backend.app.api.v1.responses import v1_error, v1_page, v1_success
from backend.app.api.v1.system_response_models import LiveResponse
from backend.app.core.contracts import ErrorBody
from backend.app.domains.identity.http_responses import identity_json_response
from backend.app.main import app


EXPECTED_SUCCESS_SCHEMAS = {
    ("GET", "/api/v1/health/live", "200"): "LiveResponse",
    ("GET", "/api/v1/health/ready", "200"): "ReadyResponse",
    ("POST", "/api/v1/auth/login", "200"): "LoginResponse",
    ("POST", "/api/v1/auth/logout", "200"): "LogoutResponse",
    ("GET", "/api/v1/auth/me", "200"): "MeResponse",
    ("GET", "/api/v1/auth/csrf", "200"): "CsrfResponse",
    ("PUT", "/api/v1/auth/password", "200"): "PasswordChangeResponse",
    ("GET", "/api/v1/users", "200"): "UserListResponse",
    ("POST", "/api/v1/users", "201"): "UserResponse",
    ("PATCH", "/api/v1/users/{user_id}", "200"): "UserResponse",
    ("PATCH", "/api/v1/users/{user_id}/status", "200"): "UserResponse",
    ("PUT", "/api/v1/users/{user_id}/roles", "200"): "UserResponse",
    ("PUT", "/api/v1/users/{user_id}/password", "200"): "UserResponse",
    ("GET", "/api/v1/roles", "200"): "RolesResponse",
    ("GET", "/api/v1/audit-events", "200"): "AuditEventListResponse",
}

USER_DATA = {
    "id": "user-1",
    "username": "alice",
    "displayName": "Alice",
    "isActive": True,
    "roles": ["technician"],
    "mustChangePassword": False,
    "version": 1,
    "createdAt": "2026-08-28T00:00:00+00:00",
    "updatedAt": "2026-08-28T00:00:00+00:00",
}
ME_DATA = {
    "user": {
        "id": "user-1",
        "displayName": "Alice",
        "roles": ["technician"],
        "permissions": ["knowledge:read"],
        "mustChangePassword": False,
    },
    "session": {
        "expiresAt": "2026-08-28T08:00:00+00:00",
        "idleExpiresAt": "2026-08-28T00:30:00+00:00",
    },
}


def _request(request_id: str = "typed-response-001") -> Request:
    request = Request({"type": "http", "method": "GET", "path": "/api/v1/test", "headers": []})
    request.state.request_id = request_id
    return request


def _v1_operations(schema: dict[str, object]) -> Iterator[tuple[str, str, dict[str, object]]]:
    for path, path_item in schema["paths"].items():  # type: ignore[union-attr]
        if not path.startswith("/api/v1"):
            continue
        for method, operation in path_item.items():
            if method in {"get", "post", "put", "patch", "delete"}:
                yield method.upper(), path, operation


def _response_ref(operation: dict[str, object], status_code: str) -> str:
    response = operation["responses"][status_code]  # type: ignore[index]
    return response["content"]["application/json"]["schema"]["$ref"]  # type: ignore[index]


def _assert_closed_schema(
    node: object,
    *,
    components: dict[str, object],
    visited_refs: set[str],
) -> None:
    if isinstance(node, list):
        for item in node:
            _assert_closed_schema(item, components=components, visited_refs=visited_refs)
        return
    if not isinstance(node, dict):
        return
    assert node, "OpenAPI contract contains an unconstrained empty schema"
    ref = node.get("$ref")
    if isinstance(ref, str):
        name = ref.rsplit("/", maxsplit=1)[-1]
        if name not in visited_refs:
            visited_refs.add(name)
            _assert_closed_schema(components[name], components=components, visited_refs=visited_refs)
        return
    if node.get("type") == "object":
        assert node.get("additionalProperties") is False
    for value in node.values():
        _assert_closed_schema(value, components=components, visited_refs=visited_refs)


def test_every_registered_v1_operation_has_a_concrete_success_model() -> None:
    schema = app.openapi()
    operations = list(_v1_operations(schema))

    assert len(operations) == len(EXPECTED_SUCCESS_SCHEMAS) == 15
    for method, path, operation in operations:
        matches = [key for key in EXPECTED_SUCCESS_SCHEMAS if key[:2] == (method, path)]
        assert len(matches) == 1
        _, _, status_code = matches[0]
        expected_model = EXPECTED_SUCCESS_SCHEMAS[matches[0]]
        assert _response_ref(operation, status_code) == f"#/components/schemas/{expected_model}"


def test_v1_success_and_error_models_are_closed_generator_inputs() -> None:
    schema = app.openapi()
    components = schema["components"]["schemas"]

    roots = set(EXPECTED_SUCCESS_SCHEMAS.values())
    roots.update({"V1ErrorResponse", "InternalErrorResponse", "ValidationErrorResponse", "ReadinessErrorResponse"})
    for root in roots:
        _assert_closed_schema(components[root], components=components, visited_refs={root})

    assert ErrorBody.schema()["properties"]["details"]["type"] == "null"
    assert components["ValidationErrorBody"]["properties"]["details"]["items"] == {
        "$ref": "#/components/schemas/ValidationIssue"
    }
    assert components["ValidationErrorBody"]["properties"]["message"]["enum"] == ["请求参数校验失败"]
    assert components["ReadinessErrorBody"]["properties"]["details"] == {
        "$ref": "#/components/schemas/ReadinessData"
    }
    assert components["ReadinessErrorBody"]["properties"]["message"]["enum"] == ["关键依赖未就绪"]
    assert components["PageData_UserData_"]["properties"]["items"]["items"] == {
        "$ref": "#/components/schemas/UserData"
    }
    assert components["PageData_AuditEventData_"]["properties"]["items"]["items"] == {
        "$ref": "#/components/schemas/AuditEventData"
    }

    with pytest.raises(ValidationError):
        v1_error(
            _request(),
            status_code=400,
            code="HTTP_ERROR",
            message="请求失败",
            details={"internal": "must-not-cross-the-public-boundary"},
        )


def test_every_v1_operation_declares_closed_validation_and_internal_errors() -> None:
    schema = app.openapi()

    for _, _, operation in _v1_operations(schema):
        assert _response_ref(operation, "default") == "#/components/schemas/V1ErrorResponse"
        assert _response_ref(operation, "422") == "#/components/schemas/ValidationErrorResponse"
        assert _response_ref(operation, "500") == "#/components/schemas/InternalErrorResponse"
    ready = schema["paths"]["/api/v1/health/ready"]["get"]
    assert _response_ref(ready, "503") == "#/components/schemas/ReadinessErrorResponse"


@pytest.mark.parametrize(
    ("model", "data"),
    [
        (LoginResponse, {**ME_DATA, "csrfToken": "csrf-token"}),
        (LogoutResponse, {"loggedOut": True}),
        (MeResponse, ME_DATA),
        (CsrfResponse, {"csrfToken": "csrf-token"}),
        (
            PasswordChangeResponse,
            {"changed": True, "mustChangePassword": False, "reauthenticationRequired": False},
        ),
        (UserResponse, USER_DATA),
        (RolesResponse, [{"code": "auditor", "permissions": ["audit:read", "ops:read"]}]),
    ],
)
def test_identity_json_response_validates_the_operation_model(model: type, data: object) -> None:
    response = identity_json_response(_request(), data, response_model=model)

    assert response.status_code == 200
    assert json.loads(response.body)["meta"] == {"requestId": "typed-response-001"}


def test_typed_response_helpers_reject_payload_drift_before_serialization() -> None:
    user_page = v1_page(_request(), [USER_DATA], response_model=UserListResponse)
    audit_page = v1_page(
        _request(),
        [
            {
                "id": "audit-1",
                "occurredAt": "2026-08-28T00:00:00+00:00",
                "actorUserId": "user-1",
                "initiatorUserId": None,
                "action": "auth.logout",
                "targetType": "session",
                "targetId": "session-1",
                "result": "success",
                "requestId": "request-1",
                "metadata": {},
            }
        ],
        response_model=AuditEventListResponse,
    )
    live = v1_success(
        _request(),
        {
            "status": "ok",
            "service": "repair-knowledge-assistant",
            "apiVersion": "v1",
            "environment": "test",
        },
        response_model=LiveResponse,
    )

    assert user_page.dict()["data"]["items"][0]["username"] == "alice"
    assert audit_page.dict()["data"]["items"][0]["metadata"] == {
        "roles": None,
        "fields": None,
        "reason": None,
        "lifecycle": None,
        "sourceHmac": None,
    }
    assert live.dict()["data"]["environment"] == "test"
    with pytest.raises(ValidationError):
        identity_json_response(_request(), {"id": "incomplete"}, response_model=UserResponse)
    with pytest.raises(ValidationError):
        v1_page(_request(), [{"id": "incomplete"}], response_model=UserListResponse)
