"""Legacy JSON/mock prototype smoke; never a production-readiness verdict."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SEED_DEVICE_MODEL = "\u53d1\u52a8\u673a-\u793a\u4f8b\u578b\u53f7 A"
SEED_FAULT_TEXT = "\u542f\u52a8\u56f0\u96be \u6020\u901f\u4e0d\u7a33"


def configure_runtime(temp_root: Path) -> None:
    examples_dir = temp_root / "examples"
    shutil.copytree(PROJECT_ROOT / "data" / "examples", examples_dir)

    os.environ["APP_EXAMPLES_DIR"] = str(examples_dir)
    os.environ["APP_UPLOAD_DIR"] = str(temp_root / "uploads")
    os.environ["APP_KNOWLEDGE_DIR"] = str(temp_root / "knowledge")
    os.environ["REMOTE_API_MODE"] = "off"
    os.environ["LLM_PROVIDER"] = "mock"
    os.environ["MULTIMODAL_PROVIDER"] = "mock"
    os.environ["OCR_PROVIDER"] = "mock"
    os.environ["MINERU_ENABLED"] = "false"
    os.environ["RAG_VECTOR_STORE"] = "off"
    os.environ["RAG_EMBEDDING_PROVIDER"] = "hash"
    os.environ["RAG_RERANK_PROVIDER"] = "heuristic"


def assert_success(response: Any, label: str) -> dict[str, Any]:
    if response.status_code < 200 or response.status_code >= 300:
        raise AssertionError(f"{label} returned HTTP {response.status_code}: {response.text}")
    payload = response.json()
    if not payload.get("success", False):
        raise AssertionError(f"{label} returned success=false: {payload}")
    return payload["data"]


def run_step(checks: list[dict[str, Any]], name: str, func: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    started = time.perf_counter()
    data = func()
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    checks.append({"name": name, "status": "passed", "durationMs": duration_ms, "data": data})
    return data


def main() -> int:
    print(
        "WARNING: legacy prototype offline smoke only; not production readiness.",
        file=sys.stderr,
    )
    started = time.perf_counter()
    checks: list[dict[str, Any]] = []
    sys.path.insert(0, str(PROJECT_ROOT))

    with tempfile.TemporaryDirectory(prefix="software-cup-readiness-") as temp_dir:
        configure_runtime(Path(temp_dir))

        from fastapi.testclient import TestClient

        from backend.app.main import app

        client = TestClient(app)

        run_step(
            checks,
            "health",
            lambda: assert_success(client.get("/api/health"), "health"),
        )

        def provider_status() -> dict[str, Any]:
            data = assert_success(client.get("/api/providers/status"), "provider status")
            system = data.get("system", {})
            if data.get("offlineFallback") is not True:
                raise AssertionError("readiness check must run with offline fallback enabled")
            if "knowledge" not in system or "parsing" not in system or "indexing" not in system:
                raise AssertionError("provider status must include system observability")
            return {
                "remoteApiMode": data.get("remoteApiMode"),
                "llm": data.get("llm", {}).get("effectiveProvider"),
                "systemKeys": sorted(system.keys()),
            }

        run_step(checks, "provider_status", provider_status)

        def async_parse_task() -> dict[str, Any]:
            queued = assert_success(
                client.post(
                    "/api/knowledge/documents/async",
                    files={
                        "file": (
                            "readiness-async.md",
                            b"readiness-async-doc-beta pending review safety checklist",
                            "text/markdown",
                        )
                    },
                    data={"source_name": "readiness async manual"},
                ),
                "submit async parse task",
            )
            task = assert_success(client.get(f"/api/knowledge/parse-tasks/{queued['id']}"), "get async parse task")
            if task.get("status") != "completed":
                raise AssertionError(f"async parse task should complete in readiness check, got {task.get('status')}")
            if task.get("documentStatus") != "pending_review":
                raise AssertionError("async parsed document should enter pending_review")
            return {
                "taskId": task.get("id"),
                "documentId": task.get("documentId"),
                "documentStatus": task.get("documentStatus"),
            }

        run_step(checks, "async_parse_task", async_parse_task)

        def search_seed() -> dict[str, Any]:
            data = assert_success(
                client.post(
                    "/api/search",
                    json={
                        "deviceModel": SEED_DEVICE_MODEL,
                        "faultText": SEED_FAULT_TEXT,
                        "inputType": "text",
                        "topK": 5,
                    },
                ),
                "seed search",
            )
            if not data["results"]:
                raise AssertionError("seed search returned no results")
            return {"resultCount": len(data["results"]), "topSourceType": data["results"][0]["sourceType"]}

        run_step(checks, "search_seed", search_seed)

        def rag_answer() -> dict[str, Any]:
            data = assert_success(
                client.post(
                    "/api/rag/answer",
                    json={
                        "deviceModel": SEED_DEVICE_MODEL,
                        "faultText": SEED_FAULT_TEXT,
                        "topK": 3,
                        "provider": "mock",
                    },
                ),
                "rag answer",
            )
            if not data.get("citations"):
                raise AssertionError("rag answer returned no citations")
            return {
                "provider": data.get("provider"),
                "citationCount": len(data.get("citations", [])),
                "hasEvidencePack": bool(data.get("evidencePack")),
                "hasSafetyRules": bool(data.get("safetyRules")),
            }

        run_step(checks, "rag_answer", rag_answer)

        def case_review_roundtrip() -> dict[str, Any]:
            created = assert_success(
                client.post(
                    "/api/cases",
                    json={
                        "deviceModel": "readiness-model",
                        "faultText": "readiness-case-alpha intermittent shutdown",
                        "cause": "readiness-case-alpha cause",
                        "solution": "readiness-case-alpha solution",
                        "result": "readiness-case-alpha resolved",
                        "tags": ["readiness-case-alpha"],
                    },
                ),
                "create case",
            )
            reviewed = assert_success(
                client.patch(
                    f"/api/cases/{created['id']}/review",
                    json={
                        "action": "approve",
                        "reviewNote": "readiness check approval",
                        "reviewer": "readiness",
                        "normalizedTags": ["readiness-case-alpha"],
                    },
                ),
                "review case",
            )
            search = assert_success(
                client.post(
                    "/api/search",
                    json={
                        "deviceModel": "readiness-model",
                        "faultText": "readiness-case-alpha",
                        "inputType": "text",
                        "topK": 5,
                    },
                ),
                "search approved case",
            )
            if not any(item.get("id") == created["id"] for item in search["results"]):
                raise AssertionError("approved case was not retrievable")
            return {"caseId": created["id"], "status": reviewed["status"]}

        run_step(checks, "case_review_roundtrip", case_review_roundtrip)

        def knowledge_chunk_lifecycle() -> dict[str, Any]:
            uploaded = assert_success(
                client.post(
                    "/api/knowledge/documents",
                    files={
                        "file": (
                            "readiness-manual.md",
                            b"readiness-doc-alpha approved safety inspection and acceptance criteria",
                            "text/markdown",
                        )
                    },
                    data={"source_name": "readiness manual"},
                ),
                "upload knowledge document",
            )
            if uploaded["status"] != "pending_review":
                raise AssertionError(f"uploaded document should be pending_review, got {uploaded['status']}")
            chunks = assert_success(
                client.get(f"/api/knowledge/documents/{uploaded['id']}/chunks"),
                "list document chunks",
            )
            chunk_id = chunks["items"][0]["id"]
            review_items = assert_success(client.get("/api/review/items?status=pending_review"), "review items")
            if not any(item.get("chunkId") == chunk_id for item in review_items["items"]):
                raise AssertionError("pending knowledge chunk was not visible in review workbench")
            approved = assert_success(
                client.patch(
                    f"/api/knowledge/documents/{uploaded['id']}/chunks/{chunk_id}/review",
                    json={"action": "approve", "reason": "readiness approved", "reviewer": "readiness"},
                ),
                "approve knowledge chunk",
            )
            search = assert_success(
                client.post(
                    "/api/search",
                    json={"deviceModel": "", "faultText": "readiness-doc-alpha", "inputType": "text", "topK": 5},
                ),
                "search approved knowledge chunk",
            )
            if not any(item.get("chunkId") == chunk_id for item in search["results"]):
                raise AssertionError("approved knowledge chunk was not retrievable")
            deprecated = assert_success(
                client.patch(
                    f"/api/knowledge/documents/{uploaded['id']}/chunks/{chunk_id}/status",
                    json={"status": "deprecated", "reason": "readiness deprecated", "reviewer": "readiness"},
                ),
                "deprecate knowledge chunk",
            )
            search_after = assert_success(
                client.post(
                    "/api/search",
                    json={"deviceModel": "", "faultText": "readiness-doc-alpha", "inputType": "text", "topK": 5},
                ),
                "search deprecated knowledge chunk",
            )
            if any(item.get("chunkId") == chunk_id for item in search_after["results"]):
                raise AssertionError("deprecated knowledge chunk remained retrievable")
            return {
                "documentId": uploaded["id"],
                "chunkId": chunk_id,
                "approvedStatus": approved["chunk"]["review_status"],
                "finalStatus": deprecated["chunk"]["review_status"],
            }

        run_step(checks, "knowledge_chunk_lifecycle", knowledge_chunk_lifecycle)

    report = {
        "success": True,
        "scope": "legacy-prototype-offline-smoke",
        "productionReady": False,
        "durationMs": round((time.perf_counter() - started) * 1000, 2),
        "checks": checks,
    }
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
