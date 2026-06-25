from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.evaluation.dataset_loader import load_eval_dataset
from scripts.prepare_external_test_data import (
    AI4I_SAMPLE_ROWS,
    ExternalDataError,
    download_sapid_pdf,
    generate_ai4i_cases,
    load_manifest,
    run,
    validate_manifest,
    write_ai4i_assets,
)


def test_external_manifest_loads_and_has_curated_assets() -> None:
    manifest = load_manifest()

    asset_ids = {asset["id"] for asset in manifest["assets"]}
    assert "sapid-maintenance-manual-pdf" in asset_ids
    assert "uci-ai4i-2020-sample" in asset_ids
    assert manifest["policy"]["no_unclear_copyright_manuals"] is True


def test_external_manifest_rejects_duplicate_asset_ids() -> None:
    manifest = {
        "schema_version": "test",
        "assets": [
            {
                "id": "dup",
                "title": "A",
                "source_type": "pdf",
                "source_url": "https://example.test/a.pdf",
                "license": "test",
                "local_path": "data/external-test/pdf/a.pdf",
                "commit_policy": "test",
                "max_mb": 1,
            },
            {
                "id": "dup",
                "title": "B",
                "source_type": "csv",
                "source_url": "https://example.test/b.csv",
                "license": "test",
                "local_path": "data/external-test/tabular/b.csv",
                "commit_policy": "test",
                "max_mb": 1,
            },
        ],
    }

    with pytest.raises(ExternalDataError, match="duplicate asset ids"):
        validate_manifest(manifest)


def test_prepare_external_dry_run_does_not_write(tmp_path) -> None:
    summary = run("ai4i", tmp_path, max_mb=1, dry_run=True)

    assert summary["dry_run"] is True
    assert summary["errors"] == []
    assert not (tmp_path / "tabular" / "ai4i2020-sample.csv").exists()
    assert not (tmp_path / "cases" / "ai4i-generated-maintenance-cases.json").exists()


def test_write_ai4i_assets_outputs_pending_review_cases(tmp_path) -> None:
    written = write_ai4i_assets(tmp_path)
    cases_path = tmp_path / "cases" / "ai4i-generated-maintenance-cases.json"
    csv_path = tmp_path / "tabular" / "ai4i2020-sample.csv"

    assert str(csv_path) in written[0] or "ai4i2020-sample.csv" in written[0]
    assert csv_path.exists()
    payload = json.loads(cases_path.read_text(encoding="utf-8"))
    assert len(payload["cases"]) == len(AI4I_SAMPLE_ROWS)
    assert {case["review_status"] for case in payload["cases"]} == {"pending_review"}
    assert {case["source_type"] for case in payload["cases"]} == {"external_dataset"}
    for case in payload["cases"]:
        assert case["id"].startswith("external-ai4i-case-")
        assert case["device_model"].startswith("AI4I-")
        assert case["content"]
        assert case["recommended_action"]


def test_generate_ai4i_cases_rejects_duplicate_ids() -> None:
    duplicate_rows = [AI4I_SAMPLE_ROWS[0], dict(AI4I_SAMPLE_ROWS[0])]

    with pytest.raises(ExternalDataError, match="duplicate generated case id"):
        generate_ai4i_cases(duplicate_rows)


def test_sapid_pdf_download_rejects_non_pdf(tmp_path, monkeypatch) -> None:
    manifest = load_manifest()

    def fake_download_file(_: str, destination: Path, __: float) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("not a pdf", encoding="utf-8")

    monkeypatch.setattr("scripts.prepare_external_test_data.download_file", fake_download_file)

    with pytest.raises(ExternalDataError, match="not a valid PDF"):
        download_sapid_pdf(tmp_path, manifest, max_mb=1)
    assert not (tmp_path / "pdf" / "maintenance-manual-sapid.pdf").exists()


def test_external_eval_dataset_loads() -> None:
    dataset = load_eval_dataset(Path("data/evaluation/rag-eval-external-dev.json"))

    assert dataset.dataset_id == "maintenance-rag-external-dev-ai4i"
    assert len(dataset.cases) == 30
    assert dataset.category_counts()["ai4i_power_failure"] == 5
    assert dataset.cases[28].must_refuse is True
    assert "pending_review" in dataset.cases[28].forbidden_review_status
