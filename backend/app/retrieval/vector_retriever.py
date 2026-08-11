from __future__ import annotations

from typing import Any

from .. import vector_store
from ..data_store import load_document_chunks
from .keyword_retriever import confidence_from_score
from .models import QueryContext, RetrievalHit


_OVERSAMPLE_FACTOR = 3
_MAX_RETRIEVAL_POOL = 100


def vector_retrieval_pool_size(candidate_k: int) -> int:
    return min(_MAX_RETRIEVAL_POOL, max(candidate_k, candidate_k * _OVERSAMPLE_FACTOR))


def vector_score_breakdown(distance: float, embedding_provider: str, retrieval_source: str) -> dict[str, Any]:
    similarity = max(0.0, min(1.0, 1.0 - distance))
    score = max(1, round(similarity * 20))
    return {
        "score": score,
        "sourceType": "document",
        "sourceWeight": 2,
        "phraseBonus": 0,
        "fieldMatches": [
            {
                "field": "vector",
                "terms": [embedding_provider],
                "weight": 1,
                "score": score,
            }
        ],
        "vectorDistance": round(distance, 6),
        "embeddingProvider": embedding_provider,
        "retrievalSource": retrieval_source,
    }


def retrieve_vector_hits(context: QueryContext) -> list[RetrievalHit]:
    hits: list[RetrievalHit] = []
    if not context.vector_query:
        return hits

    # Legacy vector indexes may not contain the latest device and review metadata.
    # Hydrating from the authoritative chunk store keeps vector recall subject to the
    # same approval and device-model filters as keyword recall.
    chunks_by_id = {str(chunk.get("id")): chunk for chunk in load_document_chunks()}
    vector_matches = vector_store.search_similar_chunks(
        context.vector_query,
        vector_retrieval_pool_size(context.candidate_k),
    )
    for index, vector_match in enumerate(vector_matches, start=1):
        chunk = chunks_by_id.get(str(vector_match.get("chunkId") or vector_match.get("id")), {})
        embedding_provider = vector_match.get("embeddingProvider", "hash")
        retrieval_source = str(vector_match.get("retrievalSource") or vector_store.vector_store_kind())
        breakdown = vector_score_breakdown(vector_match.get("distance", 1.0), embedding_provider, retrieval_source)
        recall_label = "real embedding vector recall" if embedding_provider == "openai" else "hash fallback vector recall"
        source_label = "Chroma" if retrieval_source == "chroma" else retrieval_source
        score = float(breakdown["score"])
        source_retrievers = ["vector"]
        if retrieval_source != "vector":
            source_retrievers.append(retrieval_source)
        hits.append(
            RetrievalHit(
                id=vector_match["id"],
                title=vector_match["title"],
                content=vector_match.get("snippet", ""),
                source_id=vector_match.get("chunkId") or vector_match["id"],
                source_name=vector_match["sourceName"],
                source_type="document",
                confidence=confidence_from_score(breakdown["score"], 0.9),
                snippet=vector_match["snippet"],
                page=vector_match.get("page"),
                section=vector_match.get("section"),
                document_id=vector_match.get("documentId"),
                chunk_id=vector_match.get("chunkId"),
                matched_terms=[embedding_provider],
                reason=f"{source_label} {recall_label}, distance={breakdown['vectorDistance']}",
                score_breakdown=breakdown,
                device_type=chunk.get("device_type") or chunk.get("deviceType") or vector_match.get("deviceType"),
                device_model=chunk.get("device_model") or chunk.get("deviceModel") or vector_match.get("deviceModel"),
                component=chunk.get("component") or vector_match.get("component"),
                fault_type=chunk.get("fault_symptom") or chunk.get("faultType") or vector_match.get("faultType"),
                review_status=(
                    chunk.get("review_status", "approved")
                    if chunk
                    else vector_match.get("reviewStatus", "approved")
                ),
                vector_rank=index,
                qdrant_rank=vector_match.get("qdrantRank"),
                vector_score=score,
                qdrant_score=vector_match.get("qdrantScore"),
                matched_fields=["vector", retrieval_source],
                retrieval_source=retrieval_source,
                source_retrievers=source_retrievers,
            )
        )
    return hits
