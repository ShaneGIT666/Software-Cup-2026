from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class EvalCase:
    id: str
    category: str
    question: str
    device_type: str = ""
    device_model: str = ""
    metadata_filters: dict[str, Any] = field(default_factory=dict)
    expected_source_ids: list[str] = field(default_factory=list)
    expected_chunk_ids: list[str] = field(default_factory=list)
    expected_keywords: list[str] = field(default_factory=list)
    forbidden_source_ids: list[str] = field(default_factory=list)
    forbidden_review_status: list[str] = field(default_factory=list)
    must_refuse: bool = False
    notes: str = ""

    @property
    def expected_ids(self) -> list[str]:
        return list(dict.fromkeys(self.expected_source_ids + self.expected_chunk_ids))


@dataclass(frozen=True)
class EvalDataset:
    schema_version: str
    dataset_id: str
    created_at: str
    purpose: str
    cases: list[EvalCase]

    def category_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for case in self.cases:
            counts[case.category] = counts.get(case.category, 0) + 1
        return counts


@dataclass(frozen=True)
class MetricValue:
    value: float | int | None
    available: bool = True
    reason: str = ""


@dataclass(frozen=True)
class EvalMode:
    name: str
    description: str
    env_overrides: dict[str, str]


@dataclass
class EvalCaseResult:
    id: str
    category: str
    question: str
    returned_source_ids: list[str]
    top_result_id: str
    result_count: int
    latency_ms: float
    hit_at: dict[str, bool | None]
    recall_at: dict[str, float | None]
    reciprocal_rank: float | None
    forbidden_source_violations: list[str]
    approved_only_violations: list[dict[str, str]]
    keyword_hits: list[str]
    empty_retrieval: bool
    notes: str = ""


def to_plain_dict(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return {key: to_plain_dict(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {key: to_plain_dict(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_plain_dict(item) for item in value]
    return value
