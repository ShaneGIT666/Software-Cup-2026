from __future__ import annotations

from fastapi import APIRouter

from ...core.contracts import V1Response
from .domain_registry import include_domain_routers
from .system import router as system_router


api_v1_router = APIRouter(
    prefix="/api/v1",
    responses={
        500: {
            "model": V1Response,
            "description": "服务器内部错误；响应使用脱敏 v1 错误信封并包含 request ID。",
        }
    },
)
api_v1_router.include_router(system_router)
include_domain_routers(api_v1_router)
