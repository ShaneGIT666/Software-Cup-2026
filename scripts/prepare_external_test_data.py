from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = PROJECT_ROOT / "data" / "external-test"

AI4I_SAMPLE_ROWS: list[dict[str, Any]] = [
    {
        "case_id": "external-ai4i-case-001",
        "udi": 1,
        "product_id": "M14860",
        "type": "M",
        "air_temperature_k": 298.1,
        "process_temperature_k": 308.6,
        "rotational_speed_rpm": 1551,
        "torque_nm": 42.8,
        "tool_wear_min": 0,
        "machine_failure": 0,
        "failure_type": "normal",
        "component": "drive_system",
        "risk_level": "low",
        "maintenance_action": "记录基线工况并继续巡检",
    },
    {
        "case_id": "external-ai4i-case-002",
        "udi": 51,
        "product_id": "L47230",
        "type": "L",
        "air_temperature_k": 298.9,
        "process_temperature_k": 309.1,
        "rotational_speed_rpm": 2861,
        "torque_nm": 4.6,
        "tool_wear_min": 143,
        "machine_failure": 1,
        "failure_type": "power_failure",
        "component": "drive_motor",
        "risk_level": "high",
        "maintenance_action": "停机复核电机功率与负载匹配",
    },
    {
        "case_id": "external-ai4i-case-003",
        "udi": 77,
        "product_id": "L47256",
        "type": "L",
        "air_temperature_k": 298.8,
        "process_temperature_k": 308.9,
        "rotational_speed_rpm": 1286,
        "torque_nm": 62.9,
        "tool_wear_min": 128,
        "machine_failure": 1,
        "failure_type": "overstrain_failure",
        "component": "transmission",
        "risk_level": "critical",
        "maintenance_action": "降低负载并检查传动机构和联轴器",
    },
    {
        "case_id": "external-ai4i-case-004",
        "udi": 161,
        "product_id": "M15020",
        "type": "M",
        "air_temperature_k": 298.4,
        "process_temperature_k": 308.2,
        "rotational_speed_rpm": 1410,
        "torque_nm": 65.7,
        "tool_wear_min": 191,
        "machine_failure": 1,
        "failure_type": "heat_dissipation_failure",
        "component": "cooling_system",
        "risk_level": "high",
        "maintenance_action": "检查散热通道和冷却介质状态",
    },
    {
        "case_id": "external-ai4i-case-005",
        "udi": 339,
        "product_id": "H29752",
        "type": "H",
        "air_temperature_k": 297.8,
        "process_temperature_k": 308.0,
        "rotational_speed_rpm": 1362,
        "torque_nm": 48.5,
        "tool_wear_min": 215,
        "machine_failure": 1,
        "failure_type": "tool_wear_failure",
        "component": "tooling",
        "risk_level": "medium",
        "maintenance_action": "更换磨损刀具并复核加工参数",
    },
    {
        "case_id": "external-ai4i-case-006",
        "udi": 431,
        "product_id": "L47610",
        "type": "L",
        "air_temperature_k": 300.2,
        "process_temperature_k": 310.4,
        "rotational_speed_rpm": 1324,
        "torque_nm": 70.1,
        "tool_wear_min": 226,
        "machine_failure": 1,
        "failure_type": "random_failure",
        "component": "bearing",
        "risk_level": "high",
        "maintenance_action": "停机检查轴承异响和润滑状态",
    },
    {
        "case_id": "external-ai4i-case-007",
        "udi": 612,
        "product_id": "M15471",
        "type": "M",
        "air_temperature_k": 301.4,
        "process_temperature_k": 310.9,
        "rotational_speed_rpm": 1775,
        "torque_nm": 28.3,
        "tool_wear_min": 71,
        "machine_failure": 0,
        "failure_type": "normal",
        "component": "spindle",
        "risk_level": "low",
        "maintenance_action": "确认主轴转速和扭矩波动在正常范围",
    },
    {
        "case_id": "external-ai4i-case-008",
        "udi": 777,
        "product_id": "L47956",
        "type": "L",
        "air_temperature_k": 302.6,
        "process_temperature_k": 312.1,
        "rotational_speed_rpm": 1210,
        "torque_nm": 73.3,
        "tool_wear_min": 242,
        "machine_failure": 1,
        "failure_type": "overstrain_failure",
        "component": "gearbox",
        "risk_level": "critical",
        "maintenance_action": "禁止继续带载运行并检查齿轮箱",
    },
    {
        "case_id": "external-ai4i-case-009",
        "udi": 921,
        "product_id": "H30334",
        "type": "H",
        "air_temperature_k": 303.2,
        "process_temperature_k": 313.5,
        "rotational_speed_rpm": 1398,
        "torque_nm": 45.6,
        "tool_wear_min": 251,
        "machine_failure": 1,
        "failure_type": "tool_wear_failure",
        "component": "tooling",
        "risk_level": "medium",
        "maintenance_action": "计划性换刀并记录刀具寿命",
    },
    {
        "case_id": "external-ai4i-case-010",
        "udi": 1104,
        "product_id": "M15963",
        "type": "M",
        "air_temperature_k": 304.0,
        "process_temperature_k": 313.8,
        "rotational_speed_rpm": 1564,
        "torque_nm": 38.7,
        "tool_wear_min": 93,
        "machine_failure": 0,
        "failure_type": "normal",
        "component": "drive_system",
        "risk_level": "low",
        "maintenance_action": "继续监测温升和负载趋势",
    },
]

FAILURE_LABELS = {
    "normal": ("AI4I-NORMAL", "case_summary", "设备运行参数处于正常区间，无故障标签。"),
    "power_failure": ("AI4I-PWF", "troubleshooting", "转速和扭矩组合异常，存在功率链路异常风险。"),
    "overstrain_failure": ("AI4I-OSF", "troubleshooting", "低转速高扭矩或负载冲击明显，存在过载失效风险。"),
    "heat_dissipation_failure": ("AI4I-HDF", "safety_warning", "温度和负载指标异常，存在散热不足风险。"),
    "tool_wear_failure": ("AI4I-TWF", "repair_step", "刀具磨损累计较高，存在加工质量和刀具失效风险。"),
    "random_failure": ("AI4I-RNF", "troubleshooting", "指标组合提示随机机械失效风险，需要现场复核。"),
}


class ExternalDataError(ValueError):
    pass


def relative_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def load_manifest(root: Path = DEFAULT_ROOT) -> dict[str, Any]:
    with (root / "manifest.json").open("r", encoding="utf-8") as file:
        manifest = json.load(file)
    validate_manifest(manifest)
    return manifest


def validate_manifest(manifest: dict[str, Any]) -> None:
    if not isinstance(manifest, dict):
        raise ExternalDataError("manifest must be a JSON object")
    if not manifest.get("schema_version"):
        raise ExternalDataError("manifest.schema_version is required")
    assets = manifest.get("assets")
    if not isinstance(assets, list) or not assets:
        raise ExternalDataError("manifest.assets must be a non-empty array")

    required = {"id", "title", "source_type", "source_url", "license", "local_path", "commit_policy", "max_mb"}
    ids: list[str] = []
    for asset in assets:
        if not isinstance(asset, dict):
            raise ExternalDataError("each manifest asset must be an object")
        missing = sorted(field for field in required if not asset.get(field))
        if missing:
            raise ExternalDataError(f"{asset.get('id', '<missing-id>')} missing fields: {', '.join(missing)}")
        ids.append(str(asset["id"]))
        try:
            max_mb = float(asset["max_mb"])
        except (TypeError, ValueError) as exc:
            raise ExternalDataError(f"{asset['id']}.max_mb must be numeric") from exc
        if max_mb <= 0:
            raise ExternalDataError(f"{asset['id']}.max_mb must be positive")
    duplicates = sorted({asset_id for asset_id in ids if ids.count(asset_id) > 1})
    if duplicates:
        raise ExternalDataError(f"duplicate asset ids: {', '.join(duplicates)}")


def ensure_dirs(root: Path) -> None:
    for name in ("pdf", "tabular", "cases"):
        (root / name).mkdir(parents=True, exist_ok=True)


def generate_ai4i_cases(rows: list[dict[str, Any]] = AI4I_SAMPLE_ROWS) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        case_id = str(row["case_id"])
        if case_id in seen:
            raise ExternalDataError(f"duplicate generated case id: {case_id}")
        seen.add(case_id)
        fault_code, knowledge_type, symptom = FAILURE_LABELS[str(row["failure_type"])]
        product_id = str(row["product_id"])
        model_suffix = f"{product_id[0]}-{product_id[1:]}" if len(product_id) > 1 else product_id
        device_model = f"AI4I-{model_suffix}"
        content = (
            f"空气温度 {row['air_temperature_k']}K，过程温度 {row['process_temperature_k']}K，"
            f"转速 {row['rotational_speed_rpm']}rpm，扭矩 {row['torque_nm']}Nm，"
            f"刀具磨损 {row['tool_wear_min']}min。建议{row['maintenance_action']}。"
        )
        cases.append(
            {
                "id": case_id,
                "source_type": "external_dataset",
                "review_status": "pending_review",
                "device_type": "工业加工设备",
                "device_model": device_model,
                "component": str(row["component"]),
                "fault_symptom": symptom,
                "fault_code": fault_code,
                "risk_level": str(row["risk_level"]),
                "knowledge_type": knowledge_type,
                "content": content,
                "recommended_action": str(row["maintenance_action"]),
            }
        )
    return cases


def write_ai4i_assets(root: Path) -> list[str]:
    ensure_dirs(root)
    csv_path = root / "tabular" / "ai4i2020-sample.csv"
    fieldnames = list(AI4I_SAMPLE_ROWS[0].keys())
    with csv_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(AI4I_SAMPLE_ROWS)

    cases_path = root / "cases" / "ai4i-generated-maintenance-cases.json"
    payload = {
        "schema_version": "0.1.0",
        "source_dataset": "UCI AI4I 2020 Predictive Maintenance Dataset",
        "source_url": "https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset",
        "license": "CC BY 4.0",
        "generated_at": "2026-06-25T00:00:00Z",
        "default_review_status": "pending_review",
        "cases": generate_ai4i_cases(),
    }
    cases_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return [relative_path(csv_path), relative_path(cases_path)]


def asset_by_id(manifest: dict[str, Any], asset_id: str) -> dict[str, Any]:
    for asset in manifest["assets"]:
        if asset["id"] == asset_id:
            return asset
    raise ExternalDataError(f"asset not found: {asset_id}")


def download_file(url: str, destination: Path, max_mb: float) -> None:
    max_bytes = int(max_mb * 1024 * 1024)
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "software-cup-external-test/0.1"})
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - URL is curated in manifest.
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > max_bytes:
            raise ExternalDataError(f"remote file exceeds max_mb={max_mb}: {content_length} bytes")
        data = response.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ExternalDataError(f"download exceeds max_mb={max_mb}: {len(data)} bytes")
    destination.write_bytes(data)


def download_sapid_pdf(root: Path, manifest: dict[str, Any], max_mb: float | None = None) -> list[str]:
    asset = asset_by_id(manifest, "sapid-maintenance-manual-pdf")
    limit = max_mb if max_mb is not None else float(asset["max_mb"])
    destination = PROJECT_ROOT / asset["local_path"]
    if root != DEFAULT_ROOT:
        destination = root / "pdf" / "maintenance-manual-sapid.pdf"
    download_file(str(asset["download_url"]), destination, limit)
    if not destination.read_bytes().startswith(b"%PDF"):
        destination.unlink(missing_ok=True)
        raise ExternalDataError("downloaded SAPID maintenance-manual.pdf is not a valid PDF")
    return [relative_path(destination)]


def selected_sources(value: str) -> list[str]:
    return ["ai4i", "sapid"] if value == "all" else [value]


def run(source: str, root: Path, max_mb: float, dry_run: bool) -> dict[str, Any]:
    manifest = load_manifest(DEFAULT_ROOT)
    actions: list[str] = []
    errors: list[str] = []
    for selected in selected_sources(source):
        if selected == "ai4i":
            if dry_run:
                actions.extend(
                    [
                        relative_path(root / "tabular" / "ai4i2020-sample.csv"),
                        relative_path(root / "cases" / "ai4i-generated-maintenance-cases.json"),
                    ]
                )
            else:
                actions.extend(write_ai4i_assets(root))
        elif selected == "sapid":
            if dry_run:
                actions.append(relative_path(root / "pdf" / "maintenance-manual-sapid.pdf"))
            else:
                try:
                    actions.extend(download_sapid_pdf(root, manifest, max_mb=max_mb))
                except (ExternalDataError, urllib.error.URLError, TimeoutError) as exc:
                    errors.append(f"sapid download failed: {exc}")
        else:
            raise ExternalDataError(f"unsupported source: {selected}")
    return {"dry_run": dry_run, "source": source, "actions": actions, "errors": errors}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare curated external test assets for Software Cup RAG demos.")
    parser.add_argument("--source", choices=["ai4i", "sapid", "all"], default="all")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--max-mb", type=float, default=8)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        summary = run(args.source, args.root, args.max_mb, args.dry_run)
    except ExternalDataError as exc:
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps({"success": True, **summary}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
