from __future__ import annotations

from backend.app.retrieval.fusion import fuse_hit_groups_rrf, fuse_hits_rrf, reciprocal_rank
from backend.app.retrieval import keyword_retriever, pipeline as retrieval_pipeline, vector_retriever
from backend.app.retrieval.filters import apply_metadata_filter, device_model_matches
from backend.app.retrieval.models import QueryContext, RetrievalHit
from backend.app.retrieval.pipeline import candidate_pool_size, tokenize
from backend.app.retrieval.reranker import rerank_hits
from backend.app.provider_policy import LAST_FALLBACK
from backend.app.schemas import SearchRequest


def make_hit(
    hit_id: str,
    *,
    chunk_id: str | None = None,
    device_model: str | None = None,
    keyword_rank: int | None = None,
    vector_rank: int | None = None,
    qdrant_rank: int | None = None,
    keyword_score: float | None = None,
    vector_score: float | None = None,
    qdrant_score: float | None = None,
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
        qdrant_rank=qdrant_rank,
        keyword_score=keyword_score,
        vector_score=vector_score,
        qdrant_score=qdrant_score,
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


def test_rrf_fusion_prioritizes_cross_retriever_agreement() -> None:
    keyword_only = make_hit("manual-1", keyword_rank=1, keyword_score=30)
    both_channels = make_hit("chunk-1", chunk_id="chunk-1", keyword_rank=3, keyword_score=10)
    vector_duplicate = make_hit("chunk-1", chunk_id="chunk-1", vector_rank=1, vector_score=18)

    fused = fuse_hits_rrf([keyword_only, both_channels], [vector_duplicate], top_k=5)

    assert fused[0].id == "chunk-1"
    assert fused[0].fusion_score and fused[0].fusion_score > (keyword_only.fusion_score or 0)


def test_tokenize_extracts_chinese_symptom_bigrams_from_long_sentences() -> None:
    tokens = tokenize("设备运行声音像周期敲击，伴随振动")

    assert "设备运行声音像周期敲击" in tokens
    assert "敲击" in tokens


def test_candidate_pool_expands_beyond_result_size() -> None:
    assert candidate_pool_size(1) == 12
    assert candidate_pool_size(5) == 20
    assert candidate_pool_size(20) == 50


def test_keyword_candidates_are_filtered_before_truncation_and_reranked(monkeypatch) -> None:
    wrong_model_manuals = [
        {
            "id": f"wrong-{index}",
            "title": "target model fault",
            "deviceModel": f"other-{index}",
            "chapter": "unit",
            "page": index,
            "content": "target model fault",
            "sourceName": "unit",
            "tags": ["target", "model", "fault"],
        }
        for index in range(20)
    ]
    target_manual = {
        "id": "target-manual",
        "title": "target guide",
        "deviceModel": "target-model",
        "chapter": "unit",
        "page": 99,
        "content": "fault",
        "sourceName": "unit",
        "tags": [],
    }
    monkeypatch.setattr(
        keyword_retriever,
        "load_seed_data",
        lambda: {"manuals": [*wrong_model_manuals, target_manual], "cases": []},
    )
    monkeypatch.setattr(keyword_retriever, "load_document_chunks", lambda: [])
    monkeypatch.setattr(retrieval_pipeline, "retrieve_vector_hits", lambda _context: [])

    payload = retrieval_pipeline.search_knowledge(
        SearchRequest(deviceModel="target-model", faultText="fault", topK=5)
    )

    assert [result["id"] for result in payload["results"]] == ["target-manual"]
    assert payload["results"][0]["scoreBreakdown"]["originalRanks"] == {"keyword": 1}


def test_vector_retrieval_oversamples_filtered_candidates() -> None:
    assert vector_retriever.vector_retrieval_pool_size(20) == 60
    assert vector_retriever.vector_retrieval_pool_size(50) == 100


def test_device_model_filter_accepts_device_family_without_cross_model_leakage() -> None:
    assert device_model_matches("发动机", "发动机-示例型号 A")
    assert not device_model_matches("发动机-示例型号 A", "发动机-示例型号 C")


def test_vector_recall_hydrates_chunk_metadata_before_filtering(monkeypatch) -> None:
    monkeypatch.setattr(
        vector_retriever,
        "load_document_chunks",
        lambda: [
            {
                "id": "chunk-a",
                "device_model": "发动机-示例型号 A",
                "review_status": "approved",
            }
        ],
    )
    monkeypatch.setattr(
        vector_retriever.vector_store,
        "search_similar_chunks",
        lambda _query, _top_k: [
            {
                "id": "chunk-a",
                "title": "发动机资料",
                "sourceName": "unit",
                "snippet": "unit",
                "chunkId": "chunk-a",
                "documentId": "document-a",
                "distance": 0.1,
                "retrievalSource": "sqlite",
            }
        ],
    )
    context = QueryContext(
        device_model="发动机-示例型号 C",
        fault_text="异响",
        top_k=5,
        query_tokens=["异响"],
        vector_query="发动机-示例型号 C 异响",
        metadata_filters={"device_model": "发动机-示例型号 C"},
    )

    hits = vector_retriever.retrieve_vector_hits(context)

    assert hits[0].device_model == "发动机-示例型号 A"
    assert apply_metadata_filter(context, hits) == []


def test_vector_recall_uses_authoritative_review_status(monkeypatch) -> None:
    monkeypatch.setattr(
        vector_retriever,
        "load_document_chunks",
        lambda: [{"id": "chunk-a", "review_status": "pending_review"}],
    )
    monkeypatch.setattr(
        vector_retriever.vector_store,
        "search_similar_chunks",
        lambda _query, _top_k: [
            {
                "id": "chunk-a",
                "title": "待审核资料",
                "sourceName": "unit",
                "snippet": "unit",
                "chunkId": "chunk-a",
                "documentId": "document-a",
                "distance": 0.1,
                "retrievalSource": "sqlite",
                "reviewStatus": "approved",
            }
        ],
    )
    context = QueryContext(
        device_model="",
        fault_text="异响",
        top_k=5,
        query_tokens=["异响"],
        vector_query="异响",
    )

    hits = vector_retriever.retrieve_vector_hits(context)

    assert hits[0].review_status == "pending_review"
    assert apply_metadata_filter(context, hits) == []


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
