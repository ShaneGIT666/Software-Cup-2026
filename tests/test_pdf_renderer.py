from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil

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


def install_operational_mocks(monkeypatch, *, version_ok: bool, pymupdf: bool = False) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: "pdftoppm" if name == "pdftoppm" else None)
    monkeypatch.setattr(pdf_renderer, "_pdftoppm_available", lambda: version_ok)
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object() if name == "fitz" and pymupdf else None)
    monkeypatch.setattr(pdf_renderer, "_smoke_pdf", lambda path: path.write_bytes(b"pdf"))


def test_operational_readiness_accepts_pdftoppm_smoke_even_if_version_probe_fails(monkeypatch) -> None:
    install_operational_mocks(monkeypatch, version_ok=False)
    monkeypatch.setattr(
        pdf_renderer,
        "_render_with_pdftoppm",
        lambda pdf, page, output, dpi, timeout: output.write_bytes(b"jpeg"),
    )
    readiness = pdf_renderer.renderer_operational_readiness()
    assert readiness == {
        "ready": True,
        "renderer": "pdftoppm",
        "status": "ready",
        "commandFound": True,
        "versionProbeOk": False,
        "smokeRenderOk": True,
        "failureCategory": "none",
    }


def test_operational_readiness_falls_back_to_pymupdf_after_smoke_failure(monkeypatch) -> None:
    install_operational_mocks(monkeypatch, version_ok=True, pymupdf=True)
    monkeypatch.setattr(
        pdf_renderer,
        "_render_with_pdftoppm",
        lambda *args: (_ for _ in ()).throw(pdf_renderer.RenderExecutionError("failed")),
    )
    monkeypatch.setattr(
        pdf_renderer,
        "_render_with_pymupdf",
        lambda pdf, page, output, dpi: output.write_bytes(b"jpeg"),
    )
    readiness = pdf_renderer.renderer_operational_readiness()
    assert readiness["ready"] is True
    assert readiness["renderer"] == "pymupdf"
    assert readiness["smokeRenderOk"] is True


def test_operational_readiness_reports_timeout_and_cleans_temp(monkeypatch, tmp_path: Path) -> None:
    install_operational_mocks(monkeypatch, version_ok=True)
    monkeypatch.setattr(pdf_renderer.tempfile, "tempdir", str(tmp_path))
    monkeypatch.setattr(
        pdf_renderer,
        "_render_with_pdftoppm",
        lambda *args: (_ for _ in ()).throw(TimeoutError("timeout")),
    )
    readiness = pdf_renderer.renderer_operational_readiness()
    assert readiness["ready"] is False
    assert readiness["failureCategory"] == "timeout"
    assert list(tmp_path.glob("pdf-renderer-smoke-*")) == []
