from pathlib import Path
import subprocess

import pytest

import backend.app.mineru_adapter as mineru
from backend.app.parser_router import save_parse_artifacts


def install_ready(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(mineru, "mineru_enabled", lambda: True)
    monkeypatch.setattr(mineru, "mineru_available", lambda: True)
    monkeypatch.setattr(mineru.tempfile, "tempdir", str(tmp_path))


def test_missing_cli_does_not_create_parse_directory(tmp_path: Path, monkeypatch) -> None:
    install_ready(monkeypatch, tmp_path)
    monkeypatch.setattr(mineru, "mineru_executable", lambda: (_ for _ in ()).throw(mineru.MinerUUnavailable("missing")))
    with pytest.raises(mineru.MinerUUnavailable):
        mineru.parse_with_mineru(tmp_path / "manual.pdf", "pdf", timeout_seconds=1)
    assert list(tmp_path.glob("mineru-parse-*")) == []


@pytest.mark.parametrize("failure", ["start", "nonzero", "timeout"])
def test_mineru_failures_clean_parse_and_log_directories(tmp_path: Path, monkeypatch, failure: str) -> None:
    install_ready(monkeypatch, tmp_path)
    monkeypatch.setattr(mineru, "mineru_executable", lambda: "mineru")

    def run(*_args, **_kwargs):
        if failure == "start":
            raise OSError("failed")
        if failure == "timeout":
            raise mineru.MinerUUnavailable("timed out")
        return subprocess.CompletedProcess([], 1, "", "failed")

    monkeypatch.setattr(mineru, "run_mineru_command", run)
    with pytest.raises(mineru.MinerUUnavailable):
        mineru.parse_with_mineru(tmp_path / "manual.pdf", "pdf", timeout_seconds=1)
    assert list(tmp_path.glob("mineru-parse-*")) == []
    assert list(tmp_path.glob("mineru-log-*")) == []


def test_success_keeps_root_until_artifacts_are_saved(tmp_path: Path, monkeypatch) -> None:
    install_ready(monkeypatch, tmp_path)
    monkeypatch.setattr(mineru, "mineru_executable", lambda: "mineru")
    monkeypatch.setattr(mineru, "run_mineru_command", lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, "", ""))
    monkeypatch.setattr(
        mineru,
        "collect_mineru_outputs",
        lambda root: ("text", [{"page": 1, "text": "text"}], [], {"mineruAssets": []}),
    )
    result = mineru.parse_with_mineru(tmp_path / "manual.pdf", "pdf", timeout_seconds=1)
    root = Path(result["_temporaryOutputRoot"])
    assert root.exists()
    save_parse_artifacts(tmp_path / "persisted", result)
    assert not root.exists()
