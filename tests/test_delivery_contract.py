from __future__ import annotations

from pathlib import Path


def test_dockerfile_requires_runtime_injected_token_authentication() -> None:
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

    assert "APP_ENV=production" in dockerfile
    assert "AUTH_MODE=token" in dockerfile
    assert "ALLOW_INSECURE_AUTH_OFF=false" in dockerfile
    assert "AUTH_OPERATOR_TOKEN=" not in dockerfile
    assert "AUTH_REVIEWER_TOKEN=" not in dockerfile
    assert "AUTH_ADMIN_TOKEN=" not in dockerfile


def test_loongarch_harness_has_strict_target_and_secret_safe_contracts() -> None:
    script = Path("scripts/loongarch-final-verify.sh").read_text(encoding="utf-8")

    for option in ("--preflight", "--venv", "--docker", "--strict-target"):
        assert option in script
    assert "backend/.venv/bin/python" in script
    assert "backend/.venv/Scripts/python.exe" not in script
    assert "--env-file" in script
    assert "Authorization: Bearer $OPERATOR_TOKEN" in script
    assert "strict target requires LoongArch" in script
    assert "strict target requires Kylin" in script
    assert '"result": result' in script
    assert '"authSmokePassed"' in script
    assert '"apiSmokePassed"' in script
    assert "TARGET_VERIFICATION_PENDING" in script
