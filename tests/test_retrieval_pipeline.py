from __future__ import annotations

from backend.app.retrieval.fusion import fuse_hits_rrf, reciprocal_rank
from backend.app.retrieval.models import RetrievalHit


def make_hit(
    hit_id: str,
    *,
    chunk_id: str | None = None,
    keyword_rank: int | None = None,
    vector_rank: int | None = None,
    keyword_score: float | None = None,
    vector_score: float | None = None,
) -> RetrievalHit:
    return RetrievalHit(
        id=hit_id,
        title=hit_id,
        content=hit_id,
        source_id=hit_id,
        source_name="unit",
        source_type="document" if chunk_id else "manual",
        confidence=0.8,
        snippet=hit_id,
        reason="unit",
        score_breakdown={"score": keyword_score or vector_score or 1, "fieldMatches": [], "sourceType": "document"},
        chunk_id=chunk_id,
        keyword_rank=keyword_rank,
        vector_rank=vector_rank,
        keyword_score=keyword_score,
        vector_score=vector_score,
    )


def test_reciprocal_rank_uses_stable_k() -> None:
    assert reciprocal_rank(1) > reciprocal_rank(2)
    assert reciprocal_rank(None) == 0


def test_rrf_fusion_deduplicates_chunk_and_merges_scores() -> None:
    keyword_hit = make_hit("chunk-1", chunk_id="chunk-1", keyword_rank=2, keyword_score=12)
    vector_hit = make_hit("chunk-1", chunk_id="chunk-1", vector_rank=1, vector_score=18)

    fused = fuse_hits_rrf([keyword_hit], [vector_hit], top_k=5)

    assert len(fused) == 1
    assert fused[0].keyword_rank == 2
    assert fused[0].vector_rank == 1
    assert fused[0].score_breakdown["retrievalMode"] == "rrf"
    assert fused[0].score_breakdown["keywordScore"] == 12
    assert fused[0].score_breakdown["vectorScore"] == 18


def test_rrf_fusion_orders_by_combined_rank() -> None:
    keyword_only = make_hit("manual-1", keyword_rank=1, keyword_score=30)
    both_channels = make_hit("chunk-1", chunk_id="chunk-1", keyword_rank=3, keyword_score=10)
    vector_duplicate = make_hit("chunk-1", chunk_id="chunk-1", vector_rank=1, vector_score=18)

    fused = fuse_hits_rrf([keyword_only, both_channels], [vector_duplicate], top_k=5)

    assert fused[0].id == "chunk-1"
    assert fused[0].fusion_score and fused[0].fusion_score > (keyword_only.fusion_score or 0)
