from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class ApiResponse(BaseModel):
    success: bool = True
    data: Any = None
    message: str = ""


class SearchRequest(BaseModel):
    deviceModel: str = ""
    faultText: str = ""
    deviceType: str = ""
    maintenanceLevel: str = "normal_repair"
    riskLevel: str = "medium"
    inputType: str = "text"
    topK: int = Field(default=5, ge=1, le=20)


class DiagnosisRequest(BaseModel):
    deviceModel: str = ""
    faultText: str = ""
    deviceType: str = ""
    maintenanceLevel: str = "normal_repair"
    riskLevel: str = "medium"
    evidenceIds: list[str] = Field(default_factory=list)


class RagAnswerRequest(BaseModel):
    deviceModel: str = ""
    faultText: str = ""
    deviceType: str = ""
    maintenanceLevel: str = "normal_repair"
    riskLevel: str = "medium"
    topK: int = Field(default=5, ge=1, le=10)
    provider: Literal["mock", "openai", "anthropic"] | None = None
    includeGraphContext: bool = True


class RagFeedbackCreateRequest(BaseModel):
    deviceModel: str = ""
    faultText: str = ""
    maintenanceLevel: str = "normal_repair"
    originalAnswer: str = Field(min_length=1)
    correctedAnswer: str = ""
    labels: list[str] = Field(default_factory=list)
    reason: str = ""
    reviewer: str = "operator"


class RagFeedbackReviewRequest(BaseModel):
    action: Literal["approve", "reject"]
    reviewer: str = "operator"
    reviewNote: str = ""


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
    deviceType: str = ""
    component: str = ""
    faultCode: str = ""
    riskLevel: str = "medium"
    workflowId: str | None = None
    tags: list[str] = Field(default_factory=list)
    experienceSummary: str = ""
    lessonsLearned: str = ""
    maintenanceLevel: str = "normal_repair"

    @field_validator("riskLevel")
    @classmethod
    def validate_risk_level(cls, value: str) -> str:
        normalized = (value or "medium").strip().lower()
        if normalized not in {"low", "medium", "high", "critical"}:
            raise ValueError("riskLevel must be one of low, medium, high, critical")
        return normalized

    @field_validator("maintenanceLevel")
    @classmethod
    def validate_maintenance_level(cls, value: str) -> str:
        normalized = (value or "normal_repair").strip().lower()
        if normalized not in {"daily_check", "normal_repair", "focused_repair", "major_repair", "emergency"}:
            raise ValueError("maintenanceLevel is not supported")
        return normalized

    @field_validator("workflowId")
    @classmethod
    def normalize_workflow_id(cls, value: str | None) -> str | None:
        normalized = (value or "").strip()
        return normalized or None


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


class KnowledgeChunkStatusRequest(BaseModel):
    status: Literal["draft", "pending_review", "approved", "rejected", "deprecated", "replaced"]
    reason: str = ""
    reviewer: str = "operator"
    replacementChunkId: str | None = None
