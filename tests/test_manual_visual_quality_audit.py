from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "manual-visual-quality-audit.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("manual_visual_quality_audit", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _inventory() -> list[dict[str, object]]:
    return [
        {
            "page": page,
            "imageObjectCount": 50 - page,
            "keywordHits": ["diagram"] * (page % 9),
            "textChars": page * 17,
        }
        for page in range(1, 42)
    ]


def _passing_pages() -> list[dict[str, object]]:
    visual_types = ("diagram", "photo", "table")
    return [
        {
            "page": page,
            "primaryAnalysisFailed": False,
            "judgeFailed": False,
            "semanticVerified": True,
            "imageInputSent": True,
            "fallback": False,
            "qualityScore": 9,
            "machinePass": True,
            "criticalHallucination": False,
            "unsupportedNumericClaims": [],
            "componentsCount": 1 if page <= 5 else 0,
            "operationsCount": 0,
            "visualType": visual_types[(page - 1) % len(visual_types)],
        }
        for page in range(1, 21)
    ]


def test_select_quality_pages_is_deterministic_unique_and_complete() -> None:
    module = _load_module()
    first_pages, first_reasons = module.select_quality_pages(_inventory())
    second_pages, second_reasons = module.select_quality_pages(_inventory())

    assert first_pages == second_pages
    assert first_reasons == second_reasons
    assert len(first_pages) == len(set(first_pages)) == 20
    assert first_pages == sorted(first_pages)
    assert first_pages[0] == 1
    assert first_pages[-1] == 41
    assert set(first_reasons) == {str(page) for page in first_pages}
    assert all(first_reasons[str(page)] for page in first_pages)


def test_same_model_quality_gate_cannot_claim_independent_go() -> None:
    module = _load_module()

    metrics = module.aggregate_quality(_passing_pages(), independent=False)

    assert metrics["result"] == "MACHINE_VISUAL_QUALITY_GO_SAME_MODEL"
    assert metrics["completedPages"] == 20
    assert metrics["passedPages"] == 20


def test_quality_gate_rejects_primary_failure_and_numeric_hallucination() -> None:
    module = _load_module()
    pages = _passing_pages()
    pages[0]["primaryAnalysisFailed"] = True
    pages[1]["unsupportedNumericClaims"] = ["unsupported torque value"]

    metrics = module.aggregate_quality(pages, independent=True)

    assert metrics["primaryAnalysisFailedPages"] == 1
    assert metrics["unsupportedNumericClaimPages"] == 1
    assert metrics["result"] == "VISUAL_QUALITY_NO_GO"
