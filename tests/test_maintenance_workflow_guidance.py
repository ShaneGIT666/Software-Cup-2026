from __future__ import annotations

from backend.app.evidence_pack import build_evidence_pack, build_structured_rag_output, format_structured_answer
from backend.app.maintenance_guidance import build_compliance_checks, maintenance_level_description


def test_maintenance_level_adds_preparation_risk_and_compliance_sections() -> None:
    pack = build_evidence_pack(
        [
            {
                "id": "case-001",
                "source_id": "case-001",
                "sourceId": "case-001",
                "sourceName": "应急检修案例",
                "sourceType": "case",
                "chunk_id": "chunk-001",
                "snippet": "停机后检查燃油管路，确认无泄漏后恢复启动。",
                "content": "停机后检查燃油管路，确认无泄漏后恢复启动。",
                "riskLevel": "critical",
                "score": 0.95,
                "page": 2,
                "section": "应急检修",
                "version": 1,
            }
        ]
    )

    structured = build_structured_rag_output(
        "发动机-示例型号 A",
        "启动困难并伴随燃油气味",
        pack,
        maintenance_level="emergency",
        risk_level="critical",
    )
    answer = format_structured_answer(structured)

    assert structured["maintenanceLevel"] == "emergency"
    assert structured["maintenanceLevelDescription"]
    assert structured["preWorkPreparation"]
    assert structured["riskControls"]
    assert structured["complianceChecks"]
    assert "人工复核" in " ".join(structured["safetyWarnings"])
    assert "【检修等级说明】" in answer
    assert "【合规校验提醒】" in answer


def test_build_compliance_checks_marks_high_risk_for_manual_review() -> None:
    checks = build_compliance_checks("major_repair", "high", {"items": [{"id": "chunk-1"}]})

    assert any("人工复核" in item for item in checks)
    assert "重大检修" in maintenance_level_description("major_repair")
