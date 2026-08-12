from __future__ import annotations

from fastapi import APIRouter

from .system import router as system_router


api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(system_router)
