from __future__ import annotations

from typing import Literal

from ...core.contracts import ReadinessData, V1ContractModel, V1Response


class LiveData(V1ContractModel):
    status: Literal["ok"] = "ok"
    service: Literal["repair-knowledge-assistant"] = "repair-knowledge-assistant"
    apiVersion: Literal["v1"] = "v1"
    environment: Literal["development", "test", "production"]


class LiveResponse(V1Response[LiveData]):
    pass


class ReadyResponse(V1Response[ReadinessData]):
    pass
