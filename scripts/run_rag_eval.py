from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.evaluation.dataset_loader import load_eval_dataset
from backend.app.evaluation.report_writer import build_report, write_report
from backend.app.evaluation.retrieval_evaluator import EVAL_MODES, evaluate_dataset


DEFAULT_DATASET = PROJECT_ROOT / "data" / "evaluation" / "rag-eval-template.json"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "data" / "evaluation" / "reports"
CONFIG_KEYS = [
    "APP_EXAMPLES_DIR",
    "APP_KNOWLEDGE_DIR",
    "RAG_VECTOR_STORE",
    "RAG_EMBEDDING_PROVIDER",
    "OPENAI_EMBEDDING_MODEL",
    "OPENAI_BASE_URL",
    "REMOTE_API_MODE",
    "LLM_PROVIDER",
]


def git_value(args: list[str], default: str = "unknown") -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip() or default
    except Exception:
        return default


def git_info() -> dict[str, Any]:
    status = git_value(["status", "--short"], default="")
    return {
        "commit": git_value(["rev-parse", "HEAD"]),
        "branch": git_value(["branch", "--show-current"]),
        "working_tree": "dirty" if status else "clean",
        "status_short": status.splitlines(),
    }


def display_path(path: str | Path) -> str:
    path_obj = Path(path)
    try:
        return str(path_obj.resolve().relative_to(PROJECT_ROOT.resolve())).replace("\\", "/")
    except Exception:
        if "software-cup-rag-eval-" in str(path_obj):
            return "<temporary>/knowledge"
        return str(path_obj)


def config_summary(mode_overrides: dict[str, str], knowledge_dir: Path) -> dict[str, str]:
    summary: dict[str, str] = {}
    for key in CONFIG_KEYS:
        if key == "APP_EXAMPLES_DIR":
            value = display_path(os.environ.get(key, str(PROJECT_ROOT / "data" / "examples")))
        elif key == "APP_KNOWLEDGE_DIR":
            value = display_path(knowledge_dir)
        else:
            value = mode_overrides.get(key, os.environ.get(key, ""))
        summary[key] = value
    return summary


def mode_names(value: str) -> list[str]:
    if value == "all":
        return ["keyword", "chroma_off", "llm_mock", "pending_review"]
    return [value]


def basename_for(mode_name: str, baseline: bool, run_date: str) -> str:
    normalized = mode_name.replace("_", "-")
    prefix = "rag-baseline" if baseline else "rag-run"
    return f"{prefix}-{normalized}-{run_date}"


def print_summary(report: dict[str, Any], json_path: Path, md_path: Path) -> None:
    metrics = report["metrics"]
    print(f"\nRAG eval mode: {report['mode']['name']}")
    print(f"dataset: {report['dataset']['id']} ({report['dataset']['case_count']} cases)")
    print(f"git: {report['git']['commit']} / {report['git']['working_tree']}")
    print(f"Hit@1: {metrics['Hit@1']['value']}  Hit@3: {metrics['Hit@3']['value']}  Hit@5: {metrics['Hit@5']['value']}")
    print(f"Recall@5: {metrics['Recall@5']['value']}  MRR: {metrics['MRR']['value']}")
    print(
        "violations: "
        f"forbidden={metrics['forbidden_source_violation_count']['value']}, "
        f"approved_only={metrics['approved_only_violation_count']['value']}, "
        f"empty={metrics['empty_retrieval_count']['value']}"
    )
    print(
        "latency ms: "
        f"avg={metrics['average_latency_ms']['value']}, "
        f"p50={metrics['p50_latency_ms']['value']}, "
        f"p95={metrics['p95_latency_ms']['value']}"
    )
    if report["unavailable_metrics"]:
        print(f"unavailable: {', '.join(report['unavailable_metrics'].keys())}")
    print(f"json: {json_path}")
    print(f"markdown: {md_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run lightweight retrieval evaluation against the current RAG baseline.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--mode", choices=["all", *EVAL_MODES.keys()], default="keyword")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--baseline", action="store_true", help="Use stable baseline filenames instead of rag-run filenames.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dataset = load_eval_dataset(args.dataset)
    examples_dir = os.environ.get("APP_EXAMPLES_DIR", str(PROJECT_ROOT / "data" / "examples"))
    os.environ["APP_EXAMPLES_DIR"] = examples_dir

    with tempfile.TemporaryDirectory(prefix="software-cup-rag-eval-") as temp_dir:
        knowledge_dir = Path(temp_dir) / "knowledge"
        os.environ["APP_KNOWLEDGE_DIR"] = str(knowledge_dir)
        for name in mode_names(args.mode):
            mode = EVAL_MODES[name]
            case_results, metrics = evaluate_dataset(dataset, mode, top_k=args.top_k)
            report = build_report(
                dataset=dataset,
                mode=mode,
                case_results=case_results,
                metrics=metrics,
                git_info=git_info(),
                config_summary=config_summary(mode.env_overrides, knowledge_dir),
            )
            basename = basename_for(mode.name, args.baseline, args.date)
            json_path, md_path = write_report(report, args.reports_dir, basename)
            print_summary(report, json_path, md_path)


if __name__ == "__main__":
    main()
