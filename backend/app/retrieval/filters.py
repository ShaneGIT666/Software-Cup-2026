from __future__ import annotations

from ..review_policy import normalize_review_status
from .models import QueryContext, RetrievalHit


def normalize_text(value: str | None) -> str:
    return (value or "").strip().lower()


def device_model_matches(expected: str, actual: str | None) -> bool:
    expected_norm = normalize_text(expected)
    actual_norm = normalize_text(actual)
    if not expected_norm or not actual_norm:
        return True
    return expected_norm == actual_norm


def review_status_matches(hit: RetrievalHit) -> bool:
    return normalize_review_status(hit.review_status) == "approved"


def metadata_matches(context: QueryContext, hit: RetrievalHit) -> bool:
    if not review_status_matches(hit):
        return False
    expected_model = context.metadata_filters.get("device_model", "")
    if expected_model and not device_model_matches(expected_model, hit.device_model):
        return False
    return True


def apply_metadata_filter(context: QueryContext, hits: list[RetrievalHit]) -> list[RetrievalHit]:
    return [hit for hit in hits if metadata_matches(context, hit)]
