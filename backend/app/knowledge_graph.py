from __future__ import annotations

from typing import Any

from .data_store import load_document_chunks
from .schemas import SearchRequest
from .services import search_knowledge


def add_node(nodes: dict[str, dict[str, Any]], node_id: str, label: str, node_type: str, weight: int = 1) -> None:
    if node_id in nodes:
        nodes[node_id]["weight"] = max(nodes[node_id]["weight"], weight)
        return
    nodes[node_id] = {"id": node_id, "label": label, "type": node_type, "weight": weight}


def add_edge(
    edges: list[dict[str, Any]],
    source: str,
    target: str,
    relation: str,
    evidence: str = "",
) -> None:
    edge_id = f"{source}->{relation}->{target}"
    if any(edge["id"] == edge_id for edge in edges):
        return
    edges.append({"id": edge_id, "source": source, "target": target, "relation": relation, "evidence": evidence})


def safe_label(value: str, fallback: str) -> str:
    value = value.strip()
    return value[:36] if value else fallback


def document_chunk_by_id(chunk_id: str | None) -> dict[str, Any] | None:
    if not chunk_id:
        return None
    return next((chunk for chunk in load_document_chunks() if chunk.get("id") == chunk_id), None)


def build_knowledge_graph(request: SearchRequest) -> dict[str, Any]:
    search_payload = search_knowledge(request)
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []

    device_label = safe_label(request.deviceModel, "未指定设备")
    fault_label = safe_label(request.faultText, "未指定故障")
    device_id = f"device:{device_label}"
    fault_id = f"fault:{fault_label}"
    add_node(nodes, device_id, device_label, "device", 5)
    add_node(nodes, fault_id, fault_label, "fault", 5)
    add_edge(edges, device_id, fault_id, "出现故障", "用户当前查询")

    for result in search_payload["results"]:
        source_id = f"{result['sourceType']}:{result['id']}"
        add_node(nodes, source_id, result["title"], result["sourceType"], int(result["confidence"] * 10))
        add_edge(edges, fault_id, source_id, "证据支持", result.get("reason", "检索命中"))

        for term in result.get("matchedTerms", [])[:4]:
            term_id = f"term:{term}"
            add_node(nodes, term_id, term, "term", 3)
            add_edge(edges, term_id, source_id, "命中资料", result.get("sourceName", ""))
            add_edge(edges, fault_id, term_id, "包含关键词", "检索分词")

        if result.get("workflowId"):
            workflow_id = f"workflow:{result['workflowId']}"
            add_node(nodes, workflow_id, f"作业流程 {result['workflowId']}", "workflow", 4)
            add_edge(edges, source_id, workflow_id, "关联流程", "资料或案例绑定标准作业流程")

        if result.get("sourceName"):
            source_name_id = f"source:{result['sourceName']}"
            add_node(nodes, source_name_id, result["sourceName"], "source", 2)
            add_edge(edges, source_id, source_name_id, "来自", result.get("chapter") or "")

        chunk = document_chunk_by_id(result.get("chunkId"))
        if chunk:
            provider = chunk.get("analysisProvider")
            if provider:
                provider_id = f"provider:{provider}"
                add_node(nodes, provider_id, f"{provider} 多模态分析", "provider", 2)
                add_edge(edges, provider_id, source_id, "生成片段", "资料入库增强层")

    return {
        "queryId": search_payload["queryId"],
        "summary": f"围绕当前查询生成 {len(nodes)} 个知识节点、{len(edges)} 条关系，展示设备、故障、资料、案例与流程之间的轻量知识网络。",
        "nodes": list(nodes.values()),
        "edges": edges,
    }
