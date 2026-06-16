from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from backend.app.evaluation.dataset_loader import EvaluationDatasetError, load_eval_dataset
from backend.app.evaluation.models import EvalCase, EvalCaseResult, EvalDataset, EvalMode
from backend.app.evaluation.report_writer import build_report, write_report
from backend.app.evaluation.retrieval_evaluator import aggregate_metrics, evaluate_case, evaluate_dataset


def write_dataset(path: Path, cases: list[dict[str, Any]]) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": "test",
                "dataset_id": "unit-test",
                "created_at": "2026-06-16T00:00:00Z",
                "purpose": "unit",
                "cases": cases,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def test_load_eval_dataset_template() -> None:
    dataset = load_eval_dataset(Path("data/evaluation/rag-eval-template.json"))

    assert dataset.schema_version == "0.2.0"
    assert len(dataset.cases) == 12
    assert dataset.cases[7].forbidden_source_ids == ["case-004"]
    assert "pending_review" in dataset.cases[7].forbidden_review_status


def test_load_eval_dataset_fills_optional_fields(tmp_path) -> None:
    dataset_path = write_dataset(
        tmp_path / "dataset.json",
        [{"id": "case-a", "category": "smoke", "question": "发动机怎么检查？"}],
    )

    dataset = load_eval_dataset(dataset_path)

    assert dataset.cases[0].expected_source_ids == []
    assert dataset.cases[0].metadata_filters == {}
    assert dataset.cases[0].must_refuse is False


def test_load_eval_dataset_rejects_duplicate_ids(tmp_path) -> None:
    dataset_path = write_dataset(
        tmp_path / "dataset.json",
        [
            {"id": "dup", "category": "a", "question": "q1"},
            {"id": "dup", "category": "b", "question": "q2"},
        ],
    )

    with pytest.raises(EvaluationDatasetError, match="duplicate case ids"):
        load_eval_dataset(dataset_path)


def test_load_eval_dataset_rejects_missing_required_fields(tmp_path) -> None:
    dataset_path = write_dataset(tmp_path / "dataset.json", [{"id": "missing", "category": "a"}])

    with pytest.raises(EvaluationDatasetError, match="missing required fields"):
        load_eval_dataset(dataset_path)


def test_hit_recall_and_mrr_metrics() -> None:
    case = EvalCase(
        id="case-1",
        category="metric",
        question="q",
        expected_source_ids=["doc-a", "case-a"],
    )

    def fake_search(_: Any) -> dict[str, Any]:
        return {
            "results": [
                {"id": "other", "title": "", "snippet": ""},
                {"id": "doc-a", "workflowId": "wf-a", "title": "", "snippet": ""},
                {"id": "case-a", "title": "", "snippet": ""},
            ]
        }

    result = evaluate_case(case, search_func=fake_search, source_status={})
    metrics = aggregate_metrics([result])

    assert result.hit_at["Hit@1"] is False
    assert result.hit_at["Hit@3"] is True
    assert result.recall_at["Recall@1"] == 0
    assert result.recall_at["Recall@3"] == 1
    assert result.reciprocal_rank == 0.5
    assert metrics["Hit@3"].value == 1
    assert metrics["Recall@5"].value == 1
    assert metrics["MRR"].value == 0.5


def test_forbidden_source_violation() -> None:
    case = EvalCase(
        id="case-1",
        category="forbidden",
        question="q",
        forbidden_source_ids=["case-004"],
    )

    def fake_search(_: Any) -> dict[str, Any]:
        return {"results": [{"id": "case-004", "title": "", "snippet": ""}]}

    result = evaluate_case(case, search_func=fake_search, source_status={"case-004": "pending_review"})

    assert result.forbidden_source_violations == ["case-004"]


def test_approved_only_violation() -> None:
    case = EvalCase(
        id="case-1",
        category="approval",
        question="q",
        forbidden_review_status=["pending_review"],
    )

    def fake_search(_: Any) -> dict[str, Any]:
        return {"results": [{"id": "case-004", "title": "", "snippet": ""}]}

    result = evaluate_case(case, search_func=fake_search, source_status={"case-004": "pending_review"})

    assert result.approved_only_violations == [{"source_id": "case-004", "status": "pending_review"}]
    assert aggregate_metrics([result])["approved_only_violation_count"].value == 1


def test_empty_retrieval_count() -> None:
    case = EvalCase(id="case-1", category="empty", question="q", expected_source_ids=["doc-a"])

    result = evaluate_case(case, search_func=lambda _: {"results": []}, source_status={})
    metrics = aggregate_metrics([result])

    assert result.empty_retrieval is True
    assert metrics["empty_retrieval_count"].value == 1
    assert metrics["Hit@5"].value == 0


def test_latency_statistics_and_unavailable_metric() -> None:
    results = [
        EvalCaseResult("a", "c", "q", [], "", 0, 1.0, {}, {}, None, [], [], [], True),
        EvalCaseResult("b", "c", "q", [], "", 0, 2.0, {}, {}, None, [], [], [], True),
        EvalCaseResult("c", "c", "q", [], "", 0, 100.0, {}, {}, None, [], [], [], True),
    ]

    metrics = aggregate_metrics(results)

    assert metrics["average_latency_ms"].value == 34.333
    assert metrics["p50_latency_ms"].value == 2.0
    assert metrics["p95_latency_ms"].value == 100.0
    assert metrics["fallback_count"].available is False


def test_report_output(tmp_path) -> None:
    dataset = EvalDataset("test", "dataset", "now", "purpose", [EvalCase("case-1", "cat", "q")])
    mode = EvalMode("keyword", "desc", {"RAG_VECTOR_STORE": "off"})
    result = EvalCaseResult(
        id="case-1",
        category="cat",
        question="q",
        returned_source_ids=[],
        top_result_id="",
        result_count=0,
        latency_ms=1.0,
        hit_at={"Hit@1": None, "Hit@3": None, "Hit@5": None},
        recall_at={"Recall@1": None, "Recall@3": None, "Recall@5": None},
        reciprocal_rank=None,
        forbidden_source_violations=[],
        approved_only_violations=[],
        keyword_hits=[],
        empty_retrieval=True,
    )
    metrics = aggregate_metrics([result])
    report = build_report(dataset, mode, [result], metrics, {"commit": "abc", "working_tree": "clean"}, {})

    json_path, md_path = write_report(report, tmp_path, "report")

    assert json_path.exists()
    assert md_path.exists()
    assert "fallback_count" in json.loads(json_path.read_text(encoding="utf-8"))["unavailable_metrics"]
    assert "RAG Retrieval Baseline" in md_path.read_text(encoding="utf-8")


def test_evaluate_dataset_uses_mode_env(monkeypatch) -> None:
    dataset = EvalDataset("test", "dataset", "now", "purpose", [EvalCase("case-1", "cat", "q")])
    mode = EvalMode("keyword", "desc", {"RAG_VECTOR_STORE": "off"})

    def fake_search(_: Any) -> dict[str, Any]:
        assert Path.cwd()
        return {"results": []}

    case_results, metrics = evaluate_dataset(dataset, mode, search_func=fake_search)

    assert case_results[0].empty_retrieval is True
    assert metrics["empty_retrieval_count"].value == 1
