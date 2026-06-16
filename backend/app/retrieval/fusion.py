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
    if incoming.keyword_score is not None:
        base.keyword_score = incoming.keyword_score
    if incoming.vector_score is not None:
        base.vector_score = incoming.vector_score
    base.matched_terms = list(dict.fromkeys(base.matched_terms + incoming.matched_terms))
    base.matched_fields = list(dict.fromkeys(base.matched_fields + incoming.matched_fields))
    if "vectorDistance" in incoming.score_breakdown:
        base.score_breakdown["vectorDistance"] = incoming.score_breakdown["vectorDistance"]
        base.score_breakdown["embeddingProvider"] = incoming.score_breakdown.get("embeddingProvider", "")
    if incoming.reason and incoming.reason not in base.reason:
        base.reason = f"{base.reason}；{incoming.reason}"
    return base


def apply_fusion_score(hit: RetrievalHit) -> RetrievalHit:
    fusion_score = reciprocal_rank(hit.keyword_rank) + reciprocal_rank(hit.vector_rank)
    hit.fusion_score = fusion_score
    hit.score_breakdown.update(
        {
            "score": round(fusion_score * 10000, 4),
            "retrievalMode": "rrf",
            "keywordRank": hit.keyword_rank,
            "vectorRank": hit.vector_rank,
            "keywordScore": hit.keyword_score,
            "vectorScore": hit.vector_score,
            "fusionScore": round(fusion_score, 8),
            "matchedFields": hit.matched_fields,
        }
    )
    return hit


def fuse_hits_rrf(keyword_hits: list[RetrievalHit], vector_hits: list[RetrievalHit], top_k: int) -> list[RetrievalHit]:
    merged: dict[str, RetrievalHit] = {}
    for hit in keyword_hits + vector_hits:
        key = hit.dedupe_key()
        if key in merged:
            merge_duplicate_hit(merged[key], hit)
        else:
            merged[key] = hit

    fused = [apply_fusion_score(hit) for hit in merged.values()]
    fused.sort(
        key=lambda item: (
            item.fusion_score or 0,
            item.keyword_score or 0,
            item.vector_score or 0,
            item.confidence,
        ),
        reverse=True,
    )
    return fused[:top_k]
