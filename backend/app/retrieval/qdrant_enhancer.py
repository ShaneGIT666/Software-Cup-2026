from __future__ import annotations

import os
from typing import Any

import httpx

from ..llm_adapter import _post_json
from ..provider_policy import record_fallback


def qdrant_enabled() -> bool:
    return os.getenv("RAG_VECTOR_ENHANCER", "off").strip().lower() == "qdrant"


def qdrant_url() -> str:
    return os.getenv("RAG_QDRANT_URL", "http://127.0.0.1:6333").rstrip("/")


def qdrant_collection() -> str:
    return os.getenv("RAG_QDRANT_COLLECTION", "repair_knowledge_chunks").strip() or "repair_knowledge_chunks"


def qdrant_timeout_seconds() -> float:
    return max(0.2, float(os.getenv("RAG_QDRANT_TIMEOUT_SECONDS", "3")))


def qdrant_status() -> dict[str, Any]:
    if not qdrant_enabled():
        return {
            "enabled": False,
            "available": False,
            "healthy": False,
            "status": "disabled",
            "url": qdrant_url(),
            "collection": qdrant_collection(),
            "reason": "RAG_VECTOR_ENHANCER is not qdrant.",
        }
    try:
        response = httpx.get(f"{qdrant_url()}/collections/{qdrant_collection()}", timeout=qdrant_timeout_seconds())
        response.raise_for_status()
        payload = response.json()
        return {
            "enabled": True,
            "available": True,
            "healthy": True,
            "status": "healthy",
            "url": qdrant_url(),
            "collection": qdrant_collection(),
            "responseStatus": payload.get("status", ""),
            "reason": "",
        }
    except Exception as exc:
        reason = f"Qdrant enhancer unavailable: {exc}"
        record_fallback("vector", reason)
        return {
            "enabled": True,
            "available": False,
            "healthy": False,
            "status": "unavailable",
            "url": qdrant_url(),
            "collection": qdrant_collection(),
            "reason": str(exc),
        }


def search_qdrant(
    query_embedding: list[float],
    top_k: int,
    *,
    embedding_provider: str,
) -> list[dict[str, Any]]:
    if not qdrant_enabled() or not query_embedding:
        return []
    try:
        payload = _post_json(
            f"{qdrant_url()}/collections/{qdrant_collection()}/points/search",
            headers={"Content-Type": "application/json"},
            payload={
                "vector": query_embedding,
                "limit": max(1, top_k),
                "with_payload": True,
                "params": {"exact": False},
            },
            timeout=qdrant_timeout_seconds(),
        )
    except Exception as exc:
        reason = f"Qdrant enhancer query failed, fallback to local vector store: {exc}"
        record_fallback("vector", reason)
        return []

    raw_results = payload.get("result", [])
    if not isinstance(raw_results, list):
        return []
    matches: list[dict[str, Any]] = []
    for index, item in enumerate(raw_results, start=1):
        if not isinstance(item, dict):
            continue
        point_payload = item.get("payload") or {}
        if not isinstance(point_payload, dict):
            continue
        if str(point_payload.get("reviewStatus", "approved")) != "approved":
            continue
        matches.append(
            {
                "rank": index,
                "score": float(item.get("score") or 0),
                "chunkId": point_payload.get("chunkId") or point_payload.get("chunk_id"),
                "documentId": point_payload.get("documentId") or point_payload.get("document_id"),
                "payload": point_payload,
                "embeddingProvider": point_payload.get("embeddingProvider") or embedding_provider,
            }
        )
    return matches
