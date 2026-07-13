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
        "renderer_operational_readiness",
        lambda: {"ready": True, "renderer": "pdftoppm", "status": "ready"},
    )

    def process_page(pdf_path, page_profile, output_path, policy, requested_provider, *, selected_renderer):
        assert selected_renderer == "pdftoppm"
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


def test_smart_unavailable_reports_all_candidates_without_visual_chunks(tmp_path, monkeypatch) -> None:
    profiles = inventory(41, 36)
    monkeypatch.setattr(pipeline, "inventory_pdf_pages", lambda *_: profiles)
    monkeypatch.setattr(
        pipeline,
        "renderer_operational_readiness",
        lambda: {"ready": False, "renderer": "unavailable", "status": "unavailable"},
    )
    pdf_path = tmp_path / "knowledge" / "files" / "manual.pdf"
    pdf_path.parent.mkdir(parents=True)
    pdf_path.write_bytes(b"pdf")
    result = pipeline.run_manual_visual_pipeline(
        {"id": "kdoc-test", "fileName": "manual.pdf", "sourceName": "manual"},
        pdf_path,
        resolve_parser_policy("smart_multimodal"),
    )
    assert result["pageCount"] == 41
    assert result["visualCandidatePages"] == 36
    assert result["visualFailedPages"] == list(range(1, 37))
    assert result["fallbackVisualPages"] == 36
    assert result["visualChunks"] == []
    assert result["status"] == "completed_with_warnings"


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


def test_full_visual_reports_mineru_asset_truncation(tmp_path, monkeypatch) -> None:
    calls: list[int] = []
    install_pipeline_mocks(monkeypatch, inventory(1, 1), calls)
    monkeypatch.setenv("FULL_VISUAL_MAX_ASSETS", "500")
    pdf_path = tmp_path / "knowledge" / "files" / "manual.pdf"
    pdf_path.parent.mkdir(parents=True)
    pdf_path.write_bytes(b"pdf")
    parsed_root = tmp_path / "knowledge" / "parsed" / "kdoc-test"
    shared_asset = parsed_root / "assets" / "shared.jpg"
    shared_asset.parent.mkdir(parents=True)
    shared_asset.write_bytes(b"jpeg")
    assets = [
        {
            "assetId": f"mineru-{index:04d}",
            "relativePath": "assets/shared.jpg",
            "page": 1,
            "caption": "component",
        }
        for index in range(1, 601)
    ]

    def process_asset(asset, asset_path, requested_provider):
        return {
            "assetId": asset["assetId"],
            "assetType": "mineru_asset",
            "page": 1,
            "assetFile": asset_path,
            "renderer": "mineru",
            "ocrProcessed": True,
            "analysisProcessed": True,
            "analysis": {
                "visualType": "photo",
                "summary": "component",
                "components": ["component"],
                "operations": [],
                "figureLabels": [],
                "safetyWarnings": [],
                "uncertainties": [],
                "ocrText": "",
                "nearbyText": "",
                "provider": "openai",
                "model": "model",
                "fallback": False,
                "fallbackReason": "",
                "semanticVerified": True,
                "imageInputSent": True,
            },
        }

    monkeypatch.setattr(pipeline, "process_mineru_asset", process_asset)
    result = pipeline.run_manual_visual_pipeline(
        {"id": "kdoc-test", "fileName": "manual.pdf", "sourceName": "manual"},
        pdf_path,
        resolve_parser_policy("full_visual"),
        mineru_assets=assets,
    )
    assert result["analyzedMineruAssetCount"] == 500
    assert result["realMultimodalMineruAssetCount"] == 500
    assert result["fallbackMineruAssetCount"] == 0
    assert result["failedMineruAssetCount"] == 0
    assert result["mineruAssetsTruncated"] is True
    assert result["unprocessedMineruAssetCount"] == 100
    assert result["status"] == "completed_with_warnings"


def test_mineru_assets_are_classified_as_real_fallback_and_failed(tmp_path, monkeypatch) -> None:
    calls: list[int] = []
    install_pipeline_mocks(monkeypatch, inventory(1, 1), calls)
    pdf_path = tmp_path / "knowledge" / "files" / "manual.pdf"
    pdf_path.parent.mkdir(parents=True)
    pdf_path.write_bytes(b"pdf")
    parsed_root = tmp_path / "knowledge" / "parsed" / "kdoc-test"
    asset_path = parsed_root / "assets" / "shared.jpg"
    asset_path.parent.mkdir(parents=True)
    asset_path.write_bytes(b"jpeg")
    assets = [
        {"assetId": f"mineru-{index}", "relativePath": "assets/shared.jpg", "page": 1}
        for index in range(1, 4)
    ]

    def process_asset(asset, *_args):
        if asset["assetId"] == "mineru-3":
            raise RuntimeError("failed")
        fallback = asset["assetId"] == "mineru-2"
        return {
            "assetId": asset["assetId"], "assetType": "mineru_asset", "page": 1,
            "assetFile": asset_path, "analysis": {
                "summary": "asset", "components": [], "operations": [], "figureLabels": [],
                "safetyWarnings": [], "uncertainties": [], "ocrText": "", "model": "model",
                "provider": "mock" if fallback else "openai", "fallback": fallback,
                "semanticVerified": not fallback, "imageInputSent": not fallback,
            },
        }

    monkeypatch.setattr(pipeline, "process_mineru_asset", process_asset)
    result = pipeline.run_manual_visual_pipeline(
        {"id": "kdoc-test", "fileName": "manual.pdf", "sourceName": "manual"},
        pdf_path,
        resolve_parser_policy("full_visual"),
        mineru_assets=assets,
    )
    assert result["realMultimodalMineruAssetCount"] == 1
    assert result["fallbackMineruAssetCount"] == 1
    assert result["failedMineruAssetCount"] == 1
    assert result["analyzedMineruAssetCount"] == 2
    assert result["status"] == "completed_with_warnings"


def test_manual_page_json_controls_semantic_verification() -> None:
    valid = multimodal_adapter.manual_page_from_model_text(
        '{"visualType":"wiring_diagram","summary":"点火线路","components":["点火线圈"],"operations":[],"figureLabels":[],"safetyWarnings":[],"uncertainties":[]}',
        "page.jpg",
        "openai",
        "test-model",
        image_input_sent=True,
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


def test_manual_page_accepts_fenced_or_thinking_prefixed_json() -> None:
    payload = (
        '{"visualType":"photo","summary":"黑色方形","components":[],"operations":[],'
        '"figureLabels":[],"safetyWarnings":[],"uncertainties":[]}'
    )
    for response in (f"```json\n{payload}\n```", f"<think>inspect image</think>\n{payload}"):
        result = multimodal_adapter.manual_page_from_model_text(
            response, "probe.png", "openai", "vision-model", image_input_sent=True
        )
        assert result["semanticVerified"] is True
        assert result["fallback"] is False


def test_manual_page_semantic_verification_requires_image_model_and_content() -> None:
    payload = '{"visualType":"wiring_diagram","summary":"wiring","components":[],"operations":[],"figureLabels":[],"safetyWarnings":[],"uncertainties":[]}'
    assert multimodal_adapter.manual_page_from_model_text(
        payload, "page.jpg", "openai", "model", image_input_sent=False
    )["semanticVerified"] is False
    assert multimodal_adapter.manual_page_from_model_text(
        '{"visualType":"unknown","summary":"","components":[],"operations":[],"figureLabels":[],"safetyWarnings":[],"uncertainties":[]}',
        "page.jpg",
        "openai",
        "model",
        image_input_sent=True,
    )["semanticVerified"] is False
    anthropic = multimodal_adapter.manual_page_from_model_text(
        payload, "page.jpg", "anthropic", "claude", image_input_sent=True
    )
    assert anthropic["semanticVerified"] is True
    assert anthropic["imageInputSent"] is True
    assert multimodal_adapter.manual_page_from_model_text(
        payload, "page.jpg", "mock", "mock", image_input_sent=True
    )["semanticVerified"] is False


def clear_multimodal_environment(monkeypatch) -> None:
    for name in (
        "MULTIMODAL_OPENAI_API_KEY",
        "OPENAI_API_KEY",
        "MULTIMODAL_OPENAI_MODEL",
        "OPENAI_MODEL",
        "LOCAL_MULTIMODAL_MODEL",
        "LOCAL_LLM_MODEL",
        "LOCAL_MULTIMODAL_BASE_URL",
        "LOCAL_LLM_BASE_URL",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)


def test_multimodal_readiness_for_openai_local_anthropic_and_mock(monkeypatch) -> None:
    clear_multimodal_environment(monkeypatch)
    monkeypatch.setenv("REMOTE_API_MODE", "auto")
    assert multimodal_adapter.multimodal_readiness("openai")["status"] == "missing_key"
    monkeypatch.setenv("MULTIMODAL_OPENAI_API_KEY", "key")
    monkeypatch.setenv("MULTIMODAL_OPENAI_MODEL", "model")
    assert multimodal_adapter.multimodal_readiness("openai")["ready"] is True
    monkeypatch.setenv("REMOTE_API_MODE", "off")
    assert multimodal_adapter.multimodal_readiness("openai")["status"] == "remote_disabled"

    monkeypatch.setenv("LOCAL_MULTIMODAL_MODEL", "local-model")
    monkeypatch.setenv("LOCAL_MULTIMODAL_BASE_URL", "http://127.0.0.1:11434/v1")
    local = multimodal_adapter.multimodal_readiness("local")
    assert local["ready"] is True
    assert local["credentialConfigured"] is True
    assert local["remoteAllowed"] is True

    monkeypatch.setenv("REMOTE_API_MODE", "auto")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude")
    assert multimodal_adapter.multimodal_readiness("anthropic")["ready"] is True
    assert multimodal_adapter.multimodal_readiness("mock")["status"] == "mock"


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
