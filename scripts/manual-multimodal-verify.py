from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MODES = ("text_fast", "smart_multimodal", "full_visual")
MANUAL_CANDIDATES = (
    Path("/home/vmuser/official-motorcycle-manual.pdf"),
    Path("E:/Download/Downloads/摩托车发动机维修手册.pdf"),
    ROOT / "tmp" / "official-motorcycle-manual.pdf",
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
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def resolve_manual_path() -> Path:
    configured = os.getenv("OFFICIAL_MANUAL_PATH", "").strip()
    candidates = (Path(configured),) if configured else MANUAL_CANDIDATES
    for candidate in candidates:
        if candidate.is_file() and candidate.stat().st_size > 0 and candidate.suffix.lower() == ".pdf":
            return candidate
    raise FileNotFoundError("official motorcycle manual was not found in the approved locations")


def git_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def result_label(mode: str, document: dict[str, Any]) -> str:
    if mode == "text_fast":
        passed = (
            document.get("parser") == "pypdf"
            and not document.get("mineruAttempted")
            and int(document.get("pageCount") or 0) == 41
            and int(document.get("textChunkCount") or 0) > 0
            and int(document.get("visualPagesRendered") or 0) == 0
        )
        return "TEXT_FAST_GO" if passed else "TEXT_FAST_NO_GO"
    expected = int(document.get("visualCandidatePages") or 0) if mode == "smart_multimodal" else int(document.get("pageCount") or 0)
    passed = bool(
        expected > 0
        and int(document.get("visualPagesRendered") or 0) == expected
        and int(document.get("visualPagesOcrProcessed") or 0) == expected
        and int(document.get("visualPagesAnalyzed") or 0) == expected
        and int(document.get("realMultimodalPages") or 0) == expected
        and int(document.get("fallbackVisualPages") or 0) == 0
        and not document.get("visualFailedPages")
        and float(document.get("visualCoverageRatio") or 0) == 1.0
        and float(document.get("realMultimodalCoverageRatio") or 0) == 1.0
        and int(document.get("visualChunkCount") or 0) >= expected
        and document.get("visualAnalysisStatus") == "completed"
    )
    if mode == "full_visual":
        passed = bool(
            passed
            and int(document.get("fallbackMineruAssetCount") or 0) == 0
            and int(document.get("failedMineruAssetCount") or 0) == 0
            and int(document.get("unprocessedMineruAssetCount") or 0) == 0
        )
    prefix = "SMART_MULTIMODAL_MANUAL" if mode == "smart_multimodal" else "FULL_VISUAL_MANUAL"
    return f"{prefix}_{'GO' if passed else 'NO_GO'}"


def retrieval_checks(document: dict[str, Any]) -> dict[str, Any]:
    from fastapi.testclient import TestClient

    from backend.app.data_store import load_document_chunks
    from backend.app.main import app

    chunks = [
        chunk
        for chunk in load_document_chunks()
        if chunk.get("documentId") == document.get("id") and chunk.get("origin") == "manual_visual_pipeline"
    ]
    pending_all = bool(chunks) and all(chunk.get("review_status") == "pending_review" for chunk in chunks)
    preview_chunk = next((chunk for chunk in chunks if chunk.get("previewUrl")), None)
    query_chunk = next(
        (
            chunk
            for chunk in chunks
            if chunk.get("semanticVerified") and (chunk.get("components") or chunk.get("operations"))
        ),
        preview_chunk,
    )
    client = TestClient(app)
    preview_ok = False
    if preview_chunk:
        preview = client.get(str(preview_chunk["previewUrl"]))
        preview_ok = preview.status_code == 200 and preview.headers.get("content-type", "").startswith(("image/jpeg", "image/png"))
    before_found = False
    after_found = False
    citation_fields = False
    if query_chunk:
        query = " ".join(
            [
                *[str(item) for item in query_chunk.get("components", [])[:3]],
                *[str(item) for item in query_chunk.get("operations", [])[:3]],
            ]
        ).strip() or str(query_chunk.get("visualSummary") or "")[:80]
        request = {
            "deviceModel": "摩托车",
            "faultText": query,
            "maintenanceLevel": "normal_repair",
            "inputType": "text",
            "topK": 10,
        }
        before = client.post("/api/search", json=request)
        before_items = before.json().get("data", {}).get("results", []) if before.status_code == 200 else []
        before_found = any(item.get("chunkId") == query_chunk.get("id") for item in before_items)
        review = client.patch(
            f"/api/knowledge/documents/{document['id']}/chunks/{query_chunk['id']}/review",
            json={"action": "approve", "reason": "isolated verification", "reviewer": "verification"},
        )
        if review.status_code == 200:
            after = client.post("/api/search", json=request)
            after_items = after.json().get("data", {}).get("results", []) if after.status_code == 200 else []
            match = next((item for item in after_items if item.get("chunkId") == query_chunk.get("id")), None)
            after_found = match is not None
            citation_fields = bool(
                match
                and match.get("page") is not None
                and match.get("previewUrl")
                and "semanticVerified" in match
            )
    return {
        "pendingReviewAll": pending_all,
        "previewUrlPresent": preview_chunk is not None,
        "controlledPreviewPassed": preview_ok,
        "unapprovedNotRetrievable": not before_found,
        "approvedRetrievable": after_found,
        "citationFieldsPreserved": citation_fields,
    }


def verify_mode(mode: str, manual_path: Path, sha: str) -> dict[str, Any]:
    from backend.app.data_store import load_document_chunks
    from backend.app.knowledge import ingest_knowledge_document_bytes
    from backend.app.multimodal_adapter import multimodal_operational_probe, multimodal_readiness
    from backend.app.pdf_renderer import renderer_operational_readiness

    if mode != "text_fast" and not multimodal_readiness()["ready"]:
        prefix = "SMART_MULTIMODAL_MANUAL" if mode == "smart_multimodal" else "FULL_VISUAL_MANUAL"
        return {"gitSha": sha, "mode": mode, "status": "not_run", "result": f"{prefix}_NO_GO"}
    if mode != "text_fast" and not renderer_operational_readiness()["ready"]:
        prefix = "SMART_MULTIMODAL_MANUAL" if mode == "smart_multimodal" else "FULL_VISUAL_MANUAL"
        return {"gitSha": sha, "mode": mode, "status": "not_run", "result": f"{prefix}_NO_GO"}
    if mode != "text_fast" and not multimodal_operational_probe()["probeOk"]:
        prefix = "SMART_MULTIMODAL_MANUAL" if mode == "smart_multimodal" else "FULL_VISUAL_MANUAL"
        return {"gitSha": sha, "mode": mode, "status": "not_run", "result": f"{prefix}_NO_GO"}
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix=f"manual-{mode}-", dir=ROOT / "tmp") as temp_dir:
        os.environ["APP_KNOWLEDGE_DIR"] = str(Path(temp_dir) / "knowledge")
        os.environ["APP_ENV"] = "test"
        os.environ["AUTH_MODE"] = "off"
        os.environ["ALLOW_INSECURE_AUTH_OFF"] = "true"
        document = ingest_knowledge_document_bytes(
            manual_path.read_bytes(),
            manual_path.name,
            "application/pdf",
            "official motorcycle manual",
            parser_mode=mode,
        )
        chunks = [
            chunk
            for chunk in load_document_chunks()
            if chunk.get("documentId") == document.get("id") and chunk.get("origin") == "manual_visual_pipeline"
        ]
        record = {
            "gitSha": sha,
            "mode": mode,
            "durationSeconds": round(time.monotonic() - started, 3),
            "pageCount": int(document.get("pageCount") or 0),
            "textChunkCount": int(document.get("textChunkCount") or 0),
            "parser": document.get("parser", ""),
            "mineruAttempted": bool(document.get("mineruAttempted")),
            "mineruSucceeded": bool(document.get("mineruSucceeded")),
            "parserFallback": bool(document.get("parserFallback")),
            "renderer": document.get("renderer", "unavailable"),
            "visualCandidatePages": int(document.get("visualCandidatePages") or 0),
            "visualPagesRendered": int(document.get("visualPagesRendered") or 0),
            "visualPagesOcrProcessed": int(document.get("visualPagesOcrProcessed") or 0),
            "visualPagesAnalyzed": int(document.get("visualPagesAnalyzed") or 0),
            "realMultimodalPages": int(document.get("realMultimodalPages") or 0),
            "fallbackVisualPages": int(document.get("fallbackVisualPages") or 0),
            "visualFailedPages": list(document.get("visualFailedPages") or []),
            "visualCoverageRatio": float(document.get("visualCoverageRatio") or 0),
            "realMultimodalCoverageRatio": float(document.get("realMultimodalCoverageRatio") or 0),
            "visualChunkCount": len(chunks),
            "realMultimodalMineruAssetCount": int(document.get("realMultimodalMineruAssetCount") or 0),
            "fallbackMineruAssetCount": int(document.get("fallbackMineruAssetCount") or 0),
            "failedMineruAssetCount": int(document.get("failedMineruAssetCount") or 0),
            "unprocessedMineruAssetCount": int(document.get("unprocessedMineruAssetCount") or 0),
            "status": document.get("visualAnalysisStatus", "not_requested"),
            "result": result_label(mode, document),
        }
        if mode == "full_visual":
            checks = retrieval_checks(document)
            retrieval_go = all(checks.values())
            record["result"] = (
                f"{record['result']};MULTIMODAL_RETRIEVAL_{'GO' if retrieval_go else 'NO_GO'}"
            )
        return record


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify full-page multimodal parsing with a real manual.")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--mode", choices=MODES)
    selection.add_argument("--all", action="store_true")
    return parser.parse_args()


def main() -> int:
    try:
        logging.disable(logging.CRITICAL)
        load_local_env()
        args = parse_args()
        manual_path = resolve_manual_path()
        sha = git_sha()
        modes = MODES if args.all else (args.mode,)
        results: list[dict[str, Any]] = []
        for mode in modes:
            try:
                results.append(verify_mode(mode, manual_path, sha))
            except Exception:
                prefix = {
                    "text_fast": "TEXT_FAST",
                    "smart_multimodal": "SMART_MULTIMODAL_MANUAL",
                    "full_visual": "FULL_VISUAL_MANUAL",
                }[mode]
                results.append(
                    {
                        "gitSha": sha,
                        "mode": mode,
                        "durationSeconds": 0.0,
                        "pageCount": 0,
                        "parser": "",
                        "mineruAttempted": False,
                        "mineruSucceeded": False,
                        "parserFallback": False,
                        "renderer": "unavailable",
                        "visualCandidatePages": 0,
                        "visualPagesRendered": 0,
                        "visualPagesOcrProcessed": 0,
                        "visualPagesAnalyzed": 0,
                        "realMultimodalPages": 0,
                        "fallbackVisualPages": 0,
                        "visualCoverageRatio": 0.0,
                        "realMultimodalCoverageRatio": 0.0,
                        "visualChunkCount": 0,
                        "status": "failed",
                        "result": f"{prefix}_NO_GO",
                    }
                )
        output_dir = ROOT / "tmp"
        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_path = output_dir / f"manual-multimodal-verify-{stamp}.json"
        output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"verification completed: {output_path.name}")
        for result in results:
            print(f"{result['mode']}: {result['result']}")
        return 0
    except Exception as exc:
        print(f"verification failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
