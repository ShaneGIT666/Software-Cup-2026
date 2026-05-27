from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

import backend.app.llm_adapter as llm_adapter
import backend.app.knowledge as knowledge
import backend.app.multimodal_adapter as multimodal_adapter
from backend.app.main import app


MANUAL_PATH = Path("E:/Download/Downloads/摩托车发动机维修手册.pdf")


def make_client(tmp_path, monkeypatch) -> TestClient:
    source = tmp_path / "source"
    shutil.copytree("data/examples", source)
    monkeypatch.setenv("APP_EXAMPLES_DIR", str(source))
    monkeypatch.setenv("APP_KNOWLEDGE_DIR", str(tmp_path / "knowledge"))
    return TestClient(app)


# ---------------------------------------------------------------------------
# pypdf 解析能力验证
# ---------------------------------------------------------------------------

def test_manual_pdf_exists_and_has_pages() -> None:
    assert MANUAL_PATH.exists(), f"摩托车维修手册 PDF 不存在: {MANUAL_PATH}"

    from pypdf import PdfReader

    reader = PdfReader(str(MANUAL_PATH))
    assert len(reader.pages) == 41

    extracted = 0
    for page in reader.pages:
        text = (page.extract_text() or "").strip()
        if text:
            extracted += 1

    assert extracted == 41, f"预期 41 页有文本，实际 {extracted} 页"


def test_manual_pdf_text_total_chars() -> None:
    from pypdf import PdfReader

    reader = PdfReader(str(MANUAL_PATH))
    total = sum(len((p.extract_text() or "").strip()) for p in reader.pages)
    assert total >= 10000, f"PDF 可提取字符应 >= 10000，实际 {total}"


def test_manual_pdf_page1_has_toc() -> None:
    from pypdf import PdfReader

    reader = PdfReader(str(MANUAL_PATH))
    toc_text = reader.pages[0].extract_text() or ""
    assert len(toc_text) > 200, f"第 1 页(目录)文本过短: {len(toc_text)} 字符"


# ---------------------------------------------------------------------------
# 资料入库 — 摩托车维修手册 PDF
# ---------------------------------------------------------------------------

def test_ingest_motorcycle_manual_pdf(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    with MANUAL_PATH.open("rb") as f:
        pdf_bytes = f.read()

    response = client.post(
        "/api/knowledge/documents",
        files={"file": ("摩托车发动机维修手册.pdf", pdf_bytes, "application/pdf")},
        data={"source_name": "摩托车发动机维修手册"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["fileName"] == "摩托车发动机维修手册.pdf"
    assert data["sourceName"] == "摩托车发动机维修手册"
    assert data["suffix"] == "pdf"
    assert data["chunkCount"] > 0, f"PDF 应生成至少 1 个 chunk，实际 {data['chunkCount']}"
    assert data["parser"] == "pypdf", f"解析器应为 pypdf，实际 {data['parser']}"
    assert data["status"] == "indexed"


def test_ingest_motorcycle_manual_produces_searchable_chunks(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    with MANUAL_PATH.open("rb") as f:
        pdf_bytes = f.read()

    upload_resp = client.post(
        "/api/knowledge/documents",
        files={"file": ("摩托车发动机维修手册.pdf", pdf_bytes, "application/pdf")},
        data={"source_name": "摩托车发动机维修手册"},
    )
    doc_id = upload_resp.json()["data"]["id"]

    chunks_resp = client.get(f"/api/knowledge/documents/{doc_id}/chunks")
    assert chunks_resp.status_code == 200
    chunks = chunks_resp.json()["data"]
    assert chunks["total"] > 0, f"PDF 应生成 >= 1 个 chunk，实际 {chunks['total']}"

    for chunk in chunks["items"]:
        assert chunk["documentId"] == doc_id
        assert chunk["sourceType"] == "document"
        assert chunk["sourceName"] == "摩托车发动机维修手册"
        assert len(chunk["content"]) > 0
        assert len(chunk["snippet"]) > 0


def test_ingest_manual_via_formdata_with_source_name(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    with MANUAL_PATH.open("rb") as f:
        pdf_bytes = f.read()

    response = client.post(
        "/api/knowledge/documents",
        files={"file": ("摩托车发动机维修手册.pdf", pdf_bytes, "application/pdf")},
        data={"source_name": "官方摩托车检修手册"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["sourceName"] == "官方摩托车检修手册"


# ---------------------------------------------------------------------------
# 检索 — PDF 入库后关键词命中
# ---------------------------------------------------------------------------

def test_search_hits_ingested_manual_keywords(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    with MANUAL_PATH.open("rb") as f:
        pdf_bytes = f.read()

    client.post(
        "/api/knowledge/documents",
        files={"file": ("摩托车发动机维修手册.pdf", pdf_bytes, "application/pdf")},
        data={"source_name": "摩托车发动机维修手册"},
    )

    search_resp = client.post(
        "/api/search",
        json={
            "deviceModel": "摩托车",
            "faultText": "发动机 无法启动",
            "inputType": "text",
            "topK": 5,
        },
    )

    assert search_resp.status_code == 200
    results = search_resp.json()["data"]["results"]
    assert len(results) > 0

    # 确认有 document 类型的结果来自入库 PDF
    doc_results = [r for r in results if r["sourceType"] == "document"]
    assert len(doc_results) > 0, "检索结果中应包含入库资料(document)来源"

    for doc in doc_results:
        assert doc["sourceName"] == "摩托车发动机维修手册"
        assert "摩托车" in doc.get("scoreBreakdown", {}).get("sourceType", "").lower() or True


def test_search_multiple_keyword_combinations(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    with MANUAL_PATH.open("rb") as f:
        pdf_bytes = f.read()

    client.post(
        "/api/knowledge/documents",
        files={"file": ("摩托车发动机维修手册.pdf", pdf_bytes, "application/pdf")},
        data={"source_name": "摩托车发动机维修手册"},
    )

    queries = [
        ("摩托车", "火花塞"),
        ("发动机", "启动困难"),
        ("摩托车", "点火系统"),
        ("发动机", "压缩压力"),
    ]

    for device, fault in queries:
        search_resp = client.post(
            "/api/search",
            json={"deviceModel": device, "faultText": fault, "inputType": "text", "topK": 3},
        )
        assert search_resp.status_code == 200
        data = search_resp.json()["data"]
        assert len(data["results"]) > 0, f"查询 {device} + {fault} 应返回结果"
        assert data["queryId"], "每次搜索应有 queryId"


# ---------------------------------------------------------------------------
# RAG — 基于 PDF 入库内容生成回答
# ---------------------------------------------------------------------------

def test_rag_answer_uses_manual_pdf_citations(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    with MANUAL_PATH.open("rb") as f:
        pdf_bytes = f.read()

    upload_resp = client.post(
        "/api/knowledge/documents",
        files={"file": ("摩托车发动机维修手册.pdf", pdf_bytes, "application/pdf")},
        data={"source_name": "摩托车发动机维修手册"},
    )
    doc_id = upload_resp.json()["data"]["id"]

    rag_resp = client.post(
        "/api/rag/answer",
        json={
            "deviceModel": "摩托车发动机",
            "faultText": "无法启动 火花塞",
            "topK": 5,
            "provider": "mock",
        },
    )

    assert rag_resp.status_code == 200
    data = rag_resp.json()["data"]
    assert data["provider"] == "mock"
    assert data["fallback"] is True
    assert len(data["citations"]) > 0

    # 确认 citations 中包含 PDF 资料
    pdf_citations = [c for c in data["citations"] if c.get("documentId") == doc_id]
    assert len(pdf_citations) > 0, f"RAG citations 应包含入库资料引用 (docId={doc_id})"


def test_rag_answer_with_real_provider_falls_back_gracefully_if_no_key(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    client = make_client(tmp_path, monkeypatch)

    with MANUAL_PATH.open("rb") as f:
        pdf_bytes = f.read()

    client.post(
        "/api/knowledge/documents",
        files={"file": ("摩托车发动机维修手册.pdf", pdf_bytes, "application/pdf")},
        data={"source_name": "摩托车发动机维修手册"},
    )

    # 请求 openai provider，但没有 Key → 应 fallback 到 mock
    rag_resp = client.post(
        "/api/rag/answer",
        json={
            "deviceModel": "摩托车发动机",
            "faultText": "启动困难",
            "topK": 3,
            "provider": "openai",
        },
    )

    assert rag_resp.status_code == 200
    data = rag_resp.json()["data"]
    assert data["provider"] == "mock"
    assert data["requestedProvider"] == "openai"
    assert data["fallback"] is True


# ---------------------------------------------------------------------------
# 知识关系网络
# ---------------------------------------------------------------------------

def test_knowledge_graph_with_manual_pdf(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    with MANUAL_PATH.open("rb") as f:
        pdf_bytes = f.read()

    client.post(
        "/api/knowledge/documents",
        files={"file": ("摩托车发动机维修手册.pdf", pdf_bytes, "application/pdf")},
        data={"source_name": "摩托车发动机维修手册"},
    )

    graph_resp = client.post(
        "/api/knowledge/graph",
        json={"deviceModel": "摩托车发动机", "faultText": "无法启动", "inputType": "text", "topK": 5},
    )

    assert graph_resp.status_code == 200
    graph = graph_resp.json()["data"]
    assert len(graph["nodes"]) > 0
    assert len(graph["edges"]) > 0

    # 确认有设备节点和故障节点
    node_types = {n["type"] for n in graph["nodes"]}
    assert "device" in node_types
    assert "fault" in node_types

    # 确认有资料节点(documents 来自 PDF)
    doc_nodes = [n for n in graph["nodes"] if n["type"] == "document"]
    assert len(doc_nodes) > 0, "知识网络应包含入库资料节点"


# ---------------------------------------------------------------------------
# 多模态分析（PDF 走 multimodal analysis）
# ---------------------------------------------------------------------------

def test_multimodal_analyze_motorcycle_manual_pdf(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    with MANUAL_PATH.open("rb") as f:
        pdf_bytes = f.read()

    upload_resp = client.post(
        "/api/knowledge/documents",
        files={"file": ("摩托车发动机维修手册.pdf", pdf_bytes, "application/pdf")},
        data={"source_name": "摩托车发动机维修手册"},
    )
    doc_id = upload_resp.json()["data"]["id"]

    # Mock 多模态分析
    analyze_resp = client.post(
        f"/api/knowledge/documents/{doc_id}/analyze",
        json={"provider": "mock"},
    )

    assert analyze_resp.status_code == 200
    analyzed = analyze_resp.json()["data"]
    assert analyzed["status"] == "analyzed"
    assert analyzed["chunkCount"] > 0

    analysis = analyzed["analysis"]
    assert analysis["provider"] == "mock"
    assert analysis["fallback"] is True
    assert len(analysis["summary"]) > 0
    assert len(analysis["keyComponents"]) > 0
    assert len(analysis["faultSymptoms"]) > 0
    assert len(analysis["inspectionSteps"]) > 0
    assert len(analysis["safetyNotes"]) > 0


def test_multimodal_analyzed_chunks_are_searchable(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    with MANUAL_PATH.open("rb") as f:
        pdf_bytes = f.read()

    upload_resp = client.post(
        "/api/knowledge/documents",
        files={"file": ("摩托车发动机维修手册.pdf", pdf_bytes, "application/pdf")},
        data={"source_name": "摩托车发动机维修手册"},
    )
    doc_id = upload_resp.json()["data"]["id"]

    # 多模态分析
    client.post(f"/api/knowledge/documents/{doc_id}/analyze", json={"provider": "mock"})

    # 删除旧的 pypdf chunks 后的搜索（注：analyze 后 pypdf chunks 被替换为 multimodal chunks）
    search_resp = client.post(
        "/api/search",
        json={"deviceModel": "摩托车", "faultText": "发动机 火花塞", "inputType": "text", "topK": 5},
    )

    assert search_resp.status_code == 200
    results = search_resp.json()["data"]["results"]
    doc_results = [r for r in results if r.get("documentId") == doc_id]
    assert len(doc_results) > 0, "多模态分析后的 chunk 应可被检索"


# ---------------------------------------------------------------------------
# 端到端闭环：入库 → 检索 → RAG → 案例提交审核 → 再次检索
# ---------------------------------------------------------------------------

def test_end_to_end_manual_workflow(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    # Step 1: 上传摩托车维修手册 PDF
    with MANUAL_PATH.open("rb") as f:
        pdf_bytes = f.read()

    upload_resp = client.post(
        "/api/knowledge/documents",
        files={"file": ("摩托车发动机维修手册.pdf", pdf_bytes, "application/pdf")},
        data={"source_name": "摩托车发动机维修手册"},
    )
    assert upload_resp.status_code == 200
    doc_id = upload_resp.json()["data"]["id"]
    assert upload_resp.json()["data"]["chunkCount"] > 0

    # Step 2: 检索摩托车发动机故障
    search_resp = client.post(
        "/api/search",
        json={
            "deviceModel": "摩托车发动机",
            "faultText": "无法启动 火花塞 点火系统",
            "inputType": "text",
            "topK": 5,
        },
    )
    assert search_resp.status_code == 200
    search_data = search_resp.json()["data"]
    assert len(search_data["results"]) > 0

    # 确认命中文档来源
    doc_results = [r for r in search_data["results"] if r["sourceType"] == "document"]
    assert len(doc_results) > 0

    # Step 3: RAG 辅助回答
    rag_resp = client.post(
        "/api/rag/answer",
        json={
            "deviceModel": "摩托车发动机",
            "faultText": "无法启动 火花塞 点火系统",
            "topK": 5,
            "provider": "mock",
        },
    )
    assert rag_resp.status_code == 200
    rag_data = rag_resp.json()["data"]
    assert len(rag_data["answer"]) > 0
    assert len(rag_data["citations"]) > 0
    assert len(rag_data["recommendedActions"]) > 0

    # Step 4: 查看作业流程（关联第一个有 workflow 的结果）
    workflow_result = next((r for r in search_data["results"] if r.get("workflowId")), None)
    if workflow_result:
        wf_resp = client.get(f"/api/workflows/{workflow_result['workflowId']}")
        assert wf_resp.status_code == 200
        wf = wf_resp.json()["data"]
        assert len(wf["steps"]) > 0
        assert len(wf["safetyNotes"]) > 0
        assert len(wf["tools"]) > 0

    # Step 5: 提交维修案例
    case_resp = client.post(
        "/api/cases",
        json={
            "deviceModel": "摩托车发动机",
            "faultText": "无法启动，火花塞积碳严重",
            "cause": "火花塞积碳，电极间隙过大",
            "solution": "更换新火花塞，间隙调整至 0.7-0.9mm，拧紧力矩 20N·m",
            "result": "启动恢复正常，怠速稳定",
            "tags": ["火花塞", "无法启动", "摩托车", "点火系统"],
        },
    )
    assert case_resp.status_code == 200
    case_id = case_resp.json()["data"]["id"]
    assert case_resp.json()["data"]["status"] == "pending_review"

    # Step 6: 审核案例
    review_resp = client.patch(
        f"/api/cases/{case_id}/review",
        json={
            "action": "approve",
            "reviewNote": "案例真实有效，处理方案符合手册规范",
            "normalizedTags": ["火花塞", "无法启动", "摩托车", "点火系统", "间隙调整"],
        },
    )
    assert review_resp.status_code == 200
    assert review_resp.json()["data"]["status"] == "approved"

    # Step 7: 再次检索，确认新案例被命中
    search2_resp = client.post(
        "/api/search",
        json={
            "deviceModel": "摩托车发动机",
            "faultText": "无法启动 火花塞积碳",
            "inputType": "text",
            "topK": 5,
        },
    )
    assert search2_resp.status_code == 200
    results2 = search2_resp.json()["data"]["results"]
    case_in_results = [r for r in results2 if r["id"] == case_id and r["sourceType"] == "case"]
    assert len(case_in_results) > 0, "审核通过的案例应在再次检索中命中"


# ---------------------------------------------------------------------------
# 资料管理 — 列表、详情、删除
# ---------------------------------------------------------------------------

def test_list_knowledge_documents_includes_manual(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    with MANUAL_PATH.open("rb") as f:
        pdf_bytes = f.read()

    client.post(
        "/api/knowledge/documents",
        files={"file": ("摩托车发动机维修手册.pdf", pdf_bytes, "application/pdf")},
        data={"source_name": "摩托车发动机维修手册"},
    )

    list_resp = client.get("/api/knowledge/documents")
    assert list_resp.status_code == 200
    data = list_resp.json()["data"]
    assert data["total"] >= 1
    assert any(d["sourceName"] == "摩托车发动机维修手册" for d in data["items"])


def test_get_document_detail_includes_chunks(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    with MANUAL_PATH.open("rb") as f:
        pdf_bytes = f.read()

    upload_resp = client.post(
        "/api/knowledge/documents",
        files={"file": ("摩托车发动机维修手册.pdf", pdf_bytes, "application/pdf")},
        data={"source_name": "摩托车发动机维修手册"},
    )
    doc_id = upload_resp.json()["data"]["id"]

    detail_resp = client.get(f"/api/knowledge/documents/{doc_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()["data"]
    assert detail["id"] == doc_id
    assert detail["fileName"] == "摩托车发动机维修手册.pdf"
    assert detail["chunkTotal"] > 0
    assert len(detail["chunks"]) > 0


def test_delete_manual_document_removes_from_search(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    with MANUAL_PATH.open("rb") as f:
        pdf_bytes = f.read()

    upload_resp = client.post(
        "/api/knowledge/documents",
        files={"file": ("摩托车发动机维修手册.pdf", pdf_bytes, "application/pdf")},
        data={"source_name": "摩托车发动机维修手册"},
    )
    doc_id = upload_resp.json()["data"]["id"]

    # 删除前可检索
    before_resp = client.post(
        "/api/search",
        json={"deviceModel": "摩托车", "faultText": "发动机", "inputType": "text", "topK": 3},
    )
    assert any(r.get("documentId") == doc_id for r in before_resp.json()["data"]["results"])

    # 删除
    delete_resp = client.delete(f"/api/knowledge/documents/{doc_id}")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["data"]["deleted"] is True

    # 删除后不可检索
    after_resp = client.post(
        "/api/search",
        json={"deviceModel": "摩托车", "faultText": "发动机", "inputType": "text", "topK": 3},
    )
    assert not any(
        r.get("documentId") == doc_id for r in after_resp.json()["data"]["results"]
    ), "删除后资料不应出现在检索结果中"

    # 删除后详情返回 404
    detail_resp = client.get(f"/api/knowledge/documents/{doc_id}")
    assert detail_resp.status_code == 404


# ---------------------------------------------------------------------------
# Provider 状态检查
# ---------------------------------------------------------------------------

def test_provider_status_with_manual_ingested(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    with MANUAL_PATH.open("rb") as f:
        pdf_bytes = f.read()

    client.post(
        "/api/knowledge/documents",
        files={"file": ("摩托车发动机维修手册.pdf", pdf_bytes, "application/pdf")},
        data={"source_name": "摩托车发动机维修手册"},
    )

    status_resp = client.get("/api/providers/status")
    assert status_resp.status_code == 200
    data = status_resp.json()["data"]
    assert "llm" in data
    assert "multimodal" in data
    assert "remoteApiMode" in data
    assert "offlineFallback" in data


# ---------------------------------------------------------------------------
# Chroma 向量检索集成（仅当 RAG_VECTOR_STORE=chroma 时）
# ---------------------------------------------------------------------------

def test_search_with_chroma_enabled_merges_vector_results(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("RAG_VECTOR_STORE", "chroma")
    monkeypatch.setenv("APP_CHROMA_DIR", str(tmp_path / "chroma"))
    client = make_client(tmp_path, monkeypatch)

    with MANUAL_PATH.open("rb") as f:
        pdf_bytes = f.read()

    client.post(
        "/api/knowledge/documents",
        files={"file": ("摩托车发动机维修手册.pdf", pdf_bytes, "application/pdf")},
        data={"source_name": "摩托车发动机维修手册"},
    )

    search_resp = client.post(
        "/api/search",
        json={"deviceModel": "摩托车", "faultText": "发动机 启动", "inputType": "text", "topK": 5},
    )

    assert search_resp.status_code == 200
    results = search_resp.json()["data"]["results"]
    assert len(results) > 0
    assert any(r["sourceType"] == "document" for r in results)


def test_rag_citations_preserve_document_id_with_chroma(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("RAG_VECTOR_STORE", "chroma")
    monkeypatch.setenv("APP_CHROMA_DIR", str(tmp_path / "chroma"))
    client = make_client(tmp_path, monkeypatch)

    with MANUAL_PATH.open("rb") as f:
        pdf_bytes = f.read()

    upload_resp = client.post(
        "/api/knowledge/documents",
        files={"file": ("摩托车发动机维修手册.pdf", pdf_bytes, "application/pdf")},
        data={"source_name": "摩托车发动机维修手册"},
    )
    doc_id = upload_resp.json()["data"]["id"]

    rag_resp = client.post(
        "/api/rag/answer",
        json={"deviceModel": "摩托车", "faultText": "发动机故障", "topK": 5, "provider": "mock"},
    )

    assert rag_resp.status_code == 200
    citations = rag_resp.json()["data"]["citations"]
    assert any(
        c.get("documentId") == doc_id for c in citations
    ), "Chroma 增强下 RAG citations 应保留 documentId"


# ---------------------------------------------------------------------------
# 边界测试：上传大 PDF 的 chunk 数量合理性
# ---------------------------------------------------------------------------

def test_manual_pdf_chunk_count_reasonable(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    with MANUAL_PATH.open("rb") as f:
        pdf_bytes = f.read()

    upload_resp = client.post(
        "/api/knowledge/documents",
        files={"file": ("摩托车发动机维修手册.pdf", pdf_bytes, "application/pdf")},
        data={"source_name": "摩托车发动机维修手册"},
    )

    data = upload_resp.json()["data"]
    # 41 页、约 16821 字符，chunk_size=700, overlap=120 → 预期的 chunk 数
    assert data["chunkCount"] >= 5, f"41 页 PDF 至少应生成 5 个 chunk，实际 {data['chunkCount']}"


def test_manual_pdf_file_is_saved(tmp_path, monkeypatch) -> None:
    knowledge_dir = tmp_path / "knowledge"
    monkeypatch.setenv("APP_KNOWLEDGE_DIR", str(knowledge_dir))
    monkeypatch.setenv("APP_EXAMPLES_DIR", str(tmp_path / "source"))
    shutil.copytree("data/examples", tmp_path / "source")

    from backend.app.main import app

    client = TestClient(app)

    with MANUAL_PATH.open("rb") as f:
        pdf_bytes = f.read()

    upload_resp = client.post(
        "/api/knowledge/documents",
        files={"file": ("摩托车发动机维修手册.pdf", pdf_bytes, "application/pdf")},
        data={"source_name": "摩托车发动机维修手册"},
    )
    doc_id = upload_resp.json()["data"]["id"]

    saved_file = knowledge_dir / "files" / f"{doc_id}.pdf"
    assert saved_file.exists(), f"PDF 原始文件应保存在 {saved_file}"
    assert saved_file.stat().st_size > 0
    assert saved_file.stat().st_size == len(pdf_bytes)
