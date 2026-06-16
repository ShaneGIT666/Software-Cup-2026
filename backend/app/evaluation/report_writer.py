from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import EvalCaseResult, EvalDataset, EvalMode, MetricValue, to_plain_dict


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def metric_to_dict(metric: Any) -> Any:
    if isinstance(metric, MetricValue):
        return {
            "value": metric.value,
            "available": metric.available,
            "reason": metric.reason,
        }
    if isinstance(metric, dict):
        return {key: metric_to_dict(value) for key, value in metric.items()}
    return to_plain_dict(metric)


def build_report(
    dataset: EvalDataset,
    mode: EvalMode,
    case_results: list[EvalCaseResult],
    metrics: dict[str, Any],
    git_info: dict[str, Any],
    config_summary: dict[str, str],
) -> dict[str, Any]:
    unavailable = {
        key: value.reason
        for key, value in metrics.items()
        if isinstance(value, MetricValue) and not value.available
    }
    failed_cases = [
        result.id
        for result in case_results
        if any(value is False for value in result.hit_at.values() if value is not None)
        or result.forbidden_source_violations
        or result.approved_only_violations
    ]
    return {
        "generated_at": utc_now(),
        "git": git_info,
        "config": config_summary,
        "dataset": {
            "id": dataset.dataset_id,
            "schema_version": dataset.schema_version,
            "created_at": dataset.created_at,
            "purpose": dataset.purpose,
            "case_count": len(dataset.cases),
            "category_counts": dataset.category_counts(),
        },
        "mode": {
            "name": mode.name,
            "description": mode.description,
            "env_overrides": mode.env_overrides,
        },
        "metrics": metric_to_dict(metrics),
        "unavailable_metrics": unavailable,
        "case_results": [to_plain_dict(result) for result in case_results],
        "failed_cases": failed_cases,
        "forbidden_source_violations": [
            {
                "case_id": result.id,
                "violations": result.forbidden_source_violations,
            }
            for result in case_results
            if result.forbidden_source_violations
        ],
        "approved_only_violations": [
            {
                "case_id": result.id,
                "violations": result.approved_only_violations,
            }
            for result in case_results
            if result.approved_only_violations
        ],
    }


def markdown_report(report: dict[str, Any]) -> str:
    lines = [
        f"# RAG Retrieval Baseline - {report['mode']['name']}",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Git commit: `{report['git'].get('commit', 'unknown')}`",
        f"- Working tree: `{report['git'].get('working_tree', 'unknown')}`",
        f"- Dataset: `{report['dataset']['id']}` / schema `{report['dataset']['schema_version']}`",
        f"- Cases: `{report['dataset']['case_count']}`",
        f"- Mode: {report['mode']['description']}",
        "",
        "## Config Summary",
        "",
    ]
    for key, value in report["config"].items():
        lines.append(f"- `{key}`: `{value}`")

    lines.extend(["", "## Category Counts", ""])
    for category, count in report["dataset"]["category_counts"].items():
        lines.append(f"- `{category}`: {count}")

    lines.extend(["", "## Summary Metrics", "", "| Metric | Value | Available | Reason |", "| --- | --- | --- | --- |"])
    for key, item in report["metrics"].items():
        lines.append(
            f"| {key} | {item.get('value')} | {item.get('available')} | {item.get('reason', '')} |"
        )

    if report["unavailable_metrics"]:
        lines.extend(["", "## Unavailable Metrics", ""])
        for key, reason in report["unavailable_metrics"].items():
            lines.append(f"- `{key}`: {reason}")

    lines.extend(["", "## Case Results", ""])
    lines.append(
        "| Case | Category | Top Result | Count | Latency ms | Hit@1 | Hit@3 | Hit@5 | Recall@5 | RR | Forbidden | Approved-only |"
    )
    lines.append("| --- | --- | --- | ---: | ---: | --- | --- | --- | ---: | ---: | --- | --- |")
    for result in report["case_results"]:
        lines.append(
            "| {id} | {category} | {top} | {count} | {latency} | {h1} | {h3} | {h5} | {r5} | {rr} | {forbidden} | {approved} |".format(
                id=result["id"],
                category=result["category"],
                top=result["top_result_id"],
                count=result["result_count"],
                latency=result["latency_ms"],
                h1=result["hit_at"]["Hit@1"],
                h3=result["hit_at"]["Hit@3"],
                h5=result["hit_at"]["Hit@5"],
                r5=result["recall_at"]["Recall@5"],
                rr=result["reciprocal_rank"],
                forbidden=", ".join(result["forbidden_source_violations"]),
                approved=", ".join(item["source_id"] for item in result["approved_only_violations"]),
            )
        )

    lines.extend(["", "## Failed Cases", ""])
    if report["failed_cases"]:
        for case_id in report["failed_cases"]:
            lines.append(f"- `{case_id}`")
    else:
        lines.append("None.")

    lines.extend(["", "## Forbidden Source Violations", ""])
    if report["forbidden_source_violations"]:
        for item in report["forbidden_source_violations"]:
            lines.append(f"- `{item['case_id']}`: {', '.join(item['violations'])}")
    else:
        lines.append("None.")

    lines.extend(["", "## Approved-only Violations", ""])
    if report["approved_only_violations"]:
        for item in report["approved_only_violations"]:
            values = ", ".join(f"{entry['source_id']}={entry['status']}" for entry in item["violations"])
            lines.append(f"- `{item['case_id']}`: {values}")
    else:
        lines.append("None.")

    return "\n".join(lines) + "\n"


def write_report(report: dict[str, Any], output_dir: Path, basename: str) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{basename}.json"
    md_path = output_dir / f"{basename}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(markdown_report(report), encoding="utf-8")
    return json_path, md_path
