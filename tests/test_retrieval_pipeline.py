from __future__ import annotations

from backend.app.retrieval import pipeline
from backend.app.retrieval.fusion import fuse_hit_groups_rrf, fuse_hits_rrf, reciprocal_rank
from backend.app.retrieval.models import QueryContext, RetrievalHit
from backend.app.retrieval.reranker import rerank_hits
from backend.app.provider_policy import LAST_FALLBACK
from backend.app.schemas import SearchRequest


def make_hit(
    hit_id: str,
    *,
    source_type: str | None = None,
    chunk_id: str | None = None,
    device_model: str | None = None,
    keyword_rank: int | None = None,
    vector_rank: int | None = None,
    qdrant_rank: int | None = None,
    keyword_score: float | None = None,
    vector_score: float | None = None,
    qdrant_score: float | None = None,
    fusion_score: float | None = None,
    rerank_score: float | None = None,
    review_status: str | None = "approved",
    matched_terms: list[str] | None = None,
    matched_fields: list[str] | None = None,
) -> RetrievalHit:
    return RetrievalHit(
        id=hit_id,
        title=hit_id,
        content=hit_id,
        source_id=hit_id,
        source_name="unit",
        source_type=source_type or ("document" if chunk_id else "manual"),
        confidence=0.8,
        snippet=hit_id,
        reason="unit",
        score_breakdown={"score": keyword_score or vector_score or 1, "fieldMatches": [], "sourceType": "document"},
        matched_terms=matched_terms or [],
        chunk_id=chunk_id,
        device_model=device_model,
        keyword_rank=keyword_rank,
        vector_rank=vector_rank,
        qdrant_rank=qdrant_rank,
        keyword_score=keyword_score,
        vector_score=vector_score,
        qdrant_score=qdrant_score,
        fusion_score=fusion_score,
        rerank_score=rerank_score,
        review_status=review_status,
        matched_fields=matched_fields or [],
    )


def make_context() -> QueryContext:
    return QueryContext(
        device_type="engine",
        device_model="发动机-示例型号 A",
        fault_text="启动困难",
        top_k=5,
        query_tokens=["启动困难"],
        vector_query="发动机-示例型号 A 启动困难",
    )


def test_reciprocal_rank_uses_stable_k() -> None:
    assert reciprocal_rank(1) > reciprocal_rank(2)
    assert reciprocal_rank(None) == 0


def test_reciprocal_rank_invalid_env_falls_back_to_default(monkeypatch) -> None:
    monkeypatch.setenv("RAG_RRF_K", "not-an-int")

    assert reciprocal_rank(1) == 1 / 61


def test_rrf_fusion_deduplicates_chunk_and_merges_scores() -> None:
    keyword_hit = make_hit("chunk-1", chunk_id="chunk-1", keyword_rank=2, keyword_score=12)
    vector_hit = make_hit("chunk-1", chunk_id="chunk-1", vector_rank=1, vector_score=18)

    fused = fuse_hits_rrf([keyword_hit], [vector_hit], top_k=5)

    assert len(fused) == 1
    assert fused[0].keyword_rank == 2
    assert fused[0].vector_rank == 1
    assert fused[0].score_breakdown["retrievalMode"] == "rrf"
    assert fused[0].score_breakdown["scoreKind"] == "rrf_display"
    assert fused[0].score_breakdown["keywordScore"] == 12
    assert fused[0].score_breakdown["vectorScore"] == 18
    assert fused[0].score_breakdown["sourceRetrievers"] == ["keyword", "vector"]
    assert fused[0].score_breakdown["originalRanks"] == {"keyword": 2, "vector": 1}


def test_rrf_group_fusion_keeps_optional_qdrant_rank_breakdown() -> None:
    local_hit = make_hit("chunk-1", chunk_id="chunk-1", vector_rank=2, vector_score=14)
    qdrant_hit = make_hit("chunk-1", chunk_id="chunk-1", qdrant_rank=1, qdrant_score=0.92)
    keyword_hit = make_hit("manual-1", keyword_rank=1, keyword_score=22)

    fused = fuse_hit_groups_rrf({"keyword": [keyword_hit], "vector": [local_hit], "qdrant": [qdrant_hit]}, top_k=5)
    chunk = next(hit for hit in fused if hit.id == "chunk-1")

    assert chunk.qdrant_rank == 1
    assert chunk.qdrant_score == 0.92
    assert chunk.score_breakdown["qdrantRank"] == 1
    assert chunk.score_breakdown["sourceRetrievers"] == ["vector", "qdrant"]


def test_rrf_group_fusion_accumulates_three_retrieval_routes() -> None:
    keyword_hit = make_hit("chunk-1", chunk_id="chunk-1", keyword_rank=3, keyword_score=12)
    vector_hit = make_hit("chunk-1", chunk_id="chunk-1", vector_rank=2, vector_score=14)
    qdrant_hit = make_hit("chunk-1", chunk_id="chunk-1", qdrant_rank=1, qdrant_score=0.92)

    fused = fuse_hit_groups_rrf({"keyword": [keyword_hit], "vector": [vector_hit], "qdrant": [qdrant_hit]}, top_k=5)

    expected = reciprocal_rank(3) + reciprocal_rank(2) + reciprocal_rank(1)
    assert fused[0].fusion_score == expected
    assert fused[0].score_breakdown["originalRanks"] == {"keyword": 3, "vector": 2, "qdrant": 1}


def test_rrf_fusion_ranks_higher_fusion_before_stronger_keyword_score() -> None:
    keyword_only = make_hit("manual-1", keyword_rank=1, keyword_score=30)
    both_channels = make_hit("chunk-1", chunk_id="chunk-1", keyword_rank=3, keyword_score=10)
    vector_duplicate = make_hit("chunk-1", chunk_id="chunk-1", vector_rank=1, vector_score=18)

    fused = fuse_hits_rrf([keyword_only, both_channels], [vector_duplicate], top_k=5)

    assert fused[0].id == "chunk-1"
    assert fused[0].fusion_score and fused[0].fusion_score > (keyword_only.fusion_score or 0)


def test_single_route_hits_keep_stable_rank_order() -> None:
    keyword_hits = [
        make_hit("first", keyword_rank=1, keyword_score=8),
        make_hit("second", keyword_rank=2, keyword_score=20),
        make_hit("third", keyword_rank=3, keyword_score=30),
    ]

    fused = fuse_hits_rrf(keyword_hits, [], top_k=5)

    assert [hit.id for hit in fused] == ["first", "second", "third"]


def test_top_k_does_not_change_rrf_formula() -> None:
    keyword_hit = make_hit("chunk-1", chunk_id="chunk-1", keyword_rank=2, keyword_score=12)
    vector_hit = make_hit("chunk-1", chunk_id="chunk-1", vector_rank=1, vector_score=18)

    top_one = fuse_hits_rrf([keyword_hit], [vector_hit], top_k=1)[0]
    top_many = fuse_hits_rrf(
        [make_hit("chunk-1", chunk_id="chunk-1", keyword_rank=2, keyword_score=12)],
        [make_hit("chunk-1", chunk_id="chunk-1", vector_rank=1, vector_score=18)],
        top_k=5,
    )[0]

    assert top_one.fusion_score == top_many.fusion_score


def test_candidate_pool_expands_before_heuristic_rerank(monkeypatch) -> None:
    monkeypatch.setenv("RAG_RERANK_PROVIDER", "heuristic")
    monkeypatch.setenv("RAG_RETRIEVAL_CANDIDATE_MULTIPLIER", "2")
    monkeypatch.setenv("RAG_RETRIEVAL_MIN_CANDIDATES", "6")
    monkeypatch.setenv("RAG_RETRIEVAL_MAX_CANDIDATES", "6")

    exact_model = "example-model-a"
    keyword_hits = [
        make_hit(f"rank-{index}", keyword_rank=index, keyword_score=float(100 - index))
        for index in range(1, 7)
    ]
    keyword_hits[3].device_model = exact_model
    keyword_hits[3].matched_terms = ["hard-start"]
    keyword_hits[3].matched_fields = ["deviceModel", "content"]
    monkeypatch.setattr(pipeline, "retrieve_keyword_hits", lambda context: keyword_hits)
    monkeypatch.setattr(pipeline, "retrieve_vector_hits", lambda context: [])

    response = pipeline.search_knowledge(
        SearchRequest(deviceModel=exact_model, faultText="hard-start", topK=3)
    )

    result_ids = [item["id"] for item in response["results"]]
    assert result_ids[0] == "rank-4"
    assert len(result_ids) == 3
    assert response["results"][0]["scoreBreakdown"]["candidatePoolSize"] == 6
    assert response["results"][0]["scoreBreakdown"]["requestedTopK"] == 3


def test_source_diversity_promotes_strong_approved_case() -> None:
    hits = [make_hit(f"doc-{index}", source_type="document", fusion_score=0.04 - index * 0.001) for index in range(5)]
    case_hit = make_hit(
        "case-1",
        source_type="case",
        fusion_score=0.030,
        keyword_rank=3,
        keyword_score=18,
        matched_terms=["hard-start"],
    )

    final_hits = pipeline.apply_source_diversity_policy(make_context(), [*hits, case_hit], top_k=5)

    assert [hit.id for hit in final_hits] == ["doc-0", "doc-1", "doc-2", "doc-3", "case-1"]
    assert case_hit.score_breakdown["sourceDiversityPromotion"] is True
    assert case_hit.score_breakdown["sourceDiversityReason"] == "strong_approved_case"
    assert case_hit.score_breakdown["originalRank"] == 6
    assert case_hit.score_breakdown["replacedFinalRank"] == 5


def test_source_diversity_does_not_promote_weak_vector_only_case() -> None:
    hits = [make_hit(f"doc-{index}", source_type="document", fusion_score=0.04 - index * 0.001) for index in range(5)]
    weak_case = make_hit("case-weak", source_type="case", fusion_score=0.033, vector_rank=1, matched_terms=[])

    final_hits = pipeline.apply_source_diversity_policy(make_context(), [*hits, weak_case], top_k=5)

    assert [hit.id for hit in final_hits] == ["doc-0", "doc-1", "doc-2", "doc-3", "doc-4"]
    assert "sourceDiversityPromotion" not in weak_case.score_breakdown


def test_source_diversity_does_not_replace_with_low_scoring_case() -> None:
    hits = [make_hit(f"doc-{index}", source_type="document", fusion_score=0.04 - index * 0.001) for index in range(5)]
    low_case = make_hit(
        "case-low",
        source_type="case",
        fusion_score=0.001,
        keyword_rank=4,
        matched_terms=["hard-start"],
    )

    final_hits = pipeline.apply_source_diversity_policy(make_context(), [*hits, low_case], top_k=5)

    assert [hit.id for hit in final_hits] == ["doc-0", "doc-1", "doc-2", "doc-3", "doc-4"]


def test_source_diversity_does_not_promote_case_below_score_floor_despite_keyword_match() -> None:
    hits = [
        make_hit(
            f"doc-{index}",
            source_type="document",
            fusion_score=0.04 - index * 0.001,
            keyword_score=10,
        )
        for index in range(5)
    ]
    case_hit = make_hit(
        "case-keyword-match",
        source_type="case",
        device_model=make_context().device_model,
        fusion_score=0.01,
        keyword_rank=6,
        keyword_score=12,
        matched_terms=["hard-start"],
    )

    final_hits = pipeline.apply_source_diversity_policy(make_context(), [*hits, case_hit], top_k=5)

    assert final_hits[-1].id == "doc-4"


def test_source_diversity_promotes_metadata_matched_case_in_guarded_score_band() -> None:
    context = make_context()
    hits = [
        make_hit(f"doc-{index}", source_type="document", fusion_score=0.04 - index * 0.001, keyword_score=10)
        for index in range(5)
    ]
    case_hit = make_hit(
        "case-guarded-match",
        source_type="case",
        device_model=context.device_model,
        fusion_score=0.025,
        keyword_rank=6,
        keyword_score=12,
        matched_terms=["hard-start"],
    )

    final_hits = pipeline.apply_source_diversity_policy(context, [*hits, case_hit], top_k=5)

    assert final_hits[-1].id == "case-guarded-match"


def test_source_diversity_rejects_guarded_score_band_without_exact_metadata() -> None:
    context = make_context()
    hits = [
        make_hit(f"doc-{index}", source_type="document", fusion_score=0.04 - index * 0.001, keyword_score=10)
        for index in range(5)
    ]
    case_hit = make_hit(
        "case-wrong-model",
        source_type="case",
        device_model="engine-b",
        fusion_score=0.025,
        keyword_rank=6,
        keyword_score=12,
        matched_terms=["hard-start"],
    )

    final_hits = pipeline.apply_source_diversity_policy(context, [*hits, case_hit], top_k=5)

    assert final_hits[-1].id == "doc-4"


def test_source_diversity_rejects_case_below_guarded_score_band() -> None:
    context = make_context()
    hits = [
        make_hit(f"doc-{index}", source_type="document", fusion_score=0.044 - index * 0.001, keyword_score=10)
        for index in range(5)
    ]
    case_hit = make_hit(
        "case-below-guarded-band",
        source_type="case",
        device_model=context.device_model,
        fusion_score=0.025,
        keyword_rank=6,
        keyword_score=12,
        matched_terms=["hard-start"],
    )

    final_hits = pipeline.apply_source_diversity_policy(context, [*hits, case_hit], top_k=5)

    assert final_hits[-1].id == "doc-4"


def test_source_diversity_skips_small_top_k() -> None:
    hits = [
        make_hit("doc-1", source_type="document", fusion_score=0.04),
        make_hit("doc-2", source_type="document", fusion_score=0.03),
        make_hit("case-1", source_type="case", fusion_score=0.029, keyword_rank=1, matched_terms=["hard-start"]),
    ]

    final_hits = pipeline.apply_source_diversity_policy(make_context(), hits, top_k=2)

    assert [hit.id for hit in final_hits] == ["doc-1", "doc-2"]


def test_source_diversity_skips_when_case_already_present() -> None:
    hits = [
        make_hit("doc-1", source_type="document", fusion_score=0.05),
        make_hit("case-present", source_type="case", fusion_score=0.04, keyword_rank=1, matched_terms=["hard-start"]),
        make_hit("doc-2", source_type="document", fusion_score=0.03),
        make_hit("doc-3", source_type="document", fusion_score=0.02),
        make_hit("doc-4", source_type="document", fusion_score=0.01),
        make_hit("case-extra", source_type="case", fusion_score=0.03, keyword_rank=2, matched_terms=["hard-start"]),
    ]

    final_hits = pipeline.apply_source_diversity_policy(make_context(), hits, top_k=5)

    assert [hit.id for hit in final_hits] == ["doc-1", "case-present", "doc-2", "doc-3", "doc-4"]
    assert "sourceDiversityPromotion" not in hits[-1].score_breakdown


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
