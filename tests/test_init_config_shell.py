from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest


SCRIPT = Path("scripts/init-config.sh")
TOKEN_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def run_init_config(tmp_path: Path, *args: str) -> tuple[dict[str, str], str]:
    if shutil.which("bash") is None:
        pytest.skip("bash is required for local shell delivery tests")
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    shutil.copy2(SCRIPT, scripts_dir / SCRIPT.name)
    result = subprocess.run(
        ["bash", "scripts/init-config.sh", *args, "--force"],
        cwd=tmp_path,
        check=True,
        text=True,
        capture_output=True,
    )
    content = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "$AUTH_LINES" not in content
    assert "\\n" not in content
    return dict(line.split("=", 1) for line in content.splitlines() if "=" in line), result.stdout


def assert_secure_role_tokens(config: dict[str, str], output: str) -> None:
    tokens = [config["AUTH_OPERATOR_TOKEN"], config["AUTH_REVIEWER_TOKEN"], config["AUTH_ADMIN_TOKEN"]]
    assert all(TOKEN_PATTERN.fullmatch(token) for token in tokens)
    assert len(set(tokens)) == 3
    assert all(token not in output for token in tokens)


def test_init_config_shell_offline_writes_secure_multiline_auth(tmp_path: Path) -> None:
    config, output = run_init_config(tmp_path, "--mode", "offline")

    assert config["APP_ENV"] == "competition"
    assert config["AUTH_MODE"] == "token"
    assert config["ALLOW_INSECURE_AUTH_OFF"] == "false"
    assert config["REMOTE_API_MODE"] == "off"
    assert_secure_role_tokens(config, output)
    assert "backend/.venv/bin/python" in output
    assert "backend/.venv/Scripts/python.exe" not in output


def test_init_config_shell_unsafe_mode_is_loopback_only(tmp_path: Path) -> None:
    config, output = run_init_config(tmp_path, "--mode", "offline", "--unsafe-no-auth")

    assert config["APP_ENV"] == "development"
    assert config["AUTH_MODE"] == "off"
    assert config["ALLOW_INSECURE_AUTH_OFF"] == "true"
    assert "127.0.0.1" in output
    assert "AUTH_OPERATOR_TOKEN" not in config


def test_init_config_shell_llm_mode_keeps_api_key_out_of_output(tmp_path: Path) -> None:
    api_key = "test-secret-value-123456"
    config, output = run_init_config(
        tmp_path,
        "--mode",
        "llm",
        "--base-url",
        "https://provider.example/v1",
        "--model",
        "test-model",
        "--api-key",
        api_key,
    )

    assert config["OPENAI_BASE_URL"] == "https://provider.example/v1"
    assert config["OPENAI_MODEL"] == "test-model"
    assert config["OPENAI_API_KEY"] == api_key
    assert api_key not in output
    assert_secure_role_tokens(config, output)
