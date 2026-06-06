from __future__ import annotations

import time
from typing import Any

from .knowledge_graph import build_knowledge_graph
from .llm_adapter import generate_rag_answer, real_rag_answer
from .provider_policy import configured_llm_provider, remote_api_disabled
from .schemas import DiagnosisRequest, LlmValidateRequest, RagAnswerRequest, SearchRequest
from .services import search_knowledge


def compact_graph_context(graph: dict[str, Any] | None, limit: int = 8) -> dict[str, Any]:
    if not graph:
        return {"enabled": False, "summary": "", "nodeCount": 0, "edgeCount": 0, "paths": []}

    nodes = {node["id"]: node for node in graph.get("nodes", [])}
    paths = []
    for edge in graph.get("edges", [])[:limit]:
        source = nodes.get(edge.get("source"), {})
        target = nodes.get(edge.get("target"), {})
        paths.append(
            {
                "source": source.get("label", edge.get("source", "")),
                "sourceType": source.get("type", ""),
                "relation": edge.get("relation", ""),
                "target": target.get("label", edge.get("target", "")),
                "targetType": target.get("type", ""),
                "evidence": edge.get("evidence", ""),
                "confidence": edge.get("confidence", 0),
            }
        )

    stats = graph.get("stats", {})
    return {
        "enabled": True,
        "summary": graph.get("summary", ""),
        "nodeCount": stats.get("nodeCount", len(nodes)),
        "edgeCount": stats.get("edgeCount", len(graph.get("edges", []))),
        "paths": paths,
    }


def answer_with_rag(request: RagAnswerRequest) -> dict[str, Any]:
    search_request = SearchRequest(
        deviceModel=request.deviceModel,
        faultText=request.faultText,
        inputType="text",
        topK=request.topK,
    )
    search_payload = search_knowledge(search_request)
    graph_context = (
        compact_graph_context(build_knowledge_graph(search_request))
        if request.includeGraphContext
        else compact_graph_context(None)
    )
    rag_payload = generate_rag_answer(
        device_model=request.deviceModel.strip(),
        fault_text=request.faultText.strip(),
        contexts=search_payload["results"],
        requested_provider=request.provider,
        graph_context=graph_context,
    )
    return {
        "queryId": search_payload["queryId"],
        "summary": search_payload["summary"],
        "graphContext": graph_context,
        **rag_payload,
    }


def diagnose_with_rag(request: DiagnosisRequest) -> dict[str, Any]:
    search_request = SearchRequest(
        deviceModel=request.deviceModel,
        faultText=request.faultText,
        inputType="text",
        topK=5,
    )
    search_payload = search_knowledge(search_request)
    contexts = search_payload["results"]
    graph_context = compact_graph_context(build_knowledge_graph(search_request))
    rag_payload = generate_rag_answer(
        device_model=request.deviceModel.strip(),
        fault_text=request.faultText.strip(),
        contexts=contexts,
        requested_provider=None,
        graph_context=graph_context,
    )
    citations = rag_payload.get("citations", [])
    selected_citations = [
        item for item in citations if not request.evidenceIds or item.get("id") in request.evidenceIds
    ] or citations

    possible_causes = []
    for item in selected_citations[:3]:
        reason = item.get("reason") or item.get("title") or item.get("snippet", "")
        possible_causes.append(str(reason)[:120])
    if not possible_causes:
        possible_causes = ["证据不足，需要补充设备型号、故障现象或检修资料。"]

    safety_notes = [
        "检修前确认设备停机、断电或处于安全隔离状态。",
        "佩戴防护手套、护目镜等必要防护装备。",
        "涉及高温、旋转、燃油或电气部件时，先完成现场风险确认。",
    ]

    return {
        "possibleCauses": possible_causes,
        "recommendedActions": rag_payload.get("recommendedActions", []),
        "safetyNotes": safety_notes,
        "citations": selected_citations,
        "answer": rag_payload.get("answer", ""),
        "provider": rag_payload.get("provider", "mock"),
        "model": rag_payload.get("model", "mock"),
        "fallback": rag_payload.get("fallback", True),
        "fallbackReason": rag_payload.get("fallbackReason", ""),
        "queryId": search_payload["queryId"],
        "summary": search_payload["summary"],
        "graphContext": graph_context,
    }


def validate_llm_provider(request: LlmValidateRequest) -> dict[str, Any]:
    provider = configured_llm_provider(request.provider)
    if provider == "mock":
        provider = "openai"

    search_request = SearchRequest(
        deviceModel=request.deviceModel,
        faultText=request.faultText,
        inputType="text",
        topK=request.topK,
    )
    search_payload = search_knowledge(search_request)
    contexts = search_payload["results"]
    graph_context = compact_graph_context(build_knowledge_graph(search_request))

    if remote_api_disabled():
        return {
            "remoteOk": False,
            "provider": provider,
            "model": "",
            "apiStyle": "",
            "latencyMs": 0,
            "fallback": True,
            "fallbackReason": "REMOTE_API_MODE=off，真实 API 验收已跳过。",
            "answerPreview": "",
            "contextCount": len(contexts),
            "graphContext": graph_context,
        }

    started = time.perf_counter()
    try:
        payload = real_rag_answer(
            device_model=request.deviceModel.strip(),
            fault_text=request.faultText.strip(),
            contexts=contexts,
            provider=provider,
            graph_context=graph_context,
        )
        latency_ms = round((time.perf_counter() - started) * 1000)
        return {
            "remoteOk": True,
            "provider": payload["provider"],
            "model": payload.get("model", ""),
            "apiStyle": payload.get("apiStyle", ""),
            "latencyMs": latency_ms,
            "fallback": False,
            "fallbackReason": "",
            "answerPreview": str(payload["answer"])[:240],
            "contextCount": payload.get("contextCount", len(contexts)),
            "graphContext": graph_context,
        }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - started) * 1000)
        return {
            "remoteOk": False,
            "provider": provider,
            "model": "",
            "apiStyle": "",
            "latencyMs": latency_ms,
            "fallback": True,
            "fallbackReason": str(exc),
            "answerPreview": "",
            "contextCount": len(contexts),
            "graphContext": graph_context,
        }
