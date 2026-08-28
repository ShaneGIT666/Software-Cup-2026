from __future__ import annotations

from fastapi import APIRouter

from ...core.contracts import InternalErrorResponse, V1ErrorResponse, ValidationErrorResponse
from .domain_registry import include_domain_routers
from .system import router as system_router


api_v1_router = APIRouter(
    prefix="/api/v1",
    responses={
        "default": {
            "model": V1ErrorResponse,
            "description": "其他请求错误；响应使用无公开 details 的 v1 错误信封。",
        },
        422: {
            "model": ValidationErrorResponse,
            "description": "请求参数校验失败；details 仅包含白名单校验字段。",
        },
        500: {
            "model": InternalErrorResponse,
            "description": "服务器内部错误；响应使用脱敏 v1 错误信封并包含 request ID。",
        }
    },
)
api_v1_router.include_router(system_router)
include_domain_routers(api_v1_router)
