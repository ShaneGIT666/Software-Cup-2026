from __future__ import annotations

from backend.app.evidence_pack import build_evidence_pack


def test_evidence_pack_preserves_retrieval_diagnostics() -> None:
    pack = build_evidence_pack(
        [
            {
                "id": "chunk-diagnostics",
                "title": "diagnostics",
                "sourceType": "document",
                "sourceName": "unit",
                "documentId": "doc-diagnostics",
                "chunkId": "chunk-diagnostics",
                "snippet": "diagnostics",
                "confidence": 0.9,
                "reviewStatus": "approved",
                "retrievalSource": "sqlite",
                "sourceRetrievers": ["keyword", "vector"],
                "scoreBreakdown": {
                    "score": 18,
                    "retrievalMode": "rrf",
                    "fusionScore": 0.03,
                    "vectorDistance": 0.2,
                    "embeddingProvider": "hash",
                },
            }
        ]
    )

    item = pack["items"][0]
    assert item["retrievalSource"] == "sqlite"
    assert item["retrievalMode"] == "rrf"
    assert item["sourceRetrievers"] == ["keyword", "vector"]
    assert item["fusionScore"] == 0.03
    assert item["vectorDistance"] == 0.2
    assert item["embeddingProvider"] == "hash"
