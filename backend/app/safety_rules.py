from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .evidence_pack import format_structured_answer


Severity = Literal["info", "warning", "high", "critical"]
SEVERITY_ORDER: dict[str, int] = {"info": 0, "warning": 1, "high": 2, "critical": 3}


class SafetyRuleFinding(BaseModel):
    ruleId: str
    severity: Severity
    title: str
    message: str
    matchedTerms: list[str] = Field(default_factory=list)
    requiredActions: list[str] = Field(default_factory=list)
    evidenceIds: list[str] = Field(default_factory=list)


class SafetyRuleReport(BaseModel):
    enabled: bool = True
    highestSeverity: Severity = "info"
    manualReviewRequired: bool = False
    blocking: bool = False
    findings: list[SafetyRuleFinding] = Field(default_factory=list)
    checklist: list[str] = Field(default_factory=list)


def dump_model(model: BaseModel) -> dict[str, Any]:
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()


def _text(value: object) -> str:
    return str(value or "").strip()


def _combined_text(
    device_model: str,
    fault_text: str,
    evidence_pack: dict[str, Any],
    structured_answer: dict[str, Any],
) -> str:
    parts: list[str] = [device_model, fault_text]
    for item in evidence_pack.get("items", []):
        parts.extend([item.get("title", ""), item.get("snippet", ""), item.get("reason", ""), item.get("riskLevel", "")])
    parts.extend(structured_answer.get("safetyWarnings", []))
    parts.extend(structured_answer.get("uncertainInformation", []))
    parts.extend(structured_answer.get("acceptanceCriteria", []))
    return "\n".join(_text(part).lower() for part in parts if _text(part))


def _matched_terms(text: str, terms: list[str]) -> list[str]:
    return [term for term in terms if term.lower() in text]


def _evidence_ids_with_terms(evidence_pack: dict[str, Any], terms: list[str]) -> list[str]:
    evidence_ids: list[str] = []
    for item in evidence_pack.get("items", []):
        haystack = " ".join(
            _text(item.get(field)).lower() for field in ["title", "snippet", "reason", "riskLevel", "sourceName"]
        )
        if any(term.lower() in haystack for term in terms):
            evidence_ids.append(_text(item.get("evidenceId")))
    return list(dict.fromkeys(item for item in evidence_ids if item))


def _finding(
    rule_id: str,
    severity: Severity,
    title: str,
    message: str,
    matched_terms: list[str],
    required_actions: list[str],
    evidence_ids: list[str],
) -> SafetyRuleFinding:
    return SafetyRuleFinding(
        ruleId=rule_id,
        severity=severity,
        title=title,
        message=message,
        matchedTerms=matched_terms,
        requiredActions=required_actions,
        evidenceIds=evidence_ids,
    )


def evaluate_safety_rules(
    device_model: str,
    fault_text: str,
    evidence_pack: dict[str, Any],
    structured_answer: dict[str, Any],
) -> dict[str, Any]:
    text = _combined_text(device_model, fault_text, evidence_pack, structured_answer)
    findings: list[SafetyRuleFinding] = []

    risk_terms = [
        item.get("riskLevel", "")
        for item in evidence_pack.get("items", [])
        if _text(item.get("riskLevel")).lower() in {"high", "critical"}
    ]
    if risk_terms:
        severity: Severity = "critical" if any(_text(item).lower() == "critical" for item in risk_terms) else "high"
        findings.append(
            _finding(
                "risk.high_or_critical",
                severity,
                "高风险证据复核",
                "证据包包含 high/critical 风险等级，执行前必须人工复核并记录确认人。",
                list(dict.fromkeys(_text(item).lower() for item in risk_terms)),
                ["暂停自动执行建议", "由现场负责人复核风险等级", "记录复核结论后再进入作业"],
                [
                    _text(item.get("evidenceId"))
                    for item in evidence_pack.get("items", [])
                    if _text(item.get("riskLevel")).lower() in {"high", "critical"}
                ],
            )
        )

    isolation_terms = ["断电", "高压", "电气", "点火", "绝缘", "电池", "线路", "上电", "电驱"]
    matched = _matched_terms(text, isolation_terms)
    if matched:
        findings.append(
            _finding(
                "precheck.energy_isolation",
                "high",
                "能量隔离确认",
                "涉及电气、点火或高压相关线索，作业前必须确认停机、断电和安全隔离。",
                matched,
                ["执行停机断电", "确认无残余能量", "佩戴绝缘防护用品"],
                _evidence_ids_with_terms(evidence_pack, isolation_terms),
            )
        )

    thermal_terms = ["高温", "烫伤", "冷却", "排气", "发动机", "热"]
    matched = _matched_terms(text, thermal_terms)
    if matched:
        findings.append(
            _finding(
                "precheck.thermal_cooling",
                "warning",
                "高温冷却确认",
                "涉及发动机、排气或高温部件，接触前需确认冷却状态并防止烫伤。",
                matched,
                ["等待部件冷却", "佩戴防护手套", "避免直接接触排气和高温壳体"],
                _evidence_ids_with_terms(evidence_pack, thermal_terms),
            )
        )

    rotating_terms = ["旋转", "怠速", "传动", "链条", "风扇", "皮带", "齿轮", "车轮", "运转"]
    matched = _matched_terms(text, rotating_terms)
    if matched:
        findings.append(
            _finding(
                "precheck.rotating_parts",
                "high",
                "旋转部件防护",
                "涉及怠速、传动或旋转部件，检查时需保持防护距离并避免衣物、工具卷入。",
                matched,
                ["确认防护罩状态", "保持手和工具远离旋转路径", "需要运转复测时设置观察距离"],
                _evidence_ids_with_terms(evidence_pack, rotating_terms),
            )
        )

    fuel_terms = ["燃油", "喷油", "汽油", "油压", "火花", "点火", "通风", "排气"]
    matched = _matched_terms(text, fuel_terms)
    if matched:
        findings.append(
            _finding(
                "precheck.fuel_ventilation",
                "warning",
                "燃油与通风控制",
                "涉及燃油、点火或排气线索，需控制明火和通风条件。",
                matched,
                ["远离明火", "保持现场通风", "处理燃油前准备吸附和消防用品"],
                _evidence_ids_with_terms(evidence_pack, fuel_terms),
            )
        )

    uncertainty_text = "\n".join(structured_answer.get("uncertainInformation", [])).lower()
    parameter_terms = ["参数", "阈值", "扭矩", "间隙", "温度阈值", "量化"]
    acceptance = structured_answer.get("acceptanceCriteria", [])
    matched = _matched_terms(uncertainty_text, parameter_terms)
    if matched or not acceptance:
        findings.append(
            _finding(
                "evidence.parameter_missing",
                "warning",
                "参数缺失",
                "证据未给出明确参数或验收阈值时，不得补写扭矩、间隙、温度等量化值。",
                matched or ["acceptanceCriteria"],
                ["回查原始手册参数", "由人工确认阈值后再执行", "记录参数来源"],
                [],
            )
        )

    highest = "info"
    for finding in findings:
        if SEVERITY_ORDER[finding.severity] > SEVERITY_ORDER[highest]:
            highest = finding.severity

    checklist = list(
        dict.fromkeys(action for finding in findings for action in finding.requiredActions if _text(action))
    )
    report = SafetyRuleReport(
        highestSeverity=highest,  # type: ignore[arg-type]
        manualReviewRequired=any(SEVERITY_ORDER[finding.severity] >= SEVERITY_ORDER["high"] for finding in findings),
        blocking=any(finding.severity == "critical" for finding in findings),
        findings=findings,
        checklist=checklist,
    )
    return dump_model(report)


def apply_safety_rules(rag_payload: dict[str, Any], safety_report: dict[str, Any]) -> dict[str, Any]:
    payload = {**rag_payload, "safetyRules": safety_report}
    structured = dict(payload.get("structuredAnswer") or {})
    if not structured:
        return payload

    safety_warnings = list(structured.get("safetyWarnings") or [])
    uncertain = list(structured.get("uncertainInformation") or [])
    for finding in safety_report.get("findings", []):
        prefix = f"安全规则 {finding.get('ruleId')}"
        safety_warnings.append(f"{prefix}：{finding.get('message')}")
        if finding.get("ruleId") == "evidence.parameter_missing":
            uncertain.append(f"{prefix}：{finding.get('message')}")

    structured["safetyWarnings"] = list(dict.fromkeys(safety_warnings))
    structured["uncertainInformation"] = list(dict.fromkeys(uncertain))
    if safety_report.get("manualReviewRequired"):
        structured["riskReviewRequired"] = True
    payload["structuredAnswer"] = structured
    payload["riskReviewRequired"] = bool(payload.get("riskReviewRequired") or safety_report.get("manualReviewRequired"))
    payload["answer"] = format_structured_answer(structured)
    return payload
