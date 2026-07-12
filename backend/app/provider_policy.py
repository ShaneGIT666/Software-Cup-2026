from __future__ import annotations

import os
from typing import Any


SUPPORTED_REMOTE_MODES = {"auto", "off"}
REMOTE_PROVIDERS = {"openai", "anthropic"}
LOCAL_PROVIDERS = {"local"}
SUPPORTED_RERANKERS = {"none", "heuristic"}
LAST_FALLBACK: dict[str, str] = {
    "llm": "",
    "multimodal": "",
    "embedding": "",
    "ocr": "",
    "reranker": "",
    "vector": "",
}


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


def requested_reranker_provider() -> str:
    return (os.getenv("RAG_RERANK_PROVIDER") or "none").strip().lower()


def configured_reranker_provider() -> str:
    provider = requested_reranker_provider()
    return provider if provider in SUPPORTED_RERANKERS else "none"


def key_configured(provider: str) -> bool:
    if provider == "openai":
        return bool(os.getenv("OPENAI_API_KEY", "").strip())
    if provider == "anthropic":
        return bool(os.getenv("ANTHROPIC_API_KEY", "").strip())
    if provider == "local":
        return True
    return False


def multimodal_key_configured(provider: str) -> bool:
    if provider == "openai":
        return bool(
            os.getenv("MULTIMODAL_OPENAI_API_KEY", "").strip()
            or os.getenv("OPENAI_API_KEY", "").strip()
        )
    return key_configured(provider)


def local_provider_enabled(provider: str) -> bool:
    return provider in LOCAL_PROVIDERS


def record_fallback(kind: str, reason: str) -> None:
    if kind in LAST_FALLBACK:
        LAST_FALLBACK[kind] = reason


def provider_status() -> dict[str, Any]:
    from .ocr_adapter import ocr_status
    from .system_status import build_system_status

    llm_provider = configured_llm_provider(None)
    multimodal_provider = configured_multimodal_provider(None)
    embedding_provider = configured_embedding_provider()
    requested_reranker = requested_reranker_provider()
    reranker_provider = configured_reranker_provider()
    from .vector_store import vector_backend_status

    vector_store = os.getenv("RAG_VECTOR_STORE", "sqlite").strip().lower() or "sqlite"
    vector_status = vector_backend_status()
    offline = remote_api_disabled()
    return {
        "remoteApiMode": remote_api_mode(),
        "offlineFallback": offline,
        "llm": {
            "provider": llm_provider,
            "remoteCapable": llm_provider in REMOTE_PROVIDERS,
            "keyConfigured": key_configured(llm_provider),
            "effectiveProvider": "mock" if offline or llm_provider == "mock" else llm_provider,
            "model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini") if llm_provider == "openai" else "mock",
            "apiStyle": os.getenv("OPENAI_API_STYLE", "chat_completions") if llm_provider == "openai" else "mock",
            "thinkingEnabled": os.getenv("OPENAI_ENABLE_THINKING", "false").strip().lower()
            in {"1", "true", "yes", "on"},
            "lastFallbackReason": LAST_FALLBACK["llm"],
        },
        "multimodal": {
            "provider": multimodal_provider,
            "remoteCapable": multimodal_provider in REMOTE_PROVIDERS,
            "localCapable": local_provider_enabled(multimodal_provider),
            "keyConfigured": multimodal_key_configured(multimodal_provider),
            "effectiveProvider": "mock"
            if (offline and not local_provider_enabled(multimodal_provider)) or multimodal_provider == "mock"
            else multimodal_provider,
            "model": (
                os.getenv("MULTIMODAL_OPENAI_MODEL", "").strip()
                or os.getenv("OPENAI_MODEL", "").strip()
                or "gpt-4.1-mini"
            )
            if multimodal_provider == "openai"
            else multimodal_provider,
            "apiStyle": os.getenv("MULTIMODAL_OPENAI_API_STYLE", "chat_completions")
            if multimodal_provider == "openai"
            else multimodal_provider,
            "lastFallbackReason": LAST_FALLBACK["multimodal"],
        },
        "embedding": {
            "provider": embedding_provider,
            "vectorStore": vector_store,
            "sqliteEngine": vector_status.get("sqliteEngine", {}),
            "vectorEnhancer": vector_status.get("enhancer", {}),
            "backendStatus": vector_status,
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
            "lastFallbackReason": LAST_FALLBACK["embedding"] or LAST_FALLBACK["vector"],
        },
        "ocr": {
            **ocr_status(),
            "lastFallbackReason": LAST_FALLBACK["ocr"],
        },
        "reranker": {
            "provider": requested_reranker,
            "supported": requested_reranker in SUPPORTED_RERANKERS,
            "remoteCapable": False,
            "localCapable": reranker_provider == "heuristic",
            "enabled": reranker_provider != "none",
            "effectiveProvider": reranker_provider,
            "fallbackProvider": "none",
            "lastFallbackReason": LAST_FALLBACK["reranker"],
        },
        "system": build_system_status(),
    }
