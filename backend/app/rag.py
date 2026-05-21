from __future__ import annotations

from typing import Any

from .llm_adapter import mock_rag_answer
from .schemas import RagAnswerRequest, SearchRequest
from .services import search_knowledge


def answer_with_rag(request: RagAnswerRequest) -> dict[str, Any]:
    search_payload = search_knowledge(
        SearchRequest(
            deviceModel=request.deviceModel,
            faultText=request.faultText,
            inputType="text",
            topK=request.topK,
        )
    )
    rag_payload = mock_rag_answer(
        device_model=request.deviceModel.strip(),
        fault_text=request.faultText.strip(),
        contexts=search_payload["results"],
        requested_provider=request.provider,
    )
    return {
        "queryId": search_payload["queryId"],
        "summary": search_payload["summary"],
        **rag_payload,
    }
