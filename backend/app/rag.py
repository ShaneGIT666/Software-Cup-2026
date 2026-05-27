from __future__ import annotations

from typing import Any

from .llm_adapter import generate_rag_answer
from .llm_adapter import real_rag_answer
from .provider_policy import configured_llm_provider, remote_api_disabled
from .schemas import LlmValidateRequest, RagAnswerRequest, SearchRequest
from .services import search_knowledge


def answer_with_rag(request: RagAnswerRequest) -> dict[str, Any]:
    search_payload = search_knowledge(
        SearchRequest(
            deviceModel=request.deviceModel,
            faultText=request.faultText,
            inputType="text",
            topK=request.topK,
        )
    )
    rag_payload = generate_rag_answer(
        device_model=request.deviceModel.strip(),
        fault_text=request.faultText.strip(),
        contexts=search_payload["results"],
        requested_provider=request.provider,
    )
    return {
        "queryId": search_payload["queryId"],
        "summary": search_payload["summary"],
        **rag_payload,
    }


def validate_llm_provider(request: LlmValidateRequest) -> dict[str, Any]:
    provider = configured_llm_provider(request.provider)
    if provider == "mock":
        provider = "openai"

    search_payload = search_knowledge(
        SearchRequest(
            deviceModel=request.deviceModel,
            faultText=request.faultText,
            inputType="text",
            topK=request.topK,
        )
    )
    contexts = search_payload["results"]

    if remote_api_disabled():
        return {
            "remoteOk": False,
            "provider": provider,
            "model": "",
            "apiStyle": "",
            "latencyMs": 0,
            "fallback": True,
            "fallbackReason": "REMOTE_API_MODE=off，真实 API 验收已跳过。",
            "answerPreview": "",
            "contextCount": len(contexts),
        }

    import time

    started = time.perf_counter()
    try:
        payload = real_rag_answer(
            device_model=request.deviceModel.strip(),
            fault_text=request.faultText.strip(),
            contexts=contexts,
            provider=provider,
        )
        latency_ms = round((time.perf_counter() - started) * 1000)
        return {
            "remoteOk": True,
            "provider": payload["provider"],
            "model": payload.get("model", ""),
            "apiStyle": payload.get("apiStyle", ""),
            "latencyMs": latency_ms,
            "fallback": False,
            "fallbackReason": "",
            "answerPreview": str(payload["answer"])[:240],
            "contextCount": payload.get("contextCount", len(contexts)),
        }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - started) * 1000)
        return {
            "remoteOk": False,
            "provider": provider,
            "model": "",
            "apiStyle": "",
            "latencyMs": latency_ms,
            "fallback": True,
            "fallbackReason": str(exc),
            "answerPreview": "",
            "contextCount": len(contexts),
        }
