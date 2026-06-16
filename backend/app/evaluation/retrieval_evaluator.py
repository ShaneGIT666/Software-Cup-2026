from __future__ import annotations

import os
import statistics
import time
from contextlib import contextmanager
from typing import Any, Callable, Iterable

from ..data_store import load_document_chunks, load_seed_data
from ..schemas import SearchRequest
from ..services import search_knowledge
from .models import EvalCase, EvalCaseResult, EvalDataset, EvalMode, MetricValue


DEFAULT_TOP_KS = (1, 3, 5)
EVAL_MODES: dict[str, EvalMode] = {
    "keyword": EvalMode(
        name="keyword",
        description="Current keyword/field-weight retrieval baseline with Chroma disabled.",
        env_overrides={
            "RAG_VECTOR_STORE": "off",
            "RAG_EMBEDDING_PROVIDER": "hash",
            "REMOTE_API_MODE": "off",
            "LLM_PROVIDER": "mock",
        },
    ),
    "chroma_off": EvalMode(
        name="chroma_off",
        description="Explicit Chroma-off retrieval check.",
        env_overrides={
            "RAG_VECTOR_STORE": "off",
            "RAG_EMBEDDING_PROVIDER": "hash",
        },
    ),
    "llm_mock": EvalMode(
        name="llm_mock",
        description="Retrieval with remote LLM disabled/mock; search should be unchanged.",
        env_overrides={
            "RAG_VECTOR_STORE": "off",
            "RAG_EMBEDDING_PROVIDER": "hash",
            "REMOTE_API_MODE": "off",
            "LLM_PROVIDER": "mock",
        },
    ),
    "pending_review": EvalMode(
        name="pending_review",
        description="Approved-only isolation check against pending_review sources.",
        env_overrides={
            "RAG_VECTOR_STORE": "off",
            "RAG_EMBEDDING_PROVIDER": "hash",
            "REMOTE_API_MODE": "off",
            "LLM_PROVIDER": "mock",
        },
    ),
}


SearchFunc = Callable[[SearchRequest], dict[str, Any]]


@contextmanager
def temporary_env(overrides: dict[str, str]) -> Iterable[None]:
    previous = {key: os.environ.get(key) for key in overrides}
    try:
        for key, value in overrides.items():
            os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def source_ids_for_result(result: dict[str, Any]) -> list[str]:
    candidates = [
        result.get("id"),
        result.get("documentId"),
        result.get("chunkId"),
        result.get("workflowId"),
    ]
    return list(dict.fromkeys(str(item) for item in candidates if item))


def flatten_returned_source_ids(results: list[dict[str, Any]]) -> list[str]:
    source_ids: list[str] = []
    for result in results:
        source_ids.extend(source_ids_for_result(result))
    return list(dict.fromkeys(source_ids))


def build_source_status_map() -> dict[str, str]:
    data = load_seed_data()
    status_map: dict[str, str] = {}
    for manual in data["manuals"]:
        status_map[str(manual["id"])] = "approved"
    for workflow in data["workflows"]:
        status_map[str(workflow["id"])] = "approved"
    for repair_case in data["cases"]:
        status_map[str(repair_case["id"])] = str(repair_case.get("status") or "approved")
    for chunk in load_document_chunks():
        status_map[str(chunk["id"])] = str(chunk.get("review_status", "approved"))
        if chunk.get("documentId"):
            status_map[str(chunk["documentId"])] = str(chunk.get("review_status", "approved"))
    return status_map


def rank_for_expected(results: list[dict[str, Any]], expected_ids: list[str]) -> int | None:
    expected = set(expected_ids)
    if not expected:
        return None
    for index, result in enumerate(results, start=1):
        if expected.intersection(source_ids_for_result(result)):
            return index
    return None


def hit_at_k(results: list[dict[str, Any]], expected_ids: list[str], k: int) -> bool | None:
    if not expected_ids:
        return None
    expected = set(expected_ids)
    for result in results[:k]:
        if expected.intersection(source_ids_for_result(result)):
            return True
    return False


def recall_at_k(results: list[dict[str, Any]], expected_ids: list[str], k: int) -> float | None:
    if not expected_ids:
        return None
    returned = set(flatten_returned_source_ids(results[:k]))
    return round(len(returned.intersection(expected_ids)) / len(set(expected_ids)), 4)


def keyword_hits(results: list[dict[str, Any]], expected_keywords: list[str]) -> list[str]:
    if not expected_keywords:
        return []
    haystack = " ".join(
        " ".join(
            [
                str(result.get("title", "")),
                str(result.get("snippet", "")),
                " ".join(str(term) for term in result.get("matchedTerms", [])),
            ]
        )
        for result in results
    )
    return [keyword for keyword in expected_keywords if keyword and keyword in haystack]


def forbidden_source_violations(results: list[dict[str, Any]], forbidden_ids: list[str]) -> list[str]:
    if not forbidden_ids:
        return []
    returned = set(flatten_returned_source_ids(results))
    return sorted(returned.intersection(forbidden_ids))


def approved_only_violations(
    results: list[dict[str, Any]],
    source_status: dict[str, str],
    forbidden_statuses: list[str],
) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    statuses = set(forbidden_statuses or ["pending_review", "rejected", "deprecated", "replaced"])
    for result in results:
        for source_id in source_ids_for_result(result):
            status = source_status.get(source_id)
            if status and status in statuses:
                violations.append({"source_id": source_id, "status": status})
    return violations


def evaluate_case(
    case: EvalCase,
    search_func: SearchFunc = search_knowledge,
    top_k: int = 5,
    source_status: dict[str, str] | None = None,
) -> EvalCaseResult:
    request = SearchRequest(deviceModel=case.device_model, faultText=case.question, inputType="text", topK=top_k)
    started = time.perf_counter()
    payload = search_func(request)
    latency_ms = round((time.perf_counter() - started) * 1000, 3)
    results = payload.get("results", [])
    if not isinstance(results, list):
        results = []

    expected_ids = case.expected_ids
    first_rank = rank_for_expected(results, expected_ids)
    status_map = source_status or build_source_status_map()
    return EvalCaseResult(
        id=case.id,
        category=case.category,
        question=case.question,
        returned_source_ids=flatten_returned_source_ids(results),
        top_result_id=str(results[0].get("id", "")) if results else "",
        result_count=len(results),
        latency_ms=latency_ms,
        hit_at={f"Hit@{k}": hit_at_k(results, expected_ids, k) for k in DEFAULT_TOP_KS},
        recall_at={f"Recall@{k}": recall_at_k(results, expected_ids, k) for k in DEFAULT_TOP_KS},
        reciprocal_rank=round(1 / first_rank, 4) if first_rank else (0.0 if expected_ids else None),
        forbidden_source_violations=forbidden_source_violations(results, case.forbidden_source_ids),
        approved_only_violations=approved_only_violations(results, status_map, case.forbidden_review_status),
        keyword_hits=keyword_hits(results, case.expected_keywords),
        empty_retrieval=len(results) == 0,
        notes=case.notes,
    )


def percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = round((len(ordered) - 1) * percentile_value)
    return round(ordered[index], 3)


def metric_average(values: list[float | int]) -> float:
    return round(float(statistics.mean(values)), 4) if values else 0.0


def aggregate_metrics(case_results: list[EvalCaseResult]) -> dict[str, Any]:
    expected_cases = [result for result in case_results if result.reciprocal_rank is not None]
    metrics: dict[str, Any] = {}
    for k in DEFAULT_TOP_KS:
        hit_key = f"Hit@{k}"
        recall_key = f"Recall@{k}"
        hit_values = [result.hit_at[hit_key] for result in expected_cases if result.hit_at[hit_key] is not None]
        recall_values = [
            result.recall_at[recall_key] for result in expected_cases if result.recall_at[recall_key] is not None
        ]
        metrics[hit_key] = MetricValue(
            value=round(sum(1 for value in hit_values if value) / len(hit_values), 4) if hit_values else None,
            available=bool(hit_values),
            reason="" if hit_values else "no cases with expected_source_ids",
        )
        metrics[recall_key] = MetricValue(
            value=metric_average([float(value) for value in recall_values]) if recall_values else None,
            available=bool(recall_values),
            reason="" if recall_values else "no cases with expected_source_ids",
        )

    reciprocal_values = [result.reciprocal_rank for result in expected_cases if result.reciprocal_rank is not None]
    metrics["MRR"] = MetricValue(
        value=metric_average([float(value) for value in reciprocal_values]) if reciprocal_values else None,
        available=bool(reciprocal_values),
        reason="" if reciprocal_values else "no cases with expected_source_ids",
    )
    metrics["forbidden_source_violation_count"] = MetricValue(
        value=sum(len(result.forbidden_source_violations) for result in case_results)
    )
    metrics["approved_only_violation_count"] = MetricValue(
        value=sum(len(result.approved_only_violations) for result in case_results)
    )
    metrics["empty_retrieval_count"] = MetricValue(value=sum(1 for result in case_results if result.empty_retrieval))
    metrics["fallback_count"] = MetricValue(
        value=None,
        available=False,
        reason="search_knowledge does not expose per-query fallback events; process-global provider fallback is not counted.",
    )
    latencies = [result.latency_ms for result in case_results]
    metrics["average_latency_ms"] = MetricValue(value=round(metric_average(latencies), 3))
    metrics["p50_latency_ms"] = MetricValue(value=percentile(latencies, 0.50))
    metrics["p95_latency_ms"] = MetricValue(value=percentile(latencies, 0.95))
    return metrics


def evaluate_dataset(
    dataset: EvalDataset,
    mode: EvalMode,
    search_func: SearchFunc = search_knowledge,
    top_k: int = 5,
) -> tuple[list[EvalCaseResult], dict[str, Any]]:
    with temporary_env(mode.env_overrides):
        source_status = build_source_status_map()
        case_results = [
            evaluate_case(case, search_func=search_func, top_k=top_k, source_status=source_status)
            for case in dataset.cases
        ]
    return case_results, aggregate_metrics(case_results)
