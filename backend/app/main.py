from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .data_store import PROJECT_ROOT, load_seed_data


UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"
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


class ApiResponse(BaseModel):
    success: bool = True
    data: Any = None
    message: str = ""


class SearchRequest(BaseModel):
    deviceModel: str = ""
    faultText: str = ""
    inputType: str = "text"
    topK: int = Field(default=5, ge=1, le=20)


class DiagnosisRequest(BaseModel):
    deviceModel: str = ""
    faultText: str = ""
    evidenceIds: list[str] = Field(default_factory=list)


class CaseCreateRequest(BaseModel):
    deviceModel: str
    faultText: str
    cause: str
    solution: str
    result: str
    tags: list[str] = Field(default_factory=list)


class CaseReviewRequest(BaseModel):
    action: str
    reviewNote: str = ""
    normalizedTags: list[str] = Field(default_factory=list)


def _tokens(*parts: str) -> list[str]:
    text = " ".join(part for part in parts if part).lower()
    separators = ["，", "。", "、", ",", ".", " ", "-", "_", "\n"]
    for separator in separators:
        text = text.replace(separator, " ")
    return [item for item in text.split(" ") if item]


def _score_item(query_tokens: list[str], item: dict[str, Any], fields: list[str]) -> int:
    haystack = " ".join(str(item.get(field, "")) for field in fields).lower()
    if not query_tokens:
        return 0
    return sum(1 for token in query_tokens if token in haystack)


def _find_workflow(workflow_id: str) -> dict[str, Any]:
    data = load_seed_data()
    for workflow in data["workflows"]:
        if workflow["id"] == workflow_id:
            return workflow
    raise HTTPException(status_code=404, detail="作业流程不存在")


@app.get("/api/health", response_model=ApiResponse)
def health() -> ApiResponse:
    return ApiResponse(data={"status": "ok", "version": app.version})


@app.post("/api/search", response_model=ApiResponse)
def search(request: SearchRequest) -> ApiResponse:
    data = load_seed_data()
    query_tokens = _tokens(request.deviceModel, request.faultText)

    manual_results = []
    for manual in data["manuals"]:
        score = _score_item(query_tokens, manual, ["title", "deviceModel", "content", "tags"])
        if score:
            manual_results.append(
                {
                    "id": manual["id"],
                    "title": manual["title"],
                    "sourceType": "manual",
                    "sourceName": manual["sourceName"],
                    "confidence": min(0.95, 0.58 + score * 0.09),
                    "snippet": manual["content"][:120],
                    "workflowId": manual.get("workflowId"),
                    "chapter": manual.get("chapter"),
                    "page": manual.get("page"),
                }
            )

    case_results = []
    for repair_case in data["cases"]:
        if repair_case.get("status") != "approved":
            continue
        score = _score_item(
            query_tokens,
            repair_case,
            ["faultTitle", "faultText", "solution", "possibleCauses", "tags"],
        )
        if score:
            case_results.append(
                {
                    "id": repair_case["id"],
                    "title": repair_case["faultTitle"],
                    "sourceType": "case",
                    "sourceName": "历史维修案例库",
                    "confidence": min(0.9, 0.52 + score * 0.08),
                    "snippet": repair_case["solution"],
                    "workflowId": repair_case.get("workflowId"),
                }
            )

    results = sorted(
        manual_results + case_results,
        key=lambda item: item["confidence"],
        reverse=True,
    )[: request.topK]

    return ApiResponse(
        data={
            "queryId": f"q-{uuid4().hex[:8]}",
            "summary": "可能与燃油供给、点火系统、进气密封或机械磨损有关。",
            "results": results,
        }
    )


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
    return ApiResponse(data=_find_workflow(workflow_id))


@app.post("/api/cases", response_model=ApiResponse)
def create_case(request: CaseCreateRequest) -> ApiResponse:
    return ApiResponse(
        data={"id": f"case-{uuid4().hex[:8]}", "status": "pending_review"},
        message="案例已提交，等待审核",
    )


@app.get("/api/cases", response_model=ApiResponse)
def list_cases(status: str | None = None) -> ApiResponse:
    cases = load_seed_data()["cases"]
    items = [item for item in cases if status is None or item.get("status") == status]
    return ApiResponse(data={"items": items, "total": len(items)})


@app.patch("/api/cases/{case_id}/review", response_model=ApiResponse)
def review_case(case_id: str, request: CaseReviewRequest) -> ApiResponse:
    status = "approved" if request.action == "approve" else "rejected"
    return ApiResponse(data={"id": case_id, "status": status}, message="审核完成")


@app.post("/api/uploads", response_model=ApiResponse)
async def upload_file(file: UploadFile = File(...)) -> ApiResponse:
    suffix = Path(file.filename or "").suffix
    file_id = f"file-{uuid4().hex[:8]}"
    target = UPLOAD_DIR / f"{file_id}{suffix}"
    target.write_bytes(await file.read())
    return ApiResponse(
        data={
            "id": file_id,
            "fileName": file.filename,
            "fileType": file.content_type,
            "url": f"/uploads/{target.name}",
        }
    )
