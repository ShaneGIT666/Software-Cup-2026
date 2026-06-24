from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    success: bool = True
    data: Any = None
    message: str = ""


class SearchRequest(BaseModel):
    deviceModel: str = ""
    faultText: str = ""
    inputType: str = "text"
    topK: int = Field(default=5, ge=1, le=20)


class DiagnosisRequest(BaseModel):
    deviceModel: str = ""
    faultText: str = ""
    evidenceIds: list[str] = Field(default_factory=list)


class RagAnswerRequest(BaseModel):
    deviceModel: str = ""
    faultText: str = ""
    topK: int = Field(default=5, ge=1, le=10)
    provider: Literal["mock", "openai", "anthropic"] | None = None
    includeGraphContext: bool = True


class LlmValidateRequest(BaseModel):
    deviceModel: str = "发动机-示例型号 A"
    faultText: str = "启动困难"
    topK: int = Field(default=2, ge=1, le=5)
    provider: Literal["openai", "anthropic"] | None = None


class MultimodalAnalyzeRequest(BaseModel):
    provider: Literal["mock", "openai", "anthropic", "local"] | None = None


class MultimodalValidateRequest(BaseModel):
    documentId: str | None = None
    provider: Literal["openai", "anthropic", "local"] | None = None


class CaseCreateRequest(BaseModel):
    deviceModel: str
    faultText: str
    cause: str
    solution: str
    result: str
    tags: list[str] = Field(default_factory=list)


class CaseReviewRequest(BaseModel):
    action: Literal["approve", "reject"]
    reviewNote: str = ""
    reviewer: str = "operator"
    normalizedTags: list[str] = Field(default_factory=list)


class KnowledgeChunkRevisionRequest(BaseModel):
    chunkId: str = ""
    content: str = Field(min_length=1)
    title: str | None = None
    sourceName: str | None = None
    page: int | None = None
    tags: list[str] = Field(default_factory=list)
    reason: str = ""
    reviewer: str = "operator"


class KnowledgeChunkReviewRequest(BaseModel):
    action: Literal["approve", "reject"]
    reason: str = ""
    reviewer: str = "operator"
