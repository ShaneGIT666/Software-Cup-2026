from pathlib import Path

import backend.app.manual_visual_pipeline as pipeline
from backend.app.parser_modes import resolve_parser_policy


def run_single_page(tmp_path: Path, monkeypatch, *, semantic: bool, ocr_text: str, segments=None):
    profile = {
        "page": 1, "textChars": 10, "imageObjectCount": 1, "keywordHits": [],
        "mineruAssetCount": 0, "visualCandidate": True, "candidateReasons": ["image_object"],
        "text": "context",
    }
    monkeypatch.setattr(pipeline, "inventory_pdf_pages", lambda *_: [profile])
    monkeypatch.setattr(
        pipeline,
        "renderer_operational_readiness",
        lambda: {"ready": True, "renderer": "pymupdf", "status": "ready"},
    )

    def process(_pdf, _profile, output, _policy, _provider, *, selected_renderer):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"jpeg")
        analysis = pipeline._visual_result(
            {
                "visualType": "photo", "summary": "component", "components": ["part"],
                "operations": [], "figureLabels": [], "safetyWarnings": [], "uncertainties": [],
                "provider": "openai", "model": "model", "fallback": False,
                "semanticVerified": semantic, "imageInputSent": True,
            },
            {"text": ocr_text, "textSegments": segments or []},
            "context",
        )
        return {
            "assetId": "page-0001", "assetType": "page_visual", "page": 1,
            "assetFile": output, "renderer": selected_renderer, "ocrProcessed": True,
            "analysisProcessed": True, "analysis": analysis,
        }

    monkeypatch.setattr(pipeline, "process_visual_page", process)
    pdf = tmp_path / "knowledge" / "files" / "manual.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"pdf")
    return pipeline.run_manual_visual_pipeline(
        {"id": "doc", "fileName": "manual.pdf", "sourceName": "manual"},
        pdf,
        resolve_parser_policy("smart_multimodal"),
    )


def test_unverified_page_forces_warning(tmp_path: Path, monkeypatch) -> None:
    result = run_single_page(tmp_path, monkeypatch, semantic=False, ocr_text="ocr")
    assert result["status"] == "completed_with_warnings"
    assert result["unverifiedVisualPages"] == 1
    assert result["realMultimodalPages"] == 0
    assert "not semantically verified" in result["visualFailureReason"]


def test_ocr_empty_is_counted_without_failing_page(tmp_path: Path, monkeypatch) -> None:
    result = run_single_page(tmp_path, monkeypatch, semantic=True, ocr_text="")
    assert result["visualPagesOcrProcessed"] == 1
    assert result["ocrTextAvailablePages"] == 0
    assert result["ocrEmptyPages"] == 1
    assert result["visualFailedPages"] == []
    assert result["status"] == "completed"


def test_ocr_segments_count_as_available_and_verified_stays_clean(tmp_path: Path, monkeypatch) -> None:
    result = run_single_page(tmp_path, monkeypatch, semantic=True, ocr_text="", segments=["label"])
    assert result["ocrTextAvailablePages"] == 1
    assert result["ocrEmptyPages"] == 0
    assert result["unverifiedVisualPages"] == 0
    assert result["status"] == "completed"
