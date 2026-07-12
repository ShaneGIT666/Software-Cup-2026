from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.app.schemas import CaseCreateRequest


def make_case(**overrides: object) -> CaseCreateRequest:
    values: dict[str, object] = {
        "deviceModel": "engine-a",
        "faultText": "cannot start",
        "cause": "ignition",
        "solution": "inspect plug",
        "result": "restored",
    }
    values.update(overrides)
    return CaseCreateRequest(**values)


def test_case_levels_and_workflow_are_normalized() -> None:
    request = make_case(
        riskLevel="  HIGH ",
        maintenanceLevel=" Focused_Repair ",
        workflowId=" workflow-01 ",
    )

    assert request.riskLevel == "high"
    assert request.maintenanceLevel == "focused_repair"
    assert request.workflowId == "workflow-01"


def test_empty_workflow_id_becomes_none() -> None:
    assert make_case(workflowId="   ").workflowId is None


@pytest.mark.parametrize(
    ("field", "value"),
    (("riskLevel", "extreme"), ("maintenanceLevel", "weekend_only")),
)
def test_invalid_case_levels_are_rejected(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        make_case(**{field: value})
