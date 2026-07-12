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
    start_body = script[script.index("start_backend()"):script.index("assert_status()")]
    assert "backend/.venv/Scripts/python.exe" not in start_body
    assert "exec backend/.venv/bin/python -m uvicorn" in start_body
    assert "--env-file" in script
    assert "Authorization: Bearer $OPERATOR_TOKEN" in script
    assert "strict target requires LoongArch" in script
    assert "strict target requires Kylin" in script
    assert '"result": result' in script
    assert '"authSmokePassed"' in script
    assert '"apiSmokePassed"' in script
    assert "TARGET_VERIFICATION_PENDING" in script


def test_venv_harness_loads_config_safely_and_isolates_pytest() -> None:
    script = Path("scripts/loongarch-final-verify.sh").read_text(encoding="utf-8")
    start = script.index("start_backend()")
    tests = script.index("backend/.venv/bin/python -m pytest -q")
    backend = script.index("start_backend", tests)

    start_body = script[start:script.index("assert_status()", start)]
    assert 'done < "$ROOT_DIR/.env"' in start_body
    assert 'source "$ROOT_DIR/.env"' not in script
    assert 'export APP_KNOWLEDGE_DIR="$runtime/knowledge"' in start_body
    assert 'export APP_UPLOAD_DIR="$runtime/uploads"' in start_body
    assert "export MINERU_ENABLED=false" in start_body
    assert tests < backend
    test_prefix = script[script.rfind("APP_ENV=test", 0, tests):tests]
    assert "AUTH_MODE=off" in test_prefix
    assert "ALLOW_INSECURE_AUTH_OFF=true" in test_prefix
    assert 'OFFICIAL_MANUAL_PATH="${OFFICIAL_MANUAL_PATH:-}"' in test_prefix


def test_real_provider_checks_parse_responses_before_marking_verified() -> None:
    script = Path("scripts/loongarch-final-verify.sh").read_text(encoding="utf-8")
    start = script.index("check_real_providers()")
    end = script.index("run_venv()", start)
    body = script[start:end]

    llm_request = body.index("real-llm-response.json")
    llm_assertion = body.index('d.get("provider") not in', llm_request)
    llm_verified = body.index('REAL_LLM_VERIFIED="true"', llm_assertion)
    assert llm_request < llm_assertion < llm_verified
    assert '[[ -n "${OPENAI_API_KEY:-}" ]]' not in body

    image_request = body.index("/api/multimodal/diagnosis")
    image_assertion = body.index('image.get("provider") not in', image_request)
    image_verified = body.index('REAL_MULTIMODAL_VERIFIED="true"', image_assertion)
    assert image_request < image_assertion < image_verified
    assert '[[ -f "${REAL_IMAGE_PATH:-}" ]]' not in body


def test_official_manual_smoke_precedes_real_provider_checks() -> None:
    script = Path("scripts/loongarch-final-verify.sh").read_text(encoding="utf-8")
    smoke = script[script.index("official_manual_smoke()"):script.index("api_smoke()")]

    upload = smoke.index("/api/knowledge/documents")
    chunks = smoke.index("/chunks", upload)
    review = smoke.index("/review", chunks)
    search = smoke.index("/api/search", review)
    rag = smoke.index("/api/rag/answer", search)
    download = smoke.index("/file", rag)
    verified = smoke.index('OFFICIAL_MANUAL_VERIFIED="true"', download)
    assert upload < chunks < review < search < rag < download < verified
    assert "OFFICIAL_MANUAL_PATH" in smoke
    assert "official-manual-smoke.json" in smoke


def test_docker_harness_uses_external_ephemeral_env_and_runs_tests_first() -> None:
    script = Path("scripts/loongarch-final-verify.sh").read_text(encoding="utf-8")
    docker = script[script.index("run_docker()"):script.index("while [[ $# -gt 0 ]]")]

    test_run = docker.index('docker run "${test_args[@]}"')
    tests_passed = docker.index('BACKEND_TESTS_PASSED="true"', test_run)
    make_env = docker.index('mktemp "${TMPDIR:-/tmp}/software-cup-docker-env.', tests_passed)
    production_run = docker.index("--env-file", make_env)
    immediate_delete = docker.index('rm -f "$TEMP_DOCKER_ENV"', production_run)
    assert test_run < tests_passed < make_env < production_run < immediate_delete
    assert "docs/final-audit/evidence" not in docker
    assert '[[ -z "$TEMP_DOCKER_ENV" ]] || rm -f "$TEMP_DOCKER_ENV"' in script
    assert "OPENAI_API_KEY" in script and "LOCAL_MULTIMODAL_API_KEY" in script


def test_result_state_machine_is_fail_closed() -> None:
    script = Path("scripts/loongarch-final-verify.sh").read_text(encoding="utf-8")
    cleanup = script[script.index("cleanup()"):script.index("trap cleanup EXIT")]
    gates = script[script.index("strict_gates_passed()"):script.index("cleanup()")]

    assert 'result="TARGET_VERIFICATION_PENDING"' in cleanup
    assert 'if [[ "$STRICT_TARGET" == "true" && "$MODE" != "--preflight" ]]' in cleanup
    assert 'result="GO"' in cleanup and 'result="NO-GO"' in cleanup
    for gate in (
        "BACKEND_TESTS_PASSED",
        "FRONTEND_PASSED",
        "AUTH_SMOKE_PASSED",
        "API_SMOKE_PASSED",
        "OFFICIAL_MANUAL_VERIFIED",
        "REAL_LLM_VERIFIED",
        "REAL_MULTIMODAL_VERIFIED",
    ):
        assert gate in gates


def test_raw_evidence_is_gitignored_and_manual_fixture_is_portable() -> None:
    ignore = Path(".gitignore").read_text(encoding="utf-8")
    manual_test = Path("tests/test_motorcycle_manual.py").read_text(encoding="utf-8")

    assert "docs/final-audit/evidence/*" in ignore
    assert "!docs/final-audit/evidence/.gitkeep" in ignore
    assert 'os.getenv("OFFICIAL_MANUAL_PATH")' in manual_test
    assert 'os.getenv("MOTORCYCLE_MANUAL_PATH")' in manual_test
    assert "pytest.mark.skipif" in manual_test
