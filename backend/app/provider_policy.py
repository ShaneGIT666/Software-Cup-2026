from __future__ import annotations

import os
from typing import Any


SUPPORTED_REMOTE_MODES = {"auto", "off"}
REMOTE_PROVIDERS = {"openai", "anthropic"}
LOCAL_PROVIDERS = {"local"}
LAST_FALLBACK: dict[str, str] = {"llm": "", "multimodal": "", "embedding": "", "ocr": ""}


def remote_api_mode() -> str:
    mode = (os.getenv("REMOTE_API_MODE") or "auto").strip().lower()
    return mode if mode in SUPPORTED_REMOTE_MODES else "auto"


def remote_api_disabled() -> bool:
    return remote_api_mode() == "off"


def configured_llm_provider(requested_provider: str | None) -> str:
    return (requested_provider or os.getenv("LLM_PROVIDER") or "mock").lower()


def configured_multimodal_provider(requested_provider: str | None) -> str:
    return (requested_provider or os.getenv("MULTIMODAL_PROVIDER") or "mock").lower()


def configured_embedding_provider() -> str:
    provider = (os.getenv("RAG_EMBEDDING_PROVIDER") or "openai").strip().lower()
    return provider if provider in {"hash", "openai"} else "hash"


def key_configured(provider: str) -> bool:
    if provider == "openai":
        return bool(os.getenv("OPENAI_API_KEY", "").strip())
    if provider == "anthropic":
        return bool(os.getenv("ANTHROPIC_API_KEY", "").strip())
    if provider == "local":
        return True
    return False


def local_provider_enabled(provider: str) -> bool:
    return provider in LOCAL_PROVIDERS


def record_fallback(kind: str, reason: str) -> None:
    if kind in LAST_FALLBACK:
        LAST_FALLBACK[kind] = reason


def provider_status() -> dict[str, Any]:
    from .ocr_adapter import ocr_status

    llm_provider = configured_llm_provider(None)
    multimodal_provider = configured_multimodal_provider(None)
    embedding_provider = configured_embedding_provider()
    vector_store = os.getenv("RAG_VECTOR_STORE", "chroma").strip().lower() or "chroma"
    offline = remote_api_disabled()
    return {
        "remoteApiMode": remote_api_mode(),
        "offlineFallback": offline,
        "llm": {
            "provider": llm_provider,
            "remoteCapable": llm_provider in REMOTE_PROVIDERS,
            "keyConfigured": key_configured(llm_provider),
            "effectiveProvider": "mock" if offline or llm_provider == "mock" else llm_provider,
            "lastFallbackReason": LAST_FALLBACK["llm"],
        },
        "multimodal": {
            "provider": multimodal_provider,
            "remoteCapable": multimodal_provider in REMOTE_PROVIDERS,
            "localCapable": local_provider_enabled(multimodal_provider),
            "keyConfigured": key_configured(multimodal_provider),
            "effectiveProvider": "mock"
            if (offline and not local_provider_enabled(multimodal_provider)) or multimodal_provider == "mock"
            else multimodal_provider,
            "lastFallbackReason": LAST_FALLBACK["multimodal"],
        },
        "embedding": {
            "provider": embedding_provider,
            "vectorStore": vector_store,
            "remoteCapable": embedding_provider == "openai",
            "keyConfigured": key_configured("openai") if embedding_provider == "openai" else False,
            "effectiveProvider": "hash"
            if offline or embedding_provider == "hash" or (embedding_provider == "openai" and not key_configured("openai"))
            else embedding_provider,
            "model": os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
            if embedding_provider == "openai"
            else "hash",
            "apiStyle": os.getenv("OPENAI_EMBEDDING_API_STYLE", "openai_compatible")
            if embedding_provider == "openai"
            else "hash",
            "lastFallbackReason": LAST_FALLBACK["embedding"],
        },
        "ocr": {
            **ocr_status(),
            "lastFallbackReason": LAST_FALLBACK["ocr"],
        },
    }
