from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class QueryContext:
    device_model: str
    fault_text: str
    top_k: int
    query_tokens: list[str]
    vector_query: str
    candidate_k: int = 20
    metadata_filters: dict[str, str] = field(default_factory=dict)


@dataclass
class RetrievalHit:
    id: str
    title: str
    content: str
    source_id: str
    source_name: str
    source_type: str
    confidence: float
    snippet: str
    reason: str
    score_breakdown: dict[str, Any]
    matched_terms: list[str] = field(default_factory=list)
    workflow_id: str | None = None
    chapter: str | None = None
    page: int | None = None
    section: str | None = None
    chunk_id: str | None = None
    document_id: str | None = None
    device_type: str | None = None
    device_model: str | None = None
    component: str | None = None
    fault_type: str | None = None
    review_status: str | None = "approved"
    keyword_rank: int | None = None
    vector_rank: int | None = None
    qdrant_rank: int | None = None
    keyword_score: float | None = None
    vector_score: float | None = None
    qdrant_score: float | None = None
    fusion_score: float | None = None
    rerank_score: float | None = None
    matched_fields: list[str] = field(default_factory=list)
    retrieval_source: str | None = None
    source_retrievers: list[str] = field(default_factory=list)

    def dedupe_key(self) -> str:
        if self.chunk_id:
            version = self.score_breakdown.get("version") or ""
            return f"chunk:{self.chunk_id}:{version}"
        if self.document_id:
            return f"document:{self.document_id}"
        return f"{self.source_type}:{self.id}"

    def to_search_result(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "sourceId": self.source_id,
            "sourceType": self.source_type,
            "sourceName": self.source_name,
            "confidence": self.confidence,
            "snippet": self.snippet,
            "workflowId": self.workflow_id,
            "chapter": self.chapter,
            "page": self.page,
            "section": self.section,
            "matchedTerms": self.matched_terms,
            "reason": self.reason,
            "scoreBreakdown": self.score_breakdown,
            "reviewStatus": self.review_status,
        }
        if self.retrieval_source:
            result["retrievalSource"] = self.retrieval_source
        if self.source_retrievers:
            result["sourceRetrievers"] = self.source_retrievers
        if self.device_type:
            result["deviceType"] = self.device_type
        if self.device_model:
            result["deviceModel"] = self.device_model
        if self.component:
            result["component"] = self.component
        if self.fault_type:
            result["faultType"] = self.fault_type
        if self.document_id:
            result["documentId"] = self.document_id
        if self.chunk_id:
            result["chunkId"] = self.chunk_id
        return result
