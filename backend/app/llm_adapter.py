from __future__ import annotations

import os
from typing import Any

import httpx


def configured_provider(requested_provider: str | None) -> str:
    return (requested_provider or os.getenv("LLM_PROVIDER") or "mock").lower()


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
    }


def mock_rag_answer(
    device_model: str,
    fault_text: str,
    contexts: list[dict[str, Any]],
    requested_provider: str | None,
    fallback_reason: str | None = None,
) -> dict[str, Any]:
    provider = configured_provider(requested_provider)
    active_provider = "mock"
    citations = [citation_from_result(item) for item in contexts]
    source_names = list(dict.fromkeys(item["sourceName"] for item in citations))[:3]

    if contexts:
        answer = (
            f"基于已检索到的 {len(contexts)} 条资料，{device_model or '该设备'} 的“{fault_text}”"
            "优先按来源资料进行排查：先核对高置信度手册/入库资料，再结合历史案例确认常见原因。"
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
        "provider": active_provider,
        "requestedProvider": provider,
        "fallback": True,
        "fallbackReason": fallback_reason or "未配置真实模型或真实模型调用不可用，已使用 mock provider 保证演示不断线。",
    }


def build_context_prompt(device_model: str, fault_text: str, contexts: list[dict[str, Any]]) -> str:
    context_lines = []
    for index, item in enumerate(contexts, start=1):
        source = f"{item['sourceType']} / {item['sourceName']}"
        page = f" / p.{item['page']}" if item.get("page") else ""
        context_lines.append(
            f"[{index}] {item['title']} ({source}{page})\n"
            f"命中原因：{item.get('reason', '')}\n"
            f"片段：{item['snippet']}"
        )
    context_text = "\n\n".join(context_lines) if context_lines else "暂无检索上下文。"
    return (
        "你是设备检修知识检索与作业辅助系统。请严格基于给定检索上下文回答，不要编造未出现的资料。"
        "回答使用中文，包含：可能原因、建议排查动作、安全提醒。"
        "如果上下文不足，请明确说明需要补充资料。\n\n"
        f"设备型号：{device_model or '未提供'}\n"
        f"故障现象：{fault_text or '未提供'}\n\n"
        f"检索上下文：\n{context_text}"
    )


def _post_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    response = httpx.post(url, headers=headers, json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


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


def parse_anthropic_response(payload: dict[str, Any]) -> str:
    parts = [item.get("text", "") for item in payload.get("content", []) if item.get("type") == "text"]
    return "\n".join(part for part in parts if part).strip()


def real_rag_answer(
    device_model: str,
    fault_text: str,
    contexts: list[dict[str, Any]],
    provider: str,
) -> dict[str, Any]:
    prompt = build_context_prompt(device_model, fault_text, contexts)
    timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "20"))
    citations = [citation_from_result(item) for item in contexts]
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
        model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        payload = _post_json(
            f"{base_url}/responses",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            payload={"model": model, "input": prompt},
            timeout=timeout,
        )
        answer = parse_openai_response(payload)
    elif provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY 未配置")
        base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1").rstrip("/")
        model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
        payload = _post_json(
            f"{base_url}/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": os.getenv("ANTHROPIC_VERSION", "2023-06-01"),
                "Content-Type": "application/json",
            },
            payload={"model": model, "max_tokens": 800, "messages": [{"role": "user", "content": prompt}]},
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

    try:
        return real_rag_answer(device_model, fault_text, contexts, provider)
    except Exception as exc:
        return mock_rag_answer(
            device_model,
            fault_text,
            contexts,
            provider,
            fallback_reason=f"{provider} provider 调用失败，已降级到 mock：{exc}",
        )
