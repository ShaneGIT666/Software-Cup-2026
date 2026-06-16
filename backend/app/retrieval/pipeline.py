from __future__ import annotations

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


def build_query_context(request: SearchRequest) -> QueryContext:
    query_tokens = tokenize(request.deviceModel, request.faultText)
    return QueryContext(
        device_model=request.deviceModel.strip(),
        fault_text=request.faultText.strip(),
        top_k=request.topK,
        query_tokens=query_tokens,
        vector_query=" ".join([request.deviceModel, request.faultText]).strip(),
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


def merge_results(keyword_hits: list[RetrievalHit], vector_hits: list[RetrievalHit], top_k: int) -> list[RetrievalHit]:
    return fuse_hits_rrf(keyword_hits, vector_hits, top_k)


def search_knowledge(request: SearchRequest) -> dict[str, object]:
    context = build_query_context(request)
    if not context.query_tokens:
        raise HTTPException(status_code=400, detail="设备型号和故障现象不能同时为空")

    keyword_hits = apply_metadata_filter(context, retrieve_keyword_hits(context))
    vector_hits = apply_metadata_filter(context, retrieve_vector_hits(context))
    fused_hits = merge_results(keyword_hits, vector_hits, request.topK)
    final_hits = rerank_hits(context, fused_hits)[: request.topK]
    results = [hit.to_search_result() for hit in final_hits]

    return {
        "queryId": f"q-{uuid4().hex[:8]}",
        "summary": build_search_summary(results, context.query_tokens),
        "results": results,
    }
