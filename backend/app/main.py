from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .data_store import PROJECT_ROOT, upload_dir
from .schemas import ApiResponse, CaseCreateRequest, CaseReviewRequest, DiagnosisRequest, SearchRequest
from .services import create_repair_case, find_workflow, list_repair_cases, review_repair_case, search_knowledge


UPLOAD_DIR = upload_dir()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="设备检修知识检索与作业辅助系统", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


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
    suffix = Path(file.filename or "").suffix
    file_id = f"file-{uuid4().hex[:8]}"
    target_dir = upload_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{file_id}{suffix}"
    target.write_bytes(await file.read())
    return ApiResponse(
        data={
            "id": file_id,
            "fileName": file.filename,
            "fileType": file.content_type,
            "url": f"/uploads/{target.name}",
        }
    )
