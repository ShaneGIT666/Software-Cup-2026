from __future__ import annotations

import re
from uuid import uuid4

from fastapi import HTTPException

from ..schemas import SearchRequest
from .filters import apply_metadata_filter
from .fusion import fuse_hits_rrf
from .keyword_retriever import retrieve_keyword_hits
from .models import QueryContext, RetrievalHit
from .reranker import rerank_hits
from .vector_retriever import retrieve_vector_hits


_QUERY_FRAGMENT = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]+", re.IGNORECASE)
_MIN_CANDIDATE_POOL = 12
_MAX_CANDIDATE_POOL = 50


def tokenize(*parts: str) -> list[str]:
    """Return literal terms plus useful two-character terms from long Chinese phrases.

    Chinese diagnostic text is commonly entered as an uninterrupted sentence. Keeping
    only whitespace-delimited terms makes those queries nearly impossible to match.
    The full fragment remains available for exact phrase matches; bigrams add a
    conservative lexical fallback for symptoms such as "周期敲击".
    """

    tokens: list[str] = []
    for part in parts:
        for fragment in _QUERY_FRAGMENT.findall((part or "").lower()):
            tokens.append(fragment)
            if len(fragment) >= 5 and all("\u4e00" <= char <= "\u9fff" for char in fragment):
                tokens.extend(fragment[index : index + 2] for index in range(len(fragment) - 1))
    return list(dict.fromkeys(tokens))


def candidate_pool_size(top_k: int) -> int:
    return min(_MAX_CANDIDATE_POOL, max(_MIN_CANDIDATE_POOL, top_k * 4))


def build_query_context(request: SearchRequest) -> QueryContext:
    query_tokens = tokenize(request.deviceModel, request.faultText)
    return QueryContext(
        device_model=request.deviceModel.strip(),
        fault_text=request.faultText.strip(),
        top_k=request.topK,
        query_tokens=query_tokens,
        vector_query=" ".join([request.deviceModel, request.faultText]).strip(),
        candidate_k=candidate_pool_size(request.topK),
        metadata_filters={"device_model": request.deviceModel.strip()},
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


def filter_and_rank_hits(context: QueryContext, hits: list[RetrievalHit]) -> list[RetrievalHit]:
    """Apply safety metadata before limiting candidates and calculating RRF ranks."""

    filtered_hits = apply_metadata_filter(context, hits)[: context.candidate_k]
    for rank, hit in enumerate(filtered_hits, start=1):
        if hit.keyword_rank is not None:
            hit.keyword_rank = rank
        if hit.vector_rank is not None:
            hit.vector_rank = rank
        if hit.qdrant_rank is not None:
            hit.qdrant_rank = rank
    return filtered_hits


def search_knowledge(request: SearchRequest) -> dict[str, object]:
    context = build_query_context(request)
    if not context.query_tokens:
        raise HTTPException(status_code=400, detail="设备型号和故障现象不能同时为空")

    keyword_hits = filter_and_rank_hits(context, retrieve_keyword_hits(context))
    vector_hits = filter_and_rank_hits(context, retrieve_vector_hits(context))
    fused_hits = merge_results(keyword_hits, vector_hits, context.candidate_k)
    final_hits = rerank_hits(context, fused_hits)[: request.topK]
    for final_rank, hit in enumerate(final_hits, start=1):
        hit.score_breakdown.update(
            {
                "finalRank": final_rank,
                "candidatePool": {
                    "keyword": len(keyword_hits),
                    "vector": len(vector_hits),
                    "fused": len(fused_hits),
                },
            }
        )
    results = [hit.to_search_result() for hit in final_hits]

    return {
        "queryId": f"q-{uuid4().hex[:8]}",
        "summary": build_search_summary(results, context.query_tokens),
        "results": results,
    }
