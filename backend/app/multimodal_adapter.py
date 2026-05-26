from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any

from .llm_adapter import _post_json
from .provider_policy import (
    configured_multimodal_provider as configured_multimodal_provider_from_policy,
    record_fallback,
    remote_api_disabled,
)


def configured_multimodal_provider(requested_provider: str | None) -> str:
    return configured_multimodal_provider_from_policy(requested_provider)


def mime_type_for_suffix(suffix: str) -> str:
    return {
        "pdf": "application/pdf",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }.get(suffix.lower(), "application/octet-stream")


def data_url(content: bytes, suffix: str) -> str:
    encoded = base64.b64encode(content).decode("ascii")
    return f"data:{mime_type_for_suffix(suffix)};base64,{encoded}"


def mock_multimodal_analysis(
    file_name: str,
    source_name: str,
    suffix: str,
    requested_provider: str | None,
    fallback_reason: str | None = None,
) -> dict[str, Any]:
    provider = configured_multimodal_provider(requested_provider)
    text = (
        f"{source_name} 的多模态资料已完成演示级分析。资料类型为 {suffix.upper()}，"
        "重点关注摩托车发动机无法启动、怠速不稳、点火系统、燃油供给和安全检修步骤。"
    )
    return {
        "summary": text,
        "keyComponents": ["发动机", "火花塞", "高压包", "燃油供给", "进气管路"],
        "faultSymptoms": ["无法启动", "启动困难", "怠速不稳", "排气异常"],
        "inspectionSteps": [
            "确认车辆处于安全停放状态，断开高温和转动部件风险。",
            "检查火花塞积碳、间隙和点火火花状态。",
            "检查燃油滤清器、油路供给和进气管路密封。",
            "按手册要求复测启动状态和怠速稳定性。",
        ],
        "safetyNotes": ["检修前确认发动机冷却", "佩戴护目镜和绝缘手套", "避免在通风不良环境中长时间试车"],
        "textSegments": [
            text,
            "当发动机启动困难时，应优先检查点火系统、燃油供给系统和进气密封状态，并记录现场现象。",
            "标准作业应包含安全确认、部件检查、故障复测和案例沉淀，审核通过后进入知识库。",
        ],
        "provider": "mock",
        "requestedProvider": provider,
        "fallback": True,
        "fallbackReason": fallback_reason or "未配置真实多模态模型或真实模型不可用，已使用 mock provider 保证演示连续性。",
        "fileName": file_name,
    }


def parse_openai_multimodal_response(payload: dict[str, Any]) -> str:
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


def parse_anthropic_multimodal_response(payload: dict[str, Any]) -> str:
    parts = [item.get("text", "") for item in payload.get("content", []) if item.get("type") == "text"]
    return "\n".join(part for part in parts if part).strip()


def structured_from_model_text(
    text: str,
    file_name: str,
    source_name: str,
    provider: str,
    requested_provider: str,
) -> dict[str, Any]:
    summary = text.strip()
    return {
        "summary": summary,
        "keyComponents": [],
        "faultSymptoms": [],
        "inspectionSteps": [],
        "safetyNotes": [],
        "textSegments": [summary],
        "provider": provider,
        "requestedProvider": requested_provider,
        "fallback": False,
        "fallbackReason": "",
        "fileName": file_name,
    }


def real_multimodal_analysis(
    file_path: Path,
    source_name: str,
    suffix: str,
    provider: str,
) -> dict[str, Any]:
    content = file_path.read_bytes()
    file_name = file_path.name
    timeout = float(os.getenv("MULTIMODAL_TIMEOUT_SECONDS", os.getenv("LLM_TIMEOUT_SECONDS", "30")))
    prompt = (
        "你是设备检修知识库入库助手。请分析这份摩托车/设备检修资料中的文字、图片、表格或结构图，"
        "输出中文摘要、关键部件、故障现象、检查步骤、安全注意事项，以及适合进入检索知识库的文本片段。"
        "如果资料内容不足，请明确说明限制，不要编造不存在的页码或结论。"
    )

    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY 未配置")
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        payload = _post_json(
            f"{base_url}/responses",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            payload={
                "model": model,
                "input": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": prompt},
                            {
                                "type": "input_file" if suffix == "pdf" else "input_image",
                                "filename": file_name,
                                "file_data" if suffix == "pdf" else "image_url": data_url(content, suffix),
                            },
                        ],
                    }
                ],
            },
            timeout=timeout,
        )
        text = parse_openai_multimodal_response(payload)
    elif provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY 未配置")
        base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1").rstrip("/")
        model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
        source_type = "base64"
        media_type = mime_type_for_suffix(suffix)
        document_type = "document" if suffix == "pdf" else "image"
        payload = _post_json(
            f"{base_url}/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": os.getenv("ANTHROPIC_VERSION", "2023-06-01"),
                "Content-Type": "application/json",
            },
            payload={
                "model": model,
                "max_tokens": 1200,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": document_type,
                                "source": {
                                    "type": source_type,
                                    "media_type": media_type,
                                    "data": base64.b64encode(content).decode("ascii"),
                                },
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
            },
            timeout=timeout,
        )
        text = parse_anthropic_multimodal_response(payload)
    else:
        raise RuntimeError(f"不支持的 provider: {provider}")

    if not text:
        raise RuntimeError("多模态模型返回内容为空")
    return structured_from_model_text(text, file_name, source_name, provider, provider)


def analyze_multimodal_document(
    file_path: Path,
    source_name: str,
    suffix: str,
    requested_provider: str | None,
) -> dict[str, Any]:
    provider = configured_multimodal_provider(requested_provider)
    if provider == "mock":
        return mock_multimodal_analysis(file_path.name, source_name, suffix, provider)
    if remote_api_disabled():
        reason = "REMOTE_API_MODE=off，已强制使用本地 mock 多模态分析，避免比赛现场网络不稳定影响演示。"
        record_fallback("multimodal", reason)
        return mock_multimodal_analysis(file_path.name, source_name, suffix, provider, fallback_reason=reason)

    try:
        return real_multimodal_analysis(file_path, source_name, suffix, provider)
    except Exception as exc:
        reason = f"{provider} 多模态 provider 调用失败，已降级到 mock：{exc}"
        record_fallback("multimodal", reason)
        return mock_multimodal_analysis(
            file_path.name,
            source_name,
            suffix,
            provider,
            fallback_reason=reason,
        )
