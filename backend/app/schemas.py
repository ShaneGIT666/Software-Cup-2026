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
    provider: Literal["mock", "openai", "anthropic"] = "mock"


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
    normalizedTags: list[str] = Field(default_factory=list)
