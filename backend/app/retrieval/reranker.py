from __future__ import annotations

import os
from typing import Iterable

from ..provider_policy import SUPPORTED_RERANKERS, configured_reranker_provider, record_fallback
from .models import QueryContext, RetrievalHit


def exact_device_model_bonus(context: QueryContext, hit: RetrievalHit) -> float:
    if context.device_model and hit.device_model and context.device_model == hit.device_model:
        return 0.01
    return 0.0


def heuristic_score(context: QueryContext, hit: RetrievalHit) -> float:
    base = hit.fusion_score or 0.0
    matched_term_bonus = min(0.01, len(set(hit.matched_terms)) * 0.001)
    matched_field_bonus = min(0.01, len(set(hit.matched_fields)) * 0.001)
    return round(base + matched_term_bonus + matched_field_bonus + exact_device_model_bonus(context, hit), 8)


def apply_heuristic_rerank(context: QueryContext, hits: Iterable[RetrievalHit]) -> list[RetrievalHit]:
    reranked = list(hits)
    for hit in reranked:
        hit.rerank_score = heuristic_score(context, hit)
        hit.score_breakdown.update(
            {
                "rerankProvider": "heuristic",
                "rerankScore": hit.rerank_score,
            }
        )
    reranked.sort(
        key=lambda item: (
            item.rerank_score or 0,
            item.fusion_score or 0,
            item.keyword_score or 0,
            item.vector_score or 0,
        ),
        reverse=True,
    )
    return reranked


def rerank_hits(context: QueryContext, hits: list[RetrievalHit]) -> list[RetrievalHit]:
    requested_provider = (os.getenv("RAG_RERANK_PROVIDER") or "none").strip().lower()
    provider = configured_reranker_provider()
    try:
        if provider in {"", "none"}:
            if requested_provider not in SUPPORTED_RERANKERS:
                record_fallback("reranker", f"unsupported reranker provider: {requested_provider}")
            for hit in hits:
                hit.score_breakdown.setdefault("rerankProvider", "none")
            return hits
        if provider == "heuristic":
            return apply_heuristic_rerank(context, hits)
        record_fallback("reranker", f"unsupported reranker provider: {requested_provider}")
        for hit in hits:
            hit.score_breakdown.setdefault("rerankProvider", "none")
        return hits
    except Exception as exc:
        record_fallback("reranker", f"reranker fallback to RRF: {exc}")
        for hit in hits:
            hit.score_breakdown.setdefault("rerankProvider", "none")
        return hits
