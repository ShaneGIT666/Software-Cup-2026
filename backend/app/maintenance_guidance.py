from __future__ import annotations

from typing import Any


MAINTENANCE_LEVELS = {"daily_check", "normal_repair", "major_repair", "emergency"}


LEVEL_LABELS = {
    "daily_check": "日常检查",
    "normal_repair": "一般检修",
    "major_repair": "重大检修",
    "emergency": "紧急处理",
}


def normalize_maintenance_level(value: str | None) -> str:
    level = (value or "normal_repair").strip().lower()
    return level if level in MAINTENANCE_LEVELS else "normal_repair"


def normalize_risk_level(value: str | None) -> str:
    risk = (value or "medium").strip().lower()
    return risk if risk in {"low", "medium", "high", "critical"} else "medium"


def maintenance_level_description(level: str) -> str:
    level = normalize_maintenance_level(level)
    if level == "daily_check":
        return "日常检查以观察、记录、外观和运行状态核对为主，不建议拆卸或调整关键参数。"
    if level == "major_repair":
        return "重大检修需要作业票、停机确认、备件确认和多人复核，系统只提供辅助建议。"
    if level == "emergency":
        return "紧急处理优先安全隔离、停机保护和现场负责人确认，不以恢复生产作为唯一目标。"
    return "一般检修允许常规检查和更换，但必须先完成断电、隔离、工具确认和结果记录。"


def build_pre_work_preparation(level: str, risk_level: str) -> list[str]:
    level = normalize_maintenance_level(level)
    risk_level = normalize_risk_level(risk_level)
    items = [
        "确认设备型号、故障现象、现场照片和检修等级记录完整。",
        "执行停机、断电、挂牌和必要的能量隔离确认。",
        "核对检修工具、防护用品、备件和作业人员分工。",
    ]
    if level == "daily_check":
        items.append("日常检查阶段只做观察、听诊、外观检查和运行记录，不直接拆卸。")
    if level == "major_repair":
        items.append("重大检修前确认作业票、负责人签字、备件可用性和多人复核机制。")
    if level == "emergency":
        items.append("紧急处理先划定安全区域，通知现场负责人，确认不会扩大人员和设备风险。")
    if risk_level in {"high", "critical"}:
        items.append("当前风险等级较高，执行前必须由资深检修人员或现场负责人复核。")
    return items


def build_risk_controls(level: str, risk_level: str, evidence_pack: dict[str, Any] | None = None) -> list[str]:
    level = normalize_maintenance_level(level)
    risk_level = normalize_risk_level(risk_level)
    evidence_pack = evidence_pack or {}
    controls = [
        "涉及高温、旋转、带压、电气部件时先完成安全隔离和残余能量释放。",
        "未在证据中出现的扭矩、温度、间隙、压力等参数不得由系统补写。",
    ]
    if level == "daily_check":
        controls.append("日常检查如发现需要拆卸、带压或电气操作，应升级为检修任务并重新审批。")
    if level == "major_repair":
        controls.append("重大检修不得由系统单独给出最终执行指令，必须执行人工复核和作业票流程。")
    if level == "emergency":
        controls.append("紧急处理优先排除人员风险和设备失控风险，必要时停机保护。")
    if risk_level in {"high", "critical"} or evidence_pack.get("riskReviewRequired"):
        controls.append("high/critical 风险或证据风险提示已触发，必须人工复核后执行。")
    return controls


def build_compliance_checks(
    maintenance_level: str,
    risk_level: str,
    evidence_pack: dict[str, Any] | None = None,
) -> list[str]:
    maintenance_level = normalize_maintenance_level(maintenance_level)
    risk_level = normalize_risk_level(risk_level)
    evidence_pack = evidence_pack or {}
    checks = [
        "执行前确认设备停机、断电、挂牌和隔离状态。",
        "证据包缺少页码、来源或 chunkId 时，不得直接执行参数调整。",
        "检修过程必须记录检查项、处理动作、复测结果和责任人。",
    ]
    if maintenance_level == "major_repair":
        checks.append("重大检修需要作业票、负责人确认和多人复核。")
    if maintenance_level == "emergency":
        checks.append("紧急处理必须先进行安全隔离和现场负责人确认。")
    if risk_level in {"high", "critical"} or evidence_pack.get("riskReviewRequired"):
        checks.append("涉及高风险证据或高风险等级时，必须人工复核后执行。")
    if not evidence_pack.get("items"):
        checks.append("当前缺少 approved 证据，仅允许输出通用安全排查模板。")
    return checks
