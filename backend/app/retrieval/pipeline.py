from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from .. import vector_store
from ..data_store import load_cases, load_document_chunks, load_seed_data
from ..schemas import SearchRequest


def tokens(*parts: str) -> list[str]:
    text = " ".join(part for part in parts if part).lower()
    separators = ["，", "。", "、", ",", ".", " ", "-", "_", "\n"]
    for separator in separators:
        text = text.replace(separator, " ")
    return [item for item in text.split(" ") if item]


def field_text(item: dict[str, Any], field: str) -> str:
    value = item.get(field, "")
    if isinstance(value, list):
        return " ".join(str(part) for part in value)
    return str(value)


def unique_items(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def score_item(
    query_tokens: list[str],
    item: dict[str, Any],
    field_weights: dict[str, int],
    source_weight: int,
) -> dict[str, Any]:
    field_matches = []
    matched: list[str] = []
    weighted_score = source_weight

    for field, weight in field_weights.items():
        haystack = field_text(item, field).lower()
        terms = unique_items([token for token in query_tokens if token in haystack])
        if not terms:
            continue
        matched.extend(terms)
        field_score = len(terms) * weight
        weighted_score += field_score
        field_matches.append(
            {
                "field": field,
                "terms": terms,
                "weight": weight,
                "score": field_score,
            }
        )

    query_phrase = " ".join(query_tokens)
    item_text = " ".join(field_text(item, field) for field in field_weights).lower()
    phrase_bonus = 4 if len(query_tokens) > 1 and query_phrase in item_text else 0
    weighted_score += phrase_bonus

    return {
        "score": weighted_score if field_matches else 0,
        "matchedTerms": unique_items(matched),
        "fieldMatches": field_matches,
        "phraseBonus": phrase_bonus,
        "sourceWeight": source_weight,
    }


def confidence_from_score(score: int, cap: float) -> float:
    return min(cap, round(0.5 + score * 0.045, 2))


def score_breakdown(scoring: dict[str, Any], source_type: str) -> dict[str, Any]:
    return {
        "score": scoring["score"],
        "sourceType": source_type,
        "sourceWeight": scoring["sourceWeight"],
        "phraseBonus": scoring["phraseBonus"],
        "fieldMatches": scoring["fieldMatches"],
    }


def vector_score_breakdown(distance: float, embedding_provider: str) -> dict[str, Any]:
    similarity = max(0.0, min(1.0, 1.0 - distance))
    score = max(1, round(similarity * 20))
    return {
        "score": score,
        "sourceType": "document",
        "sourceWeight": 2,
        "phraseBonus": 0,
        "fieldMatches": [
            {
                "field": "chromaVector",
                "terms": [embedding_provider],
                "weight": 1,
                "score": score,
            }
        ],
        "vectorDistance": round(distance, 6),
        "embeddingProvider": embedding_provider,
    }


def source_location(item: dict[str, Any]) -> str:
    parts = []
    if item.get("chapter"):
        parts.append(str(item["chapter"]))
    if item.get("page"):
        parts.append(f"p.{item['page']}")
    return " / ".join(parts)


def reason_text(prefix: str, terms: list[str], item: dict[str, Any]) -> str:
    term_text = "、".join(terms[:4]) if terms else "相关内容"
    location = source_location(item)
    suffix = f"；来源位置：{location}" if location else ""
    return f"{prefix}：{term_text}{suffix}"


def chunk_is_approved(chunk: dict[str, Any]) -> bool:
    return chunk.get("review_status", "approved") == "approved"


def build_search_summary(results: list[dict[str, Any]], query_tokens: list[str]) -> str:
    if not results:
        return "暂未命中手册、历史案例或入库资料；建议补充设备型号、故障现象关键词，或先上传对应资料。"

    source_labels = {"manual": "手册", "case": "案例", "document": "入库资料"}
    counts: dict[str, int] = {}
    for item in results:
        counts[item["sourceType"]] = counts.get(item["sourceType"], 0) + 1
    source_text = "、".join(f"{source_labels.get(key, key)} {value} 条" for key, value in counts.items())

    top = results[0]
    terms = "、".join(top.get("matchedTerms", [])[:4]) or "输入关键词"
    return (
        f"已按字段权重、来源类型和短语命中排序，返回 {source_text}。"
        f"当前首要参考《{top['title']}》，主要命中：{terms}。"
    )


def search_knowledge(request: SearchRequest) -> dict[str, Any]:
    data = load_seed_data()
    query_tokens = tokens(request.deviceModel, request.faultText)
    if not query_tokens:
        raise HTTPException(status_code=400, detail="设备型号和故障现象不能同时为空")

    manual_results = []
    for manual in data["manuals"]:
        field_weights = {"title": 5, "deviceModel": 4, "tags": 4, "content": 2}
        scoring = score_item(query_tokens, manual, field_weights, source_weight=3)
        if scoring["score"]:
            manual_results.append(
                {
                    "id": manual["id"],
                    "title": manual["title"],
                    "sourceType": "manual",
                    "sourceName": manual["sourceName"],
                    "confidence": confidence_from_score(scoring["score"], 0.95),
                    "snippet": manual["content"][:120],
                    "workflowId": manual.get("workflowId"),
                    "chapter": manual.get("chapter"),
                    "page": manual.get("page"),
                    "matchedTerms": scoring["matchedTerms"],
                    "reason": reason_text("命中手册字段", scoring["matchedTerms"], manual),
                    "scoreBreakdown": score_breakdown(scoring, "manual"),
                }
            )

    case_results = []
    for repair_case in data["cases"]:
        if repair_case.get("status") != "approved":
            continue
        field_weights = {"faultTitle": 5, "faultText": 4, "tags": 4, "possibleCauses": 3, "solution": 2}
        scoring = score_item(query_tokens, repair_case, field_weights, source_weight=2)
        if scoring["score"]:
            case_results.append(
                {
                    "id": repair_case["id"],
                    "title": repair_case["faultTitle"],
                    "sourceType": "case",
                    "sourceName": "历史维修案例库",
                    "confidence": confidence_from_score(scoring["score"], 0.94),
                    "snippet": repair_case["solution"],
                    "workflowId": repair_case.get("workflowId"),
                    "matchedTerms": scoring["matchedTerms"],
                    "reason": reason_text("命中历史案例", scoring["matchedTerms"], repair_case),
                    "scoreBreakdown": score_breakdown(scoring, "case"),
                }
            )

    document_results = []
    for chunk in load_document_chunks():
        if not chunk_is_approved(chunk):
            continue
        field_weights = {"title": 4, "sourceName": 3, "keywords": 4, "content": 2}
        scoring = score_item(query_tokens, chunk, field_weights, source_weight=2)
        if scoring["score"]:
            document_results.append(
                {
                    "id": chunk["id"],
                    "title": chunk["title"],
                    "sourceType": "document",
                    "sourceName": chunk["sourceName"],
                    "confidence": confidence_from_score(scoring["score"], 0.93),
                    "snippet": chunk["snippet"],
                    "workflowId": None,
                    "chapter": None,
                    "page": chunk.get("page"),
                    "documentId": chunk.get("documentId"),
                    "chunkId": chunk["id"],
                    "matchedTerms": scoring["matchedTerms"],
                    "reason": reason_text("命中入库资料片段", scoring["matchedTerms"], chunk),
                    "scoreBreakdown": score_breakdown(scoring, "document"),
                }
            )

    known_document_ids = {item["id"] for item in document_results}
    vector_results = []
    vector_query = " ".join([request.deviceModel, request.faultText]).strip()
    for vector_match in vector_store.search_similar_chunks(vector_query, request.topK):
        if vector_match["id"] in known_document_ids:
            continue
        embedding_provider = vector_match.get("embeddingProvider", "hash")
        breakdown = vector_score_breakdown(vector_match.get("distance", 1.0), embedding_provider)
        recall_label = "真实 embedding 向量召回" if embedding_provider == "openai" else "hash fallback 向量召回"
        vector_results.append(
            {
                "id": vector_match["id"],
                "title": vector_match["title"],
                "sourceType": "document",
                "sourceName": vector_match["sourceName"],
                "confidence": confidence_from_score(breakdown["score"], 0.9),
                "snippet": vector_match["snippet"],
                "workflowId": None,
                "chapter": None,
                "page": vector_match.get("page"),
                "documentId": vector_match.get("documentId"),
                "chunkId": vector_match.get("chunkId"),
                "matchedTerms": [embedding_provider],
                "reason": f"Chroma {recall_label}，距离 {breakdown['vectorDistance']}",
                "scoreBreakdown": breakdown,
            }
        )

    results = sorted(
        manual_results + case_results + document_results + vector_results,
        key=lambda item: (item["scoreBreakdown"]["score"], item["confidence"]),
        reverse=True,
    )[: request.topK]

    return {
        "queryId": f"q-{uuid4().hex[:8]}",
        "summary": build_search_summary(results, query_tokens),
        "results": results,
    }
