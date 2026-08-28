from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .data_store import chroma_dir, knowledge_dir
from .llm_adapter import _post_json
from .provider_policy import (
    configured_embedding_provider,
    key_configured,
    record_fallback,
    remote_api_disabled,
)
from .retrieval.qdrant_enhancer import qdrant_status, search_qdrant


logger = logging.getLogger(__name__)


COLLECTION_NAME_PREFIX = "repair_knowledge_chunks"
DEFAULT_DIMENSION = 384


def vector_store_enabled() -> bool:
    return vector_store_kind() in {"chroma", "json", "sqlite"}


def vector_store_kind() -> str:
    return os.getenv("RAG_VECTOR_STORE", "sqlite").strip().lower() or "sqlite"


def json_vector_index_path() -> Path:
    configured = os.getenv("APP_VECTOR_INDEX_PATH")
    return Path(configured) if configured else knowledge_dir() / "vector-index.json"


def sqlite_vector_index_path() -> Path:
    configured = os.getenv("APP_VECTOR_DB_PATH")
    return Path(configured) if configured else knowledge_dir() / "vector-index.sqlite3"


def sqlite_engine_kind() -> str:
    engine = os.getenv("RAG_VECTOR_SQLITE_ENGINE", "python_scan").strip().lower() or "python_scan"
    return engine if engine in {"python_scan", "sqlite_vec"} else "python_scan"


def vector_enhancer_kind() -> str:
    enhancer = os.getenv("RAG_VECTOR_ENHANCER", "off").strip().lower() or "off"
    return enhancer if enhancer in {"off", "chroma", "qdrant"} else "off"


def vector_fallback_local_enabled() -> bool:
    return os.getenv("RAG_VECTOR_FALLBACK_LOCAL", "on").strip().lower() not in {"0", "false", "no", "off"}


def embedding_dimension() -> int:
    return max(16, int(os.getenv("RAG_VECTOR_DIMENSION", str(DEFAULT_DIMENSION))))


def embedding_model() -> str:
    return os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small").strip() or "text-embedding-3-small"


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
            logger.warning("event=embedding_provider_fallback")
    return [hash_embed_text(text) for text in texts], "hash"


def chroma_collection(provider: str) -> Any | None:
    if vector_store_kind() != "chroma" and vector_enhancer_kind() != "chroma":
        return None
    try:
        import chromadb  # type: ignore[import-not-found]
    except Exception as exc:
        reason = f"Chroma is unavailable: {exc}"
        record_fallback("embedding", reason)
        logger.warning("event=chroma_import_unavailable")
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
        logger.warning("event=chroma_collection_unavailable")
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
        "section": chunk.get("section", ""),
        "chunkIndex": chunk.get("chunkIndex") or 0,
        "embeddingProvider": embedding_provider,
        "reviewStatus": chunk.get("review_status", "approved"),
        "version": chunk.get("version", 1),
        "deviceType": chunk.get("device_type") or chunk.get("deviceType") or "",
        "deviceModel": chunk.get("device_model") or chunk.get("deviceModel") or "",
        "component": chunk.get("component") or "",
        "faultType": chunk.get("fault_symptom") or chunk.get("faultType") or "",
    }
    if chunk.get("analysisProvider"):
        metadata["analysisProvider"] = chunk["analysisProvider"]
    return metadata


def load_json_vector_index() -> dict[str, Any]:
    path = json_vector_index_path()
    if not path.exists():
        return {"collections": {}, "updatedAt": None}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        backup = path.with_name(f"{path.name}.bak")
        if backup.exists():
            data = json.loads(backup.read_text(encoding="utf-8"))
        else:
            return {"collections": {}, "updatedAt": None}
    if not isinstance(data, dict):
        return {"collections": {}, "updatedAt": None}
    collections = data.get("collections")
    if not isinstance(collections, dict):
        data["collections"] = {}
    return data


def write_json_vector_index(index: dict[str, Any]) -> None:
    path = json_vector_index_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup = path.with_name(f"{path.name}.bak")
        backup.write_bytes(path.read_bytes())
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp_path, path)


def sqlite_connection() -> sqlite3.Connection:
    path = sqlite_vector_index_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS vector_chunks (
            collection TEXT NOT NULL,
            chunk_id TEXT NOT NULL,
            document_id TEXT NOT NULL,
            document TEXT NOT NULL,
            embedding_json TEXT NOT NULL,
            metadata_json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (collection, chunk_id)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_vector_chunks_document_id ON vector_chunks(document_id)")
    return conn


def sqlite_vec_status() -> dict[str, Any]:
    requested = sqlite_engine_kind()
    if requested != "sqlite_vec":
        return {
            "requested": requested,
            "effective": "python_scan",
            "available": False,
            "status": "python_scan",
            "reason": "RAG_VECTOR_SQLITE_ENGINE is python_scan.",
        }
    extension_path = os.getenv("SQLITE_VEC_EXTENSION_PATH", "").strip()
    try:
        with sqlite_connection() as conn:
            conn.enable_load_extension(True)
            if extension_path:
                conn.load_extension(extension_path)
            else:
                import sqlite_vec  # type: ignore[import-not-found]

                sqlite_vec.load(conn)
            version = conn.execute("select vec_version()").fetchone()[0]
            return {
                "requested": "sqlite_vec",
                "effective": "sqlite_vec",
                "available": True,
                "status": "available",
                "version": str(version),
                "reason": "",
            }
    except Exception as exc:
        reason = f"sqlite-vec unavailable, fallback to python_scan: {exc}"
        record_fallback("vector", reason)
        return {
            "requested": "sqlite_vec",
            "effective": "python_scan",
            "available": False,
            "status": "fallback",
            "reason": str(exc),
        }


def vector_backend_status() -> dict[str, Any]:
    kind = vector_store_kind()
    enhancer = vector_enhancer_kind()
    sqlite_status = sqlite_vec_status() if kind == "sqlite" else {
        "requested": "",
        "effective": "",
        "available": False,
        "status": "not_sqlite",
        "reason": "RAG_VECTOR_STORE is not sqlite.",
    }
    enhancer_status: dict[str, Any]
    if enhancer == "qdrant":
        enhancer_status = qdrant_status()
    elif enhancer == "chroma":
        enhancer_status = {
            "enabled": True,
            "kind": "chroma",
            "available": chroma_collection("hash") is not None,
            "status": "legacy_optional",
            "reason": "Chroma is configured as an optional enhancer.",
        }
    else:
        enhancer_status = {
            "enabled": False,
            "kind": "off",
            "available": False,
            "healthy": False,
            "status": "disabled",
            "reason": "RAG_VECTOR_ENHANCER is off.",
        }
    return {
        "store": kind,
        "enabled": vector_store_enabled(),
        "sqliteEngine": sqlite_status,
        "enhancer": {
            "requested": enhancer,
            **enhancer_status,
        },
        "fallbackLocal": vector_fallback_local_enabled(),
    }


def sync_sqlite_chunks(
    chunks: list[dict[str, Any]], documents: list[str], embeddings: list[list[float]], provider: str
) -> None:
    collection = collection_name(provider)
    updated_at = datetime.now(timezone.utc).isoformat()
    rows = [
        (
            collection,
            chunk["id"],
            str(chunk.get("documentId", "")),
            document,
            json.dumps(embedding, ensure_ascii=False),
            json.dumps(metadata_for_chunk(chunk, provider), ensure_ascii=False),
            updated_at,
        )
        for chunk, document, embedding in zip(chunks, documents, embeddings, strict=False)
    ]
    with sqlite_connection() as conn:
        conn.executemany(
            """
            INSERT INTO vector_chunks (
                collection, chunk_id, document_id, document, embedding_json, metadata_json, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(collection, chunk_id) DO UPDATE SET
                document_id=excluded.document_id,
                document=excluded.document,
                embedding_json=excluded.embedding_json,
                metadata_json=excluded.metadata_json,
                updated_at=excluded.updated_at
            """,
            rows,
        )


def sync_json_chunks(chunks: list[dict[str, Any]], documents: list[str], embeddings: list[list[float]], provider: str) -> None:
    index = load_json_vector_index()
    collections = index.setdefault("collections", {})
    collection = collections.setdefault(collection_name(provider), {"items": {}})
    items = collection.setdefault("items", {})
    for chunk, document, embedding in zip(chunks, documents, embeddings, strict=False):
        items[chunk["id"]] = {
            "document": document,
            "embedding": embedding,
            "metadata": metadata_for_chunk(chunk, provider),
        }
    index["updatedAt"] = datetime.now(timezone.utc).isoformat()
    write_json_vector_index(index)


def sync_chunks(chunks: list[dict[str, Any]]) -> None:
    chunks = [chunk for chunk in chunks if chunk.get("review_status", "approved") == "approved"]
    if not chunks:
        return
    documents = [chunk.get("content") or chunk.get("snippet", "") for chunk in chunks]
    embeddings, provider = embed_texts(documents)
    if vector_store_kind() == "sqlite":
        sync_sqlite_chunks(chunks, documents, embeddings, provider)
        return
    if vector_store_kind() == "json":
        sync_json_chunks(chunks, documents, embeddings, provider)
        return
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
    if vector_store_kind() == "sqlite":
        with sqlite_connection() as conn:
            conn.execute("DELETE FROM vector_chunks WHERE document_id = ?", (document_id,))
        return

    if vector_store_kind() == "json":
        index = load_json_vector_index()
        changed = False
        for collection in index.get("collections", {}).values():
            items = collection.get("items", {})
            for chunk_id in list(items):
                metadata = items[chunk_id].get("metadata", {})
                if metadata.get("documentId") == document_id:
                    del items[chunk_id]
                    changed = True
        if changed:
            index["updatedAt"] = datetime.now(timezone.utc).isoformat()
            write_json_vector_index(index)
        return

    for provider in ("hash", "openai"):
        collection = chroma_collection(provider)
        if collection is None:
            continue
        try:
            collection.delete(where={"documentId": document_id})
        except Exception as exc:
            reason = f"Chroma delete skipped for {provider}: {exc}"
            record_fallback("embedding", reason)
            logger.warning("event=chroma_delete_skipped")


def cosine_distance(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 1.0
    size = min(len(left), len(right))
    dot = sum(left[index] * right[index] for index in range(size))
    left_norm = math.sqrt(sum(value * value for value in left[:size]))
    right_norm = math.sqrt(sum(value * value for value in right[:size]))
    if not left_norm or not right_norm:
        return 1.0
    similarity = dot / (left_norm * right_norm)
    return max(0.0, min(2.0, 1.0 - similarity))


def item_from_vector_match(chunk_id: str, document: str, metadata: dict[str, Any], distance: float, provider: str) -> dict[str, Any] | None:
    if metadata.get("reviewStatus", "approved") != "approved":
        return None
    page = metadata.get("page") or None
    return {
        "id": metadata.get("chunkId") or chunk_id,
        "title": metadata.get("title", ""),
        "sourceType": metadata.get("sourceType", "document"),
        "sourceName": metadata.get("sourceName", ""),
        "snippet": metadata.get("snippet") or document[:160],
        "documentId": metadata.get("documentId", ""),
        "chunkId": metadata.get("chunkId") or chunk_id,
        "page": int(page) if str(page).isdigit() else None,
        "section": metadata.get("section", ""),
        "version": metadata.get("version", 1),
        "distance": float(distance),
        "embeddingProvider": metadata.get("embeddingProvider") or provider,
        "reviewStatus": metadata.get("reviewStatus", "approved"),
        "deviceType": metadata.get("deviceType", ""),
        "deviceModel": metadata.get("deviceModel", ""),
        "component": metadata.get("component", ""),
        "faultType": metadata.get("faultType", ""),
    }


def search_json_similar_chunks(query_embedding: list[float], provider: str, top_k: int) -> list[dict[str, Any]]:
    index = load_json_vector_index()
    collection = index.get("collections", {}).get(collection_name(provider), {})
    items = collection.get("items", {})
    scored: list[tuple[float, str, dict[str, Any]]] = []
    for chunk_id, record in items.items():
        embedding = record.get("embedding", [])
        if not isinstance(embedding, list):
            continue
        scored.append((cosine_distance(query_embedding, embedding), chunk_id, record))
    scored.sort(key=lambda item: item[0])

    results: list[dict[str, Any]] = []
    for distance, chunk_id, record in scored[: max(1, top_k)]:
        item = item_from_vector_match(
            chunk_id=chunk_id,
            document=str(record.get("document") or ""),
            metadata=record.get("metadata", {}),
            distance=distance,
            provider=provider,
        )
        if item:
            item["retrievalSource"] = "json"
            results.append(item)
    return results


def decode_vector(raw_value: str) -> list[float]:
    try:
        value = json.loads(raw_value)
    except json.JSONDecodeError:
        return []
    if not isinstance(value, list):
        return []
    return [float(item) for item in value if isinstance(item, (int, float))]


def decode_metadata(raw_value: str) -> dict[str, Any]:
    try:
        value = json.loads(raw_value)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def search_sqlite_similar_chunks(query_embedding: list[float], provider: str, top_k: int) -> list[dict[str, Any]]:
    collection = collection_name(provider)
    path = sqlite_vector_index_path()
    if not path.exists():
        return []

    scored: list[tuple[float, str, str, dict[str, Any]]] = []
    try:
        with sqlite_connection() as conn:
            rows = conn.execute(
                "SELECT chunk_id, document, embedding_json, metadata_json FROM vector_chunks WHERE collection = ?",
                (collection,),
            ).fetchall()
    except sqlite3.Error as exc:
        reason = f"SQLite vector query failed for {provider}: {exc}"
        record_fallback("embedding", reason)
        logger.warning("event=sqlite_vector_query_failed")
        return []

    for chunk_id, document, embedding_json, metadata_json in rows:
        embedding = decode_vector(str(embedding_json))
        if not embedding:
            continue
        scored.append((cosine_distance(query_embedding, embedding), str(chunk_id), str(document), decode_metadata(str(metadata_json))))
    scored.sort(key=lambda item: item[0])

    results: list[dict[str, Any]] = []
    for distance, chunk_id, document, metadata in scored[: max(1, top_k)]:
        item = item_from_vector_match(
            chunk_id=chunk_id,
            document=document,
            metadata=metadata,
            distance=distance,
            provider=provider,
        )
        if item:
            item["retrievalSource"] = "sqlite"
            results.append(item)
    return results


def local_sqlite_record_by_chunk_id(chunk_id: str, provider: str) -> tuple[str, dict[str, Any]] | None:
    path = sqlite_vector_index_path()
    if not path.exists() or not chunk_id:
        return None
    try:
        with sqlite_connection() as conn:
            row = conn.execute(
                "SELECT document, metadata_json FROM vector_chunks WHERE collection = ? AND chunk_id = ?",
                (collection_name(provider), chunk_id),
            ).fetchone()
    except sqlite3.Error:
        return None
    if not row:
        return None
    return str(row[0]), decode_metadata(str(row[1]))


def search_local_similar_chunks(query: str, top_k: int) -> list[dict[str, Any]]:
    if not query.strip():
        return []
    query_embeddings, provider = embed_texts([query])
    if vector_store_kind() == "sqlite":
        sqlite_vec = sqlite_vec_status()
        if sqlite_vec.get("requested") == "sqlite_vec" and sqlite_vec.get("effective") != "sqlite_vec":
            record_fallback("vector", f"sqlite-vec fallback to python_scan: {sqlite_vec.get('reason', '')}")
        return search_sqlite_similar_chunks(query_embeddings[0], provider, top_k)
    if vector_store_kind() == "json":
        return search_json_similar_chunks(query_embeddings[0], provider, top_k)
    collection = chroma_collection(provider)
    if collection is None:
        return []
    return search_chroma_similar_chunks(query_embeddings, provider, top_k, collection)


def qdrant_matches_to_local_items(matches: list[dict[str, Any]], provider: str, top_k: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for match in matches:
        chunk_id = str(match.get("chunkId") or "")
        record = local_sqlite_record_by_chunk_id(chunk_id, provider)
        if not record:
            continue
        document, metadata = record
        item = item_from_vector_match(
            chunk_id=chunk_id,
            document=document,
            metadata=metadata,
            distance=max(0.0, 1.0 - float(match.get("score") or 0)),
            provider=provider,
        )
        if not item:
            continue
        item["retrievalSource"] = "qdrant"
        item["qdrantRank"] = match.get("rank")
        item["qdrantScore"] = match.get("score")
        results.append(item)
        if len(results) >= top_k:
            break
    return results


def search_enhanced_similar_chunks(query: str, top_k: int) -> list[dict[str, Any]]:
    if not query.strip():
        return []
    try:
        query_embeddings, provider = embed_texts([query])
    except Exception as exc:
        reason = f"vector embedding failed: {exc}"
        record_fallback("vector", reason)
        return []

    local_results: list[dict[str, Any]] = []
    if vector_fallback_local_enabled():
        if vector_store_kind() == "sqlite":
            local_results = search_sqlite_similar_chunks(query_embeddings[0], provider, top_k)
        elif vector_store_kind() == "json":
            local_results = search_json_similar_chunks(query_embeddings[0], provider, top_k)

    enhancer = vector_enhancer_kind()
    if enhancer == "qdrant" and vector_store_kind() == "sqlite":
        qdrant_items = qdrant_matches_to_local_items(
            search_qdrant(query_embeddings[0], top_k, embedding_provider=provider),
            provider,
            top_k,
        )
        merged: dict[str, dict[str, Any]] = {item.get("chunkId") or item["id"]: item for item in local_results}
        for item in qdrant_items:
            key = item.get("chunkId") or item["id"]
            merged[key] = {**merged.get(key, {}), **item}
        return list(merged.values())[:top_k]

    if enhancer == "chroma":
        collection = chroma_collection(provider)
        chroma_items = search_chroma_similar_chunks(query_embeddings, provider, top_k, collection) if collection else []
        merged = {item.get("chunkId") or item["id"]: item for item in local_results}
        for item in chroma_items:
            merged.setdefault(item.get("chunkId") or item["id"], item)
        return list(merged.values())[:top_k]

    return local_results


def search_similar_chunks(query: str, top_k: int) -> list[dict[str, Any]]:
    if not query.strip():
        return []

    try:
        if vector_store_kind() in {"sqlite", "json"} or vector_enhancer_kind() != "off":
            return search_enhanced_similar_chunks(query, top_k)
        query_embeddings, provider = embed_texts([query])
        collection = chroma_collection(provider)
        if collection is None:
            return []
    except Exception as exc:
        reason = f"Vector query setup failed: {exc}"
        record_fallback("vector", reason)
        logger.warning("event=vector_query_setup_failed")
        return []

    return search_chroma_similar_chunks(query_embeddings, provider, top_k, collection)


def search_chroma_similar_chunks(query_embeddings: list[list[float]], provider: str, top_k: int, collection: Any) -> list[dict[str, Any]]:
    if collection is None:
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
        logger.warning("event=chroma_query_failed")
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
        item = item_from_vector_match(chunk_id, document, metadata, distance, provider)
        if not item:
            continue
        item["retrievalSource"] = "chroma"
        items.append(item)
    return items
