from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import EvalCase, EvalDataset


REQUIRED_CASE_FIELDS = {"id", "category", "question"}


class EvaluationDatasetError(ValueError):
    pass


def _string_list(value: Any, field_name: str, case_id: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise EvaluationDatasetError(f"{case_id}.{field_name} must be a list")
    return [str(item) for item in value if str(item)]


def _case_from_raw(raw: dict[str, Any]) -> EvalCase:
    missing = sorted(field for field in REQUIRED_CASE_FIELDS if not raw.get(field))
    if missing:
        case_id = raw.get("id", "<missing-id>")
        raise EvaluationDatasetError(f"{case_id} missing required fields: {', '.join(missing)}")

    case_id = str(raw["id"])
    metadata_filters = raw.get("metadata_filters") or {}
    if not isinstance(metadata_filters, dict):
        raise EvaluationDatasetError(f"{case_id}.metadata_filters must be an object")

    return EvalCase(
        id=case_id,
        category=str(raw["category"]),
        question=str(raw["question"]),
        device_type=str(raw.get("device_type") or ""),
        device_model=str(raw.get("device_model") or ""),
        metadata_filters=metadata_filters,
        expected_source_ids=_string_list(raw.get("expected_source_ids"), "expected_source_ids", case_id),
        expected_chunk_ids=_string_list(raw.get("expected_chunk_ids"), "expected_chunk_ids", case_id),
        expected_keywords=_string_list(raw.get("expected_keywords"), "expected_keywords", case_id),
        forbidden_source_ids=_string_list(raw.get("forbidden_source_ids"), "forbidden_source_ids", case_id),
        forbidden_review_status=_string_list(raw.get("forbidden_review_status"), "forbidden_review_status", case_id),
        must_refuse=bool(raw.get("must_refuse", False)),
        notes=str(raw.get("notes") or ""),
    )


def load_eval_dataset(path: Path) -> EvalDataset:
    with path.open("r", encoding="utf-8") as file:
        raw = json.load(file)
    if not isinstance(raw, dict):
        raise EvaluationDatasetError("evaluation dataset must be a JSON object")

    raw_cases = raw.get("cases")
    if not isinstance(raw_cases, list):
        raise EvaluationDatasetError("evaluation dataset must contain a cases array")

    cases = [_case_from_raw(item) for item in raw_cases if isinstance(item, dict)]
    if len(cases) != len(raw_cases):
        raise EvaluationDatasetError("all cases must be JSON objects")

    ids = [case.id for case in cases]
    duplicates = sorted({case_id for case_id in ids if ids.count(case_id) > 1})
    if duplicates:
        raise EvaluationDatasetError(f"duplicate case ids: {', '.join(duplicates)}")

    return EvalDataset(
        schema_version=str(raw.get("schema_version") or ""),
        dataset_id=str(raw.get("dataset_id") or path.stem),
        created_at=str(raw.get("created_at") or ""),
        purpose=str(raw.get("purpose") or ""),
        cases=cases,
    )
