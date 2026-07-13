from pathlib import Path

import pytest

import backend.app.multimodal_adapter as multimodal


def ready() -> dict[str, object]:
    return {
        "provider": "openai", "model": "vision-model", "credentialConfigured": True,
        "endpointConfigured": True, "remoteAllowed": True, "ready": True, "status": "ready",
    }


def successful_analysis() -> dict[str, object]:
    return {
        "provider": "openai", "model": "vision-model", "summary": "simple shape",
        "components": [], "operations": [], "figureLabels": [], "semanticVerified": True,
        "imageInputSent": True, "fallback": False,
    }


def test_probe_skips_network_when_config_is_not_ready(monkeypatch) -> None:
    config = ready()
    config.update(ready=False, status="missing_key")
    monkeypatch.setattr(multimodal, "multimodal_readiness", lambda *_: config)
    monkeypatch.setattr(multimodal, "analyze_multimodal_document", lambda *_a, **_k: pytest.fail("network called"))
    result = multimodal.multimodal_operational_probe()
    assert result["probeAttempted"] is False
    assert result["failureCategory"] == "config_not_ready"


def test_probe_go_and_temporary_file_cleanup(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(multimodal, "multimodal_readiness", lambda *_: ready())
    seen: list[Path] = []

    def analyze(path: Path, *_args, **_kwargs):
        assert path.exists()
        seen.append(path)
        return successful_analysis()

    monkeypatch.setattr(multimodal, "analyze_multimodal_document", analyze)
    result = multimodal.multimodal_operational_probe()
    assert result["probeOk"] is True
    assert result["failureCategory"] == "none"
    assert seen and not seen[0].exists()


@pytest.mark.parametrize(
    ("status", "message", "category"),
    [(401, "unauthorized", "authentication_failed"), (403, "forbidden", "permission_denied"),
     (429, "limited", "rate_limited"), (400, "vision model does not support image", "unsupported_model")],
)
def test_probe_classifies_http_failures(monkeypatch, status: int, message: str, category: str) -> None:
    class Failure(RuntimeError):
        def __init__(self) -> None:
            super().__init__(message)
            self.response = type("Response", (), {"status_code": status})()

    monkeypatch.setattr(multimodal, "multimodal_readiness", lambda *_: ready())
    monkeypatch.setattr(multimodal, "analyze_multimodal_document", lambda *_a, **_k: (_ for _ in ()).throw(Failure()))
    assert multimodal.multimodal_operational_probe()["failureCategory"] == category


def test_probe_rejects_timeout_and_invalid_semantics(monkeypatch) -> None:
    monkeypatch.setattr(multimodal, "multimodal_readiness", lambda *_: ready())
    monkeypatch.setattr(multimodal, "analyze_multimodal_document", lambda *_a, **_k: (_ for _ in ()).throw(TimeoutError()))
    assert multimodal.multimodal_operational_probe()["failureCategory"] == "timeout"
    invalid = successful_analysis()
    invalid["semanticVerified"] = False
    monkeypatch.setattr(multimodal, "analyze_multimodal_document", lambda *_a, **_k: invalid)
    assert multimodal.multimodal_operational_probe()["failureCategory"] == "invalid_response"


def test_probe_requests_fail_closed_analysis(monkeypatch) -> None:
    monkeypatch.setattr(multimodal, "multimodal_readiness", lambda *_: ready())
    received: dict[str, object] = {}

    def analyze(*_args, **kwargs):
        received.update(kwargs)
        return successful_analysis()

    monkeypatch.setattr(multimodal, "analyze_multimodal_document", analyze)
    assert multimodal.multimodal_operational_probe()["probeOk"] is True
    assert received["raise_on_failure"] is True
