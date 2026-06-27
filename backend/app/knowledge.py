from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import json
import logging
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from .data_store import (
    knowledge_dir,
    load_document_chunks,
    load_documents,
    load_knowledge_revisions,
    load_parse_tasks,
    load_review_events,
    save_document_chunks,
    save_documents,
    save_knowledge_revisions,
    save_parse_tasks,
    save_review_events,
)
from .llm_adapter import (
    _post_json,
    llm_max_tokens,
    llm_temperature,
    parse_anthropic_response,
    parse_openai_chat_response,
    parse_openai_response,
    provider_api_style,
    provider_model,
)
from .multimodal_adapter import analyze_multimodal_document
from .ocr_adapter import analyze_ocr_document
from .parser_router import parse_document, save_parse_artifacts
from .provider_policy import configured_llm_provider, key_configured, record_fallback, remote_api_disabled
from .schemas import KnowledgeChunkReviewRequest, KnowledgeChunkRevisionRequest, KnowledgeChunkStatusRequest
from .vector_store import delete_document as delete_vector_document
from .vector_store import sync_chunks


MAX_KNOWLEDGE_DOCUMENT_BYTES = 20 * 1024 * 1024
ALLOWED_KNOWLEDGE_TYPES = {
    "pdf": {"application/pdf"},
    "txt": {"text/plain", "application/octet-stream"},
    "md": {"text/markdown", "text/plain", "application/octet-stream"},
    "docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/octet-stream"},
    "pptx": {"application/vnd.openxmlformats-officedocument.presentationml.presentation", "application/octet-stream"},
    "xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/octet-stream"},
    "jpg": {"image/jpeg"},
    "jpeg": {"image/jpeg"},
    "png": {"image/png"},
    "webp": {"image/webp"},
}
MULTIMODAL_SUFFIXES = {"pdf", "jpg", "jpeg", "png", "webp"}
IMAGE_SUFFIXES = {"jpg", "jpeg", "png", "webp"}
ASSET_ANALYSIS_ORIGIN = "mineru_asset_analysis"
ASSET_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
PDF_PAGE_VISUAL_ASSET_TYPE = "pdf_page_visual_asset"
PDF_VISUAL_KEYWORDS = (
    "图",
    "图示",
    "装配",
    "部件清单",
    "拆卸",
    "安装",
    "检查",
    "火花塞",
    "起动电机",
    "发动机",
    "气缸",
    "活塞",
    "气门",
    "曲轴",
    "离合器",
)
CHUNK_SIZE = 700
CHUNK_OVERLAP = 120
logger = logging.getLogger(__name__)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def validate_knowledge_file_info(file_name: str | None, content_type: str | None, content: bytes) -> str:
    suffix = Path(file_name or "").suffix.lower().lstrip(".")
    if not suffix or suffix not in ALLOWED_KNOWLEDGE_TYPES:
        logger.warning("Rejected knowledge upload with unsupported extension: %s", file_name)
        raise HTTPException(status_code=400, detail="资料入库仅支持 pdf、txt、md、jpg、jpeg、png 和 webp 文件")
    if not content:
        logger.warning("Rejected empty knowledge upload: %s", file_name)
        raise HTTPException(status_code=400, detail="资料文件不能为空")
    if len(content) > MAX_KNOWLEDGE_DOCUMENT_BYTES:
        logger.warning("Rejected oversized knowledge upload: %s bytes=%s", file_name, len(content))
        raise HTTPException(status_code=400, detail="资料文件不能超过 20MB")

    normalized_content_type = (content_type or "").split(";", 1)[0].lower()
    if normalized_content_type and normalized_content_type not in ALLOWED_KNOWLEDGE_TYPES[suffix]:
        logger.warning(
            "Rejected knowledge upload with MIME mismatch: filename=%s suffix=%s content_type=%s",
            file_name,
            suffix,
            normalized_content_type,
        )
        raise HTTPException(status_code=400, detail="资料文件扩展名与 MIME 类型不匹配")
    return suffix


def validate_knowledge_file(file: UploadFile, content: bytes) -> str:
    return validate_knowledge_file_info(file.filename, file.content_type, content)


def decode_text(content: bytes) -> str:
    for encoding in ("utf-8-sig", "gb18030", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="ignore")


def extract_pdf_pages(content: bytes) -> tuple[list[dict[str, Any]], str]:
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
    except ImportError:
        return [], "needs_parser"

    try:
        reader = PdfReader(BytesIO(content))
    except Exception as exc:  # pragma: no cover - depends on third-party parser details
        raise HTTPException(status_code=400, detail="PDF 文件无法解析") from exc

    pages: list[dict[str, Any]] = []
    for index, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append({"page": index, "text": text})
    return pages, "indexed" if pages else "needs_multimodal_analysis"


def extract_pages(content: bytes, suffix: str) -> tuple[list[dict[str, Any]], str, str]:
    if suffix in IMAGE_SUFFIXES:
        return [], "needs_multimodal_analysis", "multimodal-image"

    if suffix == "pdf":
        pages, status = extract_pdf_pages(content)
        parser = "pypdf" if status not in {"needs_parser", "needs_multimodal_analysis"} else "multimodal-ready"
        if status == "needs_parser":
            status = "needs_multimodal_analysis"
        return pages, status, parser

    text = decode_text(content).strip()
    if not text:
        return [], "empty", "plain-text"
    return [{"page": None, "text": text}], "indexed", "plain-text"


def split_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    normalized = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if not normalized:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(len(normalized), start + size)
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(normalized):
            break
        start = max(0, end - overlap)
    return chunks


def build_keywords(text: str) -> list[str]:
    separators = ["，", "。", "、", ",", ".", " ", "-", "_", "\n", "\r", "：", ":", "；", ";"]
    normalized = text.lower()
    for separator in separators:
        normalized = normalized.replace(separator, " ")
    keywords = [item for item in normalized.split(" ") if len(item) >= 2]
    return list(dict.fromkeys(keywords[:12]))


def build_chunk(
    document_id: str,
    file_name: str,
    source_name: str,
    chunk_text: str,
    chunk_index: int,
    page: int | None = None,
    analysis_provider: str | None = None,
    section: str | None = None,
    review_status: str = "pending_review",
) -> dict[str, Any]:
    chunk_id = f"{document_id}-chunk-{chunk_index:03d}"
    now = utc_now()
    chunk = {
        "id": chunk_id,
        "chunk_id": chunk_id,
        "documentId": document_id,
        "source_doc_id": document_id,
        "title": Path(file_name or document_id).stem,
        "sourceType": "document",
        "source_type": "document",
        "sourceName": source_name or file_name or document_id,
        "page": page,
        "section": section or "",
        "chunkIndex": chunk_index,
        "content": chunk_text,
        "snippet": chunk_text[:160],
        "keywords": build_keywords(chunk_text),
        "device_model": "",
        "component": "",
        "fault_symptom": "",
        "fault_code": "",
        "knowledge_type": "manual_excerpt",
        "risk_level": "medium",
        "evidence_location": {"page": page, "section": section or ""},
        "review_status": review_status,
        "version": 1,
        "created_at": now,
        "updated_at": now,
    }
    if analysis_provider:
        chunk["analysisProvider"] = analysis_provider
    return chunk


def env_flag(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() not in {"0", "false", "no", "off"}


def auto_analyze_assets_enabled() -> bool:
    return env_flag("KNOWLEDGE_AUTO_ANALYZE_ASSETS", True)


def asset_analysis_limit() -> int:
    raw_value = os.getenv("KNOWLEDGE_ASSET_ANALYSIS_MAX_ASSETS", "12")
    try:
        return max(0, int(raw_value))
    except ValueError:
        return 12


def pdf_page_visual_asset_limit() -> int:
    raw_value = os.getenv("PDF_PAGE_VISUAL_ASSET_LIMIT", "12")
    try:
        return max(0, int(raw_value))
    except ValueError:
        return 12


def load_parse_result_from_artifacts(parse_artifacts: dict[str, Any]) -> dict[str, Any]:
    raw_path = Path(str(parse_artifacts.get("rawParseResult") or ""))
    if not raw_path.exists() or not raw_path.is_file():
        return {}
    try:
        return json.loads(raw_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to load raw parse result for asset analysis: %s", exc)
        return {}


def asset_candidates_from_artifacts(parse_artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    parse_result = load_parse_result_from_artifacts(parse_artifacts)
    assets_dir = Path(str(parse_artifacts.get("assetsDir") or ""))
    raw_assets = parse_result.get("assets") if isinstance(parse_result, dict) else []
    candidates: list[Path] = []

    if isinstance(raw_assets, list):
        for item in raw_assets:
            path = Path(str(item))
            if not path.is_absolute() and assets_dir:
                path = assets_dir / path
            candidates.append(path)

    if assets_dir.exists():
        candidates.extend(path for path in assets_dir.rglob("*") if path.is_file())

    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in candidates:
        if path.suffix.lower() not in ASSET_IMAGE_SUFFIXES or not path.exists() or not path.is_file():
            continue
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        unique.append(
            {
                "path": path,
                "assetName": path.name,
                "assetPath": str(path),
                "page": None,
                "section": f"asset:{path.name}",
            }
        )
    return unique


def safe_page_number(value: Any) -> int | None:
    try:
        page = int(value)
    except (TypeError, ValueError):
        return None
    return page if page > 0 else None


def extract_pdf_image_counts(file_path: Path) -> tuple[int, dict[int, int], dict[int, str]]:
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
    except ImportError:
        return 0, {}, {}

    try:
        reader = PdfReader(str(file_path))
    except Exception as exc:
        logger.info("PDF visual fallback could not inspect PDF with pypdf: %s", exc)
        return 0, {}, {}

    image_counts: dict[int, int] = {}
    page_texts: dict[int, str] = {}
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = (page.extract_text() or "").strip()
        except Exception:
            text = ""
        if text:
            page_texts[index] = text

        image_count = 0
        try:
            resources = page.get("/Resources") or {}
            xobjects = resources.get("/XObject") or {}
            for obj in xobjects.values():
                try:
                    resolved = obj.get_object()
                    if resolved.get("/Subtype") == "/Image":
                        image_count += 1
                except Exception:
                    continue
        except Exception:
            image_count = 0
        if image_count:
            image_counts[index] = image_count
    return len(reader.pages), image_counts, page_texts


def clean_pdf_page_summary(text: str, max_length: int = 220) -> str:
    normalized = " ".join(str(text or "").split())
    if not normalized:
        return "未提取到稳定的页面文字。"
    replacement_count = normalized.count("\ufffd")
    if replacement_count and replacement_count / max(1, len(normalized)) > 0.08:
        return "页面文字编码无法稳定提取，已保留该页作为视觉资产供人工审核。"
    return normalized[:max_length]


def pdf_page_visual_asset_candidates(document: dict[str, Any]) -> list[dict[str, Any]]:
    if str(document.get("suffix") or "").lower() != "pdf":
        return []

    parse_result = load_parse_result_from_artifacts(document.get("parseArtifacts", {}))
    parse_pages = parse_result.get("pages") if isinstance(parse_result, dict) else []
    page_infos: dict[int, dict[str, Any]] = {}

    if isinstance(parse_pages, list):
        for item in parse_pages:
            if not isinstance(item, dict):
                continue
            page = safe_page_number(item.get("page"))
            if page is None:
                continue
            page_infos.setdefault(page, {"page": page, "text": "", "section": f"pdf-page-{page}"})
            if item.get("text"):
                page_infos[page]["text"] = str(item.get("text") or "")
            if item.get("section"):
                page_infos[page]["section"] = str(item.get("section") or f"pdf-page-{page}")

    stored_file = knowledge_dir() / "files" / f"{document.get('id')}.pdf"
    page_count = 0
    image_counts: dict[int, int] = {}
    page_texts: dict[int, str] = {}
    if stored_file.exists():
        page_count, image_counts, page_texts = extract_pdf_image_counts(stored_file)

    for page, text in page_texts.items():
        page_infos.setdefault(page, {"page": page, "text": "", "section": f"pdf-page-{page}"})
        if text and not page_infos[page].get("text"):
            page_infos[page]["text"] = text
    for page, image_count in image_counts.items():
        page_infos.setdefault(page, {"page": page, "text": "", "section": f"pdf-page-{page}"})
        page_infos[page]["imageCount"] = image_count

    if not page_infos and page_count:
        for page in range(1, page_count + 1):
            page_infos[page] = {"page": page, "text": "", "section": f"pdf-page-{page}", "imageCount": 0}

    if not page_infos:
        return []

    def score(info: dict[str, Any]) -> int:
        text = str(info.get("text") or "")
        keyword_hits = sum(1 for keyword in PDF_VISUAL_KEYWORDS if keyword in text)
        image_count = int(info.get("imageCount") or 0)
        base = image_count * 1000 + keyword_hits * 100
        if info.get("text"):
            base += 10
        if safe_page_number(info.get("page")) == 1:
            base -= 20
        return base

    selected = sorted(page_infos.values(), key=lambda item: (-score(item), safe_page_number(item.get("page")) or 99999))
    if not any(score(item) > 0 for item in selected):
        selected = sorted(page_infos.values(), key=lambda item: safe_page_number(item.get("page")) or 99999)
    selected = selected[:pdf_page_visual_asset_limit()]
    selected = sorted(selected, key=lambda item: safe_page_number(item.get("page")) or 99999)

    candidates: list[dict[str, Any]] = []
    for info in selected:
        page = safe_page_number(info.get("page"))
        if page is None:
            continue
        asset_name = f"page-{page}-visual"
        candidates.append(
            {
                "assetName": asset_name,
                "assetPath": f"{stored_file}#page={page}" if stored_file.exists() else asset_name,
                "page": page,
                "section": str(info.get("section") or f"pdf-page-{page}"),
                "pageText": str(info.get("text") or ""),
                "imageCount": int(info.get("imageCount") or 0),
            }
        )
    return candidates


def has_pdf_page_visual_asset_fallback(document: dict[str, Any]) -> bool:
    return pdf_page_visual_asset_limit() > 0 and bool(pdf_page_visual_asset_candidates(document))


def update_document_asset_analysis_status(document_id: str, **updates: Any) -> dict[str, Any] | None:
    documents = load_documents()
    for index, document in enumerate(documents):
        if document.get("id") == document_id:
            updated = {**document, **updates, "assetAnalysisUpdatedAt": utc_now()}
            documents[index] = updated
            save_documents(documents)
            return updated
    return None


def mark_initial_asset_analysis_state(document: dict[str, Any]) -> dict[str, Any]:
    candidates = asset_candidates_from_artifacts(document.get("parseArtifacts", {}))
    has_pdf_fallback = has_pdf_page_visual_asset_fallback(document)
    if (candidates or has_pdf_fallback) and auto_analyze_assets_enabled() and asset_analysis_limit() > 0:
        return {
            **document,
            "assetAnalysisStatus": "queued",
            "assetAnalysisCount": 0,
            "assetAnalysisFallbackCount": 0,
            "assetAnalysisError": "",
            "assetAnalysisUpdatedAt": utc_now(),
        }
    reason = "auto_disabled" if candidates or has_pdf_fallback else "no_assets"
    return {
        **document,
        "assetAnalysisStatus": "skipped",
        "assetAnalysisCount": 0,
        "assetAnalysisFallbackCount": 0,
        "assetAnalysisError": reason,
        "assetAnalysisUpdatedAt": utc_now(),
    }


def should_enqueue_asset_analysis(document: dict[str, Any]) -> bool:
    return (
        auto_analyze_assets_enabled()
        and asset_analysis_limit() > 0
        and document.get("assetAnalysisStatus") == "queued"
    )


def apply_asset_chunk_metadata(
    chunk: dict[str, Any],
    document: dict[str, Any],
    asset: dict[str, Any],
    knowledge_type: str,
    chunk_id: str,
    provider: str,
    fallback_reason: str = "",
) -> dict[str, Any]:
    chunk["id"] = chunk_id
    chunk["chunk_id"] = chunk_id
    chunk["sourceType"] = "document_asset"
    chunk["source_type"] = "document_asset"
    chunk["knowledge_type"] = knowledge_type
    chunk["origin"] = ASSET_ANALYSIS_ORIGIN
    chunk["assetName"] = asset["assetName"]
    chunk["assetPath"] = asset["assetPath"]
    chunk["page"] = asset.get("page")
    chunk["section"] = asset.get("section", "")
    chunk["evidence_location"] = {
        "page": asset.get("page"),
        "section": asset.get("section", ""),
        "assetName": asset["assetName"],
        "assetPath": asset["assetPath"],
    }
    chunk["analysisProvider"] = provider
    chunk["review_status"] = "pending_review"
    chunk["risk_level"] = "medium"
    if fallback_reason:
        chunk["analysisFallbackReason"] = fallback_reason
    if document.get("parser"):
        chunk["parser"] = document["parser"]
    return chunk


def build_asset_text_chunks(
    document: dict[str, Any],
    asset: dict[str, Any],
    texts: list[str],
    knowledge_type: str,
    provider: str,
    id_prefix: str,
    fallback_reason: str = "",
) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    source_name = f"{document.get('sourceName') or document.get('fileName') or document['id']} / {asset['assetName']}"
    for segment in texts:
        for chunk_text in split_text(str(segment)):
            chunk = build_chunk(
                document_id=document["id"],
                file_name=asset["assetName"],
                source_name=source_name,
                chunk_text=chunk_text,
                chunk_index=len(chunks) + 1,
                page=asset.get("page"),
                analysis_provider=provider,
                section=asset.get("section", ""),
                review_status="pending_review",
            )
            chunks.append(
                apply_asset_chunk_metadata(
                    chunk=chunk,
                    document=document,
                    asset=asset,
                    knowledge_type=knowledge_type,
                    chunk_id=f"{document['id']}-asset-{id_prefix}-{len(chunks) + 1:03d}",
                    provider=provider,
                    fallback_reason=fallback_reason,
                )
            )
    return chunks


def call_text_llm_for_asset_analysis(
    document: dict[str, Any],
    asset: dict[str, Any],
    ocr_result: dict[str, Any],
    visual_fallback_reason: str,
) -> dict[str, Any]:
    provider = configured_llm_provider(None)
    if provider == "mock":
        raise RuntimeError("LLM_PROVIDER=mock")
    if remote_api_disabled():
        raise RuntimeError("REMOTE_API_MODE=off")
    if not key_configured(provider):
        raise RuntimeError(f"{provider} API key is not configured")

    ocr_text = str(ocr_result.get("text") or "\n".join(ocr_result.get("textSegments", []))).strip()
    prompt = (
        "你是设备检修知识库的资料审核助手。请基于 OCR 文本、图片文件名和来源文档信息，"
        "生成一段可进入 pending_review 的图片资产分析摘要。\n"
        "要求：只能基于给定信息，不得编造页码、参数、故障码、维修结论；证据不足时明确写“不确定”。\n\n"
        f"来源文档：{document.get('sourceName') or document.get('fileName') or document.get('id')}\n"
        f"图片资产：{asset.get('assetName')}\n"
        f"MinerU section：{asset.get('section') or 'unknown'}\n"
        f"视觉分析失败原因：{visual_fallback_reason or 'unknown'}\n"
        f"OCR 文本：\n{ocr_text or '无可用 OCR 文本'}\n\n"
        "请输出中文短摘要，包含：可见文字/部件线索、可能对应的检修用途、安全风险、仍不确定的信息。"
    )
    timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "20"))
    model = provider_model(provider)

    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "")
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        if provider_api_style(provider) == "chat_completions":
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
            text = parse_openai_chat_response(payload)
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
            text = parse_openai_response(payload)
    elif provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
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
        text = parse_anthropic_response(payload)
    else:
        raise RuntimeError(f"unsupported LLM provider: {provider}")

    if not text:
        raise RuntimeError("text LLM returned empty asset analysis")
    return {
        "provider": f"{provider}-text-fallback",
        "requestedProvider": provider,
        "fallback": True,
        "fallbackReason": visual_fallback_reason,
        "textSegments": [text],
        "summary": text[:240],
    }


def build_asset_analysis_chunks(
    document: dict[str, Any],
    asset: dict[str, Any],
    provider: str | None,
    asset_index: int,
) -> tuple[list[dict[str, Any]], int, str]:
    chunks: list[dict[str, Any]] = []
    fallback_count = 0
    errors: list[str] = []
    suffix = Path(asset["assetName"]).suffix.lower().lstrip(".")

    ocr_result = analyze_ocr_document(Path(asset["assetPath"]), asset["assetName"], suffix)
    ocr_segments = [str(segment) for segment in ocr_result.get("textSegments", []) if str(segment).strip()]
    if ocr_result.get("text") and not ocr_segments:
        ocr_segments = [str(ocr_result["text"])]
    if ocr_segments:
        chunks.extend(
            build_asset_text_chunks(
                document=document,
                asset=asset,
                texts=ocr_segments,
                knowledge_type="ocr_result",
                provider=str(ocr_result.get("provider") or "ocr"),
                id_prefix=f"{asset_index:03d}-ocr",
                fallback_reason=str(ocr_result.get("fallbackReason") or ""),
            )
        )
    if ocr_result.get("fallback"):
        fallback_count += 1

    visual_analysis = analyze_multimodal_document(
        file_path=Path(asset["assetPath"]),
        source_name=f"{document.get('sourceName') or document.get('fileName') or document['id']} / {asset['assetName']}",
        suffix=suffix,
        requested_provider=provider,
    )
    if visual_analysis.get("fallback"):
        fallback_count += 1
        try:
            visual_analysis = call_text_llm_for_asset_analysis(document, asset, ocr_result, str(visual_analysis.get("fallbackReason", "")))
        except Exception as exc:
            reason = f"asset text LLM fallback failed for {asset['assetName']}: {exc}"
            record_fallback("llm", reason)
            logger.warning(reason)
            errors.append(reason)
            return chunks, fallback_count + 1, "; ".join(errors)

    visual_segments = [str(segment) for segment in visual_analysis.get("textSegments", []) if str(segment).strip()]
    if not visual_segments and visual_analysis.get("summary"):
        visual_segments = [str(visual_analysis["summary"])]
    if visual_segments:
        chunks.extend(
            build_asset_text_chunks(
                document=document,
                asset=asset,
                texts=visual_segments,
                knowledge_type="image_analysis",
                provider=str(visual_analysis.get("provider") or "multimodal"),
                id_prefix=f"{asset_index:03d}-image",
                fallback_reason=str(visual_analysis.get("fallbackReason") or ""),
            )
        )
    return chunks, fallback_count, "; ".join(errors)


def build_pdf_page_visual_asset_chunks(document: dict[str, Any], reason: str = "") -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    source_name = document.get("sourceName") or document.get("fileName") or document["id"]
    fallback_reason = reason or document.get("parserFallbackReason") or "PDF image assets were unavailable; page visual fallback generated."

    for index, asset in enumerate(pdf_page_visual_asset_candidates(document), start=1):
        page = asset.get("page")
        image_count = int(asset.get("imageCount") or 0)
        text_summary = clean_pdf_page_summary(str(asset.get("pageText") or ""))
        image_note = f"检测到 {image_count} 个 PDF 内嵌图片对象。" if image_count else "未检测到独立图片对象，按页面文本和页码生成视觉资产。"
        content = (
            f"第 {page} 页 PDF 页面视觉资产 fallback。"
            f"{image_note}"
            "该片段用于在 MinerU 超时、不可用或未提取到图片资产时，保留维修手册图示页进入审核与知识沉淀链路。"
            f"页面文本摘要：{text_summary}"
            "该结果不是生产级图像理解结论，需人工审核后才可作为正式检修依据。"
        )
        chunk = build_chunk(
            document_id=document["id"],
            file_name=str(document.get("fileName") or document["id"]),
            source_name=f"{source_name} / {asset['assetName']}",
            chunk_text=content,
            chunk_index=index,
            page=page,
            analysis_provider="pdf-page-visual-fallback",
            section=str(asset.get("section") or f"pdf-page-{page}"),
            review_status="pending_review",
        )
        chunk = apply_asset_chunk_metadata(
            chunk=chunk,
            document=document,
            asset=asset,
            knowledge_type=PDF_PAGE_VISUAL_ASSET_TYPE,
            chunk_id=f"{document['id']}-asset-pdf-page-{index:03d}",
            provider="pdf-page-visual-fallback",
            fallback_reason=fallback_reason,
        )
        chunk["assetFallbackType"] = PDF_PAGE_VISUAL_ASSET_TYPE
        chunks.append(chunk)
    return chunks


def analyze_document_assets(document_id: str, provider: str | None = None) -> dict[str, Any]:
    documents = load_documents()
    document = next((item for item in documents if item.get("id") == document_id), None)
    if document is None:
        raise HTTPException(status_code=404, detail="knowledge document not found")

    candidates = asset_candidates_from_artifacts(document.get("parseArtifacts", {}))
    limit = asset_analysis_limit()
    if not candidates or limit <= 0:
        pdf_fallback_chunks = build_pdf_page_visual_asset_chunks(
            document,
            reason="no MinerU image assets" if not candidates else "asset analysis limit is zero",
        )
        if pdf_fallback_chunks and limit > 0:
            chunks = load_document_chunks()
            preserved_chunks = [
                chunk
                for chunk in chunks
                if not (chunk.get("documentId") == document_id and chunk.get("origin") == ASSET_ANALYSIS_ORIGIN)
            ]
            preserved_chunks.extend(pdf_fallback_chunks)
            save_document_chunks(preserved_chunks)

            documents = load_documents()
            document = next((item for item in documents if item.get("id") == document_id), document)
            document_chunks = [chunk for chunk in preserved_chunks if chunk.get("documentId") == document_id]
            update_document_review_summary(document, document_chunks)
            document["assetAnalysisStatus"] = "fallback_completed"
            document["assetAnalysisCount"] = len(pdf_fallback_chunks)
            document["assetAnalysisFallbackCount"] = int(document.get("assetAnalysisFallbackCount") or 0) + 1
            document["assetAnalysisError"] = str(document.get("parserFallbackReason") or "PDF page visual asset fallback generated.")
            document["assetAnalysisUpdatedAt"] = utc_now()
            save_documents(documents)
            return {**document, "chunks": pdf_fallback_chunks[:3]}

        updated = update_document_asset_analysis_status(
            document_id,
            assetAnalysisStatus="skipped",
            assetAnalysisCount=0,
            assetAnalysisFallbackCount=0,
            assetAnalysisError="no_assets" if not candidates else "limit_zero",
        )
        return {**(updated or document), "chunks": []}

    update_document_asset_analysis_status(document_id, assetAnalysisStatus="running", assetAnalysisError="")
    limited_assets = candidates[:limit]
    new_chunks: list[dict[str, Any]] = []
    fallback_count = 0
    errors: list[str] = []
    for index, asset in enumerate(limited_assets, start=1):
        try:
            chunks, chunk_fallback_count, error = build_asset_analysis_chunks(document, asset, provider, index)
            new_chunks.extend(chunks)
            fallback_count += chunk_fallback_count
            if error:
                errors.append(error)
        except Exception as exc:
            reason = f"asset analysis failed for {asset['assetName']}: {exc}"
            logger.warning(reason)
            errors.append(reason)
            fallback_count += 1

    if not new_chunks:
        pdf_fallback_chunks = build_pdf_page_visual_asset_chunks(
            document,
            reason="image asset OCR/visual analysis produced no reviewable chunks",
        )
        if pdf_fallback_chunks:
            new_chunks.extend(pdf_fallback_chunks)
            fallback_count += 1

    chunks = load_document_chunks()
    preserved_chunks = [
        chunk
        for chunk in chunks
        if not (chunk.get("documentId") == document_id and chunk.get("origin") == ASSET_ANALYSIS_ORIGIN)
    ]
    preserved_chunks.extend(new_chunks)
    save_document_chunks(preserved_chunks)

    documents = load_documents()
    document = next((item for item in documents if item.get("id") == document_id), document)
    document_chunks = [chunk for chunk in preserved_chunks if chunk.get("documentId") == document_id]
    update_document_review_summary(document, document_chunks)
    has_pdf_visual_fallback = any(chunk.get("knowledge_type") == PDF_PAGE_VISUAL_ASSET_TYPE for chunk in new_chunks)
    document["assetAnalysisStatus"] = "fallback_completed" if has_pdf_visual_fallback else ("completed" if new_chunks else "failed")
    document["assetAnalysisCount"] = len(new_chunks)
    document["assetAnalysisFallbackCount"] = fallback_count
    document["assetAnalysisError"] = "; ".join(errors)[:1000]
    document["assetAnalysisUpdatedAt"] = utc_now()
    save_documents(documents)
    return {**document, "chunks": new_chunks[:3]}


def ingest_knowledge_document_bytes(
    content: bytes,
    file_name: str | None,
    content_type: str | None,
    source_name: str | None = None,
) -> dict[str, Any]:
    suffix = validate_knowledge_file_info(file_name, content_type, content)
    document_id = f"kdoc-{uuid4().hex[:8]}"
    file_name = file_name or f"{document_id}.{suffix}"
    display_source = source_name or file_name or document_id
    target_dir = knowledge_dir() / "files"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{document_id}.{suffix}"
    target.write_bytes(content)

    parse_result = parse_document(target, suffix, content)
    parse_artifacts = save_parse_artifacts(knowledge_dir() / "parsed" / document_id, parse_result)
    pages = parse_result.get("pages", [])
    parser = str(parse_result.get("parser", "parser-router"))
    chunks: list[dict[str, Any]] = []
    for page in pages:
        for chunk_text in split_text(str(page.get("text", ""))):
            chunks.append(
                build_chunk(
                    document_id=document_id,
                    file_name=file_name,
                    source_name=display_source,
                    chunk_text=chunk_text,
                    chunk_index=len(chunks) + 1,
                    page=page.get("page"),
                    section=page.get("section"),
                    review_status="pending_review",
                )
            )
    status = "pending_review" if chunks else str(parse_result.get("status", "needs_parser"))

    document = {
        "id": document_id,
        "fileName": file_name,
        "fileType": content_type or "",
        "suffix": suffix,
        "sourceName": display_source,
        "status": status,
        "chunkCount": len(chunks),
        "pendingReviewCount": len(chunks),
        "parser": parser,
        "parserFallback": bool(parse_result.get("fallback", False)),
        "parserFallbackReason": parse_result.get("fallbackReason", ""),
        "parseArtifacts": parse_artifacts,
        "uploadedAt": utc_now(),
        "url": f"/knowledge/files/{target.name}",
    }
    document = mark_initial_asset_analysis_state(document)

    documents = load_documents()
    documents.append(document)
    save_documents(documents)

    existing_chunks = load_document_chunks()
    existing_chunks.extend(chunks)
    save_document_chunks(existing_chunks)

    return {**document, "chunks": chunks[:3]}


async def ingest_knowledge_document(file: UploadFile, source_name: str | None = None) -> dict[str, Any]:
    content = await file.read()
    return ingest_knowledge_document_bytes(content, file.filename, file.content_type, source_name)


def append_parse_task(task: dict[str, Any]) -> dict[str, Any]:
    tasks = load_parse_tasks()
    tasks.append(task)
    save_parse_tasks(tasks)
    return task


def update_parse_task(task_id: str, **updates: Any) -> dict[str, Any]:
    tasks = load_parse_tasks()
    for index, task in enumerate(tasks):
        if task.get("id") == task_id:
            updated = {**task, **updates, "updatedAt": utc_now()}
            tasks[index] = updated
            save_parse_tasks(tasks)
            return updated
    raise HTTPException(status_code=404, detail="parse task not found")


def parse_task_response(task: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in task.items() if key != "queuedFile"}


async def create_knowledge_parse_task(file: UploadFile, source_name: str | None = None) -> dict[str, Any]:
    content = await file.read()
    suffix = validate_knowledge_file(file, content)
    task_id = f"ptask-{uuid4().hex[:8]}"
    queue_dir = knowledge_dir() / "parse-queue"
    queue_dir.mkdir(parents=True, exist_ok=True)
    queued_file = queue_dir / f"{task_id}.{suffix}"
    queued_file.write_bytes(content)
    now = utc_now()
    task = {
        "id": task_id,
        "type": "knowledge_document_ingest",
        "status": "queued",
        "fileName": file.filename or f"{task_id}.{suffix}",
        "fileType": file.content_type or "",
        "suffix": suffix,
        "sourceName": source_name or file.filename or task_id,
        "createdAt": now,
        "updatedAt": now,
        "queuedFile": str(queued_file),
        "documentId": None,
        "error": "",
    }
    return parse_task_response(append_parse_task(task))


def process_knowledge_parse_task(task_id: str) -> None:
    task = update_parse_task(task_id, status="running", startedAt=utc_now(), error="")
    queued_file = Path(str(task.get("queuedFile") or ""))
    try:
        if not queued_file.exists():
            raise FileNotFoundError(f"queued file not found: {queued_file}")
        document = ingest_knowledge_document_bytes(
            content=queued_file.read_bytes(),
            file_name=str(task.get("fileName") or queued_file.name),
            content_type=str(task.get("fileType") or ""),
            source_name=str(task.get("sourceName") or ""),
        )
        update_parse_task(
            task_id,
            status="completed",
            completedAt=utc_now(),
            documentId=document.get("id"),
            documentStatus=document.get("status"),
            chunkCount=document.get("chunkCount", 0),
            parser=document.get("parser", ""),
            parserFallback=document.get("parserFallback", False),
            parserFallbackReason=document.get("parserFallbackReason", ""),
            assetAnalysisStatus=document.get("assetAnalysisStatus", "skipped"),
        )
        if should_enqueue_asset_analysis(document):
            analyzed_document = analyze_document_assets(str(document["id"]))
            update_parse_task(
                task_id,
                assetAnalysisStatus=analyzed_document.get("assetAnalysisStatus", ""),
                assetAnalysisCount=analyzed_document.get("assetAnalysisCount", 0),
                assetAnalysisFallbackCount=analyzed_document.get("assetAnalysisFallbackCount", 0),
                assetAnalysisError=analyzed_document.get("assetAnalysisError", ""),
            )
    except Exception as exc:  # pragma: no cover - exact parser failures vary by dependency
        logger.exception("Knowledge parse task failed: %s", task_id)
        update_parse_task(task_id, status="failed", completedAt=utc_now(), error=str(exc))


def list_knowledge_parse_tasks(status: str | None = None) -> dict[str, Any]:
    tasks = load_parse_tasks()
    if status:
        tasks = [task for task in tasks if str(task.get("status")) == status]
    tasks = sorted(tasks, key=lambda item: item.get("createdAt", ""), reverse=True)
    return {"items": [parse_task_response(task) for task in tasks], "total": len(tasks)}


def get_knowledge_parse_task(task_id: str) -> dict[str, Any]:
    for task in load_parse_tasks():
        if task.get("id") == task_id:
            return parse_task_response(task)
    raise HTTPException(status_code=404, detail="parse task not found")


def build_multimodal_chunks(document: dict[str, Any], analysis: dict[str, Any]) -> list[dict[str, Any]]:
    segments = [segment for segment in analysis.get("textSegments", []) if isinstance(segment, str) and segment.strip()]
    if not segments and analysis.get("summary"):
        segments = [str(analysis["summary"])]

    chunks: list[dict[str, Any]] = []
    keyword_context = " ".join(
        [
            " ".join(analysis.get("keyComponents", [])),
            " ".join(analysis.get("faultSymptoms", [])),
            " ".join(analysis.get("inspectionSteps", [])),
        ]
    )
    for segment in segments:
        for chunk_text in split_text(segment):
            chunk = build_chunk(
                document_id=document["id"],
                file_name=document.get("fileName") or document["id"],
                source_name=document.get("sourceName") or document.get("fileName") or document["id"],
                chunk_text=chunk_text,
                chunk_index=len(chunks) + 1,
                page=None,
                analysis_provider=analysis.get("provider", "mock"),
            )
            chunk["id"] = f"{document['id']}-mm-chunk-{len(chunks) + 1:03d}"
            chunk["chunk_id"] = chunk["id"]
            chunk["keywords"] = build_keywords(f"{chunk_text} {keyword_context}")
            chunk["knowledge_type"] = "image_analysis"
            chunk["origin"] = "document_multimodal_analysis"
            chunks.append(chunk)
    return chunks


def analyze_knowledge_document(document_id: str, provider: str | None = None) -> dict[str, Any]:
    documents = load_documents()
    document = next((item for item in documents if item["id"] == document_id), None)
    if document is None:
        raise HTTPException(status_code=404, detail="入库资料不存在")

    suffix = document.get("suffix", "")
    if asset_candidates_from_artifacts(document.get("parseArtifacts", {})):
        return analyze_document_assets(document_id, provider)
    if suffix not in MULTIMODAL_SUFFIXES:
        raise HTTPException(status_code=400, detail="该资料类型不需要多模态分析")

    stored_file = knowledge_dir() / "files" / f"{document_id}.{suffix}"
    if not stored_file.exists():
        raise HTTPException(status_code=404, detail="入库资料原始文件不存在")

    document["status"] = "analyzing"
    save_documents(documents)

    analysis = analyze_multimodal_document(
        file_path=stored_file,
        source_name=document.get("sourceName") or document.get("fileName") or document_id,
        suffix=suffix,
        requested_provider=provider,
    )
    chunks = build_multimodal_chunks(document, analysis)

    existing_chunks = [
        chunk
        for chunk in load_document_chunks()
        if not (chunk.get("documentId") == document_id and chunk.get("origin") == "document_multimodal_analysis")
    ]
    existing_chunks.extend(chunks)
    save_document_chunks(existing_chunks)

    document_chunks = [chunk for chunk in existing_chunks if chunk.get("documentId") == document_id]
    update_document_review_summary(document, document_chunks)
    document["parser"] = f"multimodal-{analysis.get('provider', 'mock')}"
    document["analysis"] = {
        "summary": analysis.get("summary", ""),
        "keyComponents": analysis.get("keyComponents", []),
        "faultSymptoms": analysis.get("faultSymptoms", []),
        "inspectionSteps": analysis.get("inspectionSteps", []),
        "safetyNotes": analysis.get("safetyNotes", []),
        "provider": analysis.get("provider", "mock"),
        "requestedProvider": analysis.get("requestedProvider", provider or "mock"),
        "fallback": analysis.get("fallback", False),
        "fallbackReason": analysis.get("fallbackReason", ""),
        "ocr": analysis.get("ocr", {}),
        "analyzedAt": utc_now(),
    }
    save_documents(documents)
    return {**document, "chunks": chunks[:3]}


def list_knowledge_documents() -> dict[str, Any]:
    documents = sorted(load_documents(), key=lambda item: item.get("uploadedAt", ""), reverse=True)
    return {"items": documents, "total": len(documents)}


def get_knowledge_document(document_id: str) -> dict[str, Any]:
    for document in load_documents():
        if document["id"] == document_id:
            chunks = [chunk for chunk in load_document_chunks() if chunk.get("documentId") == document_id]
            revisions = [item for item in load_knowledge_revisions() if item.get("documentId") == document_id]
            return {
                **document,
                "chunks": chunks[:10],
                "chunkTotal": len(chunks),
                "revisionCount": len(revisions),
                "latestRevision": revisions[-1] if revisions else None,
            }
    raise HTTPException(status_code=404, detail="入库资料不存在")


def list_knowledge_document_chunks(document_id: str) -> dict[str, Any]:
    documents = load_documents()
    if not any(document["id"] == document_id for document in documents):
        raise HTTPException(status_code=404, detail="入库资料不存在")
    chunks = [chunk for chunk in load_document_chunks() if chunk.get("documentId") == document_id]
    return {"items": chunks, "total": len(chunks)}


def list_knowledge_revisions(document_id: str) -> dict[str, Any]:
    documents = load_documents()
    if not any(document["id"] == document_id for document in documents):
        raise HTTPException(status_code=404, detail="knowledge document not found")
    revisions = [item for item in load_knowledge_revisions() if item.get("documentId") == document_id]
    revisions = sorted(revisions, key=lambda item: item.get("createdAt", ""), reverse=True)
    return {"items": revisions, "total": len(revisions)}


def update_document_review_summary(document: dict[str, Any], chunks: list[dict[str, Any]]) -> None:
    status_counts: dict[str, int] = {}
    for chunk in chunks:
        status = str(chunk.get("review_status", "approved"))
        status_counts[status] = status_counts.get(status, 0) + 1
    pending_count = status_counts.get("pending_review", 0)
    approved_count = status_counts.get("approved", 0)
    document["chunkCount"] = len(chunks)
    document["pendingReviewCount"] = pending_count
    if pending_count:
        document["status"] = "pending_review"
    elif approved_count:
        document["status"] = "indexed"
    elif chunks:
        for status in ("rejected", "deprecated", "replaced", "draft"):
            if status_counts.get(status, 0) == len(chunks):
                document["status"] = status
                break


def transition_knowledge_chunk_status(
    document_id: str,
    chunk_id: str,
    next_status: str,
    reason: str,
    reviewer: str,
    action: str,
    replacement_chunk_id: str | None = None,
) -> dict[str, Any]:
    reason = reason.strip()
    if next_status in {"rejected", "deprecated", "replaced"} and not reason:
        raise HTTPException(status_code=400, detail="拒绝、废弃或替换知识片段必须填写原因")
    if next_status == "replaced" and not (replacement_chunk_id or "").strip():
        raise HTTPException(status_code=400, detail="替换知识片段必须填写 replacementChunkId")

    documents = load_documents()
    document = next((item for item in documents if item.get("id") == document_id), None)
    if document is None:
        raise HTTPException(status_code=404, detail="knowledge document not found")

    chunks = load_document_chunks()
    chunk_index = next(
        (
            index
            for index, chunk in enumerate(chunks)
            if chunk.get("documentId") == document_id and chunk.get("id") == chunk_id
        ),
        None,
    )
    if chunk_index is None:
        raise HTTPException(status_code=404, detail="knowledge chunk not found")

    if next_status == "replaced" and not any(chunk.get("id") == replacement_chunk_id for chunk in chunks):
        raise HTTPException(status_code=404, detail="replacement knowledge chunk not found")

    previous = dict(chunks[chunk_index])
    review_time = utc_now()
    reviewer = reviewer.strip() or "operator"

    updated = dict(previous)
    updated["review_status"] = next_status
    updated["reviewer"] = reviewer
    updated["review_time"] = review_time
    updated["review_action"] = action
    updated["review_reason"] = reason
    updated["updated_at"] = review_time
    updated["updatedAt"] = review_time
    if next_status == "replaced":
        updated["replaced_by"] = replacement_chunk_id
    else:
        updated.pop("replaced_by", None)
    chunks[chunk_index] = updated
    save_document_chunks(chunks)

    document_chunks = [chunk for chunk in chunks if chunk.get("documentId") == document_id]
    update_document_review_summary(document, document_chunks)
    document["reviewer"] = reviewer
    document["review_time"] = review_time
    document["review_action"] = action
    save_documents(documents)

    delete_vector_document(document_id)
    sync_chunks(document_chunks)

    event = {
        "id": f"review-{uuid4().hex[:8]}",
        "objectType": "knowledge_chunk",
        "objectId": chunk_id,
        "documentId": document_id,
        "chunkId": chunk_id,
        "action": action,
        "beforeStatus": previous.get("review_status", "pending_review"),
        "afterStatus": next_status,
        "reason": reason,
        "reviewer": reviewer,
        "reviewTime": review_time,
        "before": previous,
        "after": updated,
    }
    if replacement_chunk_id:
        event["replacementChunkId"] = replacement_chunk_id
    events = load_review_events()
    events.append(event)
    save_review_events(events)

    return {"document": document, "chunk": updated, "reviewEvent": event}


def set_knowledge_chunk_status(
    document_id: str,
    chunk_id: str,
    request: KnowledgeChunkStatusRequest,
) -> dict[str, Any]:
    return transition_knowledge_chunk_status(
        document_id=document_id,
        chunk_id=chunk_id,
        next_status=request.status,
        reason=request.reason,
        reviewer=request.reviewer,
        action=f"set_{request.status}",
        replacement_chunk_id=request.replacementChunkId,
    )


def review_knowledge_chunk(
    document_id: str,
    chunk_id: str,
    request: KnowledgeChunkReviewRequest,
) -> dict[str, Any]:
    next_status = "approved" if request.action == "approve" else "rejected"
    return transition_knowledge_chunk_status(
        document_id=document_id,
        chunk_id=chunk_id,
        next_status=next_status,
        reason=request.reason,
        reviewer=request.reviewer,
        action=request.action,
    )


def revise_knowledge_chunk(document_id: str, request: KnowledgeChunkRevisionRequest) -> dict[str, Any]:
    documents = load_documents()
    document = next((item for item in documents if item.get("id") == document_id), None)
    if document is None:
        raise HTTPException(status_code=404, detail="knowledge document not found")

    content = request.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="revision content cannot be empty")

    chunks = load_document_chunks()
    chunk_index = next(
        (
            index
            for index, chunk in enumerate(chunks)
            if chunk.get("documentId") == document_id and chunk.get("id") == request.chunkId
        ),
        None,
    )
    if chunk_index is None:
        raise HTTPException(status_code=404, detail="knowledge chunk not found")

    previous = dict(chunks[chunk_index])
    updated = dict(previous)
    updated["content"] = content
    updated["snippet"] = content[:160]
    updated["keywords"] = build_keywords(" ".join([content, " ".join(request.tags)]))
    updated["manuallyCorrected"] = True
    updated["updatedAt"] = utc_now()
    updated["revisionTags"] = request.tags
    if request.title is not None and request.title.strip():
        updated["title"] = request.title.strip()
    if request.sourceName is not None and request.sourceName.strip():
        updated["sourceName"] = request.sourceName.strip()
    if request.page is not None:
        updated["page"] = request.page

    revision = {
        "id": f"krev-{uuid4().hex[:8]}",
        "documentId": document_id,
        "chunkId": request.chunkId,
        "source": "manual-correction",
        "status": "applied",
        "reason": request.reason.strip(),
        "reviewer": request.reviewer.strip() or "operator",
        "createdAt": utc_now(),
        "before": {
            "title": previous.get("title", ""),
            "sourceName": previous.get("sourceName", ""),
            "page": previous.get("page"),
            "content": previous.get("content", ""),
            "keywords": previous.get("keywords", []),
        },
        "after": {
            "title": updated.get("title", ""),
            "sourceName": updated.get("sourceName", ""),
            "page": updated.get("page"),
            "content": updated.get("content", ""),
            "keywords": updated.get("keywords", []),
            "tags": request.tags,
        },
    }

    chunks[chunk_index] = updated
    save_document_chunks(chunks)

    document_chunks = [chunk for chunk in chunks if chunk.get("documentId") == document_id]
    delete_vector_document(document_id)
    sync_chunks(document_chunks)

    revisions = load_knowledge_revisions()
    revisions.append(revision)
    save_knowledge_revisions(revisions)

    events = load_review_events()
    events.append(
        {
            "id": f"review-{uuid4().hex[:8]}",
            "objectType": "knowledge_revision",
            "objectId": revision["id"],
            "documentId": document_id,
            "chunkId": request.chunkId,
            "revisionId": revision["id"],
            "action": "revise",
            "beforeStatus": previous.get("review_status", "pending_review"),
            "afterStatus": updated.get("review_status", "pending_review"),
            "reason": revision["reason"],
            "reviewer": revision["reviewer"],
            "reviewTime": revision["createdAt"],
            "before": revision["before"],
            "after": revision["after"],
        }
    )
    save_review_events(events)

    document["revisionCount"] = int(document.get("revisionCount") or 0) + 1
    document["latestRevisionAt"] = revision["createdAt"]
    if document.get("status") not in {"analyzed", "needs_multimodal_analysis"}:
        document["status"] = "indexed"
    save_documents(documents)

    return {"document": document, "chunk": updated, "revision": revision}


def delete_knowledge_document(document_id: str) -> dict[str, Any]:
    documents = load_documents()
    document = next((item for item in documents if item["id"] == document_id), None)
    if document is None:
        raise HTTPException(status_code=404, detail="入库资料不存在")

    remaining_documents = [item for item in documents if item["id"] != document_id]
    remaining_chunks = [chunk for chunk in load_document_chunks() if chunk.get("documentId") != document_id]
    save_documents(remaining_documents)
    save_document_chunks(remaining_chunks)
    delete_vector_document(document_id)

    suffix = document.get("suffix", "")
    if suffix:
        stored_file = knowledge_dir() / "files" / f"{document_id}.{suffix}"
        if stored_file.exists():
            stored_file.unlink()

    return {"id": document_id, "deleted": True}
