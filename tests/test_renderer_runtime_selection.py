from pathlib import Path

import pytest

import backend.app.pdf_renderer as renderer


@pytest.mark.parametrize("selected", ["pdftoppm", "pymupdf"])
def test_selected_renderer_is_used_without_any_readiness(monkeypatch, tmp_path: Path, selected: str) -> None:
    calls: list[str] = []
    monkeypatch.setattr(renderer, "renderer_readiness", lambda: pytest.fail("legacy readiness called"))
    monkeypatch.setattr(renderer, "renderer_operational_readiness", lambda: pytest.fail("operational readiness called"))
    monkeypatch.setattr(
        renderer,
        "_render_with_pdftoppm",
        lambda _pdf, _page, output, _dpi, _timeout: (calls.append("pdftoppm"), output.write_bytes(b"jpg")),
    )
    monkeypatch.setattr(
        renderer,
        "_render_with_pymupdf",
        lambda _pdf, _page, output, _dpi: (calls.append("pymupdf"), output.write_bytes(b"jpg")),
    )
    result = renderer.render_pdf_page(
        tmp_path / "manual.pdf", 1, tmp_path / "page.jpg", 120, selected_renderer=selected
    )
    assert calls == [selected]
    assert result["renderer"] == selected


def test_no_selection_uses_operational_readiness(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(renderer, "renderer_readiness", lambda: pytest.fail("legacy readiness called"))
    monkeypatch.setattr(
        renderer,
        "renderer_operational_readiness",
        lambda: {"ready": True, "renderer": "pymupdf"},
    )
    monkeypatch.setattr(renderer, "_render_with_pymupdf", lambda _p, _n, output, _d: output.write_bytes(b"jpg"))
    result = renderer.render_pdf_page(tmp_path / "manual.pdf", 1, tmp_path / "page.jpg", 120)
    assert result["renderer"] == "pymupdf"


def test_no_selection_fails_closed_when_operational_renderer_is_unavailable(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        renderer,
        "renderer_operational_readiness",
        lambda: {"ready": False, "renderer": "unavailable"},
    )
    with pytest.raises(renderer.RendererUnavailable):
        renderer.render_pdf_page(tmp_path / "manual.pdf", 1, tmp_path / "page.jpg", 120)
