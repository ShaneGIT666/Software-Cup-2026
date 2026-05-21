from __future__ import annotations

import os
from typing import Any


def configured_provider(requested_provider: str) -> str:
    return (requested_provider or os.getenv("LLM_PROVIDER") or "mock").lower()


def citation_from_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": result["id"],
        "title": result["title"],
        "sourceType": result["sourceType"],
        "sourceName": result["sourceName"],
        "snippet": result["snippet"],
        "confidence": result["confidence"],
        "page": result.get("page"),
        "chapter": result.get("chapter"),
        "documentId": result.get("documentId"),
        "chunkId": result.get("chunkId"),
        "reason": result.get("reason", ""),
    }


def mock_rag_answer(
    device_model: str,
    fault_text: str,
    contexts: list[dict[str, Any]],
    requested_provider: str,
) -> dict[str, Any]:
    provider = configured_provider(requested_provider)
    active_provider = "mock"
    citations = [citation_from_result(item) for item in contexts]
    source_names = list(dict.fromkeys(item["sourceName"] for item in citations))[:3]

    if contexts:
        answer = (
            f"基于已检索到的 {len(contexts)} 条资料，{device_model or '该设备'} 的“{fault_text}”"
            "优先按来源资料进行排查：先核对高置信度手册/入库资料，再结合历史案例确认常见原因。"
            f"当前可参考来源包括：{'、'.join(source_names)}。"
        )
        recommended_actions = [
            "优先查看引用来源中的手册页码或资料片段，确认安全前置条件。",
            "按标准作业流程逐项检查，不跳过安全确认和验收标准。",
            "若现场处理形成新经验，提交案例并走审核入库流程。",
        ]
    else:
        answer = (
            f"暂未检索到与 {device_model or '该设备'} 的“{fault_text}”直接相关资料。"
            "建议补充设备型号、故障现象关键词，或先上传对应检修手册后再次检索。"
        )
        recommended_actions = ["补充更具体的故障描述。", "上传相关检修资料并完成入库。"]

    return {
        "answer": answer,
        "recommendedActions": recommended_actions,
        "citations": citations,
        "provider": active_provider,
        "requestedProvider": provider,
        "fallback": True,
        "fallbackReason": "当前迭代仅启用 mock provider，真实 OpenAI/Anthropic 调用留待后续接入。",
    }
