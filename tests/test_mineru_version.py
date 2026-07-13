import subprocess

import pytest

import backend.app.mineru_adapter as mineru


@pytest.fixture(autouse=True)
def reset_cache():
    mineru._reset_mineru_version_cache_for_tests()
    yield
    mineru._reset_mineru_version_cache_for_tests()


def test_version_is_unavailable_without_cli(monkeypatch) -> None:
    monkeypatch.setattr(mineru, "mineru_cli_available", lambda: False)
    assert mineru.mineru_cli_version() == "unavailable"


@pytest.mark.parametrize(("stdout", "stderr", "expected"), [("MinerU 3.4\n", "", "MinerU 3.4"), ("", "mineru 3.5\n", "mineru 3.5")])
def test_version_reads_first_nonempty_line(monkeypatch, stdout: str, stderr: str, expected: str) -> None:
    monkeypatch.setattr(mineru, "mineru_cli_available", lambda: True)
    monkeypatch.setattr(mineru, "mineru_executable", lambda: "C:/private/mineru.exe")
    monkeypatch.setattr(
        mineru.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, stdout, stderr),
    )
    assert mineru.mineru_cli_version() == expected
    assert "private" not in mineru.mineru_cli_version()


def test_version_timeout_is_unknown(monkeypatch) -> None:
    monkeypatch.setattr(mineru, "mineru_cli_available", lambda: True)
    monkeypatch.setattr(mineru, "mineru_executable", lambda: "mineru")
    monkeypatch.setattr(
        mineru.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(subprocess.TimeoutExpired("mineru", 5)),
    )
    assert mineru.mineru_cli_version() == "unknown"


def test_version_probe_runs_once(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(mineru, "mineru_cli_available", lambda: True)
    monkeypatch.setattr(mineru, "mineru_executable", lambda: "mineru")

    def run(*_args, **_kwargs):
        calls.append(1)
        return subprocess.CompletedProcess([], 0, "MinerU cached", "")

    monkeypatch.setattr(mineru.subprocess, "run", run)
    assert mineru.mineru_cli_version() == "MinerU cached"
    assert mineru.mineru_cli_version() == "MinerU cached"
    assert len(calls) == 1


def test_readiness_exposes_only_safe_version(monkeypatch) -> None:
    monkeypatch.setattr(mineru, "mineru_enabled", lambda: True)
    monkeypatch.setattr(mineru, "mineru_module_available", lambda: True)
    monkeypatch.setattr(mineru, "mineru_cli_available", lambda: True)
    monkeypatch.setattr(mineru, "mineru_cli_version", lambda: "MinerU 3.5")
    readiness = mineru.mineru_readiness()
    assert readiness["version"] == "MinerU 3.5"
    assert not any("/" in str(value) or "\\" in str(value) for value in readiness.values())
