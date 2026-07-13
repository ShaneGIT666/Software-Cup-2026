from __future__ import annotations

import json
import shutil
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from .mineru_adapter import MinerUUnavailable, parse_with_mineru
from .parser_modes import ParserPolicy, resolve_parser_policy


MINERU_FIRST_SUFFIXES = {"pdf", "docx", "pptx", "xlsx"}
IMAGE_SUFFIXES = {"jpg", "jpeg", "png", "webp"}


def _safe_mineru_fallback_reason(exc: Exception) -> str:
    message = str(exc).lower()
    if "timed out" in message:
        return "MinerU timed out; pypdf fallback used."
    if "disabled" in message:
        return "MinerU is disabled; fallback parser used."
    if "not installed" in message or "executable was not found" in message:
        return "MinerU is unavailable; fallback parser used."
    return "MinerU parsing failed; fallback parser used."


def decode_text(content: bytes) -> str:
    for encoding in ("utf-8-sig", "gb18030", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="ignore")


def parse_pdf_with_pypdf(content: bytes) -> dict[str, Any]:
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
    except ImportError:
        return mock_parse_result("pdf", "pypdf is not installed.")

    try:
        reader = PdfReader(BytesIO(content))
    except Exception as exc:  # pragma: no cover - parser details vary
        raise HTTPException(status_code=400, detail="PDF 文件无法解析") from exc

    pages: list[dict[str, Any]] = []
    markdown_parts: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append({"page": index, "text": text, "section": f"page-{index}"})
            markdown_parts.append(f"## Page {index}\n\n{text}")

    if not pages:
        return {
            "parser": "pypdf",
            "status": "needs_multimodal_analysis",
            "pages": [],
            "markdown": "",
            "assets": [],
            "fallback": True,
            "fallbackReason": "PDF contains no extractable text.",
        }

    return {
        "parser": "pypdf",
        "status": "parsed",
        "pages": pages,
        "markdown": "\n\n".join(markdown_parts),
        "assets": [],
        "fallback": False,
        "fallbackReason": "",
    }


def mock_parse_result(suffix: str, reason: str) -> dict[str, Any]:
    markdown = (
        f"# Parser fallback\n\n"
        f"File type: {suffix.upper()}\n\n"
        f"Reason: {reason}\n\n"
        "No trusted knowledge chunks were generated automatically. Please run OCR/multimodal analysis or upload a text version."
    )
    return {
        "parser": "mock-parser",
        "status": "needs_parser",
        "pages": [],
        "markdown": markdown,
        "assets": [],
        "fallback": True,
        "fallbackReason": reason,
    }


def parse_document(
    file_path: Path,
    suffix: str,
    content: bytes,
    policy: ParserPolicy | None = None,
) -> dict[str, Any]:
    suffix = suffix.lower()
    policy = policy or resolve_parser_policy(None)
    base_result = {
        "parserModeRequested": policy.mode,
        "parserModeEffective": policy.mode,
        "mineruAttempted": False,
        "mineruSucceeded": False,
        "mineruTimeoutSeconds": policy.mineru_timeout_seconds,
        "visualAnalysisRequested": policy.render_scope != "none",
    }
    if suffix in IMAGE_SUFFIXES:
        return {
            **base_result,
            "parser": "multimodal-image",
            "status": "needs_multimodal_analysis",
            "pages": [],
            "markdown": "",
            "assets": [],
            "fallback": False,
            "fallbackReason": "",
        }

    if policy.mode == "text_fast":
        if suffix == "pdf":
            return {**base_result, **parse_pdf_with_pypdf(content)}
        if suffix not in {"txt", "md"}:
            return {**base_result, **mock_parse_result(suffix, "text_fast does not parse Office documents.")}

    if suffix in MINERU_FIRST_SUFFIXES and policy.use_mineru:
        try:
            result = parse_with_mineru(
                file_path,
                suffix,
                timeout_seconds=policy.mineru_timeout_seconds,
            )
            return {
                **base_result,
                "parser": result.get("parser", "mineru"),
                "status": result.get("status", "parsed"),
                "pages": result.get("pages", []),
                "markdown": result.get("markdown", ""),
                "assets": result.get("assets", []),
                "mineruAssets": result.get("mineruAssets", []),
                "mineruAttempted": True,
                "mineruSucceeded": True,
                "fallback": False,
                "fallbackReason": "",
            }
        except MinerUUnavailable as exc:
            safe_reason = _safe_mineru_fallback_reason(exc)
            if suffix == "pdf":
                result = parse_pdf_with_pypdf(content)
                result.update(base_result)
                result["fallback"] = result.get("fallback", False) or result["parser"] != "mineru"
                result["fallbackReason"] = result.get("fallbackReason") or safe_reason
                result["mineruAttempted"] = True
                result["mineruSucceeded"] = False
                return result
            return {
                **base_result,
                **mock_parse_result(suffix, safe_reason),
                "mineruAttempted": True,
                "mineruSucceeded": False,
            }

    text = decode_text(content).strip()
    if not text:
        return {
            "parser": "plain-text",
            "status": "empty",
            "pages": [],
            "markdown": "",
            "assets": [],
            "fallback": False,
            "fallbackReason": "",
        }

    return {
        **base_result,
        "parser": "plain-text",
        "status": "parsed",
        "pages": [{"page": None, "section": "text", "text": text}],
        "markdown": text,
        "assets": [],
        "fallback": False,
        "fallbackReason": "",
    }


def save_parse_artifacts(document_dir: Path, parse_result: dict[str, Any]) -> dict[str, str]:
    assets_dir = document_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    raw_path = document_dir / "raw_parse_result.json"
    markdown_path = document_dir / "parsed.md"
    copied_assets: list[str] = []
    copied_by_name: dict[str, str] = {}
    for asset in parse_result.get("assets", []):
        source = Path(str(asset))
        if not source.exists() or not source.is_file():
            continue
        target = assets_dir / source.name
        suffix_index = 1
        while target.exists():
            target = assets_dir / f"{source.stem}-{suffix_index}{source.suffix}"
            suffix_index += 1
        shutil.copy2(source, target)
        copied_assets.append(str(target))
        copied_by_name[source.name] = f"assets/{target.name}"

    if copied_assets:
        mineru_assets: list[dict[str, Any]] = []
        for record in parse_result.get("mineruAssets", []):
            if not isinstance(record, dict):
                continue
            copied_relative = copied_by_name.get(Path(str(record.get("relativePath") or "")).name)
            if copied_relative:
                mineru_assets.append({**record, "relativePath": copied_relative})
        parse_result = {
            **parse_result,
            "assets": copied_assets,
            "mineruAssets": mineru_assets,
        }

    raw_path.write_text(json.dumps(parse_result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(str(parse_result.get("markdown", "")), encoding="utf-8")
    return {
        "rawParseResult": str(raw_path),
        "parsedMarkdown": str(markdown_path),
        "assetsDir": str(assets_dir),
    }
