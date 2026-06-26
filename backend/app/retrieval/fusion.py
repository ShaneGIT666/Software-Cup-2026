from __future__ import annotations

from .models import RetrievalHit


RRF_K = 60


def reciprocal_rank(rank: int | None, k: int = RRF_K) -> float:
    if not rank or rank <= 0:
        return 0.0
    return 1.0 / (k + rank)


def merge_duplicate_hit(base: RetrievalHit, incoming: RetrievalHit) -> RetrievalHit:
    if incoming.keyword_rank is not None:
        base.keyword_rank = incoming.keyword_rank
    if incoming.vector_rank is not None:
        base.vector_rank = incoming.vector_rank
    if incoming.qdrant_rank is not None:
        base.qdrant_rank = incoming.qdrant_rank
    if incoming.keyword_score is not None:
        base.keyword_score = incoming.keyword_score
    if incoming.vector_score is not None:
        base.vector_score = incoming.vector_score
    if incoming.qdrant_score is not None:
        base.qdrant_score = incoming.qdrant_score
    base.matched_terms = list(dict.fromkeys(base.matched_terms + incoming.matched_terms))
    base.matched_fields = list(dict.fromkeys(base.matched_fields + incoming.matched_fields))
    base.source_retrievers = list(dict.fromkeys(base.source_retrievers + incoming.source_retrievers))
    if incoming.retrieval_source and not base.retrieval_source:
        base.retrieval_source = incoming.retrieval_source
    if "vectorDistance" in incoming.score_breakdown:
        base.score_breakdown["vectorDistance"] = incoming.score_breakdown["vectorDistance"]
        base.score_breakdown["embeddingProvider"] = incoming.score_breakdown.get("embeddingProvider", "")
    if incoming.reason and incoming.reason not in base.reason:
        base.reason = f"{base.reason}；{incoming.reason}"
    return base


def apply_fusion_score(hit: RetrievalHit) -> RetrievalHit:
    fusion_score = (
        reciprocal_rank(hit.keyword_rank)
        + reciprocal_rank(hit.vector_rank)
        + reciprocal_rank(hit.qdrant_rank)
    )
    hit.fusion_score = fusion_score
    original_ranks = {
        "keyword": hit.keyword_rank,
        "vector": hit.vector_rank,
        "qdrant": hit.qdrant_rank,
    }
    original_ranks = {key: value for key, value in original_ranks.items() if value is not None}
    source_retrievers = hit.source_retrievers or [
        name
        for name, rank in (
            ("keyword", hit.keyword_rank),
            ("vector", hit.vector_rank),
            ("qdrant", hit.qdrant_rank),
        )
        if rank is not None
    ]
    hit.score_breakdown.update(
        {
            "score": round(fusion_score * 10000, 4),
            "retrievalMode": "rrf",
            "retrievalSource": hit.retrieval_source,
            "sourceRetrievers": source_retrievers,
            "originalRanks": original_ranks,
            "keywordRank": hit.keyword_rank,
            "vectorRank": hit.vector_rank,
            "qdrantRank": hit.qdrant_rank,
            "keywordScore": hit.keyword_score,
            "vectorScore": hit.vector_score,
            "qdrantScore": hit.qdrant_score,
            "fusionScore": round(fusion_score, 8),
            "matchedFields": hit.matched_fields,
        }
    )
    hit.source_retrievers = source_retrievers
    return hit


def fuse_hit_groups_rrf(hit_groups: dict[str, list[RetrievalHit]], top_k: int) -> list[RetrievalHit]:
    merged: dict[str, RetrievalHit] = {}
    for retriever_name, hits in hit_groups.items():
        for rank, hit in enumerate(hits, start=1):
            if retriever_name == "keyword" and hit.keyword_rank is None:
                hit.keyword_rank = rank
            elif retriever_name == "vector" and hit.vector_rank is None:
                hit.vector_rank = rank
            elif retriever_name == "qdrant" and hit.qdrant_rank is None:
                hit.qdrant_rank = rank
            if retriever_name not in hit.source_retrievers:
                hit.source_retrievers.append(retriever_name)
            key = hit.dedupe_key()
            if key in merged:
                merge_duplicate_hit(merged[key], hit)
            else:
                merged[key] = hit

    fused = [apply_fusion_score(hit) for hit in merged.values()]
    fused.sort(
        key=lambda item: (
            item.keyword_score or 0,
            item.fusion_score or 0,
            item.vector_score or 0,
            item.qdrant_score or 0,
            item.confidence,
        ),
        reverse=True,
    )
    return fused[:top_k]


def fuse_hits_rrf(keyword_hits: list[RetrievalHit], vector_hits: list[RetrievalHit], top_k: int) -> list[RetrievalHit]:
    return fuse_hit_groups_rrf({"keyword": keyword_hits, "vector": vector_hits}, top_k)
