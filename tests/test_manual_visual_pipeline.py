from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

import backend.app.manual_visual_pipeline as pipeline
import backend.app.multimodal_adapter as multimodal_adapter
from backend.app.parser_modes import resolve_parser_policy


def inventory(page_count: int, candidate_count: int) -> list[dict[str, object]]:
    return [
        {
            "page": page,
            "textChars": 40 if page <= candidate_count else 200,
            "imageObjectCount": 1 if page <= candidate_count else 0,
            "keywordHits": [],
            "mineruAssetCount": 0,
            "visualCandidate": page <= candidate_count,
            "candidateReasons": ["image_object"] if page <= candidate_count else [],
            "text": "manual page context",
        }
        for page in range(1, page_count + 1)
    ]


def install_pipeline_mocks(monkeypatch, profiles: list[dict[str, object]], calls: list[int]) -> None:
    monkeypatch.setattr(pipeline, "inventory_pdf_pages", lambda *_: profiles)
    monkeypatch.setattr(
        pipeline,
        "renderer_readiness",
        lambda: {"ready": True, "renderer": "pdftoppm", "status": "ready"},
    )

    def process_page(pdf_path, page_profile, output_path, policy, requested_provider):
        page = int(page_profile["page"])
        calls.append(page)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"jpeg")
        return {
            "assetId": f"page-{page:04d}",
            "assetType": "page_visual",
            "page": page,
            "assetFile": output_path,
            "renderer": "pdftoppm",
            "ocrProcessed": True,
            "analysisProcessed": True,
            "analysis": {
                "visualType": "assembly_diagram",
                "summary": "assembly",
                "components": ["component"],
                "operations": ["inspect"],
                "figureLabels": [],
                "safetyWarnings": [],
                "uncertainties": [],
                "ocrText": "ocr",
                "nearbyText": "context",
                "provider": "openai",
                "model": "test-model",
                "fallback": False,
                "fallbackReason": "",
                "semanticVerified": True,
            },
        }

    monkeypatch.setattr(pipeline, "process_visual_page", process_page)


def run_pipeline(tmp_path: Path, monkeypatch, mode: str, page_count: int, candidate_count: int):
    calls: list[int] = []
    install_pipeline_mocks(monkeypatch, inventory(page_count, candidate_count), calls)
    pdf_path = tmp_path / "knowledge" / "files" / "manual.pdf"
    pdf_path.parent.mkdir(parents=True)
    pdf_path.write_bytes(b"pdf")
    result = pipeline.run_manual_visual_pipeline(
        {"id": "kdoc-test", "fileName": "manual.pdf", "sourceName": "manual"},
        pdf_path,
        resolve_parser_policy(mode),
    )
    return result, calls


def test_smart_processes_all_36_visual_pages_in_41_page_manual(tmp_path, monkeypatch) -> None:
    result, calls = run_pipeline(tmp_path, monkeypatch, "smart_multimodal", 41, 36)
    assert len(calls) == 36
    assert result["visualCandidatePages"] == 36
    assert result["visualPagesRendered"] == 36
    assert result["visualPagesOcrProcessed"] == 36
    assert result["realMultimodalPages"] == 36
    assert result["status"] == "completed"


def test_full_visual_processes_every_page(tmp_path, monkeypatch) -> None:
    result, calls = run_pipeline(tmp_path, monkeypatch, "full_visual", 41, 36)
    assert len(calls) == 41
    assert result["visualPagesRendered"] == 41
    assert result["visualPagesAnalyzed"] == 41
    assert result["realMultimodalPages"] == 41


def test_smart_caps_at_80_and_reports_partial_coverage(tmp_path, monkeypatch) -> None:
    result, calls = run_pipeline(tmp_path, monkeypatch, "smart_multimodal", 100, 100)
    assert len(calls) == 80
    assert result["visualCoverageRatio"] == 0.8
    assert result["status"] == "completed_with_warnings"


def test_full_visual_rejects_more_than_300_pages_before_model_calls(tmp_path, monkeypatch) -> None:
    calls: list[int] = []
    install_pipeline_mocks(monkeypatch, inventory(301, 301), calls)
    pdf_path = tmp_path / "knowledge" / "files" / "manual.pdf"
    pdf_path.parent.mkdir(parents=True)
    pdf_path.write_bytes(b"pdf")
    with pytest.raises(HTTPException) as exc_info:
        pipeline.run_manual_visual_pipeline(
            {"id": "kdoc-test", "fileName": "manual.pdf", "sourceName": "manual"},
            pdf_path,
            resolve_parser_policy("full_visual"),
        )
    assert exc_info.value.status_code == 422
    assert calls == []


def test_manual_page_json_controls_semantic_verification() -> None:
    valid = multimodal_adapter.manual_page_from_model_text(
        '{"visualType":"wiring_diagram","summary":"点火线路","components":["点火线圈"],"operations":[],"figureLabels":[],"safetyWarnings":[],"uncertainties":[]}',
        "page.jpg",
        "openai",
        "test-model",
    )
    invalid = multimodal_adapter.manual_page_from_model_text(
        "not-json model output",
        "page.jpg",
        "openai",
        "test-model",
    )
    assert valid["semanticVerified"] is True
    assert valid["fallback"] is False
    assert invalid["semanticVerified"] is False
    assert invalid["fallback"] is True


def test_manual_page_timeout_retries_only_once(monkeypatch, tmp_path) -> None:
    image = tmp_path / "page.jpg"
    image.write_bytes(b"jpeg")
    calls: list[int] = []
    monkeypatch.setattr(multimodal_adapter, "configured_multimodal_provider", lambda *_: "openai")
    monkeypatch.setattr(multimodal_adapter, "remote_api_disabled", lambda: False)
    monkeypatch.setattr(multimodal_adapter, "analyze_ocr_document", lambda *_: {"text": "ocr", "textSegments": ["ocr"]})
    monkeypatch.setattr(multimodal_adapter, "record_fallback", lambda *_: None)
    monkeypatch.setattr(multimodal_adapter.time, "sleep", lambda *_: None)

    def fail_timeout(*args, **kwargs):
        calls.append(1)
        raise TimeoutError("timed out")

    monkeypatch.setattr(multimodal_adapter, "real_multimodal_analysis", fail_timeout)
    result = multimodal_adapter.analyze_multimodal_document(
        image,
        "page",
        "jpg",
        analysis_task="manual_page",
    )
    assert len(calls) == 2
    assert result["provider"] == "mock"
    assert result["semanticVerified"] is False
