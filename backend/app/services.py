from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from .data_store import load_cases, load_document_chunks, load_seed_data, save_cases
from .schemas import CaseCreateRequest, CaseReviewRequest, SearchRequest


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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


def find_workflow(workflow_id: str) -> dict[str, Any]:
    data = load_seed_data()
    for workflow in data["workflows"]:
        if workflow["id"] == workflow_id:
            return workflow
    raise HTTPException(status_code=404, detail="作业流程不存在")


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

    results = sorted(
        manual_results + case_results + document_results,
        key=lambda item: (item["scoreBreakdown"]["score"], item["confidence"]),
        reverse=True,
    )[: request.topK]

    return {
        "queryId": f"q-{uuid4().hex[:8]}",
        "summary": build_search_summary(results, query_tokens),
        "results": results,
    }


def create_repair_case(request: CaseCreateRequest) -> dict[str, str]:
    cases = load_cases()
    case_id = f"case-{uuid4().hex[:8]}"
    repair_case = {
        "id": case_id,
        "deviceType": "发动机",
        "deviceModel": request.deviceModel,
        "faultTitle": request.faultText[:20] or "新提交维修案例",
        "faultText": request.faultText,
        "symptoms": [request.faultText],
        "possibleCauses": [request.cause],
        "solution": request.solution,
        "result": request.result,
        "status": "pending_review",
        "tags": request.tags,
        "workflowId": "wf-001",
        "createdAt": utc_now(),
        "reviewedAt": "",
    }
    cases.append(repair_case)
    save_cases(cases)
    return {"id": case_id, "status": "pending_review"}


def list_repair_cases(status: str | None = None) -> dict[str, Any]:
    cases = load_cases()
    items = [item for item in cases if status is None or item.get("status") == status]
    return {"items": items, "total": len(items)}


def review_repair_case(case_id: str, request: CaseReviewRequest) -> dict[str, str]:
    cases = load_cases()
    status = "approved" if request.action == "approve" else "rejected"
    for repair_case in cases:
        if repair_case["id"] == case_id:
            repair_case["status"] = status
            repair_case["reviewedAt"] = utc_now()
            if request.normalizedTags:
                repair_case["tags"] = request.normalizedTags
            save_cases(cases)
            return {"id": case_id, "status": status}
    raise HTTPException(status_code=404, detail="案例不存在")
