from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any

from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter


ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = Path(os.getenv("MANUAL_SMOKE_TMP_ROOT", str(ROOT / "tmp"))).resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MANUAL_CANDIDATES = (
    Path("/home/vmuser/official-motorcycle-manual.pdf"),
    Path("E:/Download/Downloads/摩托车发动机维修手册.pdf"),
    TMP_ROOT / "official-motorcycle-manual.pdf",
)


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
        if candidate.is_file() and candidate.stat().st_size > 0 and candidate.suffix.lower() == ".pdf":
            return candidate
    raise FileNotFoundError("official motorcycle manual was not found in approved locations")


def git_sha() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def extract_three_pages(source: Path, target: Path) -> None:
    reader = PdfReader(str(source))
    if len(reader.pages) < 3:
        raise ValueError("official manual has fewer than three pages")
    writer = PdfWriter()
    for page in reader.pages[:3]:
        writer.add_page(page)
    with target.open("wb") as output:
        writer.write(output)


def base_record(
    renderer: dict[str, Any],
    multimodal: dict[str, Any],
    provider_probe: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "gitSha": git_sha(),
        "rendererReadiness": renderer,
        "multimodalReadiness": multimodal,
        "providerProbe": provider_probe,
        "mode": "smart_multimodal",
        "pageCount": 3,
        "parser": "",
        "textChunkCount": 0,
        "visualCandidatePages": 0,
        "visualPagesRendered": 0,
        "visualPagesOcrProcessed": 0,
        "visualPagesAnalyzed": 0,
        "realMultimodalPages": 0,
        "unverifiedVisualPages": 0,
        "fallbackVisualPages": 0,
        "visualFailedPages": [],
        "visualCoverageRatio": 0.0,
        "realMultimodalCoverageRatio": 0.0,
        "visualChunkCount": 0,
        "pendingReviewAll": False,
        "semanticVerifiedAll": False,
        "unapprovedNotRetrievable": False,
        "approvedRetrievable": False,
        "controlledPreviewPassed": False,
        "durationSeconds": 0.0,
        "status": "not_run",
        "result": "THREE_PAGE_REAL_MULTIMODAL_NO_GO",
    }


def run_smoke(
    three_page_pdf: Path,
    renderer: dict[str, Any],
    multimodal: dict[str, Any],
    provider_probe: dict[str, Any],
) -> dict[str, Any]:
    from backend.app import data_store
    from backend.app.main import app

    record = base_record(renderer, multimodal, provider_probe)
    if not renderer["ready"] or not renderer["smokeRenderOk"]:
        record["result"] = "RENDERER_SMOKE_NO_GO"
        return record
    if not multimodal["ready"] or multimodal["provider"] == "mock":
        record["result"] = "MULTIMODAL_CONFIG_NO_GO"
        return record
    if not provider_probe["probeOk"]:
        record["result"] = "MULTIMODAL_PROVIDER_PROBE_NO_GO"
        return record

    started = time.monotonic()
    operator_token = "manual-smoke-operator"
    reviewer_token = "manual-smoke-reviewer"
    os.environ.update(
        {
            "APP_KNOWLEDGE_DIR": str(three_page_pdf.parent / "knowledge"),
            "APP_ENV": "test",
            "AUTH_MODE": "token",
            "AUTH_OPERATOR_TOKEN": operator_token,
            "AUTH_REVIEWER_TOKEN": reviewer_token,
            "AUTH_ADMIN_TOKEN": "manual-smoke-admin",
        }
    )
    operator = {"Authorization": f"Bearer {operator_token}"}
    reviewer = {"Authorization": f"Bearer {reviewer_token}"}
    client = TestClient(app)
    response = client.post(
        "/api/knowledge/documents/async",
        files={"file": ("motorcycle-manual-three-pages.pdf", three_page_pdf.read_bytes(), "application/pdf")},
        data={"parser_mode": "smart_multimodal", "source_name": "official motorcycle manual smoke"},
        headers=operator,
    )
    if response.status_code != 200:
        raise RuntimeError(f"async upload failed with HTTP {response.status_code}")
    task_id = response.json()["data"]["id"]
    deadline = time.monotonic() + 1800
    task: dict[str, Any] = {}
    while time.monotonic() < deadline:
        task_response = client.get(f"/api/knowledge/parse-tasks/{task_id}", headers=operator)
        if task_response.status_code != 200:
            raise RuntimeError("parse task status could not be read")
        task = task_response.json()["data"]
        if task.get("status") in {"completed", "completed_with_warnings", "failed"}:
            break
        time.sleep(2)
    if task.get("status") not in {"completed", "completed_with_warnings", "failed"}:
        raise TimeoutError("three-page parse task timed out")

    document_id = str(task.get("documentId") or "")
    document = next(item for item in data_store.load_documents() if item.get("id") == document_id)
    chunks = [
        item
        for item in data_store.load_document_chunks()
        if item.get("documentId") == document_id and item.get("origin") == "manual_visual_pipeline"
    ]
    pending_all = bool(chunks) and all(
        item.get("review_status") == "pending_review" and item.get("is_current") is False
        for item in chunks
    )
    semantic_all = bool(chunks) and all(
        item.get("semanticVerified") is True
        and item.get("imageInputSent") is True
        and item.get("analysisFallback") is False
        and item.get("analysisProvider") not in {None, "", "mock"}
        and item.get("analysisModel")
        and item.get("previewUrl")
        for item in chunks
    )
    chosen = next((item for item in chunks if str(item.get("content") or "").strip()), None)
    retrieval_ok = False
    preview_ok = False
    before_hidden = False
    approved_retrievable = False
    if chosen:
        query = {
            "deviceModel": "motorcycle",
            "faultText": str(chosen.get("content"))[:180],
            "maintenanceLevel": "normal_repair",
            "inputType": "text",
            "topK": 10,
        }
        before = client.post("/api/search", json=query, headers=operator).json()["data"]["results"]
        before_hidden = not any(item.get("chunkId") == chosen["id"] for item in before)
        reviewed = client.patch(
            f"/api/knowledge/documents/{document_id}/chunks/{chosen['id']}/review",
            json={"action": "approve", "reason": "real smoke verified", "reviewer": "reviewer"},
            headers=reviewer,
        )
        after = client.post("/api/search", json=query, headers=operator).json()["data"]["results"]
        match = next((item for item in after if item.get("chunkId") == chosen["id"]), None)
        retrieval_ok = bool(
            before_hidden
            and reviewed.status_code == 200
            and match
            and match.get("previewUrl")
            and match.get("semanticVerified") is True
            and match.get("analysisProvider")
            and match.get("analysisFallback") is False
        )
        approved_retrievable = bool(reviewed.status_code == 200 and match)
        preview_url = str(chosen.get("previewUrl") or "")
        unauthorized = client.get(preview_url)
        authorized = client.get(preview_url, headers=operator)
        preview_ok = bool(
            unauthorized.status_code == 401
            and authorized.status_code == 200
            and authorized.headers.get("content-type", "").startswith(("image/jpeg", "image/png"))
        )

    metric_names = (
        "pageCount",
        "textChunkCount",
        "visualCandidatePages",
        "visualPagesRendered",
        "visualPagesOcrProcessed",
        "visualPagesAnalyzed",
        "realMultimodalPages",
        "unverifiedVisualPages",
        "fallbackVisualPages",
        "visualFailedPages",
        "visualCoverageRatio",
        "realMultimodalCoverageRatio",
        "visualChunkCount",
    )
    record.update({name: document.get(name, 0) for name in metric_names})
    record.update(
        parser=document.get("parser", ""),
        durationSeconds=round(time.monotonic() - started, 3),
        status=task.get("status", "failed"),
        queueFileCleaned=not any((three_page_pdf.parent / "knowledge" / "parse-queue").glob("*")),
        pendingReviewAll=pending_all,
        semanticVerifiedAll=semantic_all,
        unapprovedNotRetrievable=before_hidden,
        approvedRetrievable=approved_retrievable,
        controlledPreviewPassed=preview_ok,
    )
    expected = int(document.get("visualPagesRendered") or 0)
    metrics_ok = bool(
        int(document.get("pageCount") or 0) == 3
        and expected > 0
        and int(document.get("visualPagesOcrProcessed") or 0) == expected
        and int(document.get("visualPagesAnalyzed") or 0) == expected
        and int(document.get("realMultimodalPages") or 0) == expected
        and int(document.get("fallbackVisualPages") or 0) == 0
        and float(document.get("visualCoverageRatio") or 0) == 1.0
        and float(document.get("realMultimodalCoverageRatio") or 0) == 1.0
        and int(document.get("visualChunkCount") or 0) == expected
        and document.get("renderer") == renderer.get("renderer")
        and record["queueFileCleaned"]
        and task.get("status") == "completed"
    )
    record["result"] = (
        "THREE_PAGE_REAL_MULTIMODAL_GO"
        if metrics_ok and pending_all and semantic_all and retrieval_ok and preview_ok
        else "THREE_PAGE_REAL_MULTIMODAL_NO_GO"
    )
    return record


def write_result(record: dict[str, Any]) -> Path:
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    configured = os.getenv("MANUAL_SMOKE_OUTPUT", "").strip()
    if configured:
        output = Path(configured).resolve()
        if output.parent != TMP_ROOT:
            raise ValueError("MANUAL_SMOKE_OUTPUT must be directly inside MANUAL_SMOKE_TMP_ROOT")
    else:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output = TMP_ROOT / f"manual-multimodal-smoke-{timestamp}.json"
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def main() -> int:
    try:
        logging.disable(logging.CRITICAL)
        load_local_env()
        manual = resolve_manual_path()
        TMP_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="manual-smoke-", dir=TMP_ROOT) as temp_dir:
            three_page_pdf = Path(temp_dir) / "manual-three-pages.pdf"
            extract_three_pages(manual, three_page_pdf)
            from backend.app.multimodal_adapter import multimodal_operational_probe, multimodal_readiness
            from backend.app.pdf_renderer import renderer_operational_readiness

            renderer = renderer_operational_readiness()
            multimodal = multimodal_readiness()
            provider_probe = multimodal_operational_probe()
            record = run_smoke(three_page_pdf, renderer, multimodal, provider_probe)
        output = write_result(record)
        print(f"three-page smoke completed: {output.name}")
        print(f"result: {record['result']}")
        return 0 if record["result"] == "THREE_PAGE_REAL_MULTIMODAL_GO" else 1
    except Exception as exc:
        safe_record = base_record(
            {
                "ready": False,
                "renderer": "unavailable",
                "status": "unavailable",
                "commandFound": False,
                "versionProbeOk": False,
                "smokeRenderOk": False,
                "failureCategory": "unavailable",
            },
            {
                "provider": "unknown",
                "model": "",
                "credentialConfigured": False,
                "endpointConfigured": False,
                "remoteAllowed": False,
                "ready": False,
                "status": "unavailable",
            },
            None,
        )
        safe_record["status"] = f"failed:{type(exc).__name__}"
        output = write_result(safe_record)
        print(f"three-page smoke failed safely: {output.name}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
