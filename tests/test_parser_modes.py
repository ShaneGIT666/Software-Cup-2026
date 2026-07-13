from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import subprocess

import pytest
from fastapi import HTTPException
from pypdf import PdfWriter

import backend.app.parser_router as parser_router
import backend.app.mineru_adapter as mineru_adapter
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


def test_mineru_mode_specific_timeouts_and_legacy_fallback(monkeypatch) -> None:
    monkeypatch.setenv("MINERU_TIMEOUT_SECONDS", "240")
    monkeypatch.delenv("MINERU_SMART_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("MINERU_FULL_TIMEOUT_SECONDS", raising=False)
    assert resolve_parser_policy("smart_multimodal").mineru_timeout_seconds == 240
    assert resolve_parser_policy("full_visual").mineru_timeout_seconds == 240

    monkeypatch.setenv("MINERU_SMART_TIMEOUT_SECONDS", "181")
    monkeypatch.setenv("MINERU_FULL_TIMEOUT_SECONDS", "601")
    smart = resolve_parser_policy("smart_multimodal")
    full = resolve_parser_policy("full_visual")
    assert smart.mineru_timeout_seconds == 181
    assert full.mineru_timeout_seconds == 601
    assert resolve_parser_policy("text_fast").mineru_timeout_seconds == 0


class FakeProcess:
    def __init__(self, *, timeout: bool = False) -> None:
        self.returncode = 0
        self.timeout = timeout
        self.wait_count = 0
        self.pid = 1234

    def wait(self, timeout=None):
        self.wait_count += 1
        if self.timeout and self.wait_count == 1:
            raise subprocess.TimeoutExpired("mineru", timeout)
        return 0

    def kill(self) -> None:
        self.returncode = -9


@pytest.mark.parametrize("timeout", [False, True])
def test_mineru_log_directory_is_cleaned(monkeypatch, tmp_path: Path, timeout: bool) -> None:
    log_dir = tmp_path / "mineru-log"

    def make_temp(prefix: str) -> str:
        log_dir.mkdir()
        return str(log_dir)

    monkeypatch.setattr(mineru_adapter.tempfile, "mkdtemp", make_temp)
    monkeypatch.setattr(mineru_adapter.subprocess, "Popen", lambda *args, **kwargs: FakeProcess(timeout=timeout))
    monkeypatch.setattr(
        mineru_adapter.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0),
    )
    if timeout:
        with pytest.raises(mineru_adapter.MinerUUnavailable, match="timed out"):
            mineru_adapter.run_mineru_command(["mineru"], 30)
    else:
        result = mineru_adapter.run_mineru_command(["mineru"], 30)
        assert result.returncode == 0
    assert not log_dir.exists()


def test_mineru_parse_output_is_removed_after_artifacts_are_saved(monkeypatch, tmp_path: Path) -> None:
    output_root = tmp_path / "mineru-parse"
    output_root.mkdir()
    (output_root / "manual.md").write_text("# Manual\nIgnition inspection", encoding="utf-8")
    asset = output_root / "figure.png"
    asset.write_bytes(b"png")
    monkeypatch.setattr(mineru_adapter, "mineru_enabled", lambda: True)
    monkeypatch.setattr(mineru_adapter, "mineru_available", lambda: True)
    monkeypatch.setattr(mineru_adapter, "mineru_executable", lambda: "mineru")
    monkeypatch.setattr(mineru_adapter.tempfile, "mkdtemp", lambda prefix: str(output_root))
    monkeypatch.setattr(
        mineru_adapter,
        "run_mineru_command",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "", ""),
    )

    result = mineru_adapter.parse_with_mineru(
        tmp_path / "manual.pdf",
        "pdf",
        timeout_seconds=180,
    )
    assert output_root.exists()
    artifacts = parser_router.save_parse_artifacts(tmp_path / "stored", result)
    assert not output_root.exists()
    raw_text = Path(artifacts["rawParseResult"]).read_text(encoding="utf-8")
    raw = json.loads(raw_text)
    assert "_temporaryOutputRoot" not in raw
    assert "_temporaryLogRoot" not in raw
    assert str(tmp_path) not in raw_text
    assert raw["assets"] == ["assets/figure.png"]


def test_mineru_parse_output_is_removed_on_failure(monkeypatch, tmp_path: Path) -> None:
    output_root = tmp_path / "mineru-failed"
    output_root.mkdir()
    monkeypatch.setattr(mineru_adapter, "mineru_enabled", lambda: True)
    monkeypatch.setattr(mineru_adapter, "mineru_available", lambda: True)
    monkeypatch.setattr(mineru_adapter, "mineru_executable", lambda: "mineru")
    monkeypatch.setattr(mineru_adapter.tempfile, "mkdtemp", lambda prefix: str(output_root))
    monkeypatch.setattr(
        mineru_adapter,
        "run_mineru_command",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 2, "", "failed"),
    )
    with pytest.raises(mineru_adapter.MinerUUnavailable):
        mineru_adapter.parse_with_mineru(tmp_path / "manual.pdf", "pdf", timeout_seconds=180)
    assert not output_root.exists()
