from __future__ import annotations

from backend.app.corrective_rag import apply_corrective_rag, assess_corrective_rag
from backend.app.rag import finalize_rag_answer_semantics


def test_corrective_rag_requests_more_evidence_when_empty() -> None:
    decision = assess_corrective_rag("", "启动困难", [])

    assert decision["action"] == "needs_more_evidence"
    assert decision["qualityScore"] == 0
    assert "deviceModel" in decision["missingFields"]
    assert decision["retryRecommended"] is True
    assert decision["suggestedQueries"]


def test_corrective_rag_answers_with_caution_for_single_source() -> None:
    decision = assess_corrective_rag(
        "发动机-示例型号 A",
        "启动困难",
        [
            {
                "id": "doc-001",
                "sourceId": "doc-001",
                "title": "启动困难检查",
                "sourceType": "manual",
                "confidence": 0.72,
                "scoreBreakdown": {"score": 13},
            }
        ],
    )

    assert decision["action"] == "answer_with_caution"
    assert decision["evidenceCount"] == 1
    assert any("少于 2 条" in reason for reason in decision["reasons"])
    assert decision["retryRecommended"] is True


def test_corrective_rag_accepts_strong_evidence() -> None:
    decision = assess_corrective_rag(
        "发动机-示例型号 A",
        "启动困难",
        [
            {
                "id": "doc-001",
                "sourceId": "manual-001",
                "documentId": "manual-001",
                "chunkId": "chunk-001",
                "sourceType": "manual",
                "confidence": 0.93,
                "scoreBreakdown": {"score": 28},
            },
            {
                "id": "case-001",
                "sourceId": "case-001",
                "sourceType": "case",
                "confidence": 0.88,
                "scoreBreakdown": {"score": 24},
            },
            {
                "id": "doc-002",
                "sourceId": "doc-002",
                "documentId": "doc-002",
                "chunkId": "chunk-002",
                "sourceType": "document",
                "confidence": 0.86,
                "scoreBreakdown": {"score": 22},
            },
        ],
    )

    assert decision["action"] == "answer"
    assert decision["qualityScore"] >= 0.72
    assert decision["retryRecommended"] is False
    assert decision["reasons"] == []


def test_apply_corrective_rag_merges_uncertainty_into_structured_answer() -> None:
    payload = {
        "answer": "",
        "riskReviewRequired": False,
        "structuredAnswer": {
            "preliminaryJudgment": "已有证据。",
            "inspectionSteps": [],
            "repairSteps": ["证据不足时不应保留的具体维修步骤"],
            "safetyWarnings": [],
            "acceptanceCriteria": [],
            "citations": [],
            "uncertainInformation": ["原有不确定信息。"],
            "riskReviewRequired": False,
        },
    }
    decision = {
        "action": "needs_more_evidence",
        "reasons": ["没有检索到 approved 证据。"],
        "suggestedQueries": ["发动机 启动困难 故障码"],
        "manualReviewRequired": True,
    }

    updated = apply_corrective_rag(payload, decision)

    assert updated["correctiveRag"] == decision
    assert updated["riskReviewRequired"] is True
    assert updated["structuredAnswer"]["repairSteps"] == []
    assert updated["recommendedActions"] == []
    assert any("Corrective RAG" in item for item in updated["structuredAnswer"]["uncertainInformation"])
    assert "Corrective RAG" in updated["answer"]


def test_finalize_rag_answer_mode_follows_corrective_outcome() -> None:
    base_payload = {
        "rawAnswer": "candidate answer",
        "answer": "candidate answer",
        "llmAnswerUsed": True,
        "evidencePack": {"evidenceCount": 1, "approvedOnly": True},
        "structuredAnswer": {"inspectionSteps": ["inspect"], "repairSteps": ["repair"]},
    }

    grounded = finalize_rag_answer_semantics({**base_payload, "correctiveRag": {"action": "answer"}})
    caution = finalize_rag_answer_semantics({**base_payload, "correctiveRag": {"action": "answer_with_caution"}})
    insufficient = finalize_rag_answer_semantics({**base_payload, "correctiveRag": {"action": "needs_more_evidence"}})

    assert grounded["answerMode"] == "grounded"
    assert caution["answerMode"] == "grounded_with_caution"
    assert insufficient["answerMode"] == "insufficient_evidence"
    assert insufficient["structuredAnswer"]["repairSteps"] == []
    assert insufficient["riskReviewRequired"] is True
    assert insufficient["llmAnswerUsed"] is False
    assert insufficient["llmCandidateAccepted"] is False
    assert insufficient["finalAnswerSource"] == "template"
