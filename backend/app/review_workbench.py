from __future__ import annotations

from typing import Any

from .data_store import load_cases, load_document_chunks, load_documents


def case_review_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"case:{item.get('id', '')}",
        "objectType": "case",
        "objectId": item.get("id", ""),
        "status": item.get("status", "pending_review"),
        "title": item.get("faultTitle") or item.get("faultText", "")[:24] or item.get("id", ""),
        "sourceName": "维修案例",
        "deviceModel": item.get("deviceModel", ""),
        "content": item.get("faultText", ""),
        "summary": item.get("solution", ""),
        "createdAt": item.get("createdAt", ""),
        "reviewer": item.get("reviewer", ""),
        "reviewTime": item.get("reviewedAt", ""),
        "tags": item.get("tags", []),
        "caseId": item.get("id", ""),
    }


def chunk_review_item(chunk: dict[str, Any], document: dict[str, Any] | None) -> dict[str, Any]:
    document = document or {}
    return {
        "id": f"knowledge_chunk:{chunk.get('id', '')}",
        "objectType": "knowledge_chunk",
        "objectId": chunk.get("id", ""),
        "status": chunk.get("review_status", "pending_review"),
        "title": chunk.get("title") or document.get("sourceName") or chunk.get("id", ""),
        "sourceName": chunk.get("sourceName") or document.get("sourceName", ""),
        "deviceModel": chunk.get("device_model", ""),
        "content": chunk.get("content") or chunk.get("snippet", ""),
        "summary": chunk.get("snippet", ""),
        "createdAt": chunk.get("created_at") or document.get("uploadedAt", ""),
        "reviewer": chunk.get("reviewer", ""),
        "reviewTime": chunk.get("review_time", ""),
        "tags": chunk.get("keywords", []),
        "documentId": chunk.get("documentId", ""),
        "chunkId": chunk.get("id", ""),
        "fileName": document.get("fileName", ""),
        "page": chunk.get("page"),
        "section": chunk.get("section", ""),
    }


def list_review_items(status: str = "pending_review", item_type: str = "all") -> dict[str, Any]:
    documents = {document.get("id"): document for document in load_documents()}
    items: list[dict[str, Any]] = []

    if item_type in {"all", "case"}:
        for repair_case in load_cases():
            if status == "all" or repair_case.get("status") == status:
                items.append(case_review_item(repair_case))

    if item_type in {"all", "knowledge_chunk"}:
        for chunk in load_document_chunks():
            if status == "all" or chunk.get("review_status", "approved") == status:
                items.append(chunk_review_item(chunk, documents.get(chunk.get("documentId"))))

    items.sort(key=lambda item: item.get("createdAt", ""), reverse=True)
    return {"items": items, "total": len(items)}
