from __future__ import annotations

import shutil
from typing import Any

from fastapi.testclient import TestClient

import backend.app.data_store as data_store
import backend.app.main as main_module
from backend.app.main import app


def make_client(tmp_path, monkeypatch) -> TestClient:
    source = tmp_path / "source"
    shutil.copytree("data/examples", source)
    monkeypatch.setenv("APP_EXAMPLES_DIR", str(source))
    monkeypatch.setenv("APP_KNOWLEDGE_DIR", str(tmp_path / "knowledge"))
    monkeypatch.setenv("MINERU_ENABLED", "false")
    monkeypatch.setenv("REMOTE_API_MODE", "off")
    return TestClient(app)


def test_multimodal_signals_are_returned_and_annotate_citations(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    monkeypatch.setattr(
        main_module,
        "analyze_ocr_document",
        lambda *_args, **_kwargs: {"provider": "mock-ocr", "text": "OCR_LOW_FUEL_PRESSURE", "fallback": False},
    )
    monkeypatch.setattr(
        main_module,
        "analyze_multimodal_document",
        lambda *_args, **_kwargs: {
            "provider": "mock-vision",
            "summary": "VISION_FUEL_LEAK",
            "keyComponents": ["fuel pipe"],
            "faultSymptoms": ["wet stain"],
            "textSegments": ["warning label visible"],
            "fallback": False,
        },
    )

    def fake_diagnose(request: Any, provider: str | None = None) -> dict[str, Any]:
        assert "OCR_LOW_FUEL_PRESSURE" in request.faultText
        assert "VISION_FUEL_LEAK" in request.faultText
        assert "fuel pipe" in request.faultText
        return {
            "answer": "template answer",
            "structuredAnswer": {"complianceChecks": ["人工复核"]},
            "citations": [
                {
                    "id": "manual-1",
                    "title": "燃油系统检查",
                    "sourceId": "manual-approved-001",
                    "sourceName": "燃油系统手册",
                    "sourceType": "manual",
                    "chunkId": "chunk-approved-001",
                    "snippet": "approved 证据",
                    "confidence": 0.91,
                    "page": 3,
                    "section": "燃油检查",
                    "version": 1,
                    "scoreBreakdown": {"score": 9},
                }
            ],
            "evidencePack": {"items": [], "warnings": [], "riskLevel": "medium"},
            "provider": "mock",
            "fallback": False,
            "fallbackReason": "",
        }

    monkeypatch.setattr(main_module, "diagnose_with_rag", fake_diagnose)

    response = client.post(
        "/api/multimodal/diagnosis",
        data={"deviceModel": "发动机-示例型号 A", "faultText": "启动困难", "maintenanceLevel": "emergency"},
        files={"image": ("fault.png", b"image-bytes", "image/png")},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    signals = data["multimodalSignals"]
    assert signals["ocrText"] == "OCR_LOW_FUEL_PRESSURE"
    assert signals["detectedComponents"] == ["fuel pipe"]
    assert "wet stain" in signals["visualSymptoms"]
    assert signals["matchMode"] == "semantic_clue_to_text_retrieval"
    assert data["queryContext"]["multimodalSignals"]["signalSource"] == "ocr+multimodal"
    breakdown = data["citations"][0]["scoreBreakdown"]
    assert breakdown["crossModalMatchMode"] == "semantic_clue_to_text_retrieval"
    assert "OCR_LOW_FUEL_PRESSURE" in breakdown["multimodalSignals"]
    assert "snippet" in breakdown["crossModalMatchedFields"]


def test_multimodal_signal_fallback_does_not_return_500(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    monkeypatch.setattr(
        main_module,
        "analyze_ocr_document",
        lambda *_args, **_kwargs: {"provider": "mock-ocr", "text": "OCR 温度高", "fallback": False},
    )

    def broken_multimodal(*_args, **_kwargs):
        raise RuntimeError("vision unavailable")

    monkeypatch.setattr(main_module, "analyze_multimodal_document", broken_multimodal)
    monkeypatch.setattr(
        main_module,
        "diagnose_with_rag",
        lambda *_args, **_kwargs: {
            "answer": "fallback answer",
            "structuredAnswer": {},
            "citations": [],
            "evidencePack": {},
            "provider": "mock",
            "fallback": True,
            "fallbackReason": "mock fallback",
        },
    )

    response = client.post(
        "/api/multimodal/diagnosis",
        data={"deviceModel": "泵站-P1", "faultText": "异常发热"},
        files={"image": ("fault.png", b"image-bytes", "image/png")},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["fallback"] is True
    assert data["multimodalSignals"]["fallback"] is True
    assert data["imageAnalysis"]["fallback"] is True
    assert "vision unavailable" in data["imageAnalysis"]["fallbackReason"]


def test_multimodal_diagnosis_still_excludes_unapproved_chunks(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    data_store.save_document_chunks(
        [
            {
                "id": "chunk-pending-cross-modal",
                "documentId": "doc-pending-cross-modal",
                "title": "未审核图片诊断资料",
                "sourceName": "未审核资料",
                "sourceType": "document",
                "content": "UNAPPROVED_VISUAL_ONLY_TOKEN",
                "snippet": "UNAPPROVED_VISUAL_ONLY_TOKEN",
                "review_status": "pending_review",
                "keywords": ["UNAPPROVED_VISUAL_ONLY_TOKEN"],
            },
            {
                "id": "chunk-rejected-cross-modal",
                "documentId": "doc-rejected-cross-modal",
                "title": "已拒绝图片诊断资料",
                "sourceName": "已拒绝资料",
                "sourceType": "document",
                "content": "REJECTED_VISUAL_ONLY_TOKEN",
                "snippet": "REJECTED_VISUAL_ONLY_TOKEN",
                "review_status": "rejected",
                "keywords": ["REJECTED_VISUAL_ONLY_TOKEN"],
            },
        ]
    )
    monkeypatch.setattr(
        main_module,
        "analyze_ocr_document",
        lambda *_args, **_kwargs: {"provider": "mock-ocr", "text": "UNAPPROVED_VISUAL_ONLY_TOKEN", "fallback": False},
    )
    monkeypatch.setattr(
        main_module,
        "analyze_multimodal_document",
        lambda *_args, **_kwargs: {
            "provider": "mock-vision",
            "summary": "REJECTED_VISUAL_ONLY_TOKEN",
            "fallback": False,
        },
    )

    response = client.post(
        "/api/multimodal/diagnosis",
        data={"deviceModel": "测试设备", "faultText": "图片线索隔离"},
        files={"image": ("fault.png", b"image-bytes", "image/png")},
    )

    assert response.status_code == 200
    citations = response.json()["data"]["citations"]
    assert all(item.get("chunkId") not in {"chunk-pending-cross-modal", "chunk-rejected-cross-modal"} for item in citations)
    assert all(item.get("reviewStatus", "approved") == "approved" for item in citations)
