from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .data_store import PROJECT_ROOT, knowledge_dir, upload_dir
from .knowledge import (
    analyze_knowledge_document,
    delete_knowledge_document,
    get_knowledge_document,
    ingest_knowledge_document,
    list_knowledge_document_chunks,
    list_knowledge_documents,
    list_knowledge_revisions,
    revise_knowledge_chunk,
)
from .knowledge_graph import build_global_knowledge_graph, build_knowledge_graph, knowledge_graph_overview
from .provider_policy import provider_status
from .rag import answer_with_rag, diagnose_with_rag, validate_llm_provider
from .multimodal_adapter import validate_multimodal_provider
from .schemas import (
    ApiResponse,
    CaseCreateRequest,
    CaseReviewRequest,
    DiagnosisRequest,
    KnowledgeChunkRevisionRequest,
    LlmValidateRequest,
    MultimodalAnalyzeRequest,
    MultimodalValidateRequest,
    RagAnswerRequest,
    SearchRequest,
)
from .services import create_repair_case, find_workflow, list_repair_cases, review_repair_case, search_knowledge


UPLOAD_DIR = upload_dir()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
KNOWLEDGE_DIR = knowledge_dir()
KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_UPLOAD_TYPES = {
    "jpg": {"image/jpeg"},
    "jpeg": {"image/jpeg"},
    "png": {"image/png"},
    "webp": {"image/webp"},
    "pdf": {"application/pdf"},
}
logger = logging.getLogger(__name__)

app = FastAPI(title="设备检修知识检索与作业辅助系统", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/knowledge", StaticFiles(directory=KNOWLEDGE_DIR), name="knowledge")


def error_response(status_code: int, message: str) -> JSONResponse:
    payload = ApiResponse(success=False, data=None, message=message)
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump() if hasattr(payload, "model_dump") else payload.dict(),
    )


def validation_message(errors: list[dict[str, Any]]) -> str:
    if not errors:
        return "请求参数校验失败"
    first_error = errors[0]
    location = ".".join(str(item) for item in first_error.get("loc", []) if item != "body")
    message = first_error.get("msg", "请求参数校验失败")
    return f"{location}: {message}" if location else message


def serve_frontend_enabled() -> bool:
    return os.getenv("SERVE_FRONTEND", "auto").strip().lower() != "off"


def frontend_dist_dir() -> Path:
    configured = os.getenv("FRONTEND_DIST_DIR")
    if not configured:
        return PROJECT_ROOT / "frontend" / "dist"

    configured_path = Path(configured)
    if configured_path.is_absolute():
        return configured_path

    root_candidate = PROJECT_ROOT / configured_path
    backend_candidate = PROJECT_ROOT / "backend" / configured_path
    return backend_candidate if backend_candidate.exists() else root_candidate


def spa_index_path() -> Path:
    return frontend_dist_dir() / "index.html"


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Any, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) else "请求处理失败"
    return error_response(exc.status_code, detail)


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(_: Any, exc: RequestValidationError) -> JSONResponse:
    return error_response(422, validation_message(exc.errors()))


@app.get("/api/health", response_model=ApiResponse)
def health() -> ApiResponse:
    return ApiResponse(data={"status": "ok", "version": app.version})


@app.get("/api/providers/status", response_model=ApiResponse)
def get_provider_status() -> ApiResponse:
    return ApiResponse(data=provider_status())


@app.post("/api/providers/llm/validate", response_model=ApiResponse)
def validate_llm(request: LlmValidateRequest) -> ApiResponse:
    return ApiResponse(data=validate_llm_provider(request))


@app.post("/api/providers/multimodal/validate", response_model=ApiResponse)
def validate_multimodal(request: MultimodalValidateRequest) -> ApiResponse:
    return ApiResponse(data=validate_multimodal_provider(request))


@app.post("/api/search", response_model=ApiResponse)
def search(request: SearchRequest) -> ApiResponse:
    return ApiResponse(data=search_knowledge(request))


@app.post("/api/diagnosis", response_model=ApiResponse)
def diagnosis(request: DiagnosisRequest) -> ApiResponse:
    return ApiResponse(data=diagnose_with_rag(request), message="诊断建议已生成")


@app.post("/api/rag/answer", response_model=ApiResponse)
def rag_answer(request: RagAnswerRequest) -> ApiResponse:
    return ApiResponse(data=answer_with_rag(request), message="当前为 Mock RAG 回答")


@app.post("/api/knowledge/graph", response_model=ApiResponse)
def knowledge_graph(request: SearchRequest) -> ApiResponse:
    return ApiResponse(data=build_knowledge_graph(request))


@app.get("/api/knowledge/graph", response_model=ApiResponse)
def knowledge_graph_global() -> ApiResponse:
    return ApiResponse(data=knowledge_graph_overview())


@app.post("/api/knowledge/graph/rebuild", response_model=ApiResponse)
def rebuild_knowledge_graph() -> ApiResponse:
    return ApiResponse(data=build_global_knowledge_graph(), message="知识图谱已重建")


@app.get("/api/workflows/{workflow_id}", response_model=ApiResponse)
def get_workflow(workflow_id: str) -> ApiResponse:
    return ApiResponse(data=find_workflow(workflow_id))


@app.post("/api/cases", response_model=ApiResponse)
def create_case(request: CaseCreateRequest) -> ApiResponse:
    return ApiResponse(
        data=create_repair_case(request),
        message="案例已提交，等待审核",
    )


@app.get("/api/cases", response_model=ApiResponse)
def list_cases(status: str | None = None) -> ApiResponse:
    return ApiResponse(data=list_repair_cases(status))


@app.patch("/api/cases/{case_id}/review", response_model=ApiResponse)
def review_case(case_id: str, request: CaseReviewRequest) -> ApiResponse:
    return ApiResponse(data=review_repair_case(case_id, request), message="审核完成")


@app.post("/api/uploads", response_model=ApiResponse)
async def upload_file(file: UploadFile = File(...)) -> ApiResponse:
    suffix = Path(file.filename or "").suffix.lower().lstrip(".")
    if not suffix or suffix not in ALLOWED_UPLOAD_TYPES:
        logger.warning("Rejected upload with unsupported extension: %s", file.filename)
        raise HTTPException(status_code=400, detail="仅支持 jpg、jpeg、png、webp 和 pdf 文件")

    content_type = (file.content_type or "").split(";", 1)[0].lower()
    if content_type not in ALLOWED_UPLOAD_TYPES[suffix]:
        logger.warning(
            "Rejected upload with MIME mismatch: filename=%s suffix=%s content_type=%s",
            file.filename,
            suffix,
            content_type,
        )
        raise HTTPException(status_code=400, detail="文件扩展名与 MIME 类型不匹配")

    content = await file.read()
    if not content:
        logger.warning("Rejected empty upload: %s", file.filename)
        raise HTTPException(status_code=400, detail="上传文件不能为空")
    if len(content) > MAX_UPLOAD_BYTES:
        logger.warning("Rejected oversized upload: %s bytes=%s", file.filename, len(content))
        raise HTTPException(status_code=400, detail="上传文件不能超过 10MB")

    file_id = f"file-{uuid4().hex[:8]}"
    target_dir = upload_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{file_id}.{suffix}"
    target.write_bytes(content)
    return ApiResponse(
        data={
            "id": file_id,
            "fileName": file.filename,
            "fileType": file.content_type,
            "url": f"/uploads/{target.name}",
        }
    )


@app.post("/api/knowledge/documents", response_model=ApiResponse)
async def upload_knowledge_document(
    file: UploadFile = File(...),
    source_name: str | None = Form(default=None),
) -> ApiResponse:
    return ApiResponse(
        data=await ingest_knowledge_document(file, source_name),
        message="资料已入库",
    )


@app.get("/api/knowledge/documents", response_model=ApiResponse)
def get_knowledge_documents() -> ApiResponse:
    return ApiResponse(data=list_knowledge_documents())


@app.get("/api/knowledge/documents/{document_id}", response_model=ApiResponse)
def get_knowledge_document_detail(document_id: str) -> ApiResponse:
    return ApiResponse(data=get_knowledge_document(document_id))


@app.get("/api/knowledge/documents/{document_id}/chunks", response_model=ApiResponse)
def get_knowledge_document_chunks(document_id: str) -> ApiResponse:
    return ApiResponse(data=list_knowledge_document_chunks(document_id))


@app.get("/api/knowledge/documents/{document_id}/revisions", response_model=ApiResponse)
def get_knowledge_document_revisions(document_id: str) -> ApiResponse:
    return ApiResponse(data=list_knowledge_revisions(document_id))


@app.patch("/api/knowledge/documents/{document_id}/chunks/{chunk_id}", response_model=ApiResponse)
def revise_document_chunk(document_id: str, chunk_id: str, request: KnowledgeChunkRevisionRequest) -> ApiResponse:
    request.chunkId = chunk_id
    return ApiResponse(data=revise_knowledge_chunk(document_id, request), message="知识片段修正已保存")


@app.post("/api/knowledge/documents/{document_id}/analyze", response_model=ApiResponse)
def analyze_document(document_id: str, request: MultimodalAnalyzeRequest | None = None) -> ApiResponse:
    provider = request.provider if request else None
    return ApiResponse(data=analyze_knowledge_document(document_id, provider), message="资料多模态分析完成")


@app.get("/assets/{asset_path:path}", include_in_schema=False)
def frontend_asset(asset_path: str) -> FileResponse:
    asset = frontend_dist_dir() / "assets" / asset_path
    if not serve_frontend_enabled() or not asset.exists() or not asset.is_file():
        raise HTTPException(status_code=404, detail="frontend asset not found")
    return FileResponse(asset)


@app.get("/{full_path:path}", include_in_schema=False)
def frontend_spa(full_path: str) -> HTMLResponse:
    if full_path.startswith(("api", "uploads", "knowledge")):
        raise HTTPException(status_code=404, detail="resource not found")
    index = spa_index_path()
    if not serve_frontend_enabled() or not index.exists():
        raise HTTPException(status_code=404, detail="frontend dist not found")
    return HTMLResponse(index.read_text(encoding="utf-8"))


@app.delete("/api/knowledge/documents/{document_id}", response_model=ApiResponse)
def remove_knowledge_document(document_id: str) -> ApiResponse:
    return ApiResponse(data=delete_knowledge_document(document_id), message="资料已删除")
