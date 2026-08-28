from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .provider_policy import record_fallback


SUPPORTED_OCR_PROVIDERS = {"mock", "rapidocr", "tesseract", "off"}
OCR_IMAGE_SUFFIXES = {"jpg", "jpeg", "png", "webp"}
logger = logging.getLogger(__name__)


def configured_ocr_provider() -> str:
    provider = (os.getenv("OCR_PROVIDER") or "mock").strip().lower()
    return provider if provider in SUPPORTED_OCR_PROVIDERS else "mock"


def ocr_available(provider: str) -> bool:
    if provider == "mock":
        return True
    if provider == "rapidocr":
        try:
            import rapidocr_onnxruntime  # noqa: F401

            return True
        except ImportError:
            try:
                import rapidocr  # noqa: F401

                return True
            except ImportError:
                return False
    if provider == "tesseract":
        return shutil.which("tesseract") is not None
    return False


def mock_ocr_result(
    file_path: Path,
    source_name: str,
    suffix: str,
    requested_provider: str,
    fallback_reason: str | None = None,
) -> dict[str, Any]:
    text = (
        f"{source_name} 的 OCR 演示级识别结果：图像或扫描件中可能包含摩托车发动机、"
        "火花塞、点火系统、燃油供给、启动困难、怠速不稳和安全检修提示等文字线索。"
    )
    return {
        "provider": "mock",
        "requestedProvider": requested_provider,
        "fallback": True,
        "fallbackReason": fallback_reason or "未启用真实 OCR provider，已使用 mock OCR 保证演示连续性。",
        "text": text,
        "textSegments": [
            text,
            "OCR 识别文本可作为跨模态检索入口：现场图片或扫描手册中的故障码、部件名和检修步骤会转为可检索知识片段。",
        ],
        "confidence": 0.55,
        "fileName": file_path.name,
        "suffix": suffix,
    }


def rapidocr_text(file_path: Path) -> str:
    try:
        from rapidocr_onnxruntime import RapidOCR  # type: ignore[import-not-found]
    except ImportError:
        from rapidocr import RapidOCR  # type: ignore[import-not-found]

    engine = RapidOCR()
    result, _ = engine(str(file_path))
    texts: list[str] = []
    for item in result or []:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            text = item[1]
            if isinstance(text, str) and text.strip():
                texts.append(text.strip())
    return "\n".join(texts).strip()


def tesseract_text(file_path: Path, lang: str) -> str:
    if file_path.suffix.lower().lstrip(".") not in OCR_IMAGE_SUFFIXES:
        raise RuntimeError("Tesseract 本地兜底当前仅支持图片文件 OCR")
    command = [
        "tesseract",
        str(file_path),
        "stdout",
        "-l",
        lang,
        "--psm",
        os.getenv("OCR_TESSERACT_PSM", "6"),
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=float(os.getenv("OCR_TIMEOUT_SECONDS", "30")))
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or "tesseract OCR failed").strip())
    return completed.stdout.strip()


def real_ocr_result(file_path: Path, source_name: str, suffix: str, provider: str) -> dict[str, Any]:
    lang = (os.getenv("OCR_LANG") or "ch").strip()
    if provider == "rapidocr":
        text = rapidocr_text(file_path)
    elif provider == "tesseract":
        tesseract_lang = os.getenv("OCR_TESSERACT_LANG") or ("chi_sim" if lang in {"ch", "zh", "zh-cn"} else lang)
        text = tesseract_text(file_path, tesseract_lang)
    else:
        raise RuntimeError(f"不支持的 OCR provider: {provider}")

    if not text:
        raise RuntimeError("OCR 未识别出有效文本")
    return {
        "provider": provider,
        "requestedProvider": provider,
        "fallback": False,
        "fallbackReason": "",
        "text": text,
        "textSegments": [text],
        "confidence": None,
        "fileName": file_path.name,
        "suffix": suffix,
        "sourceName": source_name,
    }


def analyze_ocr_document(file_path: Path, source_name: str, suffix: str) -> dict[str, Any]:
    provider = configured_ocr_provider()
    if provider == "off":
        return {
            "provider": "off",
            "requestedProvider": "off",
            "fallback": False,
            "fallbackReason": "",
            "text": "",
            "textSegments": [],
            "confidence": None,
            "fileName": file_path.name,
            "suffix": suffix,
        }
    if provider == "mock":
        return mock_ocr_result(file_path, source_name, suffix, provider)

    try:
        return real_ocr_result(file_path, source_name, suffix, provider)
    except Exception as exc:
        reason = f"{provider} OCR provider 不可用，已降级到 mock OCR：{exc}"
        record_fallback("ocr", reason)
        logger.warning("event=ocr_provider_fallback")
        return mock_ocr_result(file_path, source_name, suffix, provider, reason)


def ocr_status() -> dict[str, Any]:
    provider = configured_ocr_provider()
    return {
        "provider": provider,
        "remoteCapable": False,
        "keyConfigured": False,
        "effectiveProvider": provider if provider != "off" and ocr_available(provider) else ("off" if provider == "off" else "mock"),
        "available": ocr_available(provider),
        "model": os.getenv("OCR_MODEL", "provider-default" if provider not in {"mock", "off"} else provider),
        "lastFallbackReason": "",
    }
