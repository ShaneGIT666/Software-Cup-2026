from __future__ import annotations

import os
import time
import logging
from typing import Any

import httpx

from .provider_policy import configured_llm_provider, record_fallback, remote_api_disabled


logger = logging.getLogger(__name__)


def configured_provider(requested_provider: str | None) -> str:
    return configured_llm_provider(requested_provider)


def context_max_chars() -> int:
    return max(400, int(os.getenv("RAG_CONTEXT_MAX_CHARS", "4000")))


def llm_max_tokens() -> int:
    return max(128, int(os.getenv("LLM_MAX_TOKENS", "800")))


def llm_temperature() -> float:
    return max(0.0, min(2.0, float(os.getenv("LLM_TEMPERATURE", "0.2"))))


def provider_model(provider: str) -> str:
    if provider == "openai":
        return os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    if provider == "anthropic":
        return os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
    return "mock"


def provider_api_style(provider: str) -> str:
    if provider == "openai":
        return os.getenv("OPENAI_API_STYLE", "chat_completions").strip().lower()
    if provider == "anthropic":
        return "messages"
    return "mock"


def truncate_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return f"{text[: max(0, limit - 12)].rstrip()}... [truncated]"


def compress_contexts(contexts: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    budget = context_max_chars()
    used = 0
    compressed: list[dict[str, Any]] = []
    for item in contexts:
        snippet = str(item.get("snippet", ""))
        remaining = budget - used
        if remaining <= 0:
            break
        clipped = truncate_text(snippet, min(len(snippet), remaining))
        used += len(clipped)
        compressed.append({**item, "snippet": clipped})
    return compressed, used


def citation_from_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": result["id"],
        "title": result["title"],
        "sourceType": result["sourceType"],
        "sourceName": result["sourceName"],
        "snippet": result["snippet"],
        "confidence": result["confidence"],
        "page": result.get("page"),
        "chapter": result.get("chapter"),
        "documentId": result.get("documentId"),
        "chunkId": result.get("chunkId"),
        "reason": result.get("reason", ""),
        "scoreBreakdown": result.get("scoreBreakdown", {}),
    }


def mock_rag_answer(
    device_model: str,
    fault_text: str,
    contexts: list[dict[str, Any]],
    requested_provider: str | None,
    fallback_reason: str | None = None,
) -> dict[str, Any]:
    provider = configured_provider(requested_provider)
    compressed_contexts, context_chars = compress_contexts(contexts)
    citations = [citation_from_result(item) for item in compressed_contexts]
    source_names = list(dict.fromkeys(item["sourceName"] for item in citations))[:3]

    if compressed_contexts:
        answer = (
            f"基于已检索到的 {len(compressed_contexts)} 条资料，{device_model or '该设备'} 的“{fault_text}”"
            "优先按引用资料进行排查：先核对高置信度手册/入库资料，再结合历史案例确认常见原因。"
            f"当前可参考来源包括：{'、'.join(source_names)}。"
        )
        recommended_actions = [
            "优先查看引用来源中的手册页码或资料片段，确认安全前置条件。",
            "按标准作业流程逐项检查，不跳过安全确认和验收标准。",
            "若现场处理形成新经验，提交案例并走审核入库流程。",
        ]
    else:
        answer = (
            f"暂未检索到与 {device_model or '该设备'} 的“{fault_text}”直接相关资料。"
            "建议补充设备型号、故障现象关键词，或先上传对应检修手册后再次检索。"
        )
        recommended_actions = ["补充更具体的故障描述。", "上传相关检修资料并完成入库。"]

    return {
        "answer": answer,
        "recommendedActions": recommended_actions,
        "citations": citations,
        "provider": "mock",
        "requestedProvider": provider,
        "fallback": True,
        "fallbackReason": fallback_reason or "未配置真实模型或真实模型调用不可用，已使用 mock provider 保证演示不断线。",
        "contextCount": len(compressed_contexts),
        "contextChars": context_chars,
        "model": "mock",
        "apiStyle": "mock",
    }


def build_context_prompt(device_model: str, fault_text: str, contexts: list[dict[str, Any]]) -> str:
    context_lines = []
    for index, item in enumerate(contexts, start=1):
        source = f"{item['sourceType']} / {item['sourceName']}"
        page = f" / p.{item['page']}" if item.get("page") else ""
        context_lines.append(
            f"[{index}] {item['title']} ({source}{page})\n"
            f"命中原因：{item.get('reason', '')}\n"
            f"排序分：{item.get('scoreBreakdown', {}).get('score', 0)}\n"
            f"片段：{item['snippet']}"
        )
    context_text = "\n\n".join(context_lines) if context_lines else "暂无检索上下文。"
    return (
        "你是设备检修知识检索与作业辅助系统。请严格基于给定检索上下文回答，不要编造未出现的资料。"
        "必须使用 [1]、[2] 这样的编号标注引用来源；如果证据不足，明确说明需要补充资料。"
        "回答使用中文，包含：可能原因、建议排查动作、安全提醒。\n\n"
        f"设备型号：{device_model or '未提供'}\n"
        f"故障现象：{fault_text or '未提供'}\n\n"
        f"检索上下文：\n{context_text}"
    )


def _post_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    retry_count = max(0, int(os.getenv("PROVIDER_RETRY_COUNT", "1")))
    backoff_seconds = max(0.0, float(os.getenv("PROVIDER_BACKOFF_SECONDS", "0.5")))
    last_error: Exception | None = None
    for attempt in range(retry_count + 1):
        try:
            response = httpx.post(url, headers=headers, json=payload, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except Exception as exc:  # pragma: no cover - network details vary by provider
            last_error = exc
            logger.warning("Provider request failed on attempt %s/%s: %s", attempt + 1, retry_count + 1, exc)
            if attempt < retry_count and backoff_seconds:
                time.sleep(backoff_seconds)
    raise RuntimeError(str(last_error) if last_error else "provider request failed")


def parse_openai_response(payload: dict[str, Any]) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    parts: list[str] = []
    for output in payload.get("output", []):
        for content in output.get("content", []):
            text = content.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts).strip()


def parse_openai_chat_response(payload: dict[str, Any]) -> str:
    choices = payload.get("choices", [])
    if not choices:
        return ""
    message = choices[0].get("message", {})
    content = message.get("content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [item.get("text", "") for item in content if isinstance(item, dict)]
        return "\n".join(part for part in parts if part).strip()
    return ""


def parse_anthropic_response(payload: dict[str, Any]) -> str:
    parts = [item.get("text", "") for item in payload.get("content", []) if item.get("type") == "text"]
    return "\n".join(part for part in parts if part).strip()


def real_rag_answer(
    device_model: str,
    fault_text: str,
    contexts: list[dict[str, Any]],
    provider: str,
) -> dict[str, Any]:
    compressed_contexts, context_chars = compress_contexts(contexts)
    prompt = build_context_prompt(device_model, fault_text, compressed_contexts)
    timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "20"))
    citations = [citation_from_result(item) for item in compressed_contexts]
    model = provider_model(provider)
    api_style = provider_api_style(provider)
    recommended_actions = [
        "核对引用来源中的手册页码或资料片段。",
        "按标准作业流程执行检查，并记录现场证据。",
        "如处理形成新经验，提交案例并审核入库。",
    ]

    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY 未配置")
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        if api_style == "chat_completions":
            payload = _post_json(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                payload={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": llm_max_tokens(),
                    "temperature": llm_temperature(),
                },
                timeout=timeout,
            )
            answer = parse_openai_chat_response(payload)
        else:
            payload = _post_json(
                f"{base_url}/responses",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                payload={
                    "model": model,
                    "input": prompt,
                    "max_output_tokens": llm_max_tokens(),
                    "temperature": llm_temperature(),
                },
                timeout=timeout,
            )
            answer = parse_openai_response(payload)
    elif provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY 未配置")
        base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1").rstrip("/")
        payload = _post_json(
            f"{base_url}/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": os.getenv("ANTHROPIC_VERSION", "2023-06-01"),
                "Content-Type": "application/json",
            },
            payload={
                "model": model,
                "max_tokens": llm_max_tokens(),
                "temperature": llm_temperature(),
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=timeout,
        )
        answer = parse_anthropic_response(payload)
    else:
        raise RuntimeError(f"不支持的 provider: {provider}")

    if not answer:
        raise RuntimeError("模型返回内容为空")

    return {
        "answer": answer,
        "recommendedActions": recommended_actions,
        "citations": citations,
        "provider": provider,
        "requestedProvider": provider,
        "fallback": False,
        "fallbackReason": "",
        "contextCount": len(compressed_contexts),
        "contextChars": context_chars,
        "model": model,
        "apiStyle": api_style,
    }


def generate_rag_answer(
    device_model: str,
    fault_text: str,
    contexts: list[dict[str, Any]],
    requested_provider: str | None,
) -> dict[str, Any]:
    provider = configured_provider(requested_provider)
    if provider == "mock":
        return mock_rag_answer(device_model, fault_text, contexts, provider)
    if remote_api_disabled():
        reason = "REMOTE_API_MODE=off，已强制使用本地 mock provider，避免比赛现场网络不稳定影响演示。"
        record_fallback("llm", reason)
        logger.info("LLM fallback: %s", reason)
        return mock_rag_answer(device_model, fault_text, contexts, provider, fallback_reason=reason)

    try:
        return real_rag_answer(device_model, fault_text, contexts, provider)
    except Exception as exc:
        reason = f"{provider} provider 调用失败，已降级到 mock：{exc}"
        record_fallback("llm", reason)
        logger.warning("LLM fallback: %s", reason)
        return mock_rag_answer(
            device_model,
            fault_text,
            contexts,
            provider,
            fallback_reason=reason,
        )
