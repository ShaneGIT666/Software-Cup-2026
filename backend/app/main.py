from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .data_store import PROJECT_ROOT, knowledge_dir, upload_dir
from .knowledge import (
    delete_knowledge_document,
    get_knowledge_document,
    ingest_knowledge_document,
    list_knowledge_document_chunks,
    list_knowledge_documents,
)
from .schemas import ApiResponse, CaseCreateRequest, CaseReviewRequest, DiagnosisRequest, SearchRequest
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
    return JSONResponse(
        status_code=status_code,
        content=ApiResponse(success=False, data=None, message=message).model_dump(),
    )


def validation_message(errors: list[dict[str, Any]]) -> str:
    if not errors:
        return "请求参数校验失败"
    first_error = errors[0]
    location = ".".join(str(item) for item in first_error.get("loc", []) if item != "body")
    message = first_error.get("msg", "请求参数校验失败")
    return f"{location}: {message}" if location else message


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


@app.post("/api/search", response_model=ApiResponse)
def search(request: SearchRequest) -> ApiResponse:
    return ApiResponse(data=search_knowledge(request))


@app.post("/api/diagnosis", response_model=ApiResponse)
def diagnosis(request: DiagnosisRequest) -> ApiResponse:
    return ApiResponse(
        data={
            "possibleCauses": ["燃油供给不足", "火花塞积碳", "进气系统漏气"],
            "recommendedActions": ["检查燃油滤清器", "检查火花塞间隙和积碳", "检查进气管路密封"],
            "safetyNotes": ["作业前确认设备停止运行", "佩戴防护手套和护目镜", "保持维修区域通风"],
            "fallback": True,
        },
        message="当前为模拟诊断结果",
    )


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
        raise HTTPException(status_code=400, detail="仅支持 jpg、jpeg、png、webp 和 pdf 文件")

    content_type = (file.content_type or "").split(";", 1)[0].lower()
    if content_type not in ALLOWED_UPLOAD_TYPES[suffix]:
        raise HTTPException(status_code=400, detail="文件扩展名与 MIME 类型不匹配")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传文件不能为空")
    if len(content) > MAX_UPLOAD_BYTES:
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


@app.delete("/api/knowledge/documents/{document_id}", response_model=ApiResponse)
def remove_knowledge_document(document_id: str) -> ApiResponse:
    return ApiResponse(data=delete_knowledge_document(document_id), message="资料已删除")
