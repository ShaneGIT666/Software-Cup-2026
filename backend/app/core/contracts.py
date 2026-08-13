from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ResponseMeta(BaseModel):
    requestId: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Any = None


class PageRequest(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)
    cursor: str | None = None


class PageMeta(ResponseMeta):
    nextCursor: str | None = None


class PageData(BaseModel):
    """Payload shape for every cursor-paginated v1 list endpoint."""

    items: list[Any] = Field(default_factory=list)


class V1Response(BaseModel):
    """Stable envelope for non-paginated ``/api/v1`` endpoints only.

    Legacy ``/api`` responses deliberately keep their existing shape during
    the staged migration.
    """

    success: bool = True
    data: Any = None
    error: ErrorBody | None = None
    meta: ResponseMeta


class V1PageResponse(BaseModel):
    """Stable envelope for cursor-paginated ``/api/v1`` list endpoints."""

    success: bool = True
    data: PageData
    error: ErrorBody | None = None
    meta: PageMeta
