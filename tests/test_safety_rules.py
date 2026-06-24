from __future__ import annotations

from backend.app.safety_rules import apply_safety_rules, evaluate_safety_rules


def test_safety_rules_flags_high_risk_evidence() -> None:
    report = evaluate_safety_rules(
        "电驱系统",
        "无法上电",
        {
            "items": [
                {
                    "evidenceId": "E1",
                    "title": "高压系统检查",
                    "sourceName": "安全手册",
                    "snippet": "高压系统维修前需断电。",
                    "riskLevel": "critical",
                }
            ]
        },
        {"safetyWarnings": [], "uncertainInformation": [], "acceptanceCriteria": ["人工确认。"]},
    )

    assert report["blocking"] is True
    assert report["manualReviewRequired"] is True
    assert report["highestSeverity"] == "critical"
    assert any(item["ruleId"] == "risk.high_or_critical" for item in report["findings"])
    assert any("断电" in action for action in report["checklist"])


def test_safety_rules_flags_rotating_and_thermal_terms() -> None:
    report = evaluate_safety_rules(
        "发动机",
        "怠速不稳 排气高温",
        {"items": []},
        {"safetyWarnings": [], "uncertainInformation": [], "acceptanceCriteria": ["复测怠速。"]},
    )

    rule_ids = {item["ruleId"] for item in report["findings"]}
    assert "precheck.thermal_cooling" in rule_ids
    assert "precheck.rotating_parts" in rule_ids
    assert report["manualReviewRequired"] is True


def test_safety_rules_flags_missing_parameters() -> None:
    report = evaluate_safety_rules(
        "发动机",
        "启动困难",
        {"items": []},
        {
            "safetyWarnings": [],
            "uncertainInformation": ["未在证据中出现的参数、扭矩、间隙均不做推断。"],
            "acceptanceCriteria": [],
        },
    )

    assert any(item["ruleId"] == "evidence.parameter_missing" for item in report["findings"])
    assert report["highestSeverity"] == "warning"


def test_apply_safety_rules_updates_structured_answer() -> None:
    payload = {
        "answer": "",
        "riskReviewRequired": False,
        "structuredAnswer": {
            "preliminaryJudgment": "已有证据。",
            "inspectionSteps": [],
            "repairSteps": [],
            "safetyWarnings": [],
            "acceptanceCriteria": [],
            "citations": [],
            "uncertainInformation": [],
            "riskReviewRequired": False,
        },
    }
    report = {
        "manualReviewRequired": True,
        "findings": [
            {
                "ruleId": "precheck.energy_isolation",
                "message": "作业前必须确认停机、断电和安全隔离。",
            },
            {
                "ruleId": "evidence.parameter_missing",
                "message": "证据未给出明确参数。",
            },
        ],
    }

    updated = apply_safety_rules(payload, report)

    assert updated["safetyRules"] == report
    assert updated["riskReviewRequired"] is True
    assert any("precheck.energy_isolation" in item for item in updated["structuredAnswer"]["safetyWarnings"])
    assert any("parameter_missing" in item for item in updated["structuredAnswer"]["uncertainInformation"])
    assert "安全规则" in updated["answer"]
