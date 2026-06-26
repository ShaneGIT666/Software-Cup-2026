# 官方赛题符合度矩阵（最终交付版）

更新时间：2026-06-26

## 结论

本项目按“设备检修知识检索与作业辅助系统”交付，主链路覆盖资料入库、解析、pending_review 审核隔离、approved 检索、标准作业指引、RAG 建议、证据引用、案例经验沉淀、知识关系网络和目标环境复验。增强能力采用可降级方案，默认不因 MinerU、OCR、视觉模型或向量库不可用而中断主链路。

## 符合度矩阵

| 赛题要求 | 当前实现 | 关键接口/文件 | 验证方式 | 状态 |
|---|---|---|---|---|
| 支持本地或云端大模型服务 | OpenAI-compatible LLM，可接 Qwen 服务；mock 仅兜底 | `backend/app/llm_adapter.py`、`/api/providers/status`、`/api/providers/llm/validate` | Provider status、真实 LLM 冒烟 | 已实现 |
| PC Web 可视化界面 | Vue + Element Plus 工作台，展示检索、资料、审核、RAG、图谱 | `frontend/src/App.vue` | `npm run build`、页面截图 | 已实现 |
| 文本、故障图片、设备型号输入 | 新增 `/api/multimodal/diagnosis`，前端提供图片诊断入口 | `backend/app/main.py`、`QueryPanel.vue` | `tests/test_multimodal_diagnosis.py` | 已实现 |
| 精准语义检索与跨模态匹配 | 关键词、SQLite/hash 向量兜底、可选 Qdrant/sqlite-vec；图片线索扩展 query context | `backend/app/retrieval/`、`vector_store.py`、`main.py` | eval runner、搜索接口冒烟 | 准生产原型 |
| 快速调取检修手册等资源 | approved 手册、文档 chunk、案例可检索并保留 citation | `backend/app/services.py`、`evidence_pack.py` | 搜索、RAG 测试 | 已实现 |
| 标准化作业指引 | RAG 输出含检查步骤、维修步骤、安全、验收、检修等级说明 | `backend/app/evidence_pack.py`、`maintenance_guidance.py` | `tests/test_maintenance_workflow_guidance.py` | 已实现 |
| 个性化流程推送 | 前端选择 `maintenanceLevel`，后端生成作业前准备、风险控制、合规校验 | `schemas.py`、`rag.py`、`llm_adapter.py` | RAG smoke | 已实现 |
| 降低操作失误 | high/critical 风险提示人工复核，证据不足明确“不确定” | `evidence_pack.py` | evidence pack 测试 | 已实现 |
| 一线人员上传案例/经验 | 案例提交支持经验总结、教训、检修等级，默认 pending_review | `services.py`、`CaseCreateRequest` | `tests/test_case_experience_review_flow.py` | 已实现 |
| 审核后纳入知识 | 案例、chunk 审核通过后才进入检索和索引同步 | `review_workbench.py`、`knowledge.py` | 审核流测试 | 已实现 |
| 人工标注与修正大模型输出 | chunk revision 生成 revision 和审计事件，并同步索引 | `knowledge.py` | `tests/test_chunk_revision_audit.py` | 已实现 |
| 知识图谱/关系网络 | 轻量 approved-only 关系网络，含 device、component、fault、chunk、case、document、review | `knowledge_graph.py` | `tests/test_knowledge_graph_approved_only.py` | 已实现 |
| LoongArch/银河麒麟运行闭环 | 提供 `scripts/loongarch-final-verify.sh`，以目标环境实测为准 | `docs/testing/loongarch-final-verification.md` | VM 执行记录 | 待目标环境最终复验 |

## 风险边界

- MinerU、OCR、真实视觉模型在目标环境是否可用，以 LoongArch/Kylin 实测为准；不可用时自动降级，不阻塞上传、审核、检索、RAG 主链路。
- 向量增强优先采用 LoongArch 可运行的本地方案；若外部向量服务不可部署，则使用 SQLite/hash fallback，并在报告中标注。
- 所有图片分析结果默认 pending_review。审核前只作为诊断输入线索，不作为正式 evidence pack。
