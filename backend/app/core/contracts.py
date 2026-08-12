from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ResponseMeta(BaseModel):
    requestId: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Any = None


class V1Response(BaseModel):
    """Stable envelope for new ``/api/v1`` endpoints only.

    Legacy ``/api`` responses deliberately keep their existing shape during
    the staged migration.
    """

    success: bool = True
    data: Any = None
    error: ErrorBody | None = None
    meta: ResponseMeta


class PageRequest(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)
    cursor: str | None = None


class PageMeta(ResponseMeta):
    nextCursor: str | None = None

