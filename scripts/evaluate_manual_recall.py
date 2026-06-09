from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient


DEFAULT_MANUAL_PATH = Path("E:/Download/Downloads/摩托车发动机维修手册.pdf")
DEFAULT_QUERIES = [
    ("摩托车发动机", "无法启动"),
    ("摩托车发动机", "启动困难"),
    ("摩托车发动机", "火花塞"),
    ("摩托车发动机", "点火系统"),
    ("摩托车发动机", "压缩压力"),
    ("摩托车发动机", "怠速不稳"),
    ("摩托车发动机", "燃油供给"),
    ("摩托车发动机", "气门间隙"),
    ("摩托车发动机", "机油润滑"),
    ("摩托车发动机", "排气异常"),
    ("摩托车发动机", "离合器"),
    ("摩托车发动机", "链条张紧"),
]


def parse_topks(value: str) -> list[int]:
    topks = [int(item.strip()) for item in value.split(",") if item.strip()]
    if not topks:
        raise argparse.ArgumentTypeError("topks cannot be empty")
    if any(item <= 0 for item in topks):
        raise argparse.ArgumentTypeError("topks must be positive integers")
    return sorted(set(topks))


def first_document_rank(results: list[dict[str, Any]], document_id: str) -> int | None:
    for index, item in enumerate(results, start=1):
        if item.get("documentId") == document_id:
            return index
    return None


def hit_rate(hits: int, total: int) -> float:
    return round(hits / total, 4) if total else 0.0


def evaluate(manual_path: Path, topks: list[int], max_topk: int) -> dict[str, Any]:
    if not manual_path.exists():
        raise FileNotFoundError(f"manual PDF not found: {manual_path}")

    project_root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="software-cup-rag-eval-") as temp_dir:
        temp_path = Path(temp_dir)
        examples_dir = temp_path / "examples"
        knowledge_dir = temp_path / "knowledge"
        shutil.copytree(project_root / "data" / "examples", examples_dir)

        os.environ["APP_EXAMPLES_DIR"] = str(examples_dir)
        os.environ["APP_KNOWLEDGE_DIR"] = str(knowledge_dir)
        os.environ["REMOTE_API_MODE"] = "off"
        os.environ["RAG_VECTOR_STORE"] = "off"

        from backend.app.main import app

        client = TestClient(app)
        upload_response = client.post(
            "/api/knowledge/documents",
            files={"file": ("motorcycle-engine-repair-manual.pdf", manual_path.read_bytes(), "application/pdf")},
            data={"source_name": "official-motorcycle-engine-repair-manual"},
        )
        upload_response.raise_for_status()
        upload_payload = upload_response.json()["data"]
        document_id = upload_payload["id"]

        search_hits = {topk: 0 for topk in topks}
        citation_hits = {topk: 0 for topk in topks}
        rows: list[dict[str, Any]] = []

        for device_model, fault_text in DEFAULT_QUERIES:
            search_response = client.post(
                "/api/search",
                json={
                    "deviceModel": device_model,
                    "faultText": fault_text,
                    "inputType": "text",
                    "topK": max_topk,
                },
            )
            search_response.raise_for_status()
            search_results = search_response.json()["data"]["results"]
            rank = first_document_rank(search_results, document_id)
            for topk in topks:
                if rank is not None and rank <= topk:
                    search_hits[topk] += 1

            rag_response = client.post(
                "/api/rag/answer",
                json={
                    "deviceModel": device_model,
                    "faultText": fault_text,
                    "topK": max_topk,
                    "provider": "mock",
                    "includeGraphContext": True,
                },
            )
            rag_response.raise_for_status()
            rag_payload = rag_response.json()["data"]
            citations = rag_payload.get("citations", [])
            citation_rank = first_document_rank(citations, document_id)
            for topk in topks:
                if citation_rank is not None and citation_rank <= topk:
                    citation_hits[topk] += 1

            top_result = search_results[0] if search_results else {}
            rows.append(
                {
                    "deviceModel": device_model,
                    "faultText": fault_text,
                    "documentRank": rank,
                    "citationRank": citation_rank,
                    "topSourceType": top_result.get("sourceType", ""),
                    "topSourceName": top_result.get("sourceName", ""),
                    "topTitle": top_result.get("title", ""),
                    "graphEdgeCount": rag_payload.get("graphContext", {}).get("edgeCount", 0),
                }
            )

    query_count = len(DEFAULT_QUERIES)
    return {
        "manualPath": str(manual_path),
        "queryCount": query_count,
        "document": {
            "id": document_id,
            "chunkCount": upload_payload["chunkCount"],
            "parser": upload_payload["parser"],
            "status": upload_payload["status"],
        },
        "searchRecall": {
            f"Recall@{topk}": {
                "hits": search_hits[topk],
                "total": query_count,
                "rate": hit_rate(search_hits[topk], query_count),
            }
            for topk in topks
        },
        "ragCitationHit": {
            f"CitationHit@{topk}": {
                "hits": citation_hits[topk],
                "total": query_count,
                "rate": hit_rate(citation_hits[topk], query_count),
            }
            for topk in topks
        },
        "queries": rows,
        "metricScope": "source-document level; a query is counted as hit when any chunk from the official manual appears in TopK.",
    }


def print_text_report(report: dict[str, Any]) -> None:
    document = report["document"]
    print("Official manual RAG recall evaluation")
    print(f"manual: {report['manualPath']}")
    print(f"document: id={document['id']} chunks={document['chunkCount']} parser={document['parser']} status={document['status']}")
    print(f"queries: {report['queryCount']}")
    print("\nSearch source-document recall:")
    for metric, item in report["searchRecall"].items():
        print(f"- {metric}: {item['hits']}/{item['total']} = {item['rate']:.2%}")
    print("\nRAG citation hit:")
    for metric, item in report["ragCitationHit"].items():
        print(f"- {metric}: {item['hits']}/{item['total']} = {item['rate']:.2%}")
    print("\nPer-query detail:")
    for item in report["queries"]:
        print(
            f"- {item['deviceModel']} | {item['faultText']}: "
            f"documentRank={item['documentRank']}, citationRank={item['citationRank']}, "
            f"top={item['topSourceType']}/{item['topSourceName']}/{item['topTitle']}, "
            f"graphEdges={item['graphEdgeCount']}"
        )
    print(f"\nScope: {report['metricScope']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate source-document recall on the official motorcycle manual.")
    parser.add_argument("--manual", type=Path, default=DEFAULT_MANUAL_PATH, help="Path to the official manual PDF.")
    parser.add_argument("--topks", type=parse_topks, default=parse_topks("1,3,5"), help="Comma-separated K values.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    report = evaluate(args.manual, args.topks, max(args.topks))
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_text_report(report)


if __name__ == "__main__":
    main()
