from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from fastapi import HTTPException
from pypdf import PdfWriter

import backend.app.parser_router as parser_router
from backend.app.parser_modes import resolve_parser_policy


def pdf_bytes(page_count: int = 1) -> bytes:
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=200, height=200)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_parser_mode_contract_and_default() -> None:
    assert resolve_parser_policy(None).mode == "smart_multimodal"
    assert resolve_parser_policy("text_fast").render_scope == "none"
    assert resolve_parser_policy("smart_multimodal").visual_page_limit == 80
    assert resolve_parser_policy("full_visual").visual_page_limit == 300
    with pytest.raises(HTTPException) as exc_info:
        resolve_parser_policy("unknown")
    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "parser_mode must be one of text_fast, smart_multimodal, full_visual"


def test_text_fast_pdf_bypasses_mineru(monkeypatch, tmp_path: Path) -> None:
    def fail_mineru(*args, **kwargs):
        raise AssertionError("MinerU must not run in text_fast mode")

    monkeypatch.setattr(parser_router, "parse_with_mineru", fail_mineru)
    content = pdf_bytes()
    result = parser_router.parse_document(
        tmp_path / "manual.pdf",
        "pdf",
        content,
        resolve_parser_policy("text_fast"),
    )
    assert result["parser"] == "pypdf"
    assert result["mineruAttempted"] is False
    assert result["visualAnalysisRequested"] is False


def test_parser_policies_are_immutable_and_isolated() -> None:
    fast = resolve_parser_policy("text_fast")
    full = resolve_parser_policy("full_visual")
    assert fast.use_mineru is False
    assert full.use_mineru is True
    assert fast.render_scope == "none"
    assert full.render_scope == "all"
    with pytest.raises(Exception):
        fast.mode = "full_visual"  # type: ignore[misc]
