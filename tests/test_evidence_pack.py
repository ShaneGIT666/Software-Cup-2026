from __future__ import annotations

from backend.app.evidence_pack import build_evidence_pack, build_structured_rag_output, format_structured_answer


def test_evidence_pack_preserves_trace_fields() -> None:
    pack = build_evidence_pack(
        [
            {
                "id": "chunk-001",
                "title": "火花塞检查",
                "sourceType": "document",
                "sourceName": "发动机手册",
                "documentId": "doc-001",
                "chunkId": "chunk-001",
                "page": 12,
                "section": "启动系统",
                "snippet": "检查火花塞积碳。",
                "confidence": 0.91,
                "reviewStatus": "approved",
                "scoreBreakdown": {"score": 18, "version": 2},
            }
        ]
    )

    assert pack["evidenceCount"] == 1
    assert pack["approvedOnly"] is True
    assert pack["items"][0]["sourceDocId"] == "doc-001"
    assert pack["items"][0]["version"] == 2
    assert pack["citationTrace"][0]["chunkId"] == "chunk-001"
    assert pack["citationTrace"][0]["page"] == 12
    assert pack["citationTrace"][0]["section"] == "启动系统"


def test_structured_output_marks_no_evidence_as_uncertain() -> None:
    pack = build_evidence_pack([])
    structured = build_structured_rag_output("发动机", "启动困难", pack)

    assert structured["riskReviewRequired"] is True
    assert structured["citations"] == []
    assert structured["repairSteps"] == []
    assert "不能给出确定检修判断" in structured["preliminaryJudgment"]
    assert "未检索到" in structured["uncertainInformation"][0]
    assert "【不确定信息】" in format_structured_answer(structured)


def test_high_risk_evidence_requires_manual_review() -> None:
    pack = build_evidence_pack(
        [
            {
                "id": "manual-001",
                "title": "高压系统检查",
                "sourceType": "manual",
                "sourceName": "安全手册",
                "sourceId": "manual-001",
                "snippet": "高压系统维修前需复核。",
                "confidence": 0.9,
                "scoreBreakdown": {"score": 20, "riskLevel": "critical"},
            }
        ]
    )
    structured = build_structured_rag_output("电驱系统", "无法上电", pack)

    assert pack["riskReviewRequired"] is True
    assert structured["riskReviewRequired"] is True
    assert any("人工复核" in item for item in structured["safetyWarnings"])
