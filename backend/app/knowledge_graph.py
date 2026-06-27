from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .data_store import (
    load_document_chunks,
    load_documents,
    load_knowledge_graph_cache,
    load_rag_feedback,
    load_seed_data,
    save_knowledge_graph_cache,
)
from .schemas import SearchRequest
from .services import search_knowledge, tokens


MAX_OVERVIEW_NODES = 160
MAX_OVERVIEW_EDGES = 260


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def compact(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    return text[:48] if text else fallback


def node_id(node_type: str, raw: Any) -> str:
    label = compact(raw, node_type).lower()
    safe = "".join(char if char.isalnum() else "-" for char in label).strip("-")
    return f"{node_type}:{safe[:72] or node_type}"


def add_node(
    nodes: dict[str, dict[str, Any]],
    node_type: str,
    label: Any,
    *,
    raw_id: str | None = None,
    weight: int = 1,
    properties: dict[str, Any] | None = None,
) -> str:
    identifier = raw_id or node_id(node_type, label)
    if identifier in nodes:
        nodes[identifier]["weight"] = max(nodes[identifier]["weight"], weight)
        nodes[identifier]["properties"].update(properties or {})
        return identifier

    nodes[identifier] = {
        "id": identifier,
        "label": compact(label, node_type),
        "type": node_type,
        "reviewStatus": (properties or {}).get("reviewStatus") or (properties or {}).get("status") or "approved",
        "weight": weight,
        "properties": properties or {},
    }
    return identifier


def add_edge(
    edges: dict[str, dict[str, Any]],
    source: str,
    target: str,
    relation: str,
    *,
    evidence: str = "",
    confidence: float = 0.75,
) -> str:
    identifier = f"{source}->{relation}->{target}"
    if identifier not in edges:
        edges[identifier] = {
            "id": identifier,
            "source": source,
            "target": target,
            "relation": relation,
            "type": relation,
            "evidence": compact(evidence, ""),
            "confidence": round(confidence, 2),
        }
    return identifier


def add_terms(
    nodes: dict[str, dict[str, Any]],
    edges: dict[str, dict[str, Any]],
    owner_id: str,
    terms: list[str],
    *,
    relation: str = "包含术语",
    evidence: str = "",
) -> None:
    for term in [item for item in terms if str(item).strip()][:8]:
        term_id = add_node(nodes, "term", term, weight=2)
        add_edge(edges, owner_id, term_id, relation, evidence=evidence or "结构化字段抽取", confidence=0.7)


def approved_rag_feedback() -> list[dict[str, Any]]:
    return [item for item in load_rag_feedback() if item.get("status") == "approved"]


def feedback_matches_query(feedback: dict[str, Any], request: SearchRequest) -> bool:
    haystack = " ".join(
        str(feedback.get(field, ""))
        for field in ["deviceModel", "faultText", "correctedAnswer", "reason"]
    ).lower()
    for label in feedback.get("labels", []):
        haystack += f" {str(label).lower()}"
    query_terms = tokens(request.deviceModel, request.faultText)
    return not query_terms or any(term in haystack for term in query_terms)


def add_rag_feedback_node(
    nodes: dict[str, dict[str, Any]],
    edges: dict[str, dict[str, Any]],
    feedback: dict[str, Any],
) -> str:
    feedback_id = add_node(
        nodes,
        "rag_feedback",
        feedback.get("reason") or feedback.get("faultText") or feedback.get("id"),
        raw_id=f"rag_feedback:{feedback['id']}",
        weight=4,
        properties={
            "status": feedback.get("status", ""),
            "reviewStatus": feedback.get("status", ""),
            "maintenanceLevel": feedback.get("maintenanceLevel", ""),
            "labels": feedback.get("labels", []),
            "approvedAt": feedback.get("approvedAt", ""),
        },
    )
    if feedback.get("deviceModel"):
        device_id = add_node(nodes, "device", feedback["deviceModel"], weight=5)
        add_edge(edges, device_id, feedback_id, "采纳回答修正", evidence=feedback.get("reviewNote", ""), confidence=0.78)
    if feedback.get("faultText"):
        fault_id = add_node(nodes, "fault", feedback["faultText"], weight=5)
        add_edge(edges, fault_id, feedback_id, "修正建议", evidence=feedback.get("correctedAnswer") or feedback.get("reason", ""), confidence=0.8)
    add_terms(nodes, edges, feedback_id, feedback.get("labels", []), relation="标注标签", evidence=feedback.get("reason", ""))
    return feedback_id


def graph_stats(nodes: dict[str, dict[str, Any]], edges: dict[str, dict[str, Any]]) -> dict[str, Any]:
    node_types: dict[str, int] = {}
    relation_types: dict[str, int] = {}
    for node in nodes.values():
        node_types[node["type"]] = node_types.get(node["type"], 0) + 1
    for edge in edges.values():
        relation_types[edge["relation"]] = relation_types.get(edge["relation"], 0) + 1
    return {
        "nodeCount": len(nodes),
        "edgeCount": len(edges),
        "nodeTypes": node_types,
        "relationTypes": relation_types,
    }


def sort_nodes(nodes: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(nodes.values(), key=lambda item: (item["weight"], item["type"], item["label"]), reverse=True)


def sort_edges(edges: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(edges.values(), key=lambda item: (item["confidence"], item["relation"]), reverse=True)


def build_global_knowledge_graph() -> dict[str, Any]:
    data = load_seed_data()
    documents = load_documents()
    chunks = [chunk for chunk in load_document_chunks() if chunk.get("review_status", "approved") == "approved"]
    approved_document_ids = {str(chunk.get("documentId", "")) for chunk in chunks}
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}

    for device in data["devices"]:
        device_id = add_node(
            nodes,
            "device",
            device.get("model") or device.get("name"),
            raw_id=f"device:{device['id']}",
            weight=7,
            properties={
                "model": device.get("model", ""),
                "deviceType": device.get("type", ""),
                "manufacturer": device.get("manufacturer", ""),
            },
        )
        add_terms(nodes, edges, device_id, device.get("tags", []), relation="具有特征")

    for manual in data["manuals"]:
        manual_id = add_node(
            nodes,
            "manual",
            manual.get("title"),
            raw_id=f"manual:{manual['id']}",
            weight=6,
            properties={
                "sourceName": manual.get("sourceName", ""),
                "chapter": manual.get("chapter", ""),
                "page": manual.get("page"),
            },
        )
        device_label = manual.get("deviceModel") or manual.get("deviceType")
        device_ref = add_node(nodes, "device", device_label, weight=5)
        add_edge(edges, device_ref, manual_id, "适用资料", evidence=manual.get("sourceName", ""), confidence=0.86)
        add_terms(nodes, edges, manual_id, manual.get("tags", []), evidence=manual.get("chapter", ""))
        if manual.get("workflowId"):
            workflow_id = add_node(nodes, "workflow", f"作业流程 {manual['workflowId']}", raw_id=f"workflow:{manual['workflowId']}", weight=5)
            add_edge(edges, manual_id, workflow_id, "关联流程", evidence="手册绑定标准作业流程", confidence=0.82)

    for workflow in data["workflows"]:
        workflow_id = add_node(
            nodes,
            "workflow",
            workflow.get("title"),
            raw_id=f"workflow:{workflow['id']}",
            weight=6,
            properties={"level": workflow.get("level", ""), "deviceType": workflow.get("deviceType", "")},
        )
        if workflow.get("faultType"):
            fault_id = add_node(nodes, "fault", workflow["faultType"], weight=5)
            add_edge(edges, fault_id, workflow_id, "推荐流程", evidence=workflow.get("level", ""), confidence=0.84)
        add_terms(nodes, edges, workflow_id, workflow.get("tools", []), relation="需要工具", evidence="作业流程工具清单")

    for repair_case in data["cases"]:
        if repair_case.get("status", "approved") != "approved":
            continue
        case_id = add_node(
            nodes,
            "case",
            repair_case.get("faultTitle"),
            raw_id=f"case:{repair_case['id']}",
            weight=5 if repair_case.get("status") == "approved" else 2,
            properties={
                "status": repair_case.get("status", "approved"),
                "reviewStatus": repair_case.get("status", "approved"),
                "createdAt": repair_case.get("createdAt", ""),
                "experienceSummary": repair_case.get("experienceSummary", ""),
                "lessonsLearned": repair_case.get("lessonsLearned", ""),
            },
        )
        device_ref = add_node(nodes, "device", repair_case.get("deviceModel") or repair_case.get("deviceType"), weight=5)
        fault_ref = add_node(nodes, "fault", repair_case.get("faultTitle") or repair_case.get("faultText"), weight=5)
        add_edge(edges, device_ref, fault_ref, "出现故障", evidence="维修案例", confidence=0.8)
        add_edge(edges, fault_ref, case_id, "案例证据", evidence=repair_case.get("solution", ""), confidence=0.82)
        add_terms(nodes, edges, case_id, repair_case.get("tags", []) + repair_case.get("possibleCauses", []), evidence="案例标签与原因")
        if repair_case.get("workflowId"):
            workflow_id = add_node(nodes, "workflow", f"作业流程 {repair_case['workflowId']}", raw_id=f"workflow:{repair_case['workflowId']}", weight=5)
            add_edge(edges, case_id, workflow_id, "复用流程", evidence="案例关联流程", confidence=0.78)

    for feedback in approved_rag_feedback():
        add_rag_feedback_node(nodes, edges, feedback)

    chunks_by_document: dict[str, list[dict[str, Any]]] = {}
    for chunk in chunks:
        chunks_by_document.setdefault(str(chunk.get("documentId", "")), []).append(chunk)

    for document in documents:
        if document["id"] not in approved_document_ids and document.get("status") != "approved":
            continue
        document_id = add_node(
            nodes,
            "document",
            document.get("sourceName") or document.get("fileName"),
            raw_id=f"document:{document['id']}",
            weight=6,
            properties={
                "status": document.get("status", ""),
                "reviewStatus": "approved",
                "parser": document.get("parser", ""),
                "chunkCount": document.get("chunkCount", 0),
            },
        )
        if document.get("analysis", {}).get("provider"):
            provider_id = add_node(nodes, "provider", f"{document['analysis']['provider']} 多模态分析", weight=3)
            add_edge(edges, provider_id, document_id, "生成资料摘要", evidence=document["analysis"].get("summary", ""), confidence=0.72)
        for chunk in chunks_by_document.get(document["id"], [])[:8]:
            chunk_id = add_node(nodes, "chunk", chunk.get("title") or chunk.get("id"), raw_id=f"chunk:{chunk['id']}", weight=3)
            add_edge(edges, document_id, chunk_id, "包含片段", evidence=chunk.get("snippet", ""), confidence=0.76)
            add_terms(nodes, edges, chunk_id, chunk.get("keywords", []), evidence=chunk.get("sourceName", ""))

    node_list = sort_nodes(nodes)[:MAX_OVERVIEW_NODES]
    kept_ids = {node["id"] for node in node_list}
    edge_list = [edge for edge in sort_edges(edges) if edge["source"] in kept_ids and edge["target"] in kept_ids][:MAX_OVERVIEW_EDGES]
    graph = {
        "mode": "global",
        "approvedOnly": True,
        "queryId": "global-knowledge-graph",
        "summary": f"当前知识图谱沉淀 {len(node_list)} 个实体节点、{len(edge_list)} 条关系，覆盖设备、故障、资料、案例、流程、术语和模型分析来源。",
        "generatedAt": utc_now(),
        "nodes": node_list,
        "edges": edge_list,
        "stats": graph_stats({node["id"]: node for node in node_list}, {edge["id"]: edge for edge in edge_list}),
        "recommendations": [
            "优先补充真实维修手册和审核案例，可直接增加 document/case 节点密度。",
            "真实多模态分析完成后会把图片/PDF 摘要连接到资料节点，提升答辩时的可追溯性。",
            "当前采用轻量 JSON 图谱，适合比赛演示；生产级多跳推理可后续迁移到 Neo4j 或 GraphRAG。",
        ],
    }
    save_knowledge_graph_cache(graph)
    return graph


def build_knowledge_graph(request: SearchRequest) -> dict[str, Any]:
    search_payload = search_knowledge(request)
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}

    device_label = compact(request.deviceModel, "未指定设备")
    fault_label = compact(request.faultText, "未指定故障")
    device_id = add_node(nodes, "device", device_label, weight=8)
    fault_id = add_node(nodes, "fault", fault_label, weight=8)
    add_edge(edges, device_id, fault_id, "出现故障", evidence="用户当前查询", confidence=0.9)

    focus_ids = [device_id, fault_id]
    for result in search_payload["results"]:
        source_id = add_node(
            nodes,
            result["sourceType"],
            result["title"],
            raw_id=f"{result['sourceType']}:{result['id']}",
            weight=max(3, int(result["confidence"] * 10)),
            properties={
                "sourceName": result.get("sourceName", ""),
                "confidence": result.get("confidence", 0),
                "documentId": result.get("documentId"),
                "chunkId": result.get("chunkId"),
            },
        )
        focus_ids.append(source_id)
        add_edge(edges, fault_id, source_id, "证据支持", evidence=result.get("reason", "检索命中"), confidence=result.get("confidence", 0.75))

        for term in result.get("matchedTerms", [])[:5]:
            term_id = add_node(nodes, "term", term, weight=3)
            add_edge(edges, fault_id, term_id, "包含关键词", evidence="检索分词", confidence=0.68)
            add_edge(edges, term_id, source_id, "命中证据", evidence=result.get("sourceName", ""), confidence=0.7)

        if result.get("workflowId"):
            workflow_id = add_node(nodes, "workflow", f"作业流程 {result['workflowId']}", raw_id=f"workflow:{result['workflowId']}", weight=5)
            add_edge(edges, source_id, workflow_id, "关联流程", evidence="资料或案例绑定标准作业流程", confidence=0.78)

        if result.get("sourceName"):
            source_name_id = add_node(nodes, "source", result["sourceName"], weight=2)
            add_edge(edges, source_id, source_name_id, "来自", evidence=result.get("chapter") or "", confidence=0.66)

        chunk = next((item for item in load_document_chunks() if item.get("id") == result.get("chunkId")), None)
        if chunk and chunk.get("analysisProvider"):
            provider = chunk["analysisProvider"]
            provider_id = add_node(nodes, "provider", f"{provider} 多模态分析", weight=2)
            add_edge(edges, provider_id, source_id, "生成片段", evidence="资料入库增强层", confidence=0.68)

    for feedback in approved_rag_feedback():
        if not feedback_matches_query(feedback, request):
            continue
        feedback_id = add_rag_feedback_node(nodes, edges, feedback)
        focus_ids.append(feedback_id)

    node_list = sort_nodes(nodes)
    edge_list = sort_edges(edges)
    graph = {
        "mode": "query",
        "approvedOnly": True,
        "queryId": search_payload["queryId"],
        "summary": f"围绕当前查询生成 {len(node_list)} 个知识节点、{len(edge_list)} 条关系，展示设备、故障、证据、流程与来源之间的可追溯链路。",
        "generatedAt": utc_now(),
        "nodes": node_list,
        "edges": edge_list,
        "stats": graph_stats(nodes, edges),
        "focusNodeIds": focus_ids,
        "recommendations": [
            "若证据节点较少，建议先上传对应维修手册或补充审核案例。",
            "点击资料入库并执行多模态分析后，图谱会增加资料、片段和 provider 关系。",
        ],
    }
    return graph


def knowledge_graph_overview() -> dict[str, Any]:
    cached = load_knowledge_graph_cache()
    if cached.get("nodes") and cached.get("edges"):
        cached["cacheHit"] = True
        return cached
    return build_global_knowledge_graph()
