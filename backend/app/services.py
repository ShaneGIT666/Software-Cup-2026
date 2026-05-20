from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from .data_store import load_cases, load_seed_data, save_cases
from .schemas import CaseCreateRequest, CaseReviewRequest, SearchRequest


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def tokens(*parts: str) -> list[str]:
    text = " ".join(part for part in parts if part).lower()
    separators = ["，", "。", "、", ",", ".", " ", "-", "_", "\n"]
    for separator in separators:
        text = text.replace(separator, " ")
    return [item for item in text.split(" ") if item]


def score_item(query_tokens: list[str], item: dict[str, Any], fields: list[str]) -> int:
    haystack = " ".join(str(item.get(field, "")) for field in fields).lower()
    if not query_tokens:
        return 0
    return sum(1 for token in query_tokens if token in haystack)


def find_workflow(workflow_id: str) -> dict[str, Any]:
    data = load_seed_data()
    for workflow in data["workflows"]:
        if workflow["id"] == workflow_id:
            return workflow
    raise HTTPException(status_code=404, detail="作业流程不存在")


def search_knowledge(request: SearchRequest) -> dict[str, Any]:
    data = load_seed_data()
    query_tokens = tokens(request.deviceModel, request.faultText)

    manual_results = []
    for manual in data["manuals"]:
        score = score_item(query_tokens, manual, ["title", "deviceModel", "content", "tags"])
        if score:
            manual_results.append(
                {
                    "id": manual["id"],
                    "title": manual["title"],
                    "sourceType": "manual",
                    "sourceName": manual["sourceName"],
                    "confidence": min(0.95, 0.58 + score * 0.09),
                    "snippet": manual["content"][:120],
                    "workflowId": manual.get("workflowId"),
                    "chapter": manual.get("chapter"),
                    "page": manual.get("page"),
                }
            )

    case_results = []
    for repair_case in data["cases"]:
        if repair_case.get("status") != "approved":
            continue
        score = score_item(
            query_tokens,
            repair_case,
            ["faultTitle", "faultText", "solution", "possibleCauses", "tags"],
        )
        if score:
            case_results.append(
                {
                    "id": repair_case["id"],
                    "title": repair_case["faultTitle"],
                    "sourceType": "case",
                    "sourceName": "历史维修案例库",
                    "confidence": min(0.94, 0.6 + score * 0.1),
                    "snippet": repair_case["solution"],
                    "workflowId": repair_case.get("workflowId"),
                }
            )

    results = sorted(
        manual_results + case_results,
        key=lambda item: item["confidence"],
        reverse=True,
    )[: request.topK]

    return {
        "queryId": f"q-{uuid4().hex[:8]}",
        "summary": "可能与燃油供给、点火系统、进气密封或机械磨损有关。",
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
