from __future__ import annotations

import base64
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from .data_store import knowledge_dir, load_documents
from .llm_adapter import _post_json, parse_openai_chat_response
from .ocr_adapter import analyze_ocr_document
from .provider_policy import (
    configured_multimodal_provider as configured_multimodal_provider_from_policy,
    multimodal_key_configured,
    record_fallback,
    remote_api_disabled,
)


logger = logging.getLogger(__name__)


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
    ocr_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    provider = configured_multimodal_provider(requested_provider)
    text = (
        f"{source_name} 的多模态资料已完成演示级分析。资料类型为 {suffix.upper()}，"
        "重点关注摩托车发动机无法启动、怠速不稳、点火系统、燃油供给和安全检修步骤。"
    )
    text_segments = [
        text,
        "当发动机启动困难时，应优先检查点火系统、燃油供给系统和进气密封状态，并记录现场现象。",
        "标准作业应包含安全确认、部件检查、故障复测和案例沉淀，审核通过后进入知识库。",
    ]
    if ocr_result and ocr_result.get("textSegments"):
        text_segments.extend(str(segment) for segment in ocr_result.get("textSegments", []) if str(segment).strip())

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
        "textSegments": text_segments,
        "provider": "mock",
        "requestedProvider": provider,
        "fallback": True,
        "fallbackReason": fallback_reason or "未配置真实多模态模型或真实模型不可用，已使用 mock provider 保证演示连续性。",
        "fileName": file_name,
        "ocr": ocr_result or {},
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


def local_multimodal_base_url() -> str:
    return (
        os.getenv("LOCAL_MULTIMODAL_BASE_URL", "").strip()
        or os.getenv("LOCAL_LLM_BASE_URL", "").strip()
        or "http://127.0.0.1:11434/v1"
    ).rstrip("/")


def local_multimodal_model() -> str:
    return (
        os.getenv("LOCAL_MULTIMODAL_MODEL", "").strip()
        or os.getenv("LOCAL_LLM_MODEL", "").strip()
        or "llava:latest"
    )


def local_multimodal_api_key() -> str:
    return os.getenv("LOCAL_MULTIMODAL_API_KEY", "").strip() or os.getenv("LOCAL_LLM_API_KEY", "").strip() or "ollama"


def multimodal_openai_base_url() -> str:
    return (
        os.getenv("MULTIMODAL_OPENAI_BASE_URL", "").strip()
        or os.getenv("OPENAI_BASE_URL", "").strip()
        or "https://api.openai.com/v1"
    ).rstrip("/")


def multimodal_openai_api_key() -> str:
    return os.getenv("MULTIMODAL_OPENAI_API_KEY", "").strip() or os.getenv("OPENAI_API_KEY", "").strip()


def multimodal_openai_model() -> str:
    return (
        os.getenv("MULTIMODAL_OPENAI_MODEL", "").strip()
        or os.getenv("OPENAI_MODEL", "").strip()
        or "gpt-4.1-mini"
    )


def multimodal_openai_api_style() -> str:
    value = os.getenv("MULTIMODAL_OPENAI_API_STYLE", "chat_completions").strip().lower()
    return value if value in {"chat_completions", "responses"} else "chat_completions"


def multimodal_openai_thinking_enabled() -> bool:
    return os.getenv("MULTIMODAL_OPENAI_ENABLE_THINKING", "false").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


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


def enrich_with_ocr(analysis: dict[str, Any], ocr_result: dict[str, Any]) -> dict[str, Any]:
    if not ocr_result or not ocr_result.get("textSegments"):
        analysis["ocr"] = ocr_result or {}
        return analysis

    segments = [str(segment).strip() for segment in ocr_result.get("textSegments", []) if str(segment).strip()]
    existing_segments = [str(segment) for segment in analysis.get("textSegments", []) if str(segment).strip()]
    analysis["textSegments"] = existing_segments + segments
    analysis["ocr"] = ocr_result
    if not analysis.get("summary") and ocr_result.get("text"):
        analysis["summary"] = str(ocr_result["text"])[:240]
    return analysis


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
        api_key = multimodal_openai_api_key()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY 未配置")
        base_url = multimodal_openai_base_url()
        model = multimodal_openai_model()
        api_style = multimodal_openai_api_style()
        if api_style == "chat_completions":
            if suffix == "pdf":
                raise RuntimeError(
                    "chat_completions multimodal accepts image input only; "
                    "use OCR/page visual assets for PDF ingestion"
                )
            request_payload: dict[str, Any] = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": data_url(content, suffix)}},
                        ],
                    }
                ],
                "max_tokens": int(os.getenv("MULTIMODAL_MAX_TOKENS", "1200")),
                "temperature": float(os.getenv("MULTIMODAL_TEMPERATURE", "0.2")),
                "stream": False,
            }
            if multimodal_openai_thinking_enabled():
                request_payload["enable_thinking"] = True
            payload = _post_json(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                payload=request_payload,
                timeout=timeout,
            )
            text = parse_openai_chat_response(payload)
        else:
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
    elif provider == "local":
        if suffix == "pdf":
            raise RuntimeError("local multimodal provider supports image files directly; use OCR ingestion for PDFs.")
        model = local_multimodal_model()
        payload = _post_json(
            f"{local_multimodal_base_url()}/chat/completions",
            headers={"Authorization": f"Bearer {local_multimodal_api_key()}", "Content-Type": "application/json"},
            payload={
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": data_url(content, suffix)}},
                        ],
                    }
                ],
                "max_tokens": int(os.getenv("LOCAL_MULTIMODAL_MAX_TOKENS", "1200")),
                "temperature": float(os.getenv("LOCAL_MULTIMODAL_TEMPERATURE", "0.2")),
            },
            timeout=timeout,
        )
        text = parse_openai_chat_response(payload)
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
    ocr_result = analyze_ocr_document(file_path, source_name, suffix)
    if provider == "mock":
        return mock_multimodal_analysis(file_path.name, source_name, suffix, provider, ocr_result=ocr_result)
    if remote_api_disabled() and provider != "local":
        reason = "REMOTE_API_MODE=off，已强制使用本地 mock 多模态分析，避免比赛现场网络不稳定影响演示。"
        record_fallback("multimodal", reason)
        logger.info("Multimodal fallback: %s", reason)
        return mock_multimodal_analysis(file_path.name, source_name, suffix, provider, fallback_reason=reason, ocr_result=ocr_result)

    try:
        return enrich_with_ocr(real_multimodal_analysis(file_path, source_name, suffix, provider), ocr_result)
    except Exception as exc:
        reason = f"{provider} 多模态 provider 调用失败，已降级到 mock：{exc}"
        record_fallback("multimodal", reason)
        logger.warning("Multimodal fallback: %s", reason)
        return mock_multimodal_analysis(
            file_path.name,
            source_name,
            suffix,
            provider,
            fallback_reason=reason,
            ocr_result=ocr_result,
        )


def validation_sample_file() -> tuple[Path, str, str]:
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
    )
    sample = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    sample.write(png_bytes)
    sample.close()
    return Path(sample.name), "multimodal-validation-sample.png", "png"


def document_file_for_validation(document_id: str) -> tuple[Path, str, str]:
    document = next((item for item in load_documents() if item.get("id") == document_id), None)
    if document is None:
        raise HTTPException(status_code=404, detail="入库资料不存在")
    suffix = str(document.get("suffix", "")).lower()
    file_path = knowledge_dir() / "files" / f"{document_id}.{suffix}"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="入库资料原始文件不存在")
    return file_path, str(document.get("sourceName") or document.get("fileName") or document_id), suffix


def validate_multimodal_provider(request: Any) -> dict[str, Any]:
    provider = configured_multimodal_provider(getattr(request, "provider", None))
    if provider == "openai":
        model = multimodal_openai_model()
    elif provider == "local":
        model = local_multimodal_model()
    else:
        model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
    start = time.perf_counter()
    temp_file: Path | None = None

    try:
        document_id = getattr(request, "documentId", None)
        if document_id:
            file_path, source_name, suffix = document_file_for_validation(document_id)
        else:
            file_path, source_name, suffix = validation_sample_file()
            temp_file = file_path

        if provider == "mock":
            analysis = mock_multimodal_analysis(file_path.name, source_name, suffix, provider)
            return {
                "remoteOk": False,
                "provider": "mock",
                "model": "mock",
                "fallback": True,
                "fallbackReason": "MULTIMODAL_PROVIDER=mock，当前仅执行本地演示级多模态兜底。",
                "summaryPreview": analysis.get("summary", "")[:200],
                "latencyMs": round((time.perf_counter() - start) * 1000),
            }

        if remote_api_disabled() and provider != "local":
            reason = "REMOTE_API_MODE=off，已跳过真实多模态 API 验收。"
            record_fallback("multimodal", reason)
            logger.info("Multimodal validation skipped: %s", reason)
            return {
                "remoteOk": False,
                "provider": provider,
                "model": model,
                "fallback": True,
                "fallbackReason": reason,
                "summaryPreview": "",
                "latencyMs": round((time.perf_counter() - start) * 1000),
            }

        if not multimodal_key_configured(provider):
            reason = f"{provider} API key 未配置。"
            record_fallback("multimodal", reason)
            logger.info("Multimodal validation fallback: %s", reason)
            return {
                "remoteOk": False,
                "provider": provider,
                "model": model,
                "fallback": True,
                "fallbackReason": reason,
                "summaryPreview": "",
                "latencyMs": round((time.perf_counter() - start) * 1000),
            }

        analysis = real_multimodal_analysis(file_path, source_name, suffix, provider)
        return {
            "remoteOk": True,
            "provider": provider,
            "model": model,
            "fallback": False,
            "fallbackReason": "",
            "summaryPreview": str(analysis.get("summary", ""))[:200],
            "latencyMs": round((time.perf_counter() - start) * 1000),
        }
    except HTTPException:
        raise
    except Exception as exc:
        reason = f"{provider} 多模态验收失败：{exc}"
        record_fallback("multimodal", reason)
        logger.warning("Multimodal validation fallback: %s", reason)
        return {
            "remoteOk": False,
            "provider": provider,
            "model": model,
            "fallback": True,
            "fallbackReason": reason,
            "summaryPreview": "",
            "latencyMs": round((time.perf_counter() - start) * 1000),
        }
    finally:
        if temp_file and temp_file.exists():
            temp_file.unlink()
