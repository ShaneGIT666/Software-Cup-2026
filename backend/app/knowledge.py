from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from .data_store import (
    knowledge_dir,
    load_document_chunks,
    load_documents,
    save_document_chunks,
    save_documents,
)
from .multimodal_adapter import analyze_multimodal_document
from .vector_store import delete_document as delete_vector_document
from .vector_store import sync_chunks


MAX_KNOWLEDGE_DOCUMENT_BYTES = 20 * 1024 * 1024
ALLOWED_KNOWLEDGE_TYPES = {
    "pdf": {"application/pdf"},
    "txt": {"text/plain", "application/octet-stream"},
    "md": {"text/markdown", "text/plain", "application/octet-stream"},
    "jpg": {"image/jpeg"},
    "jpeg": {"image/jpeg"},
    "png": {"image/png"},
    "webp": {"image/webp"},
}
MULTIMODAL_SUFFIXES = {"pdf", "jpg", "jpeg", "png", "webp"}
IMAGE_SUFFIXES = {"jpg", "jpeg", "png", "webp"}
CHUNK_SIZE = 700
CHUNK_OVERLAP = 120


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def validate_knowledge_file(file: UploadFile, content: bytes) -> str:
    suffix = Path(file.filename or "").suffix.lower().lstrip(".")
    if not suffix or suffix not in ALLOWED_KNOWLEDGE_TYPES:
        raise HTTPException(status_code=400, detail="资料入库仅支持 pdf、txt、md、jpg、jpeg、png 和 webp 文件")
    if not content:
        raise HTTPException(status_code=400, detail="资料文件不能为空")
    if len(content) > MAX_KNOWLEDGE_DOCUMENT_BYTES:
        raise HTTPException(status_code=400, detail="资料文件不能超过 20MB")

    content_type = (file.content_type or "").split(";", 1)[0].lower()
    if content_type and content_type not in ALLOWED_KNOWLEDGE_TYPES[suffix]:
        raise HTTPException(status_code=400, detail="资料文件扩展名与 MIME 类型不匹配")
    return suffix


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
) -> dict[str, Any]:
    chunk = {
        "id": f"{document_id}-chunk-{chunk_index:03d}",
        "documentId": document_id,
        "title": Path(file_name or document_id).stem,
        "sourceType": "document",
        "sourceName": source_name or file_name or document_id,
        "page": page,
        "chunkIndex": chunk_index,
        "content": chunk_text,
        "snippet": chunk_text[:160],
        "keywords": build_keywords(chunk_text),
    }
    if analysis_provider:
        chunk["analysisProvider"] = analysis_provider
    return chunk


async def ingest_knowledge_document(file: UploadFile, source_name: str | None = None) -> dict[str, Any]:
    content = await file.read()
    suffix = validate_knowledge_file(file, content)
    document_id = f"kdoc-{uuid4().hex[:8]}"
    file_name = file.filename or f"{document_id}.{suffix}"
    display_source = source_name or file_name or document_id
    target_dir = knowledge_dir() / "files"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{document_id}.{suffix}"
    target.write_bytes(content)

    pages, status, parser = extract_pages(content, suffix)
    chunks: list[dict[str, Any]] = []
    for page in pages:
        for chunk_text in split_text(page["text"]):
            chunks.append(
                build_chunk(
                    document_id=document_id,
                    file_name=file_name,
                    source_name=display_source,
                    chunk_text=chunk_text,
                    chunk_index=len(chunks) + 1,
                    page=page["page"],
                )
            )

    document = {
        "id": document_id,
        "fileName": file_name,
        "fileType": file.content_type or "",
        "suffix": suffix,
        "sourceName": display_source,
        "status": "indexed" if chunks else status,
        "chunkCount": len(chunks),
        "parser": parser,
        "uploadedAt": utc_now(),
        "url": f"/knowledge/files/{target.name}",
    }

    documents = load_documents()
    documents.append(document)
    save_documents(documents)

    existing_chunks = load_document_chunks()
    existing_chunks.extend(chunks)
    save_document_chunks(existing_chunks)
    sync_chunks(chunks)

    return {**document, "chunks": chunks[:3]}


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
            chunk["keywords"] = build_keywords(f"{chunk_text} {keyword_context}")
            chunks.append(chunk)
    return chunks


def analyze_knowledge_document(document_id: str, provider: str | None = None) -> dict[str, Any]:
    documents = load_documents()
    document = next((item for item in documents if item["id"] == document_id), None)
    if document is None:
        raise HTTPException(status_code=404, detail="入库资料不存在")

    suffix = document.get("suffix", "")
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

    existing_chunks = [chunk for chunk in load_document_chunks() if chunk.get("documentId") != document_id]
    existing_chunks.extend(chunks)
    save_document_chunks(existing_chunks)
    sync_chunks(chunks)

    document["status"] = "analyzed" if chunks else "needs_multimodal_analysis"
    document["chunkCount"] = len(chunks)
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
            return {**document, "chunks": chunks[:10], "chunkTotal": len(chunks)}
    raise HTTPException(status_code=404, detail="入库资料不存在")


def list_knowledge_document_chunks(document_id: str) -> dict[str, Any]:
    documents = load_documents()
    if not any(document["id"] == document_id for document in documents):
        raise HTTPException(status_code=404, detail="入库资料不存在")
    chunks = [chunk for chunk in load_document_chunks() if chunk.get("documentId") == document_id]
    return {"items": chunks, "total": len(chunks)}


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
