from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def explicit_test_auth_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    if "APP_ENV" not in os.environ:
        monkeypatch.setenv("APP_ENV", "test")
    if "AUTH_MODE" not in os.environ:
        monkeypatch.setenv("AUTH_MODE", "off")
    if "ALLOW_INSECURE_AUTH_OFF" not in os.environ:
        monkeypatch.setenv("ALLOW_INSECURE_AUTH_OFF", "true")
