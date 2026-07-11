from __future__ import annotations

import os
from uuid import uuid4

from fastapi import HTTPException

from ..schemas import SearchRequest
from .filters import apply_metadata_filter
from .fusion import fuse_hits_rrf
from .keyword_retriever import retrieve_keyword_hits
from .models import QueryContext, RetrievalHit
from .reranker import rerank_hits
from .vector_retriever import retrieve_vector_hits


def tokenize(*parts: str) -> list[str]:
    text = " ".join(part for part in parts if part).lower()
    separators = ["，", "。", "、", ",", ".", " ", "-", "_", "\n"]
    for separator in separators:
        text = text.replace(separator, " ")
    return [item for item in text.split(" ") if item]


def env_int(name: str, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    raw_value = os.getenv(name, str(default))
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        value = default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def candidate_pool_size(requested_top_k: int) -> int:
    multiplier = env_int("RAG_RETRIEVAL_CANDIDATE_MULTIPLIER", 4, minimum=1, maximum=20)
    min_candidates = env_int("RAG_RETRIEVAL_MIN_CANDIDATES", 20, minimum=1, maximum=500)
    max_candidates = env_int("RAG_RETRIEVAL_MAX_CANDIDATES", 100, minimum=1, maximum=1000)
    if max_candidates < min_candidates:
        max_candidates = min_candidates
    return min(max(requested_top_k * multiplier, min_candidates), max_candidates)


def build_query_context(request: SearchRequest) -> QueryContext:
    query_tokens = tokenize(request.deviceModel, request.faultText)
    requested_top_k = request.topK
    candidate_k = candidate_pool_size(requested_top_k)
    return QueryContext(
        device_model=request.deviceModel.strip(),
        fault_text=request.faultText.strip(),
        top_k=requested_top_k,
        query_tokens=query_tokens,
        vector_query=" ".join([request.deviceModel, request.faultText]).strip(),
        metadata_filters={"device_model": request.deviceModel.strip()},
        requested_top_k=requested_top_k,
        candidate_k=candidate_k,
    )


def build_search_summary(results: list[dict[str, object]], query_tokens: list[str]) -> str:
    if not results:
        return "暂未命中手册、历史案例或入库资料；建议补充设备型号、故障现象关键词，或先上传对应资料。"

    source_labels = {"manual": "手册", "case": "案例", "document": "入库资料"}
    counts: dict[str, int] = {}
    for item in results:
        source_type = str(item["sourceType"])
        counts[source_type] = counts.get(source_type, 0) + 1
    source_text = "、".join(f"{source_labels.get(key, key)} {value} 条" for key, value in counts.items())

    top = results[0]
    matched_terms = top.get("matchedTerms", [])
    terms = "、".join(matched_terms[:4]) if isinstance(matched_terms, list) else ""
    terms = terms or "输入关键词"
    return (
        f"已按字段权重、来源类型和短语命中排序，返回 {source_text}。"
        f"当前首要参考《{top['title']}》，主要命中：{terms}。"
    )


def merge_results(keyword_hits: list[RetrievalHit], vector_hits: list[RetrievalHit], candidate_k: int) -> list[RetrievalHit]:
    return fuse_hits_rrf(keyword_hits, vector_hits, candidate_k)


def search_knowledge(request: SearchRequest) -> dict[str, object]:
    context = build_query_context(request)
    if not context.query_tokens:
        raise HTTPException(status_code=400, detail="设备型号和故障现象不能同时为空")

    requested_top_k = context.requested_top_k or context.top_k
    candidate_k = context.candidate_k or context.top_k
    keyword_hits = apply_metadata_filter(context, retrieve_keyword_hits(context))[:candidate_k]
    vector_hits = apply_metadata_filter(context, retrieve_vector_hits(context))
    fused_hits = merge_results(keyword_hits, vector_hits, candidate_k)
    reranked_hits = rerank_hits(context, fused_hits)
    candidate_pool_count = len(reranked_hits)
    final_hits = reranked_hits[:requested_top_k]
    for final_rank, hit in enumerate(final_hits, start=1):
        hit.score_breakdown["finalRank"] = final_rank
        hit.score_breakdown["candidatePoolSize"] = candidate_pool_count
        hit.score_breakdown["requestedTopK"] = requested_top_k
    results = [hit.to_search_result() for hit in final_hits]

    return {
        "queryId": f"q-{uuid4().hex[:8]}",
        "summary": build_search_summary(results, context.query_tokens),
        "results": results,
    }
