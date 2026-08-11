from __future__ import annotations

from .models import QueryContext, RetrievalHit


def normalize_text(value: str | None) -> str:
    return (value or "").strip().lower()


def device_model_matches(expected: str, actual: str | None) -> bool:
    expected_norm = normalize_text(expected)
    actual_norm = normalize_text(actual)
    if not expected_norm or not actual_norm:
        return True
    # A request may name a full model ("发动机-示例型号 A") or only a device
    # family ("发动机"). Keep exact-model isolation while allowing the latter.
    return expected_norm == actual_norm or expected_norm in actual_norm or actual_norm in expected_norm


def review_status_matches(hit: RetrievalHit) -> bool:
    return (hit.review_status or "approved") == "approved"


def metadata_matches(context: QueryContext, hit: RetrievalHit) -> bool:
    if not review_status_matches(hit):
        return False
    expected_model = context.metadata_filters.get("device_model", "")
    if expected_model and not device_model_matches(expected_model, hit.device_model):
        return False
    return True


def apply_metadata_filter(context: QueryContext, hits: list[RetrievalHit]) -> list[RetrievalHit]:
    return [hit for hit in hits if metadata_matches(context, hit)]
