from __future__ import annotations

import os
import secrets
from typing import Annotated, Any, Callable

from fastapi import Header, HTTPException


ROLE_ORDER = {"viewer": 0, "operator": 1, "reviewer": 2, "admin": 3}
VALID_AUTH_MODES = {"off", "token"}
CONFIGURABLE_ROLES = {"operator", "reviewer", "admin"}
TRUTHY_VALUES = {"1", "true", "yes", "on"}
PROTECTED_APP_ENVS = {"production", "competition", "submission"}


def auth_mode() -> str:
    return (os.getenv("AUTH_MODE") or "off").strip().lower()


def app_environment() -> str:
    return (os.getenv("APP_ENV") or "development").strip().lower()


def env_flag(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in TRUTHY_VALUES


def insecure_auth_off_allowed() -> bool:
    if app_environment() in PROTECTED_APP_ENVS:
        return False
    return env_flag("ALLOW_INSECURE_AUTH_OFF", False)


def configured_token_pairs() -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    role_tokens = {
        "operator": os.getenv("AUTH_OPERATOR_TOKEN", "").strip(),
        "reviewer": os.getenv("AUTH_REVIEWER_TOKEN", "").strip(),
        "admin": os.getenv("AUTH_ADMIN_TOKEN", "").strip(),
    }
    for role, token in role_tokens.items():
        if token:
            pairs.append((token, role))
    generic = os.getenv("AUTH_TOKEN", "").strip()
    if generic:
        pairs.append((generic, (os.getenv("AUTH_TOKEN_ROLE") or "admin").strip().lower() or "admin"))
    return pairs


def auth_config_errors() -> list[str]:
    errors: list[str] = []
    mode = auth_mode()
    if mode not in VALID_AUTH_MODES:
        errors.append(f"Unsupported AUTH_MODE: {mode}")
    if mode == "off":
        if app_environment() in PROTECTED_APP_ENVS:
            errors.append("AUTH_MODE=off is forbidden in protected application environments")
        elif not insecure_auth_off_allowed():
            errors.append("AUTH_MODE=off requires ALLOW_INSECURE_AUTH_OFF=true")
    generic_role = (os.getenv("AUTH_TOKEN_ROLE") or "admin").strip().lower() or "admin"
    if generic_role not in CONFIGURABLE_ROLES:
        errors.append("AUTH_TOKEN_ROLE must be one of operator, reviewer, admin")
    token_roles: dict[str, str] = {}
    for token, role in configured_token_pairs():
        if role not in CONFIGURABLE_ROLES:
            errors.append("Configured token role must be one of operator, reviewer, admin")
        previous_role = token_roles.get(token)
        if previous_role and previous_role != role:
            errors.append("Authentication tokens must be unique across roles")
        token_roles[token] = role
    if mode == "token" and "admin" not in set(token_roles.values()):
        errors.append("AUTH_MODE=token requires an admin token")
    return list(dict.fromkeys(errors))


def validate_auth_config() -> None:
    errors = auth_config_errors()
    if errors:
        raise HTTPException(status_code=500, detail="; ".join(errors))


def configured_tokens() -> dict[str, str]:
    validate_auth_config()
    tokens: dict[str, str] = {}
    for token, role in configured_token_pairs():
        tokens[token] = role
    return tokens


def role_for_token(token: str) -> str | None:
    for configured_token, role in configured_tokens().items():
        if secrets.compare_digest(token, configured_token):
            return role
    return None


def auth_status() -> dict[str, Any]:
    pairs = configured_token_pairs()
    tokens = {token: role for token, role in pairs}
    roles = set(tokens.values())
    mode = auth_mode()
    errors = auth_config_errors()
    return {
        "mode": mode,
        "enabled": mode == "token",
        "valid": not errors,
        "appEnvironment": app_environment(),
        "insecureAuthOffAllowed": insecure_auth_off_allowed(),
        "operatorConfigured": "operator" in roles,
        "reviewerConfigured": "reviewer" in roles,
        "adminConfigured": "admin" in roles,
        "errors": errors,
    }


def bearer_token(authorization: str | None, api_token: str | None) -> str:
    if api_token:
        return api_token.strip()
    value = (authorization or "").strip()
    if value.lower().startswith("bearer "):
        return value[7:].strip()
    if value:
        raise HTTPException(status_code=401, detail="Malformed Authorization header")
    return ""


def require_role(min_role: str) -> Callable[..., dict[str, Any]]:
    required_level = ROLE_ORDER[min_role]

    def dependency(
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
        x_api_token: Annotated[str | None, Header(alias="X-API-Token")] = None,
    ) -> dict[str, Any]:
        mode = auth_mode()
        validate_auth_config()
        if mode == "off":
            return {"role": "admin", "authMode": mode or "off"}

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
