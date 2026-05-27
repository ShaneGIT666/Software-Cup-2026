from __future__ import annotations

import hashlib
import logging
import math
import os
import re
from typing import Any

from .data_store import chroma_dir
from .llm_adapter import _post_json
from .provider_policy import (
    configured_embedding_provider,
    key_configured,
    record_fallback,
    remote_api_disabled,
)


logger = logging.getLogger(__name__)


COLLECTION_NAME_PREFIX = "repair_knowledge_chunks"
DEFAULT_DIMENSION = 384


def vector_store_enabled() -> bool:
    return os.getenv("RAG_VECTOR_STORE", "off").strip().lower() == "chroma"


def embedding_dimension() -> int:
    return max(16, int(os.getenv("RAG_VECTOR_DIMENSION", str(DEFAULT_DIMENSION))))


def embedding_model() -> str:
    return os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-v3").strip() or "text-embedding-v3"


def embedding_api_style() -> str:
    return os.getenv("OPENAI_EMBEDDING_API_STYLE", "openai_compatible").strip().lower() or "openai_compatible"


def collection_name(provider: str) -> str:
    if provider == "openai":
        suffix = re.sub(r"[^a-zA-Z0-9_]+", "_", embedding_model()).strip("_").lower()
        return f"{COLLECTION_NAME_PREFIX}_openai_{suffix[:32] or 'model'}"
    return f"{COLLECTION_NAME_PREFIX}_hash"


def tokenize_for_embedding(text: str) -> list[str]:
    normalized = "".join(char.lower() if not char.isspace() else " " for char in text)
    words = [part for part in normalized.replace("\n", " ").split(" ") if part]
    grams = []
    for word in words:
        if len(word) <= 2:
            grams.append(word)
        else:
            grams.extend(word[index : index + 2] for index in range(len(word) - 1))
    return grams or [normalized[:32]]


def hash_embed_text(text: str) -> list[float]:
    dimension = embedding_dimension()
    vector = [0.0] * dimension
    for token in tokenize_for_embedding(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimension
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign

    norm = math.sqrt(sum(value * value for value in vector))
    if not norm:
        return vector
    return [round(value / norm, 6) for value in vector]


def embed_text(text: str) -> list[float]:
    return hash_embed_text(text)


def openai_embed_texts(texts: list[str]) -> list[list[float]]:
    if remote_api_disabled():
        raise RuntimeError("REMOTE_API_MODE=off")
    if not key_configured("openai"):
        raise RuntimeError("OPENAI_API_KEY is not configured")

    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    timeout = float(os.getenv("EMBEDDING_TIMEOUT_SECONDS", os.getenv("LLM_TIMEOUT_SECONDS", "20")))
    payload = _post_json(
        f"{base_url}/embeddings",
        headers={
            "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY', '')}",
            "Content-Type": "application/json",
        },
        payload={"model": embedding_model(), "input": texts},
        timeout=timeout,
    )
    data = payload.get("data", [])
    vectors = [item.get("embedding", []) for item in data if isinstance(item, dict)]
    if len(vectors) != len(texts) or any(not vector for vector in vectors):
        raise RuntimeError("embedding provider returned an invalid response")
    return vectors


def embed_texts(texts: list[str]) -> tuple[list[list[float]], str]:
    provider = configured_embedding_provider()
    if provider == "openai":
        try:
            return openai_embed_texts(texts), "openai"
        except Exception as exc:
            reason = f"openai embedding fallback to hash: {exc}"
            record_fallback("embedding", reason)
            logger.warning(reason)
    return [hash_embed_text(text) for text in texts], "hash"


def chroma_collection(provider: str) -> Any | None:
    if not vector_store_enabled():
        return None
    try:
        import chromadb  # type: ignore[import-not-found]
    except Exception as exc:
        reason = f"Chroma is unavailable: {exc}"
        record_fallback("embedding", reason)
        logger.warning(reason)
        return None

    try:
        path = chroma_dir()
        path.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(path))
        return client.get_or_create_collection(
            name=collection_name(provider),
            metadata={"hnsw:space": "cosine"},
        )
    except Exception as exc:
        reason = f"Chroma collection unavailable for {provider}: {exc}"
        record_fallback("embedding", reason)
        logger.warning(reason)
        return None


def metadata_for_chunk(chunk: dict[str, Any], embedding_provider: str) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "chunkId": chunk["id"],
        "documentId": chunk.get("documentId", ""),
        "title": chunk.get("title", ""),
        "sourceType": chunk.get("sourceType", "document"),
        "sourceName": chunk.get("sourceName", ""),
        "snippet": chunk.get("snippet", ""),
        "page": chunk.get("page") or "",
        "chunkIndex": chunk.get("chunkIndex") or 0,
        "embeddingProvider": embedding_provider,
    }
    if chunk.get("analysisProvider"):
        metadata["analysisProvider"] = chunk["analysisProvider"]
    return metadata


def sync_chunks(chunks: list[dict[str, Any]]) -> None:
    if not chunks:
        return
    documents = [chunk.get("content") or chunk.get("snippet", "") for chunk in chunks]
    embeddings, provider = embed_texts(documents)
    collection = chroma_collection(provider)
    if collection is None:
        return

    ids = [chunk["id"] for chunk in chunks]
    collection.upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=[metadata_for_chunk(chunk, provider) for chunk in chunks],
    )


def delete_document(document_id: str) -> None:
    for provider in ("hash", "openai"):
        collection = chroma_collection(provider)
        if collection is None:
            continue
        try:
            collection.delete(where={"documentId": document_id})
        except Exception as exc:
            reason = f"Chroma delete skipped for {provider}: {exc}"
            record_fallback("embedding", reason)
            logger.warning(reason)


def search_similar_chunks(query: str, top_k: int) -> list[dict[str, Any]]:
    if not query.strip():
        return []

    try:
        query_embeddings, provider = embed_texts([query])
        collection = chroma_collection(provider)
        if collection is None:
            return []
    except Exception as exc:
        reason = f"Chroma query setup failed: {exc}"
        record_fallback("embedding", reason)
        logger.warning(reason)
        return []

    try:
        result = collection.query(
            query_embeddings=query_embeddings,
            n_results=max(1, top_k),
            include=["documents", "metadatas", "distances"],
        )
    except Exception as exc:
        reason = f"Chroma query failed for {provider}: {exc}"
        record_fallback("embedding", reason)
        logger.warning(reason)
        return []

    ids = result.get("ids", [[]])[0]
    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]

    items: list[dict[str, Any]] = []
    for index, chunk_id in enumerate(ids):
        metadata = metadatas[index] if index < len(metadatas) and metadatas[index] else {}
        document = documents[index] if index < len(documents) else ""
        distance = distances[index] if index < len(distances) else 1.0
        page = metadata.get("page") or None
        items.append(
            {
                "id": metadata.get("chunkId") or chunk_id,
                "title": metadata.get("title", ""),
                "sourceType": metadata.get("sourceType", "document"),
                "sourceName": metadata.get("sourceName", ""),
                "snippet": metadata.get("snippet") or document[:160],
                "documentId": metadata.get("documentId", ""),
                "chunkId": metadata.get("chunkId") or chunk_id,
                "page": int(page) if str(page).isdigit() else None,
                "distance": float(distance),
                "embeddingProvider": metadata.get("embeddingProvider") or provider,
            }
        )
    return items
