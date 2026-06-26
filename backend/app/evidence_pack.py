from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


HIGH_RISK_LEVELS = {"high", "critical"}


class EvidenceTrace(BaseModel):
    evidenceId: str
    chunkId: str | None = None
    sourceDocId: str | None = None
    page: int | None = None
    section: str | None = None


class EvidenceItem(BaseModel):
    evidenceId: str
    resultId: str
    title: str
    sourceType: str
    sourceName: str
    sourceDocId: str | None = None
    documentId: str | None = None
    chunkId: str | None = None
    version: str | int | None = None
    page: int | None = None
    section: str | None = None
    chapter: str | None = None
    snippet: str
    reason: str = ""
    confidence: float = 0
    reviewStatus: str = "approved"
    riskLevel: str = "unknown"
    score: float | int | None = None
    retrievalSource: str | None = None
    retrievalMode: str | None = None
    sourceRetrievers: list[str] = Field(default_factory=list)
    finalRank: int | None = None
    fusionScore: float | None = None
    vectorDistance: float | None = None
    embeddingProvider: str | None = None
    scoreBreakdown: dict[str, Any] = Field(default_factory=dict)
    trace: EvidenceTrace


class EvidencePack(BaseModel):
    evidenceCount: int
    items: list[EvidenceItem] = Field(default_factory=list)
    citationTrace: list[EvidenceTrace] = Field(default_factory=list)
    sourceDocIds: list[str] = Field(default_factory=list)
    approvedOnly: bool = True
    riskReviewRequired: bool = False
    uncertaintyReasons: list[str] = Field(default_factory=list)


class StructuredRagOutput(BaseModel):
    preliminaryJudgment: str
    inspectionSteps: list[str] = Field(default_factory=list)
    repairSteps: list[str] = Field(default_factory=list)
    safetyWarnings: list[str] = Field(default_factory=list)
    acceptanceCriteria: list[str] = Field(default_factory=list)
    citations: list[EvidenceTrace] = Field(default_factory=list)
    uncertainInformation: list[str] = Field(default_factory=list)
    riskReviewRequired: bool = False


def dump_model(model: BaseModel) -> dict[str, Any]:
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()


def _source_doc_id(result: dict[str, Any]) -> str | None:
    return result.get("documentId") or result.get("sourceDocId") or result.get("sourceId") or result.get("id")


def _risk_level(result: dict[str, Any]) -> str:
    score_breakdown = result.get("scoreBreakdown") or {}
    risk_level = result.get("riskLevel") or score_breakdown.get("riskLevel") or score_breakdown.get("risk_level")
    return str(risk_level or "unknown").strip().lower()


def build_evidence_pack(results: list[dict[str, Any]]) -> dict[str, Any]:
    items: list[EvidenceItem] = []
    for index, result in enumerate(results, start=1):
        score_breakdown = result.get("scoreBreakdown") or {}
        source_doc_id = _source_doc_id(result)
        trace = EvidenceTrace(
            evidenceId=f"E{index}",
            chunkId=result.get("chunkId"),
            sourceDocId=source_doc_id,
            page=result.get("page"),
            section=result.get("section"),
        )
        items.append(
            EvidenceItem(
                evidenceId=trace.evidenceId,
                resultId=str(result.get("id", "")),
                title=str(result.get("title", "")),
                sourceType=str(result.get("sourceType", "")),
                sourceName=str(result.get("sourceName", "")),
                sourceDocId=source_doc_id,
                documentId=result.get("documentId"),
                chunkId=result.get("chunkId"),
                version=score_breakdown.get("version"),
                page=result.get("page"),
                section=result.get("section"),
                chapter=result.get("chapter"),
                snippet=str(result.get("snippet", "")),
                reason=str(result.get("reason", "")),
                confidence=float(result.get("confidence") or 0),
                reviewStatus=str(result.get("reviewStatus") or "approved"),
                riskLevel=_risk_level(result),
                score=score_breakdown.get("score"),
                retrievalSource=result.get("retrievalSource") or score_breakdown.get("retrievalSource"),
                retrievalMode=score_breakdown.get("retrievalMode"),
                sourceRetrievers=list(result.get("sourceRetrievers") or score_breakdown.get("sourceRetrievers") or []),
                finalRank=score_breakdown.get("finalRank"),
                fusionScore=score_breakdown.get("fusionScore"),
                vectorDistance=score_breakdown.get("vectorDistance"),
                embeddingProvider=score_breakdown.get("embeddingProvider"),
                scoreBreakdown=score_breakdown,
                trace=trace,
            )
        )

    source_doc_ids = list(dict.fromkeys(str(item.sourceDocId) for item in items if item.sourceDocId))
    approved_only = all(item.reviewStatus == "approved" for item in items)
    risk_review_required = any(item.riskLevel in HIGH_RISK_LEVELS for item in items)
    uncertainty_reasons: list[str] = []
    if not items:
        uncertainty_reasons.append("未检索到可用于回答的 approved 证据。")
    if any(not item.chunkId and item.sourceType == "document" for item in items):
        uncertainty_reasons.append("部分文档证据缺少 chunk_id，引用粒度不足。")
    if any(item.page is None and item.sourceType in {"manual", "document"} for item in items):
        uncertainty_reasons.append("部分手册或文档证据缺少页码，需回查原始资料。")
    if not approved_only:
        uncertainty_reasons.append("证据包存在非 approved 状态片段，正式建议前必须剔除或复核。")
    if risk_review_required:
        uncertainty_reasons.append("证据包包含 high/critical 风险等级，必须人工复核。")

    pack = EvidencePack(
        evidenceCount=len(items),
        items=items,
        citationTrace=[item.trace for item in items],
        sourceDocIds=source_doc_ids,
        approvedOnly=approved_only,
        riskReviewRequired=risk_review_required,
        uncertaintyReasons=uncertainty_reasons,
    )
    return dump_model(pack)


def _evidence_label(item: dict[str, Any]) -> str:
    title = item.get("title") or item.get("sourceName") or item.get("resultId") or "证据"
    return f"{item['evidenceId']}（{title}）"


def build_structured_rag_output(
    device_model: str,
    fault_text: str,
    evidence_pack: dict[str, Any],
) -> dict[str, Any]:
    items = evidence_pack.get("items", [])
    traces = evidence_pack.get("citationTrace", [])
    risk_review_required = bool(evidence_pack.get("riskReviewRequired"))

    if not items:
        output = StructuredRagOutput(
            preliminaryJudgment="当前没有 approved 证据支撑，不能给出确定检修判断。",
            inspectionSteps=["补充设备型号、故障码、故障图片或上传并审核相关手册后重新检索。"],
            repairSteps=["暂无证据支持的维修步骤，不建议直接执行拆装或参数调整。"],
            safetyWarnings=["证据不足时不得执行高风险操作，需由现场负责人或资深检修人员复核。"],
            acceptanceCriteria=["暂无证据支持的验收标准。"],
            citations=[],
            uncertainInformation=evidence_pack.get("uncertaintyReasons", []),
            riskReviewRequired=True,
        )
        return dump_model(output)

    top_labels = "、".join(_evidence_label(item) for item in items[:3])
    preliminary = (
        f"已检索到 {len(items)} 条 approved 证据，当前判断仅限于 {device_model or '未指明设备'} "
        f"的“{fault_text or '未指明故障'}”场景；优先参考 {top_labels}。"
    )
    inspection_steps = [
        f"核对 {_evidence_label(item)} 的适用设备、故障现象与现场记录是否一致。"
        for item in items[:3]
    ]
    repair_steps = [
        f"若现场现象与 {_evidence_label(item)} 一致，仅按该来源资料支持的内容执行处理并记录结果。"
        for item in items[:2]
    ]
    safety_warnings = []
    if risk_review_required:
        safety_warnings.append("证据包包含 high/critical 风险等级，执行前必须人工复核。")
    else:
        safety_warnings.append("证据包未标记 high/critical 风险；涉及断电、拆装、高温或旋转部件时仍需按现场安全规程复核。")
    acceptance_criteria = [
        f"处理后回查 {_evidence_label(items[0])} 对应来源，确认故障现象消失或进入来源要求的验收状态。",
        "证据未给出量化阈值时，本系统不补写参数，需由人工依据原始手册确认。",
    ]
    uncertain = list(evidence_pack.get("uncertaintyReasons", []))
    uncertain.append("未在证据中出现的参数、扭矩、间隙、温度阈值均不做推断。")

    output = StructuredRagOutput(
        preliminaryJudgment=preliminary,
        inspectionSteps=inspection_steps,
        repairSteps=repair_steps,
        safetyWarnings=safety_warnings,
        acceptanceCriteria=acceptance_criteria,
        citations=traces,
        uncertainInformation=list(dict.fromkeys(uncertain)),
        riskReviewRequired=risk_review_required,
    )
    return dump_model(output)


def _numbered(items: list[str]) -> str:
    if not items:
        return "暂无。"
    return "\n".join(f"{index}. {item}" for index, item in enumerate(items, start=1))


def _citation_line(trace: dict[str, Any]) -> str:
    parts = [trace.get("evidenceId", "E?")]
    if trace.get("sourceDocId"):
        parts.append(f"source_doc_id={trace['sourceDocId']}")
    if trace.get("chunkId"):
        parts.append(f"chunk_id={trace['chunkId']}")
    if trace.get("page") is not None:
        parts.append(f"page={trace['page']}")
    if trace.get("section"):
        parts.append(f"section={trace['section']}")
    return "；".join(str(part) for part in parts)


def format_structured_answer(structured_output: dict[str, Any]) -> str:
    citations = structured_output.get("citations", [])
    citation_text = "\n".join(_citation_line(trace) for trace in citations) if citations else "暂无可追溯证据。"
    uncertain = structured_output.get("uncertainInformation", [])
    return (
        f"【初步判断】\n{structured_output.get('preliminaryJudgment', '')}\n\n"
        f"【建议检查步骤】\n{_numbered(structured_output.get('inspectionSteps', []))}\n\n"
        f"【建议维修步骤】\n{_numbered(structured_output.get('repairSteps', []))}\n\n"
        f"【安全提醒】\n{_numbered(structured_output.get('safetyWarnings', []))}\n\n"
        f"【验收标准】\n{_numbered(structured_output.get('acceptanceCriteria', []))}\n\n"
        f"【引用证据】\n{citation_text}\n\n"
        f"【不确定信息】\n{_numbered(uncertain)}"
    )
