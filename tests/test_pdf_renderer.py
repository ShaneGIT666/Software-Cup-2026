from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

import backend.app.pdf_renderer as pdf_renderer


def test_renderer_readiness_prefers_pdftoppm(monkeypatch) -> None:
    monkeypatch.setattr(pdf_renderer, "_pdftoppm_available", lambda: True)
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object() if name == "fitz" else None)
    assert pdf_renderer.renderer_readiness()["renderer"] == "pdftoppm"


def test_renderer_readiness_falls_back_to_pymupdf(monkeypatch) -> None:
    monkeypatch.setattr(pdf_renderer, "_pdftoppm_available", lambda: False)
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object() if name == "fitz" else None)
    assert pdf_renderer.renderer_readiness()["renderer"] == "pymupdf"


def test_renderer_readiness_reports_unavailable_without_paths(monkeypatch) -> None:
    monkeypatch.setattr(pdf_renderer, "_pdftoppm_available", lambda: False)
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    readiness = pdf_renderer.renderer_readiness()
    assert readiness["renderer"] == "unavailable"
    assert readiness["status"] == "unavailable"
    assert not any("\\" in str(value) or ":/" in str(value) for value in readiness.values())


def test_render_pdf_page_is_one_based(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(pdf_renderer, "renderer_readiness", lambda: {"ready": True, "renderer": "pymupdf"})
    with pytest.raises(ValueError, match="1-based"):
        pdf_renderer.render_pdf_page(tmp_path / "manual.pdf", 0, tmp_path / "page.jpg", 120)
