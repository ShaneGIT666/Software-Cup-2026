from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .evidence_pack import format_structured_answer


CorrectiveAction = Literal["answer", "answer_with_caution", "needs_more_evidence"]


class CorrectiveRagDecision(BaseModel):
    enabled: bool = True
    action: CorrectiveAction
    qualityScore: float
    evidenceCount: int
    reasons: list[str] = Field(default_factory=list)
    missingFields: list[str] = Field(default_factory=list)
    suggestedQueries: list[str] = Field(default_factory=list)
    retryRecommended: bool = False
    manualReviewRequired: bool = False


def dump_model(model: BaseModel) -> dict[str, Any]:
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()


def _text(value: object) -> str:
    return str(value or "").strip()


def _score(result: dict[str, Any]) -> float:
    breakdown = result.get("scoreBreakdown") or {}
    try:
        return float(breakdown.get("score") or 0)
    except (TypeError, ValueError):
        return 0.0


def _confidence(result: dict[str, Any]) -> float:
    try:
        return float(result.get("confidence") or 0)
    except (TypeError, ValueError):
        return 0.0


def _source_key(result: dict[str, Any]) -> str:
    return _text(result.get("documentId") or result.get("sourceId") or result.get("id"))


def _query_suggestions(device_model: str, fault_text: str, missing_fields: list[str]) -> list[str]:
    device = device_model or "设备型号"
    fault = fault_text or "故障现象"
    suggestions = [
        f"{device} {fault} 故障码 部件 检查步骤",
        f"{device} {fault} 安全提醒 验收标准",
    ]
    if "deviceModel" in missing_fields:
        suggestions.append(f"补充精确设备型号后检索：{fault} 检修手册")
    if "faultText" in missing_fields:
        suggestions.append(f"{device} 补充故障现象、故障码或图片 OCR 结果后检索")
    return list(dict.fromkeys(item for item in suggestions if item.strip()))


def assess_corrective_rag(
    device_model: str,
    fault_text: str,
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    reasons: list[str] = []
    missing_fields: list[str] = []

    clean_device = _text(device_model)
    clean_fault = _text(fault_text)
    if not clean_device:
        missing_fields.append("deviceModel")
        reasons.append("缺少设备型号，无法稳定应用 metadata filter。")
    if not clean_fault:
        missing_fields.append("faultText")
        reasons.append("缺少故障现象，语义检索证据不足。")

    evidence_count = len(results)
    if evidence_count == 0:
        reasons.append("没有检索到 approved 证据。")
        quality_score = 0.0
    else:
        avg_confidence = sum(_confidence(item) for item in results) / evidence_count
        top_score = max((_score(item) for item in results), default=0.0)
        distinct_sources = len({key for key in (_source_key(item) for item in results) if key})
        has_trace = any(item.get("chunkId") or item.get("documentId") or item.get("sourceId") for item in results)
        quality_score = min(1.0, avg_confidence * 0.55 + min(top_score / 30.0, 1.0) * 0.3 + min(distinct_sources / 3, 1.0) * 0.15)
        if evidence_count < 2:
            reasons.append("命中证据少于 2 条，建议补充检索条件或资料。")
        if distinct_sources < 2 and evidence_count >= 2:
            reasons.append("证据来源过于集中，建议补充手册、案例或图片证据交叉验证。")
        if not has_trace:
            reasons.append("命中结果缺少 chunk/document/source 追溯字段。")
        if avg_confidence < 0.65:
            reasons.append("检索结果平均置信度偏低。")

    manual_review_required = any(
        _text((item.get("scoreBreakdown") or {}).get("riskLevel") or item.get("riskLevel")).lower()
        in {"high", "critical"}
        for item in results
    )
    if manual_review_required:
        reasons.append("命中证据包含 high/critical 风险等级。")

    if evidence_count == 0 or missing_fields:
        action: CorrectiveAction = "needs_more_evidence"
    elif reasons or quality_score < 0.72:
        action = "answer_with_caution"
    else:
        action = "answer"

    decision = CorrectiveRagDecision(
        action=action,
        qualityScore=round(quality_score, 4),
        evidenceCount=evidence_count,
        reasons=list(dict.fromkeys(reasons)),
        missingFields=missing_fields,
        suggestedQueries=_query_suggestions(clean_device, clean_fault, missing_fields),
        retryRecommended=action != "answer",
        manualReviewRequired=manual_review_required,
    )
    return dump_model(decision)


def apply_corrective_rag(rag_payload: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    payload = {**rag_payload, "correctiveRag": decision}
    structured = dict(payload.get("structuredAnswer") or {})
    if not structured:
        return payload

    uncertain = list(structured.get("uncertainInformation") or [])
    if decision.get("action") != "answer":
        uncertain.extend(f"Corrective RAG：{reason}" for reason in decision.get("reasons", []))
        if decision.get("suggestedQueries"):
            uncertain.append("建议改写检索：" + "；".join(decision["suggestedQueries"][:3]))
    if decision.get("manualReviewRequired"):
        structured["riskReviewRequired"] = True
        safety = list(structured.get("safetyWarnings") or [])
        safety.append("Corrective RAG 已触发人工复核要求，处理前需由负责人确认。")
        structured["safetyWarnings"] = list(dict.fromkeys(safety))

    if decision.get("action") == "needs_more_evidence":
        structured["repairSteps"] = []
        structured["riskReviewRequired"] = True

    structured["uncertainInformation"] = list(dict.fromkeys(uncertain))
    payload["structuredAnswer"] = structured
    payload["recommendedActions"] = structured.get("inspectionSteps", []) + structured.get("repairSteps", [])
    payload["riskReviewRequired"] = bool(payload.get("riskReviewRequired") or structured.get("riskReviewRequired"))
    payload["answer"] = format_structured_answer(structured)
    return payload
