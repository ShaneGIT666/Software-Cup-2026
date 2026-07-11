from __future__ import annotations

from typing import Any

from .. import vector_store
from .keyword_retriever import confidence_from_score
from .models import QueryContext, RetrievalHit


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

    candidate_k = context.candidate_k or context.top_k
    for index, vector_match in enumerate(vector_store.search_similar_chunks(context.vector_query, candidate_k), start=1):
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
                review_status="approved",
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
