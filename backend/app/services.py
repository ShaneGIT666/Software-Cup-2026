from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from . import vector_store
from .data_store import (
    load_cases,
    load_document_chunks,
    load_rag_feedback,
    load_review_events,
    load_seed_data,
    save_cases,
    save_knowledge_graph_cache,
    save_rag_feedback,
    save_review_events,
)
from .review_policy import is_current_approved_chunk
from .retrieval.pipeline import search_knowledge as run_retrieval_pipeline
from .schemas import CaseCreateRequest, CaseReviewRequest, RagFeedbackCreateRequest, RagFeedbackReviewRequest, SearchRequest


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
    return is_current_approved_chunk(chunk)


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
    return run_retrieval_pipeline(request)


def normalize_match_text(value: str | None) -> str:
    return (value or "").strip().lower()


def compatible_text(expected: str, actual: str) -> bool:
    expected_norm = normalize_match_text(expected)
    actual_norm = normalize_match_text(actual)
    if not expected_norm or not actual_norm:
        return True
    return expected_norm == actual_norm or expected_norm in actual_norm or actual_norm in expected_norm


def fault_matches(workflow_fault: str, fault_text: str) -> bool:
    workflow_fault_norm = normalize_match_text(workflow_fault)
    fault_text_norm = normalize_match_text(fault_text)
    return bool(workflow_fault_norm and fault_text_norm and workflow_fault_norm in fault_text_norm)


def select_workflow(request: CaseCreateRequest) -> tuple[str | None, str]:
    data = load_seed_data()
    workflows = data["workflows"]
    requested = (request.workflowId or "").strip()
    device_type = request.deviceType.strip()
    fault_text = request.faultText.strip()
    if requested:
        workflow = next((item for item in workflows if item.get("id") == requested), None)
        if workflow is None:
            raise HTTPException(status_code=400, detail="workflowId does not exist")
        workflow_device = str(workflow.get("deviceType") or "")
        if device_type and workflow_device and not compatible_text(workflow_device, device_type):
            raise HTTPException(status_code=400, detail="workflowId is not compatible with deviceType")
        return requested, "explicit"

    for workflow in workflows:
        workflow_device = str(workflow.get("deviceType") or "")
        workflow_fault = str(workflow.get("faultType") or "")
        if normalize_match_text(workflow_device) == normalize_match_text(device_type) and fault_matches(workflow_fault, fault_text):
            return str(workflow["id"]), "device_and_fault_match"
    for workflow in workflows:
        workflow_device = str(workflow.get("deviceType") or "")
        if normalize_match_text(workflow_device) == normalize_match_text(device_type):
            return str(workflow["id"]), "device_match"
    for workflow in workflows:
        workflow_fault = str(workflow.get("faultType") or "")
        if fault_matches(workflow_fault, fault_text):
            return str(workflow["id"]), "fault_match"
    return None, "no_reliable_match"


def create_repair_case(request: CaseCreateRequest) -> dict[str, Any]:
    cases = load_cases()
    case_id = f"case-{uuid4().hex[:8]}"
    device_type = request.deviceType.strip() or request.deviceModel.strip() or "unknown"
    workflow_id, workflow_reason = select_workflow(request)
    repair_case = {
        "id": case_id,
        "deviceType": device_type,
        "deviceModel": request.deviceModel,
        "component": request.component,
        "faultCode": request.faultCode,
        "faultTitle": request.faultText[:20] or "新提交维修案例",
        "faultText": request.faultText,
        "symptoms": [request.faultText],
        "possibleCauses": [request.cause],
        "solution": request.solution,
        "result": request.result,
        "experienceSummary": request.experienceSummary,
        "lessonsLearned": request.lessonsLearned,
        "maintenanceLevel": request.maintenanceLevel,
        "riskLevel": request.riskLevel,
        "status": "pending_review",
        "tags": request.tags,
        "workflowId": workflow_id,
        "workflowSelectionReason": workflow_reason,
        "createdAt": utc_now(),
        "reviewedAt": "",
    }
    cases.append(repair_case)
    save_cases(cases)
    return repair_case


def list_repair_cases(status: str | None = None) -> dict[str, Any]:
    cases = load_cases()
    items = [item for item in cases if status is None or item.get("status") == status]
    return {"items": items, "total": len(items)}


def review_repair_case(case_id: str, request: CaseReviewRequest) -> dict[str, Any]:
    cases = load_cases()
    status = "approved" if request.action == "approve" else "rejected"
    reason = request.reviewNote.strip()
    if request.action == "reject" and not reason:
        raise HTTPException(status_code=400, detail="拒绝审核必须填写原因")
    for repair_case in cases:
        if repair_case["id"] == case_id:
            before_snapshot = dict(repair_case)
            previous_status = repair_case.get("status", "pending_review")
            reviewed_at = utc_now()
            reviewer = request.reviewer.strip() or "operator"
            repair_case["status"] = status
            repair_case["reviewedAt"] = reviewed_at
            repair_case["reviewer"] = reviewer
            repair_case["reviewAction"] = request.action
            repair_case["reviewNote"] = reason
            if request.normalizedTags:
                repair_case["tags"] = request.normalizedTags
            save_cases(cases)
            events = load_review_events()
            events.append(
                {
                    "id": f"review-{uuid4().hex[:8]}",
                    "objectType": "case",
                    "objectId": case_id,
                    "action": request.action,
                    "beforeStatus": previous_status,
                    "afterStatus": status,
                    "reason": reason,
                    "reviewer": reviewer,
                    "reviewTime": reviewed_at,
                    "before": before_snapshot,
                    "after": dict(repair_case),
                }
            )
            save_review_events(events)
            return repair_case
    raise HTTPException(status_code=404, detail="案例不存在")


def create_rag_feedback(request: RagFeedbackCreateRequest) -> dict[str, Any]:
    corrected = request.correctedAnswer.strip()
    labels = unique_items([label.strip() for label in request.labels])
    reason = request.reason.strip()
    if not corrected and not labels and not reason:
        raise HTTPException(status_code=400, detail="提交标注时，修正答案、标签或修正原因至少填写一项")

    feedback_items = load_rag_feedback()
    now = utc_now()
    item = {
        "id": f"ragfb-{uuid4().hex[:8]}",
        "deviceModel": request.deviceModel,
        "faultText": request.faultText,
        "maintenanceLevel": request.maintenanceLevel,
        "originalAnswer": request.originalAnswer,
        "correctedAnswer": corrected,
        "labels": labels,
        "reason": reason,
        "status": "pending_review",
        "reviewer": request.reviewer.strip() or "operator",
        "reviewNote": "",
        "createdAt": now,
        "updatedAt": now,
        "approvedAt": "",
    }
    feedback_items.append(item)
    save_rag_feedback(feedback_items)
    return item


def list_rag_feedback(status: str | None = None) -> dict[str, Any]:
    items = load_rag_feedback()
    if status and status != "all":
        items = [item for item in items if item.get("status") == status]
    items = sorted(items, key=lambda item: item.get("updatedAt") or item.get("createdAt", ""), reverse=True)
    return {"items": items, "total": len(items)}


def review_rag_feedback(feedback_id: str, request: RagFeedbackReviewRequest) -> dict[str, Any]:
    items = load_rag_feedback()
    status = "approved" if request.action == "approve" else "rejected"
    note = request.reviewNote.strip()
    if request.action == "reject" and not note:
        raise HTTPException(status_code=400, detail="拒绝审核必须填写原因")

    for item in items:
        if item.get("id") != feedback_id:
            continue
        before = dict(item)
        previous_status = item.get("status", "pending_review")
        now = utc_now()
        reviewer = request.reviewer.strip() or "operator"
        item["status"] = status
        item["reviewer"] = reviewer
        item["reviewAction"] = request.action
        item["reviewNote"] = note
        item["updatedAt"] = now
        item["approvedAt"] = now if status == "approved" else ""
        save_rag_feedback(items)

        events = load_review_events()
        events.append(
            {
                "id": f"review-{uuid4().hex[:8]}",
                "objectType": "rag_feedback",
                "objectId": feedback_id,
                "action": request.action,
                "beforeStatus": previous_status,
                "afterStatus": status,
                "reason": note,
                "reviewer": reviewer,
                "reviewTime": now,
                "before": before,
                "after": dict(item),
            }
        )
        save_review_events(events)
        save_knowledge_graph_cache({})
        return item

    raise HTTPException(status_code=404, detail="RAG 回答修正记录不存在")
