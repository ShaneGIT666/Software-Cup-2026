from __future__ import annotations

import argparse
import base64
import csv
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = ROOT / "tmp"
AUDIT_DOC = ROOT / "docs" / "final-audit" / "06-manual-visual-quality-audit.md"
HUMAN_ROOT = TMP_ROOT / "manual-visual-human-review"
MANUAL_CANDIDATES = (
    Path("/home/vmuser/official-motorcycle-manual.pdf"),
    Path("E:/Download/Downloads/摩托车发动机维修手册.pdf"),
    TMP_ROOT / "official-motorcycle-manual.pdf",
)
SCORE_KEYS = (
    "factualConsistency", "componentAccuracy", "operationAccuracy", "numericSafety", "uncertaintyHandling",
)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_local_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")


def resolve_manual_path() -> Path:
    configured = os.getenv("OFFICIAL_MANUAL_PATH", "").strip()
    candidates = (Path(configured),) if configured else MANUAL_CANDIDATES
    for candidate in candidates:
        if candidate.is_file() and candidate.suffix.lower() == ".pdf" and candidate.stat().st_size > 0:
            return candidate
    raise FileNotFoundError("official motorcycle manual was not found in approved locations")


def git_sha() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def select_quality_pages(inventory: list[dict[str, Any]], sample_size: int = 20) -> tuple[list[int], dict[str, list[str]]]:
    if len(inventory) < sample_size:
        raise ValueError("manual has fewer pages than the required quality sample")
    by_page = {int(item["page"]): item for item in inventory}
    selected: list[int] = []
    reasons: dict[int, list[str]] = {}

    def add(page: int, reason: str) -> bool:
        if page in selected:
            if reason not in reasons[page]:
                reasons[page].append(reason)
            return False
        selected.append(page)
        reasons[page] = [reason]
        return True

    add(1, "first_page")
    add(max(by_page), "last_page")

    rankings = (
        (sorted(inventory, key=lambda item: (-int(item.get("imageObjectCount") or 0), int(item["page"]))), 5, "high_image_count"),
        (sorted(inventory, key=lambda item: (-len(item.get("keywordHits") or []), int(item["page"]))), 5, "high_visual_keyword_count"),
        (sorted(inventory, key=lambda item: (int(item.get("textChars") or 0), int(item["page"]))), 4, "low_text_density"),
    )
    for ranking, count, reason in rankings:
        added = 0
        for item in ranking:
            if add(int(item["page"]), reason):
                added += 1
            if added == count:
                break

    remaining = sorted(set(by_page) - set(selected))
    needed = sample_size - len(selected)
    if needed > 0:
        indices = [round((index + 1) * (len(remaining) + 1) / (needed + 1)) - 1 for index in range(needed)]
        for index in indices:
            add(remaining[max(0, min(index, len(remaining) - 1))], "uniform_distribution")
    if len(set(selected)) != sample_size:
        for page in remaining:
            add(page, "uniform_distribution")
            if len(selected) == sample_size:
                break
    ordered = sorted(selected)
    return ordered, {str(page): reasons[page] for page in ordered}


def parse_json_object(text: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    clean = text.strip()
    for index, character in enumerate(clean):
        if character != "{":
            continue
        try:
            payload, _ = decoder.raw_decode(clean[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise ValueError("judge response did not contain a JSON object")


def judge_configuration() -> dict[str, Any]:
    from backend.app.multimodal_adapter import (
        configured_multimodal_provider,
        local_multimodal_api_key,
        local_multimodal_base_url,
        local_multimodal_model,
        multimodal_openai_api_key,
        multimodal_openai_base_url,
        multimodal_openai_model,
    )

    eval_values = {
        "provider": os.getenv("MULTIMODAL_EVAL_PROVIDER", "").strip().lower(),
        "baseUrl": os.getenv("MULTIMODAL_EVAL_BASE_URL", "").strip().rstrip("/"),
        "apiKey": os.getenv("MULTIMODAL_EVAL_API_KEY", "").strip(),
        "model": os.getenv("MULTIMODAL_EVAL_MODEL", "").strip(),
    }
    if all(eval_values.values()) and eval_values["provider"] != "mock":
        return {**eval_values, "independentJudge": True, "sameModelJudge": False}

    provider = configured_multimodal_provider(None)
    if provider == "openai":
        base_url, api_key, model = multimodal_openai_base_url(), multimodal_openai_api_key(), multimodal_openai_model()
    elif provider == "local":
        base_url, api_key, model = local_multimodal_base_url(), local_multimodal_api_key(), local_multimodal_model()
    elif provider == "anthropic":
        base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1").rstrip("/")
        api_key, model = os.getenv("ANTHROPIC_API_KEY", ""), os.getenv("ANTHROPIC_MODEL", "")
    else:
        raise RuntimeError("mock judge is not allowed")
    if not all((base_url, api_key, model)):
        raise RuntimeError("judge configuration is incomplete")
    return {
        "provider": provider, "baseUrl": base_url, "apiKey": api_key, "model": model,
        "independentJudge": False, "sameModelJudge": True,
    }


def judge_page(
    image_path: Path,
    nearby_text: str,
    primary: dict[str, Any],
    config: dict[str, Any],
    timeout_seconds: float = 45,
) -> dict[str, Any]:
    from backend.app.llm_adapter import _post_json, parse_openai_chat_response
    from backend.app.multimodal_adapter import data_url, parse_anthropic_multimodal_response

    primary_safe = {
        key: primary.get(key)
        for key in ("visualType", "summary", "components", "operations", "figureLabels", "safetyWarnings", "uncertainties")
    }
    ocr = primary.get("ocr", {}) if isinstance(primary.get("ocr"), dict) else {}
    prompt = (
        "你是维修手册视觉质量审计员。必须同时核对原始页面图片、OCR、附近正文和主模型结构化结果。"
        "重点识别部件、拆装/检查关系、图号、扭矩、间隙、尺寸、故障码和安全警告是否被编造。"
        "无法确认时应要求主结果写入 uncertainties。只输出 JSON："
        '{"factualConsistency":0,"componentAccuracy":0,"operationAccuracy":0,"numericSafety":0,'
        '"uncertaintyHandling":0,"criticalHallucination":false,"unsupportedNumericClaims":[],'
        '"incorrectComponents":[],"incorrectOperations":[],"missingUncertainties":[],"reason":""}. '
        "每项只能为 0、1、2。\n"
        f"OCR/附近正文：{str(ocr.get('text') or '')[:2000]}\n{nearby_text[:2000]}\n"
        f"主模型结果：{json.dumps(primary_safe, ensure_ascii=False)}"
    )
    provider = config["provider"]
    content = image_path.read_bytes()
    if provider in {"openai", "local"}:
        payload = _post_json(
            f"{config['baseUrl']}/chat/completions",
            headers={"Authorization": f"Bearer {config['apiKey']}", "Content-Type": "application/json"},
            payload={
                "model": config["model"],
                "messages": [{"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url(content, "jpg")}},
                ]}],
                "max_tokens": 1000, "temperature": 0, "stream": False,
            },
            timeout=timeout_seconds,
        )
        text = parse_openai_chat_response(payload)
    elif provider == "anthropic":
        payload = _post_json(
            f"{config['baseUrl']}/messages",
            headers={"x-api-key": config["apiKey"], "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
            payload={
                "model": config["model"], "max_tokens": 1000,
                "messages": [{"role": "user", "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(content).decode("ascii")}},
                    {"type": "text", "text": prompt},
                ]}],
            },
            timeout=timeout_seconds,
        )
        text = parse_anthropic_multimodal_response(payload)
    else:
        raise RuntimeError("unsupported judge provider")
    raw = parse_json_object(text)
    result = {key: max(0, min(2, int(raw.get(key, 0)))) for key in SCORE_KEYS}
    result.update(
        criticalHallucination=bool(raw.get("criticalHallucination", False)),
        unsupportedNumericClaims=[str(item)[:120] for item in raw.get("unsupportedNumericClaims", []) if str(item).strip()],
        incorrectComponents=[str(item)[:120] for item in raw.get("incorrectComponents", []) if str(item).strip()],
        incorrectOperations=[str(item)[:120] for item in raw.get("incorrectOperations", []) if str(item).strip()],
        missingUncertainties=[str(item)[:120] for item in raw.get("missingUncertainties", []) if str(item).strip()],
        reason=str(raw.get("reason") or "")[:240],
    )
    result["qualityScore"] = sum(result[key] for key in SCORE_KEYS)
    result["passed"] = bool(
        result["qualityScore"] >= 8
        and not result["criticalHallucination"]
        and not result["unsupportedNumericClaims"]
    )
    return result


def aggregate_quality(pages: list[dict[str, Any]], *, independent: bool) -> dict[str, Any]:
    completed = [item for item in pages if not item.get("primaryAnalysisFailed") and not item.get("judgeFailed")]
    scores = [int(item.get("qualityScore") or 0) for item in completed]
    metrics = {
        "completedPages": len(completed),
        "primaryAnalysisFailedPages": sum(bool(item.get("primaryAnalysisFailed")) for item in pages),
        "judgeFailedPages": sum(bool(item.get("judgeFailed")) for item in pages),
        "passedPages": sum(bool(item.get("machinePass")) for item in pages),
        "averageScore": round(sum(scores) / len(scores), 3) if scores else 0.0,
        "lowestScore": min(scores) if scores else 0,
        "criticalHallucinationPages": sum(bool(item.get("criticalHallucination")) for item in pages),
        "unsupportedNumericClaimPages": sum(bool(item.get("unsupportedNumericClaims")) for item in pages),
        "pagesWithComponentsOrOperations": sum(
            int(int(item.get("componentsCount") or 0) > 0 or int(item.get("operationsCount") or 0) > 0) for item in pages
        ),
        "nonUnknownVisualTypes": len({item.get("visualType") for item in pages if item.get("visualType") not in {None, "", "unknown"}}),
    }
    passed = bool(
        len(pages) == 20 and metrics["completedPages"] == 20
        and metrics["primaryAnalysisFailedPages"] == 0 and metrics["judgeFailedPages"] == 0
        and metrics["criticalHallucinationPages"] == 0 and metrics["unsupportedNumericClaimPages"] == 0
        and metrics["passedPages"] >= 18 and metrics["averageScore"] >= 8.5 and metrics["lowestScore"] >= 6
        and metrics["pagesWithComponentsOrOperations"] >= 5 and metrics["nonUnknownVisualTypes"] >= 3
        and all(item.get("semanticVerified") and item.get("imageInputSent") and not item.get("fallback") for item in pages)
    )
    metrics["result"] = (
        "INDEPENDENT_VISUAL_QUALITY_GO" if passed and independent
        else "MACHINE_VISUAL_QUALITY_GO_SAME_MODEL" if passed
        else "VISUAL_QUALITY_NO_GO"
    )
    return metrics


def existing_human_results() -> dict[int, tuple[str, str]]:
    path = HUMAN_ROOT / "review-results.csv"
    if not path.is_file():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {
            int(row["page"]): (row.get("human_result", ""), row.get("human_notes", ""))
            for row in csv.DictReader(handle)
        }


def write_human_package(pages: list[dict[str, Any]], reasons: dict[str, list[str]]) -> None:
    HUMAN_ROOT.mkdir(parents=True, exist_ok=True)
    pages_dir = HUMAN_ROOT / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    selected = {int(item["page"]) for item in pages}
    for stale in pages_dir.glob("page-*.jpg"):
        page = int(stale.stem.split("-")[-1])
        if page not in selected:
            stale.unlink()
    prior = existing_human_results()
    fields = [
        "page", "selection_reason", "visual_type", "summary_preview", "components", "operations",
        "figure_labels", "safety_warnings", "uncertainties", "machine_score", "machine_pass",
        "human_result", "human_notes",
    ]
    with (HUMAN_ROOT / "review-results.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in pages:
            human_result, human_notes = prior.get(int(item["page"]), ("", ""))
            writer.writerow({
                "page": item["page"], "selection_reason": ";".join(reasons[str(item["page"])]),
                "visual_type": item.get("visualType", "unknown"), "summary_preview": item.get("summaryPreview", ""),
                "components": ";".join(item.get("components", [])), "operations": ";".join(item.get("operations", [])),
                "figure_labels": ";".join(item.get("figureLabels", [])),
                "safety_warnings": ";".join(item.get("safetyWarnings", [])),
                "uncertainties": ";".join(item.get("uncertainties", [])),
                "machine_score": item.get("qualityScore", 0), "machine_pass": item.get("machinePass", False),
                "human_result": human_result, "human_notes": human_notes,
            })
    (HUMAN_ROOT / "review-index.md").write_text(
        "# Manual Visual Human Review\n\n"
        "1. Open every image under `pages/`.\n"
        "2. Compare the page with summary, components, operations, and figure labels in `review-results.csv`.\n"
        "3. Carefully check torque, clearance, dimensions, identifiers, and safety warnings.\n"
        "4. Set `human_result` to `PASS` or `FAIL` only; record concise evidence in `human_notes`.\n\n"
        "Current status: HUMAN_VISUAL_REVIEW_PENDING\n",
        encoding="utf-8",
    )


def write_audit_doc(record: dict[str, Any]) -> None:
    metrics = record["metrics"]
    rows = [
        "| Page | Type | Score | Pass | Failure type | Critical hallucination | Unsupported numeric |",
        "|---:|---|---:|---|---|---|---|",
    ]
    for item in record["pages"]:
        if item.get("primaryAnalysisFailed"):
            failure_type = "primary analysis failed"
        elif item.get("judgeFailed"):
            failure_type = "judge failed"
        elif item.get("criticalHallucination"):
            failure_type = "critical hallucination"
        elif item.get("unsupportedNumericClaims"):
            failure_type = "unsupported numeric claim"
        elif not item.get("machinePass"):
            failure_type = "below page threshold"
        else:
            failure_type = "none"
        rows.append(
            f"| {item['page']} | {item.get('visualType', 'unknown')} | {item.get('qualityScore', 0)} | "
            f"{str(bool(item.get('machinePass'))).lower()} | {failure_type} | "
            f"{str(bool(item.get('criticalHallucination'))).lower()} | "
            f"{len(item.get('unsupportedNumericClaims', []))} |"
        )
    AUDIT_DOC.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_DOC.write_text(
        "# Manual Visual Quality Audit\n\n"
        f"- Audit date: {record['auditDate']}\n- Git SHA: `{record['gitSha']}`\n"
        f"- Manual SHA256: `{record['manualSha256']}`\n- Selected pages: {', '.join(map(str, record['selectedPages']))}\n"
        f"- Primary: {record['primaryProvider']} / {record['primaryModel']}\n"
        f"- Judge: {record['judgeProvider']} / {record['judgeModel']}\n"
        f"- Independent judge: {str(record['independentJudge']).lower()}\n- Same-model judge: {str(record['sameModelJudge']).lower()}\n"
        f"- Completed pages: {metrics['completedPages']}\n- Passed pages: {metrics['passedPages']}\n"
        f"- Average score: {metrics['averageScore']}\n- Lowest score: {metrics['lowestScore']}\n"
        f"- Critical hallucination pages: {metrics['criticalHallucinationPages']}\n"
        f"- Unsupported numeric claim pages: {metrics['unsupportedNumericClaimPages']}\n"
        f"- Machine conclusion: **{metrics['result']}**\n- Human review: **HUMAN_VISUAL_REVIEW_PENDING**\n\n"
        + "\n".join(rows) + "\n",
        encoding="utf-8",
    )


def run_audit() -> dict[str, Any]:
    from backend.app.manual_visual_pipeline import inventory_pdf_pages
    from backend.app.multimodal_adapter import analyze_multimodal_document, multimodal_readiness
    from backend.app.pdf_renderer import render_pdf_page, renderer_operational_readiness

    manual = resolve_manual_path()
    inventory = inventory_pdf_pages(manual)
    selected, reasons = select_quality_pages(inventory)
    readiness = renderer_operational_readiness()
    multimodal = multimodal_readiness()
    if not readiness["ready"] or not readiness["smokeRenderOk"]:
        raise RuntimeError("renderer operational smoke is not ready")
    if not multimodal["ready"] or multimodal["provider"] == "mock":
        raise RuntimeError("primary multimodal configuration is not ready")
    judge = judge_configuration()
    HUMAN_ROOT.mkdir(parents=True, exist_ok=True)
    pages_dir = HUMAN_ROOT / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    profiles = {int(item["page"]): item for item in inventory}
    results = []
    for index, page in enumerate(selected, start=1):
        image = pages_dir / f"page-{page:04d}.jpg"
        entry: dict[str, Any] = {
            "page": page, "selectionReasons": reasons[str(page)], "primaryAnalysisFailed": False,
            "judgeFailed": False, "semanticVerified": False, "imageInputSent": False, "fallback": True,
            "visualType": "unknown", "componentsCount": 0, "operationsCount": 0, "uncertaintiesCount": 0,
            "qualityScore": 0, "machinePass": False, "errorCategory": "none",
        }
        try:
            render_pdf_page(manual, page, image, 180, selected_renderer=str(readiness["renderer"]))
            primary = analyze_multimodal_document(
                image, image.name, "jpg", None, context_text=str(profiles[page].get("text") or "")[:2000],
                analysis_task="manual_page", timeout_seconds=45, raise_on_failure=True,
            )
            entry.update(
                semanticVerified=bool(primary.get("semanticVerified")), imageInputSent=bool(primary.get("imageInputSent")),
                fallback=bool(primary.get("fallback", True)), visualType=str(primary.get("visualType") or "unknown"),
                summaryPreview=str(primary.get("summary") or "")[:160], components=list(primary.get("components") or []),
                operations=list(primary.get("operations") or []), figureLabels=list(primary.get("figureLabels") or []),
                safetyWarnings=list(primary.get("safetyWarnings") or []), uncertainties=list(primary.get("uncertainties") or []),
                componentsCount=len(primary.get("components") or []), operationsCount=len(primary.get("operations") or []),
                uncertaintiesCount=len(primary.get("uncertainties") or []),
            )
            if not entry["semanticVerified"] or not entry["imageInputSent"] or entry["fallback"]:
                raise ValueError("primary semantic verification failed")
        except Exception as exc:
            entry.update(primaryAnalysisFailed=True, errorCategory=f"primary_{type(exc).__name__}")
            results.append(entry)
            print(f"page {index}/20: primary_failed")
            continue
        try:
            score = judge_page(image, str(profiles[page].get("text") or ""), primary, judge)
            entry.update(
                qualityScore=score["qualityScore"], machinePass=score["passed"],
                criticalHallucination=score["criticalHallucination"],
                unsupportedNumericClaims=score["unsupportedNumericClaims"],
                incorrectComponents=score["incorrectComponents"], incorrectOperations=score["incorrectOperations"],
                missingUncertainties=score["missingUncertainties"], scoreReason=score["reason"],
                **{key: score[key] for key in SCORE_KEYS},
            )
        except Exception as exc:
            entry.update(judgeFailed=True, errorCategory=f"judge_{type(exc).__name__}")
        results.append(entry)
        print(f"page {index}/20: {'pass' if entry.get('machinePass') else 'no_go'}")

    metrics = aggregate_quality(results, independent=bool(judge["independentJudge"]))
    record = {
        "auditDate": datetime.now(timezone.utc).date().isoformat(), "gitSha": git_sha(),
        "manualSha256": hashlib.sha256(manual.read_bytes()).hexdigest(), "pageCount": len(inventory),
        "selectedPages": selected, "selectionReasons": reasons, "renderer": readiness["renderer"],
        "primaryProvider": multimodal["provider"], "primaryModel": multimodal["model"],
        "judgeProvider": judge["provider"], "judgeModel": judge["model"],
        "independentJudge": judge["independentJudge"], "sameModelJudge": judge["sameModelJudge"],
        "pages": [{key: value for key, value in item.items() if key not in {"components", "operations", "figureLabels", "safetyWarnings", "uncertainties", "summaryPreview"}} for item in results],
        "metrics": metrics,
    }
    write_human_package(results, reasons)
    write_audit_doc(record)
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = TMP_ROOT / f"manual-visual-quality-audit-{stamp}.json"
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"result: {metrics['result']}")
    print(f"output: {output.name}")
    return record


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit visual semantics for a fixed 20-page manual sample.")
    parser.add_argument("--from-json", type=Path, help="Regenerate the Markdown summary from a sanitized audit JSON.")
    return parser.parse_args()


def main() -> int:
    try:
        logging.disable(logging.CRITICAL)
        load_local_env()
        args = parse_args()
        if args.from_json:
            audit_path = args.from_json.resolve()
            if audit_path.parent != TMP_ROOT.resolve() or not audit_path.name.startswith("manual-visual-quality-audit-"):
                raise ValueError("audit JSON must be an approved tmp quality-audit artifact")
            record = json.loads(audit_path.read_text(encoding="utf-8"))
            write_audit_doc(record)
            print(f"audit document regenerated: {AUDIT_DOC.name}")
            return 0
        record = run_audit()
        return 0 if record["metrics"]["result"] != "VISUAL_QUALITY_NO_GO" else 1
    except Exception as exc:
        print(f"quality audit failed safely: {type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
