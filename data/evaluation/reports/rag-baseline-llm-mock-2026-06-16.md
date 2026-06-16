# RAG Retrieval Baseline - llm_mock

- Generated at: `2026-06-16T03:35:57.206985Z`
- Git commit: `526222742e4a1d25564427a7b33a9df8156b268b`
- Working tree: `dirty`
- Dataset: `maintenance-rag-seed-baseline` / schema `0.2.0`
- Cases: `12`
- Mode: Retrieval with remote LLM disabled/mock; search should be unchanged.

## Config Summary

- `APP_EXAMPLES_DIR`: `data/examples`
- `APP_KNOWLEDGE_DIR`: `<temporary>/knowledge`
- `RAG_VECTOR_STORE`: `off`
- `RAG_EMBEDDING_PROVIDER`: `hash`
- `OPENAI_EMBEDDING_MODEL`: ``
- `OPENAI_BASE_URL`: ``
- `REMOTE_API_MODE`: `off`
- `LLM_PROVIDER`: `mock`

## Category Counts

- `device_model_exact`: 1
- `semantic_symptom`: 1
- `safety`: 1
- `metadata_filter`: 1
- `electrical_safety`: 1
- `component`: 1
- `risk_high`: 1
- `pending_review_isolation`: 1
- `insufficient_evidence`: 1
- `semantic_weak_keyword`: 1
- `keyword_fallback`: 1
- `llm_disabled_retrieval`: 1

## Summary Metrics

| Metric | Value | Available | Reason |
| --- | --- | --- | --- |
| Hit@1 | 0.6 | True |  |
| Recall@1 | 0.35 | True |  |
| Hit@3 | 0.9 | True |  |
| Recall@3 | 0.6167 | True |  |
| Hit@5 | 0.9 | True |  |
| Recall@5 | 0.7 | True |  |
| MRR | 0.7 | True |  |
| forbidden_source_violation_count | 2 | True |  |
| approved_only_violation_count | 0 | True |  |
| empty_retrieval_count | 2 | True |  |
| fallback_count | None | False | search_knowledge does not expose per-query fallback events; process-global provider fallback is not counted. |
| average_latency_ms | 0.931 | True |  |
| p50_latency_ms | 0.865 | True |  |
| p95_latency_ms | 0.985 | True |  |

## Unavailable Metrics

- `fallback_count`: search_knowledge does not expose per-query fallback events; process-global provider fallback is not counted.

## Case Results

| Case | Category | Top Result | Count | Latency ms | Hit@1 | Hit@3 | Hit@5 | Recall@5 | RR | Forbidden | Approved-only |
| --- | --- | --- | ---: | ---: | --- | --- | --- | ---: | ---: | --- | --- |
| eval-001 | device_model_exact | doc-001 | 5 | 0.865 | True | True | True | 1.0 | 1.0 |  |  |
| eval-002 | semantic_symptom | doc-001 | 5 | 0.817 | True | True | True | 0.6667 | 1.0 |  |  |
| eval-003 | safety | doc-001 | 5 | 0.925 | True | True | True | 1.0 | 1.0 |  |  |
| eval-004 | metadata_filter | doc-004 | 5 | 1.533 | False | True | True | 0.6667 | 0.3333 | doc-001 |  |
| eval-005 | electrical_safety | doc-007 | 5 | 0.922 | True | True | True | 1.0 | 1.0 |  |  |
| eval-006 | component | doc-008 | 5 | 0.905 | True | True | True | 0.6667 | 1.0 | doc-003 |  |
| eval-007 | risk_high | doc-004 | 5 | 0.833 | False | True | True | 0.6667 | 0.3333 |  |  |
| eval-008 | pending_review_isolation | doc-001 | 5 | 0.843 | None | None | None | None | None |  |  |
| eval-009 | insufficient_evidence |  | 0 | 0.856 | None | None | None | None | None |  |  |
| eval-010 | semantic_weak_keyword |  | 0 | 0.985 | False | False | False | 0.0 | 0.0 |  |  |
| eval-011 | keyword_fallback | doc-008 | 5 | 0.83 | True | True | True | 0.6667 | 1.0 |  |  |
| eval-012 | llm_disabled_retrieval | doc-004 | 5 | 0.853 | False | True | True | 0.6667 | 0.3333 |  |  |

## Failed Cases

- `eval-004`
- `eval-006`
- `eval-007`
- `eval-010`
- `eval-012`

## Forbidden Source Violations

- `eval-004`: doc-001
- `eval-006`: doc-003

## Approved-only Violations

None.
