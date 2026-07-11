from __future__ import annotations

import os
import secrets
from typing import Annotated, Any, Callable

from fastapi import Header, HTTPException


ROLE_ORDER = {"viewer": 0, "operator": 1, "reviewer": 2, "admin": 3}


def auth_mode() -> str:
    return (os.getenv("AUTH_MODE") or "off").strip().lower()


def configured_tokens() -> dict[str, str]:
    tokens: dict[str, str] = {}
    operator = os.getenv("AUTH_OPERATOR_TOKEN", "").strip()
    reviewer = os.getenv("AUTH_REVIEWER_TOKEN", "").strip()
    admin = os.getenv("AUTH_ADMIN_TOKEN", "").strip()
    generic = os.getenv("AUTH_TOKEN", "").strip()
    if operator:
        tokens[operator] = "operator"
    if reviewer:
        tokens[reviewer] = "reviewer"
    if admin:
        tokens[admin] = "admin"
    if generic:
        tokens[generic] = (os.getenv("AUTH_TOKEN_ROLE") or "admin").strip().lower() or "admin"
    return tokens


def role_for_token(token: str) -> str | None:
    for configured_token, role in configured_tokens().items():
        if secrets.compare_digest(token, configured_token):
            return role
    return None


def auth_status() -> dict[str, Any]:
    tokens = configured_tokens()
    roles = set(tokens.values())
    mode = auth_mode()
    return {
        "mode": mode,
        "enabled": mode == "token",
        "operatorConfigured": "operator" in roles,
        "reviewerConfigured": "reviewer" in roles,
        "adminConfigured": "admin" in roles,
    }


def bearer_token(authorization: str | None, api_token: str | None) -> str:
    if api_token:
        return api_token.strip()
    value = (authorization or "").strip()
    if value.lower().startswith("bearer "):
        return value[7:].strip()
    return value


def require_role(min_role: str) -> Callable[..., dict[str, Any]]:
    required_level = ROLE_ORDER[min_role]

    def dependency(
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
        x_api_token: Annotated[str | None, Header(alias="X-API-Token")] = None,
    ) -> dict[str, Any]:
        mode = auth_mode()
        if mode in {"", "off", "none", "dev"}:
            return {"role": "admin", "authMode": mode or "off"}
        if mode != "token":
            raise HTTPException(status_code=500, detail=f"Unsupported AUTH_MODE: {mode}")

        token = bearer_token(authorization, x_api_token)
        if not token:
            raise HTTPException(status_code=401, detail="Authentication token required")
        role = role_for_token(token)
        if role is None:
            raise HTTPException(status_code=401, detail="Invalid authentication token")
        if ROLE_ORDER.get(role, -1) < required_level:
            raise HTTPException(status_code=403, detail=f"{min_role} role required")
        return {"role": role, "authMode": mode}

    return dependency
