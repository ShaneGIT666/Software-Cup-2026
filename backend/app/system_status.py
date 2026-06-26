from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import importlib.util
import sqlite3
from typing import Any, Callable

from .data_store import (
    chroma_dir,
    load_cases,
    load_document_chunks,
    load_documents,
    load_knowledge_revisions,
    load_parse_tasks,
    load_review_events,
    load_seed_data,
)
from .mineru_adapter import mineru_available, mineru_enabled, mineru_timeout_seconds
from .vector_store import (
    json_vector_index_path,
    sqlite_vector_index_path,
    vector_backend_status,
    vector_store_enabled,
    vector_store_kind,
)


REVIEW_STATUSES = ("draft", "pending_review", "approved", "rejected", "deprecated", "replaced")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def safe_load_list(loader: Callable[[], list[dict[str, Any]]], label: str, warnings: list[str]) -> list[dict[str, Any]]:
    try:
        return loader()
    except Exception as exc:
        warnings.append(f"{label} unavailable: {exc}")
        return []


def safe_seed_data(warnings: list[str]) -> dict[str, list[dict[str, Any]]]:
    try:
        return load_seed_data()
    except Exception as exc:
        warnings.append(f"seed data unavailable: {exc}")
        return {"devices": [], "manuals": [], "cases": [], "workflows": []}


def count_statuses(items: list[dict[str, Any]], key: str, default: str = "approved") -> dict[str, int]:
    counts = Counter(str(item.get(key) or default) for item in items)
    for status in REVIEW_STATUSES:
        counts.setdefault(status, 0)
    return dict(sorted(counts.items()))


def count_values(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(item.get(key) or "unknown") for item in items).items()))


def latest_value(values: list[str]) -> str | None:
    clean_values = [value for value in values if value]
    return max(clean_values) if clean_values else None


def latest_parse_task(documents: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not documents:
        return None
    document = max(
        documents,
        key=lambda item: latest_value(
            [
                str(item.get("analysis", {}).get("analyzedAt") or ""),
                str(item.get("latestRevisionAt") or ""),
                str(item.get("uploadedAt") or ""),
            ]
        )
        or "",
    )
    analysis = document.get("analysis") if isinstance(document.get("analysis"), dict) else {}
    return {
        "documentId": document.get("id", ""),
        "fileName": document.get("fileName", ""),
        "status": document.get("status", ""),
        "parser": document.get("parser", ""),
        "parserFallback": bool(document.get("parserFallback", False)),
        "parserFallbackReason": document.get("parserFallbackReason", ""),
        "uploadedAt": document.get("uploadedAt", ""),
        "analyzedAt": analysis.get("analyzedAt", ""),
        "chunkCount": int(document.get("chunkCount") or 0),
        "pendingReviewCount": int(document.get("pendingReviewCount") or 0),
    }


def latest_async_parse_task(tasks: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not tasks:
        return None
    task = max(
        tasks,
        key=lambda item: latest_value(
            [
                str(item.get("completedAt") or ""),
                str(item.get("startedAt") or ""),
                str(item.get("updatedAt") or ""),
                str(item.get("createdAt") or ""),
            ]
        )
        or "",
    )
    return {
        "taskId": task.get("id", ""),
        "type": task.get("type", ""),
        "status": task.get("status", ""),
        "fileName": task.get("fileName", ""),
        "sourceName": task.get("sourceName", ""),
        "documentId": task.get("documentId"),
        "createdAt": task.get("createdAt", ""),
        "startedAt": task.get("startedAt", ""),
        "completedAt": task.get("completedAt", ""),
        "error": task.get("error", ""),
    }


def index_activity(documents: list[dict[str, Any]], chunks: list[dict[str, Any]]) -> dict[str, Any]:
    explicit_candidates: list[str] = []
    inferred_candidates: list[str] = []
    for document in documents:
        for key in ("latestIndexedAt", "indexedAt"):
            if document.get(key):
                explicit_candidates.append(str(document[key]))
        for key in ("latestRevisionAt", "uploadedAt"):
            if document.get(key):
                inferred_candidates.append(str(document[key]))

    for chunk in chunks:
        if str(chunk.get("review_status") or "approved") != "approved":
            continue
        for key in ("indexedAt", "updatedAt", "updated_at", "created_at", "createdAt"):
            if chunk.get(key):
                inferred_candidates.append(str(chunk[key]))

    latest_explicit = latest_value(explicit_candidates)
    return {
        "latestIndexTime": latest_explicit,
        "latestKnownIndexActivityAt": latest_value(explicit_candidates + inferred_candidates),
        "unavailableReason": ""
        if latest_explicit
        else "当前向量同步未持久化显式索引时间，latestKnownIndexActivityAt 由 approved 片段或 revision 时间推断。",
    }


def mineru_status() -> dict[str, Any]:
    enabled = mineru_enabled()
    try:
        available = mineru_available()
    except Exception:
        available = False
    if not enabled:
        status = "disabled"
    elif available:
        status = "available"
    else:
        status = "fallback"
    return {
        "enabled": enabled,
        "available": available,
        "status": status,
        "timeoutSeconds": mineru_timeout_seconds(),
        "fallbackEnabled": not enabled or not available,
    }


def chroma_status() -> dict[str, Any]:
    enabled = vector_store_enabled()
    kind = vector_store_kind()
    if kind == "sqlite":
        path = sqlite_vector_index_path()
    elif kind == "json":
        path = json_vector_index_path()
    else:
        path = chroma_dir()
    if not enabled:
        return {
            "enabled": False,
            "available": False,
            "healthy": False,
            "status": "disabled",
            "path": str(path),
            "collectionCount": None,
            "reason": "RAG_VECTOR_STORE is off.",
        }

    if kind == "json":
        if not path.exists():
            return {
                "enabled": True,
                "available": True,
                "healthy": True,
                "status": "json_available_not_initialized",
                "path": str(path),
                "collectionCount": 0,
                "reason": "Pure Python JSON vector index is enabled, but no approved chunks have been synced yet.",
            }
        try:
            import json

            data = json.loads(path.read_text(encoding="utf-8"))
            collections = data.get("collections", {})
            return {
                "enabled": True,
                "available": True,
                "healthy": True,
                "status": "json_healthy",
                "path": str(path),
                "collectionCount": len(collections) if isinstance(collections, dict) else None,
                "reason": "",
            }
        except Exception as exc:
            return {
                "enabled": True,
                "available": True,
                "healthy": False,
                "status": "json_unhealthy",
                "path": str(path),
                "collectionCount": None,
                "reason": str(exc),
            }

    if kind == "sqlite":
        if not path.exists():
            return {
                "enabled": True,
                "available": True,
                "healthy": True,
                "status": "sqlite_available_not_initialized",
                "path": str(path),
                "collectionCount": 0,
                "itemCount": 0,
                "reason": "SQLite vector index is enabled, but no approved chunks have been synced yet.",
            }
        try:
            with sqlite3.connect(path) as conn:
                collection_count = conn.execute(
                    "SELECT COUNT(DISTINCT collection) FROM vector_chunks"
                ).fetchone()[0]
                item_count = conn.execute("SELECT COUNT(*) FROM vector_chunks").fetchone()[0]
            return {
                "enabled": True,
                "available": True,
                "healthy": True,
                "status": "sqlite_healthy",
                "path": str(path),
                "collectionCount": int(collection_count),
                "itemCount": int(item_count),
                "reason": "",
            }
        except Exception as exc:
            return {
                "enabled": True,
                "available": True,
                "healthy": False,
                "status": "sqlite_unhealthy",
                "path": str(path),
                "collectionCount": None,
                "itemCount": None,
                "reason": str(exc),
            }

    if importlib.util.find_spec("chromadb") is None:
        return {
            "enabled": True,
            "available": False,
            "healthy": False,
            "status": "unavailable",
            "path": str(path),
            "collectionCount": None,
            "reason": "chromadb package is not installed.",
        }

    if not path.exists():
        return {
            "enabled": True,
            "available": True,
            "healthy": True,
            "status": "available_not_initialized",
            "path": str(path),
            "collectionCount": 0,
            "reason": "Chroma package is installed, but the persistent directory has not been created yet.",
        }

    try:
        import chromadb  # type: ignore[import-not-found]

        client = chromadb.PersistentClient(path=str(path))
        collections = client.list_collections()
        return {
            "enabled": True,
            "available": True,
            "healthy": True,
            "status": "healthy",
            "path": str(path),
            "collectionCount": len(collections),
            "reason": "",
        }
    except Exception as exc:
        return {
            "enabled": True,
            "available": True,
            "healthy": False,
            "status": "unhealthy",
            "path": str(path),
            "collectionCount": None,
            "reason": str(exc),
        }


def build_system_status() -> dict[str, Any]:
    warnings: list[str] = []
    seed_data = safe_seed_data(warnings)
    documents = safe_load_list(load_documents, "knowledge documents", warnings)
    chunks = safe_load_list(load_document_chunks, "knowledge chunks", warnings)
    revisions = safe_load_list(load_knowledge_revisions, "knowledge revisions", warnings)
    review_events = safe_load_list(load_review_events, "review events", warnings)
    parse_tasks = safe_load_list(load_parse_tasks, "parse tasks", warnings)
    cases = safe_load_list(load_cases, "repair cases", warnings) or seed_data.get("cases", [])

    chunk_status_counts = count_statuses(chunks, "review_status")
    case_status_counts = count_statuses(cases, "status")
    document_status_counts = count_statuses(documents, "status", default="unknown")
    approved_chunks = chunk_status_counts.get("approved", 0)
    approved_cases = case_status_counts.get("approved", 0)

    parser_fallback_count = sum(1 for document in documents if document.get("parserFallback"))
    pending_documents = sum(1 for document in documents if document.get("status") == "pending_review")
    pending_cases = case_status_counts.get("pending_review", 0)

    return {
        "generatedAt": utc_now(),
        "knowledge": {
            "deviceCount": len(seed_data.get("devices", [])),
            "manualCount": len(seed_data.get("manuals", [])),
            "workflowCount": len(seed_data.get("workflows", [])),
            "caseCount": len(cases),
            "documentCount": len(documents),
            "chunkCount": len(chunks),
            "approvedChunkCount": approved_chunks,
            "retrievableSourceCount": len(seed_data.get("manuals", [])) + approved_cases + approved_chunks,
            "pendingReviewCount": chunk_status_counts.get("pending_review", 0) + pending_documents + pending_cases,
            "chunkStatusCounts": chunk_status_counts,
            "caseStatusCounts": case_status_counts,
            "documentStatusCounts": document_status_counts,
            "revisionCount": len(revisions),
            "reviewEventCount": len(review_events),
        },
        "indexing": {
            **index_activity(documents, chunks),
            "vector": vector_backend_status(),
            "chroma": chroma_status(),
        },
        "parsing": {
            "mineru": mineru_status(),
            "latestTask": latest_parse_task(documents),
            "latestAsyncTask": latest_async_parse_task(parse_tasks),
            "asyncTaskCount": len(parse_tasks),
            "asyncTaskStatusCounts": count_values(parse_tasks, "status"),
            "parserFallbackCount": parser_fallback_count,
        },
        "fallback": {
            "enabled": True,
            "parserFallbackCount": parser_fallback_count,
            "vectorFallbackEnabled": True,
            "chromaFallbackEnabled": True,
            "llmFallbackEnabled": True,
            "ocrFallbackEnabled": True,
        },
        "warnings": warnings,
    }
