from __future__ import annotations

import shutil
from typing import Any

from fastapi.testclient import TestClient

import backend.app.main as main_module
from backend.app.main import app


def make_client(tmp_path, monkeypatch) -> TestClient:
    source = tmp_path / "source"
    shutil.copytree("data/examples", source)
    monkeypatch.setenv("APP_EXAMPLES_DIR", str(source))
    monkeypatch.setenv("APP_KNOWLEDGE_DIR", str(tmp_path / "knowledge"))
    monkeypatch.setenv("MINERU_ENABLED", "false")
    return TestClient(app)


def test_multimodal_diagnosis_uses_image_clues_without_promoting_image_to_evidence(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    def fake_ocr(path: str, source_name: str, suffix: str, provider: str | None = None) -> dict[str, Any]:
        return {
            "provider": "mock-ocr",
            "text": "OCR_LOW_FUEL_PRESSURE",
            "fallback": False,
        }

    def fake_multimodal(path: str, source_name: str, suffix: str, provider: str | None = None) -> dict[str, Any]:
        return {
            "provider": "mock-vision",
            "summary": "VISION_FUEL_LEAK",
            "observations": ["VISION_PIPE_WET", "VISION_NO_ALARM"],
            "fallback": False,
        }

    def fake_diagnose(request: Any, provider: str | None = None) -> dict[str, Any]:
        assert "OCR_LOW_FUEL_PRESSURE" in request.faultText
        assert "VISION_FUEL_LEAK" in request.faultText
        assert request.maintenanceLevel == "emergency"
        return {
            "answer": "【初步判断】基于 approved 证据给出建议。",
            "structuredAnswer": {"preliminary": "基于 approved 证据给出建议。"},
            "citations": [
                {
                    "sourceId": "manual-approved-001",
                    "sourceName": "燃油系统手册",
                    "sourceType": "manual",
                    "chunkId": "chunk-approved-001",
                    "snippet": "approved 证据",
                    "page": 3,
                    "section": "燃油检查",
                    "version": 1,
                }
            ],
            "evidencePack": {"items": [], "warnings": [], "riskLevel": "medium"},
            "provider": "mock",
            "fallback": False,
            "fallbackReason": "",
        }

    monkeypatch.setattr(main_module, "analyze_ocr_document", fake_ocr)
    monkeypatch.setattr(main_module, "analyze_multimodal_document", fake_multimodal)
    monkeypatch.setattr(main_module, "diagnose_with_rag", fake_diagnose)

    response = client.post(
        "/api/multimodal/diagnosis",
        data={
            "deviceModel": "发动机-示例型号 A",
            "faultText": "启动困难",
            "maintenanceLevel": "emergency",
            "riskLevel": "critical",
            "topK": "5",
        },
        files={"image": ("fault.png", b"image-bytes", "image/png")},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["queryContext"]["clueType"] == "inputClue"
    assert data["queryContext"]["fallbackUsed"] is False
    assert "OCR_LOW_FUEL_PRESSURE" in data["queryContext"]["ocrText"]
    assert data["imageAnalysis"]["provider"] == "mock-vision"
    assert data["citations"][0]["sourceId"] == "manual-approved-001"


def test_multimodal_diagnosis_keeps_running_when_vision_falls_back(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    monkeypatch.setattr(
        main_module,
        "analyze_ocr_document",
        lambda *_args, **_kwargs: {"provider": "mock-ocr", "text": "OCR 识别到温度过高", "fallback": False},
    )
    monkeypatch.setattr(
        main_module,
        "analyze_multimodal_document",
        lambda *_args, **_kwargs: {
            "provider": "mock-vision",
            "summary": "",
            "observations": [],
            "fallback": True,
            "fallbackReason": "vision unavailable",
        },
    )
    monkeypatch.setattr(
        main_module,
        "diagnose_with_rag",
        lambda *_args, **_kwargs: {
            "answer": "template answer",
            "structuredAnswer": {},
            "citations": [],
            "evidencePack": {},
            "provider": "mock",
            "fallback": True,
            "fallbackReason": "llm unavailable",
        },
    )

    response = client.post(
        "/api/multimodal/diagnosis",
        data={"deviceModel": "泵站-01", "faultText": "异常发热"},
        files={"image": ("fault.png", b"image-bytes", "image/png")},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["fallback"] is True
    assert data["imageAnalysis"]["fallback"] is True
    assert data["queryContext"]["ocrText"] == "OCR 识别到温度过高"
