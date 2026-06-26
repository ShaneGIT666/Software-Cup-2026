from __future__ import annotations

from backend.app.retrieval.fusion import fuse_hits_rrf, reciprocal_rank
from backend.app.retrieval.models import QueryContext, RetrievalHit
from backend.app.retrieval.reranker import rerank_hits
from backend.app.provider_policy import LAST_FALLBACK


def make_hit(
    hit_id: str,
    *,
    chunk_id: str | None = None,
    device_model: str | None = None,
    keyword_rank: int | None = None,
    vector_rank: int | None = None,
    keyword_score: float | None = None,
    vector_score: float | None = None,
    fusion_score: float | None = None,
    matched_terms: list[str] | None = None,
    matched_fields: list[str] | None = None,
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
        matched_terms=matched_terms or [],
        chunk_id=chunk_id,
        device_model=device_model,
        keyword_rank=keyword_rank,
        vector_rank=vector_rank,
        keyword_score=keyword_score,
        vector_score=vector_score,
        fusion_score=fusion_score,
        matched_fields=matched_fields or [],
    )


def make_context() -> QueryContext:
    return QueryContext(
        device_model="发动机-示例型号 A",
        fault_text="启动困难",
        top_k=5,
        query_tokens=["启动困难"],
        vector_query="发动机-示例型号 A 启动困难",
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


def test_rrf_fusion_keeps_stronger_keyword_match_first() -> None:
    keyword_only = make_hit("manual-1", keyword_rank=1, keyword_score=30)
    both_channels = make_hit("chunk-1", chunk_id="chunk-1", keyword_rank=3, keyword_score=10)
    vector_duplicate = make_hit("chunk-1", chunk_id="chunk-1", vector_rank=1, vector_score=18)

    fused = fuse_hits_rrf([keyword_only, both_channels], [vector_duplicate], top_k=5)

    assert fused[0].id == "manual-1"
    assert fused[1].id == "chunk-1"
    assert fused[1].fusion_score and fused[1].fusion_score > (keyword_only.fusion_score or 0)


def test_reranker_none_preserves_rrf_order(monkeypatch) -> None:
    monkeypatch.setenv("RAG_RERANK_PROVIDER", "none")
    first = make_hit("first", fusion_score=0.03)
    second = make_hit("second", fusion_score=0.02)

    reranked = rerank_hits(make_context(), [first, second])

    assert [hit.id for hit in reranked] == ["first", "second"]
    assert all(hit.score_breakdown["rerankProvider"] == "none" for hit in reranked)


def test_heuristic_reranker_uses_metadata_bonus(monkeypatch) -> None:
    monkeypatch.setenv("RAG_RERANK_PROVIDER", "heuristic")
    generic_hit = make_hit("generic", fusion_score=0.012)
    exact_model_hit = make_hit(
        "exact",
        device_model="发动机-示例型号 A",
        fusion_score=0.005,
        matched_terms=["启动困难"],
        matched_fields=["deviceModel"],
    )

    reranked = rerank_hits(make_context(), [generic_hit, exact_model_hit])

    assert reranked[0].id == "exact"
    assert reranked[0].score_breakdown["rerankProvider"] == "heuristic"
    assert reranked[0].score_breakdown["rerankScore"] == reranked[0].rerank_score


def test_unsupported_reranker_falls_back_to_rrf_order(monkeypatch) -> None:
    monkeypatch.setenv("RAG_RERANK_PROVIDER", "cross-encoder")
    LAST_FALLBACK["reranker"] = ""
    first = make_hit("first", fusion_score=0.03)
    second = make_hit("second", fusion_score=0.02)

    reranked = rerank_hits(make_context(), [first, second])

    assert [hit.id for hit in reranked] == ["first", "second"]
    assert LAST_FALLBACK["reranker"] == "unsupported reranker provider: cross-encoder"
    assert all(hit.score_breakdown["rerankProvider"] == "none" for hit in reranked)
