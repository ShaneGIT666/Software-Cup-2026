from __future__ import annotations

import json
import shutil
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from .mineru_adapter import MinerUUnavailable, parse_with_mineru


MINERU_FIRST_SUFFIXES = {"pdf", "docx", "pptx", "xlsx"}
IMAGE_SUFFIXES = {"jpg", "jpeg", "png", "webp"}


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


def parse_document(file_path: Path, suffix: str, content: bytes) -> dict[str, Any]:
    suffix = suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        return {
            "parser": "multimodal-image",
            "status": "needs_multimodal_analysis",
            "pages": [],
            "markdown": "",
            "assets": [],
            "fallback": False,
            "fallbackReason": "",
        }

    if suffix in MINERU_FIRST_SUFFIXES:
        try:
            result = parse_with_mineru(file_path, suffix)
            return {
                "parser": result.get("parser", "mineru"),
                "status": result.get("status", "parsed"),
                "pages": result.get("pages", []),
                "markdown": result.get("markdown", ""),
                "assets": result.get("assets", []),
                "fallback": False,
                "fallbackReason": "",
            }
        except MinerUUnavailable as exc:
            if suffix == "pdf":
                result = parse_pdf_with_pypdf(content)
                result["fallback"] = result.get("fallback", False) or result["parser"] != "mineru"
                result["fallbackReason"] = result.get("fallbackReason") or f"MinerU unavailable: {exc}"
                return result
            return mock_parse_result(suffix, f"MinerU unavailable: {exc}")

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

    if copied_assets:
        parse_result = {**parse_result, "assets": copied_assets}

    raw_path.write_text(json.dumps(parse_result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(str(parse_result.get("markdown", "")), encoding="utf-8")
    return {
        "rawParseResult": str(raw_path),
        "parsedMarkdown": str(markdown_path),
        "assetsDir": str(assets_dir),
    }
