from __future__ import annotations

from typing import Any

from ..data_store import load_document_chunks, load_seed_data
from .models import QueryContext, RetrievalHit


def field_text(item: dict[str, Any], field: str) -> str:
    value = item.get(field, "")
    if isinstance(value, list):
        return " ".join(str(part) for part in value)
    return str(value)


def unique_items(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def non_overlapping_matches(query_tokens: list[str], haystack: str) -> list[str]:
    """Prefer specific terms over their shorter overlapping fallback terms."""

    matched: list[str] = []
    for token in sorted(set(query_tokens), key=lambda item: (-len(item), item)):
        if token not in haystack:
            continue
        if any(token in selected for selected in matched):
            continue
        matched.append(token)
    return matched


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
        terms = non_overlapping_matches(query_tokens, haystack)
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

    item_text = " ".join(field_text(item, field) for field in field_weights).lower()
    phrase_bonus = 4 if any(len(token) >= 3 and token in item_text for token in query_tokens) else 0
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


def matched_fields(scoring: dict[str, Any]) -> list[str]:
    return [item["field"] for item in scoring.get("fieldMatches", [])]


def chunk_is_approved(chunk: dict[str, Any]) -> bool:
    return chunk.get("review_status", "approved") == "approved"


def retrieve_keyword_hits(context: QueryContext) -> list[RetrievalHit]:
    data = load_seed_data()
    hits: list[RetrievalHit] = []

    for manual in data["manuals"]:
        field_weights = {"title": 5, "deviceModel": 4, "tags": 4, "content": 2}
        scoring = score_item(context.query_tokens, manual, field_weights, source_weight=3)
        if scoring["score"]:
            hits.append(
                RetrievalHit(
                    id=manual["id"],
                    title=manual["title"],
                    content=manual["content"],
                    source_id=manual["id"],
                    source_name=manual["sourceName"],
                    source_type="manual",
                    confidence=confidence_from_score(scoring["score"], 0.95),
                    snippet=manual["content"][:120],
                    workflow_id=manual.get("workflowId"),
                    chapter=manual.get("chapter"),
                    page=manual.get("page"),
                    matched_terms=scoring["matchedTerms"],
                    reason=reason_text("命中手册字段", scoring["matchedTerms"], manual),
                    score_breakdown=score_breakdown(scoring, "manual"),
                    device_type=manual.get("deviceType"),
                    device_model=manual.get("deviceModel"),
                    fault_type=manual.get("chapter"),
                    keyword_score=float(scoring["score"]),
                    matched_fields=matched_fields(scoring),
                )
            )

    for repair_case in data["cases"]:
        if repair_case.get("status") != "approved":
            continue
        field_weights = {"faultTitle": 5, "faultText": 4, "tags": 4, "possibleCauses": 3, "solution": 2}
        scoring = score_item(context.query_tokens, repair_case, field_weights, source_weight=2)
        if scoring["score"]:
            hits.append(
                RetrievalHit(
                    id=repair_case["id"],
                    title=repair_case["faultTitle"],
                    content=repair_case.get("faultText", "") + "\n" + repair_case.get("solution", ""),
                    source_id=repair_case["id"],
                    source_name="历史维修案例库",
                    source_type="case",
                    confidence=confidence_from_score(scoring["score"], 0.94),
                    snippet=repair_case["solution"],
                    workflow_id=repair_case.get("workflowId"),
                    matched_terms=scoring["matchedTerms"],
                    reason=reason_text("命中历史案例", scoring["matchedTerms"], repair_case),
                    score_breakdown=score_breakdown(scoring, "case"),
                    device_type=repair_case.get("deviceType"),
                    device_model=repair_case.get("deviceModel"),
                    fault_type=repair_case.get("faultTitle"),
                    review_status=repair_case.get("status", "approved"),
                    keyword_score=float(scoring["score"]),
                    matched_fields=matched_fields(scoring),
                )
            )

    for chunk in load_document_chunks():
        if not chunk_is_approved(chunk):
            continue
        field_weights = {"title": 4, "sourceName": 3, "keywords": 4, "content": 2}
        scoring = score_item(context.query_tokens, chunk, field_weights, source_weight=2)
        if scoring["score"]:
            hits.append(
                RetrievalHit(
                    id=chunk["id"],
                    title=chunk["title"],
                    content=chunk.get("content", ""),
                    source_id=chunk["id"],
                    source_name=chunk["sourceName"],
                    source_type="document",
                    confidence=confidence_from_score(scoring["score"], 0.93),
                    snippet=chunk["snippet"],
                    page=chunk.get("page"),
                    document_id=chunk.get("documentId"),
                    chunk_id=chunk["id"],
                    matched_terms=scoring["matchedTerms"],
                    reason=reason_text("命中入库资料片段", scoring["matchedTerms"], chunk),
                    score_breakdown=score_breakdown(scoring, "document"),
                    device_type=chunk.get("device_type") or chunk.get("deviceType"),
                    device_model=chunk.get("device_model") or chunk.get("deviceModel"),
                    component=chunk.get("component"),
                    fault_type=chunk.get("fault_symptom") or chunk.get("faultType"),
                    review_status=chunk.get("review_status", "approved"),
                    keyword_score=float(scoring["score"]),
                    matched_fields=matched_fields(scoring),
                )
            )

    hits.sort(key=lambda item: (item.keyword_score or 0, item.confidence), reverse=True)
    for index, hit in enumerate(hits, start=1):
        hit.keyword_rank = index
    return hits
