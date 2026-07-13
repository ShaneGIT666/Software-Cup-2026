from __future__ import annotations

import base64
import json
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
PROBE_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAIAAAAlC+aJAAAAVElEQVR42u3ZMQ0AQAjAQETg3yX7m/gQCFcHNzdqeQE"
    "AAAAAAAAAAHACkI0BAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEwAuJQAAAAAAAAAAACfe54cmLFgRv96AAAAAElFTkSuQmCC"
)


def configured_multimodal_provider(requested_provider: str | None) -> str:
    return configured_multimodal_provider_from_policy(requested_provider)


def multimodal_readiness(requested_provider: str | None = None) -> dict[str, Any]:
    provider = configured_multimodal_provider(requested_provider)
    remote_allowed = provider == "local" or not remote_api_disabled()
    credential_configured = False
    endpoint_configured = False
    model = ""

    if provider == "mock":
        status = "mock"
    elif provider == "openai":
        credential_configured = bool(multimodal_openai_api_key())
        model = os.getenv("MULTIMODAL_OPENAI_MODEL", "").strip() or os.getenv("OPENAI_MODEL", "").strip()
        endpoint_configured = True
        if not credential_configured:
            status = "missing_key"
        elif not model:
            status = "missing_model"
        elif not remote_allowed:
            status = "remote_disabled"
        else:
            status = "ready"
    elif provider == "local":
        credential_configured = True
        model = os.getenv("LOCAL_MULTIMODAL_MODEL", "").strip() or os.getenv("LOCAL_LLM_MODEL", "").strip()
        endpoint_configured = bool(
            os.getenv("LOCAL_MULTIMODAL_BASE_URL", "").strip()
            or os.getenv("LOCAL_LLM_BASE_URL", "").strip()
        )
        if not model:
            status = "missing_model"
        elif not endpoint_configured:
            status = "missing_endpoint"
        else:
            status = "ready"
    elif provider == "anthropic":
        credential_configured = bool(os.getenv("ANTHROPIC_API_KEY", "").strip())
        model = os.getenv("ANTHROPIC_MODEL", "").strip()
        endpoint_configured = True
        if not credential_configured:
            status = "missing_key"
        elif not model:
            status = "missing_model"
        elif not remote_allowed:
            status = "remote_disabled"
        else:
            status = "ready"
    else:
        status = "unsupported_provider"

    return {
        "provider": provider,
        "model": model,
        "credentialConfigured": credential_configured,
        "endpointConfigured": endpoint_configured,
        "remoteAllowed": remote_allowed,
        "ready": status == "ready",
        "status": status,
    }


def _probe_failure_category(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None) or getattr(exc, "status_code", None)
    response_text = str(getattr(response, "text", "") or "")
    message = f"{exc} {response_text}".lower()
    if status_code == 401:
        return "authentication_failed"
    if status_code == 403:
        return "permission_denied"
    if status_code == 429:
        return "rate_limited"
    if status_code == 400 and any(marker in message for marker in ("image", "vision", "model")):
        return "unsupported_model"
    if isinstance(exc, TimeoutError) or "timed out" in message or "timeout" in message:
        return "timeout"
    if isinstance(exc, ConnectionError) or any(
        marker in message for marker in ("connection error", "connection refused", "name resolution", "network")
    ):
        return "network_error"
    return "provider_error"


def multimodal_operational_probe(
    requested_provider: str | None = None,
    *,
    timeout_seconds: float = 30,
) -> dict[str, Any]:
    readiness = multimodal_readiness(requested_provider)
    started = time.perf_counter()
    base = {
        "provider": readiness["provider"],
        "model": readiness["model"],
        "configReady": bool(readiness["ready"]),
        "probeAttempted": False,
        "probeOk": False,
        "status": "config_not_ready",
        "durationMs": 0,
        "semanticVerified": False,
        "imageInputSent": False,
        "fallback": True,
        "failureCategory": "config_not_ready",
    }
    if not readiness["ready"]:
        return base

    base["probeAttempted"] = True
    try:
        with tempfile.TemporaryDirectory(prefix="multimodal-operational-probe-") as temp_dir:
            image_path = Path(temp_dir) / "multimodal-operational-probe.png"
            image_path.write_bytes(base64.b64decode(PROBE_PNG_BASE64))
            analysis = analyze_multimodal_document(
                image_path,
                "multimodal-operational-probe.png",
                "png",
                requested_provider,
                analysis_task="manual_page",
                timeout_seconds=timeout_seconds,
                raise_on_failure=True,
            )
        has_content = any(
            (
                str(analysis.get("summary") or "").strip(),
                analysis.get("components") or [],
                analysis.get("operations") or [],
                analysis.get("figureLabels") or [],
            )
        )
        probe_ok = bool(
            analysis.get("provider") != "mock"
            and analysis.get("imageInputSent") is True
            and analysis.get("semanticVerified") is True
            and analysis.get("fallback") is False
            and str(analysis.get("model") or "").strip()
            and has_content
        )
        base.update(
            provider=str(analysis.get("provider") or readiness["provider"]),
            model=str(analysis.get("model") or readiness["model"]),
            probeOk=probe_ok,
            status="ready" if probe_ok else "invalid_response",
            semanticVerified=bool(analysis.get("semanticVerified")),
            imageInputSent=bool(analysis.get("imageInputSent")),
            fallback=bool(analysis.get("fallback", True)),
            failureCategory="none" if probe_ok else "invalid_response",
        )
    except Exception as exc:
        category = _probe_failure_category(exc)
        base.update(status=category, failureCategory=category)
    base["durationMs"] = round((time.perf_counter() - started) * 1000)
    return base


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
        "visualType": "unknown",
        "summary": text,
        "components": [],
        "operations": [],
        "figureLabels": [],
        "safetyWarnings": [],
        "uncertainties": ["当前结果为 mock/OCR 上下文降级，不是经过验证的图片语义理解。"],
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
        "semanticVerified": False,
        "imageInputSent": False,
        "model": "mock",
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


def manual_page_from_model_text(
    text: str,
    file_name: str,
    provider: str,
    model: str,
    image_input_sent: bool = False,
) -> dict[str, Any]:
    clean_text = text.strip()
    try:
        payload: Any = None
        decoder = json.JSONDecoder()
        for index, character in enumerate(clean_text):
            if character != "{":
                continue
            try:
                payload, _ = decoder.raw_decode(clean_text[index:])
                break
            except json.JSONDecodeError:
                continue
        if payload is None:
            raise json.JSONDecodeError("no JSON object found", clean_text, 0)
        if not isinstance(payload, dict):
            raise ValueError("manual page response must be a JSON object")
    except (json.JSONDecodeError, ValueError) as exc:
        return {
            "visualType": "unknown",
            "summary": clean_text[:500],
            "components": [],
            "operations": [],
            "figureLabels": [],
            "safetyWarnings": [],
            "uncertainties": ["模型输出不是有效 JSON，结果需要人工复核。"],
            "textSegments": [clean_text[:1000]] if clean_text else [],
            "provider": provider,
            "requestedProvider": provider,
            "model": model,
            "fallback": True,
            "fallbackReason": f"manual page JSON parse failed: {exc}",
            "semanticVerified": False,
            "imageInputSent": image_input_sent,
            "fileName": file_name,
        }
    allowed_types = {
        "photo", "exploded_view", "assembly_diagram", "wiring_diagram",
        "table", "warning", "mixed", "unknown",
    }
    visual_type = str(payload.get("visualType") or "unknown")
    if visual_type not in allowed_types:
        visual_type = "unknown"
    has_semantic_content = any(
        (
            str(payload.get("summary") or "").strip(),
            payload.get("components") or [],
            payload.get("operations") or [],
            payload.get("figureLabels") or [],
        )
    )
    semantic_verified = bool(
        provider in {"openai", "local", "anthropic"}
        and image_input_sent
        and model.strip()
        and has_semantic_content
    )
    result = {
        "visualType": visual_type,
        "summary": str(payload.get("summary") or "").strip(),
        "components": [str(item) for item in payload.get("components", []) if str(item).strip()],
        "operations": [str(item) for item in payload.get("operations", []) if str(item).strip()],
        "figureLabels": [str(item) for item in payload.get("figureLabels", []) if str(item).strip()],
        "safetyWarnings": [str(item) for item in payload.get("safetyWarnings", []) if str(item).strip()],
        "uncertainties": [str(item) for item in payload.get("uncertainties", []) if str(item).strip()],
        "provider": provider,
        "requestedProvider": provider,
        "model": model,
        "fallback": False,
        "fallbackReason": "",
        "semanticVerified": semantic_verified,
        "imageInputSent": image_input_sent,
        "fileName": file_name,
    }
    result["textSegments"] = [result["summary"]] if result["summary"] else []
    return result


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
    *,
    context_text: str = "",
    analysis_task: str = "generic",
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    content = file_path.read_bytes()
    file_name = file_path.name
    timeout = timeout_seconds or float(os.getenv("MULTIMODAL_TIMEOUT_SECONDS", os.getenv("LLM_TIMEOUT_SECONDS", "30")))
    if analysis_task == "manual_page" and suffix == "pdf":
        raise RuntimeError("manual_page analysis requires a rendered image input")
    if analysis_task == "manual_page":
        prompt = (
            "你是设备维修手册页面视觉分析器。只能根据当前图片、OCR 和附近正文判断；不得编造页码，"
            "不得编造扭矩、尺寸、间隙、故障码或维修步骤。数值无法辨认时必须写入 uncertainties。"
            "区分实物照片、爆炸图、装配图、电路图和表格。summary 使用简明中文。"
            "输出纯 JSON，不加 Markdown 代码块，结构必须为："
            '{"visualType":"photo | exploded_view | assembly_diagram | wiring_diagram | table | warning | mixed | unknown",'
            '"summary":"","components":[],"operations":[],"figureLabels":[],"safetyWarnings":[],"uncertainties":[]}\n'
            f"OCR 与附近正文（最多 2000 字符）：{context_text[:2000]}"
        )
    else:
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
    if analysis_task == "manual_page":
        return manual_page_from_model_text(
            text,
            file_name,
            provider,
            model,
            image_input_sent=suffix in {"jpg", "jpeg", "png", "webp"},
        )
    result = structured_from_model_text(text, file_name, source_name, provider, provider)
    result["model"] = model
    result["semanticVerified"] = False
    return result


def _retryable_multimodal_error(exc: Exception) -> bool:
    status_code = getattr(getattr(exc, "response", None), "status_code", None)
    if status_code is not None:
        return int(status_code) == 429 or int(status_code) >= 500
    message = str(exc).lower()
    return isinstance(exc, (TimeoutError, ConnectionError)) or "timed out" in message or "timeout" in message


def analyze_multimodal_document(
    file_path: Path,
    source_name: str,
    suffix: str,
    requested_provider: str | None = None,
    *,
    context_text: str = "",
    analysis_task: str = "generic",
    timeout_seconds: float | None = None,
    raise_on_failure: bool = False,
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

    retry_count = min(1, max(0, int(os.getenv("MANUAL_VISUAL_RETRY_COUNT", "1")))) if analysis_task == "manual_page" else 0
    attempts = retry_count + 1
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            analysis = real_multimodal_analysis(
                file_path,
                source_name,
                suffix,
                provider,
                context_text="\n\n".join(
                    part
                    for part in (str(ocr_result.get("text") or "")[:2000], context_text[:2000])
                    if part
                ),
                analysis_task=analysis_task,
                timeout_seconds=timeout_seconds,
            )
            return enrich_with_ocr(analysis, ocr_result)
        except Exception as exc:
            last_error = exc
            if attempt >= attempts - 1 or not _retryable_multimodal_error(exc):
                break
            time.sleep(max(0.0, float(os.getenv("MANUAL_VISUAL_RETRY_DELAY_SECONDS", "2"))))

    if raise_on_failure and last_error is not None:
        raise last_error

    reason = (
        f"{provider} multimodal request failed; OCR/context fallback used."
        if analysis_task == "manual_page"
        else f"{provider} 多模态 provider 调用失败，已降级到 mock：{last_error}"
    )
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
