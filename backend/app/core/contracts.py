from __future__ import annotations

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field, StrictFloat, StrictInt, StrictStr
from pydantic.generics import GenericModel


DataT = TypeVar("DataT")
ItemT = TypeVar("ItemT")


class V1ContractModel(BaseModel):
    """Base for generated-client contracts with no undeclared fields."""

    class Config:
        extra = "forbid"


class _ClosedGenericModel(GenericModel):
    class Config:
        extra = "forbid"


class ResponseMeta(V1ContractModel):
    requestId: str


class PageMeta(ResponseMeta):
    nextCursor: str | None = None


class ErrorBody(V1ContractModel):
    """Error body for errors whose public contract permits no details."""

    code: str
    message: str
    details: None = None


class ValidationIssueContext(V1ContractModel):
    """Allowlisted context emitted by the validators used by v1 requests."""

    limit_value: StrictInt | StrictFloat | StrictStr | None = None


class ValidationIssue(V1ContractModel):
    loc: list[StrictStr | StrictInt]
    msg: str
    type: str
    ctx: ValidationIssueContext | None = None


class ValidationErrorBody(ErrorBody):
    code: Literal["VALIDATION_ERROR"] = "VALIDATION_ERROR"
    message: Literal["请求参数校验失败"] = "请求参数校验失败"
    details: list[ValidationIssue]


ReadinessDialect = Literal["postgresql", "postgresql+psycopg", "postgresql+psycopg2"]
ReadinessMode = Literal["local", "oidc"]
ReadinessViolation = Literal["idempotency_secret", "trusted_https_origins", "legacy_surface"]


class ReadinessCheckData(V1ContractModel):
    required: bool
    healthy: bool
    reason: str
    configured: bool | None = None
    dialect: ReadinessDialect | None = None
    mode: ReadinessMode | None = None
    latencyMs: int | None = Field(default=None, ge=0)
    violations: list[ReadinessViolation] | None = None


class ReadinessData(V1ContractModel):
    status: Literal["ok", "not_ready"]
    database: ReadinessCheckData
    foundation: ReadinessCheckData
    identity: ReadinessCheckData | None = None
    documents: ReadinessCheckData | None = None
    knowledge: ReadinessCheckData | None = None
    devices: ReadinessCheckData | None = None
    workflows: ReadinessCheckData | None = None
    workers: ReadinessCheckData | None = None
    indexing: ReadinessCheckData | None = None
    rag: ReadinessCheckData | None = None


class ReadinessErrorBody(ErrorBody):
    code: Literal["DEPENDENCY_UNAVAILABLE"] = "DEPENDENCY_UNAVAILABLE"
    message: Literal["关键依赖未就绪"] = "关键依赖未就绪"
    details: ReadinessData


class InternalErrorBody(ErrorBody):
    code: Literal["INTERNAL_ERROR"] = "INTERNAL_ERROR"
    message: Literal["服务器内部错误"] = "服务器内部错误"
    details: None = None


class PageData(_ClosedGenericModel, Generic[ItemT]):
    """Typed payload for one cursor-paginated v1 operation."""

    items: list[ItemT] = Field(default_factory=list)


class V1Response(_ClosedGenericModel, Generic[DataT]):
    """Typed success envelope; public operations must bind ``DataT``."""

    success: Literal[True] = True
    data: DataT
    error: None = None
    meta: ResponseMeta


class V1PageResponse(_ClosedGenericModel, Generic[ItemT]):
    """Typed page envelope; public list operations must bind ``ItemT``."""

    success: Literal[True] = True
    data: PageData[ItemT]
    error: None = None
    meta: PageMeta


class V1ErrorResponse(V1ContractModel):
    success: Literal[False] = False
    data: None = None
    error: ErrorBody
    meta: ResponseMeta


class ValidationErrorResponse(V1ErrorResponse):
    error: ValidationErrorBody


class ReadinessErrorResponse(V1ErrorResponse):
    error: ReadinessErrorBody


class InternalErrorResponse(V1ErrorResponse):
    error: InternalErrorBody


class PageRequest(V1ContractModel):
    limit: int = Field(default=20, ge=1, le=100)
    cursor: str | None = None
