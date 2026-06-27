# 官方赛题符合度矩阵（最终交付版）

更新时间：2026-06-27

## 状态口径

状态列只使用以下枚举：

- 已完成
- 已完成但需复验
- 部分完成
- 未完成
- 不适用

## 结论

本项目按“设备检修知识检索与作业辅助系统”交付。主链路覆盖资料入库、解析、pending_review 审核隔离、approved-only 检索、Evidence Pack、结构化 RAG 作业指引、案例/经验沉淀、人工修正、审计流水、轻量知识关系网络和 LoongArch/Kylin 目标环境复验。增强能力全部保留 fallback，不把真实 LLM、真实 OCR、真实多模态、Chroma、Qdrant、sqlite-vec 或 MinerU 作为比赛演示硬依赖。

## 符合度矩阵

| 赛题要求 | 当前实现 | 关键接口/文件 | 验证方式 | 状态 |
|---|---|---|---|---|
| 支持本地或云端大模型服务 | OpenAI-compatible LLM，可接比赛 Qwen 服务；mock/offline 为兜底 | `backend/app/llm_adapter.py`、`/api/providers/status`、`/api/providers/llm/validate` | 历史 Qwen 小样本通过；最终 Key 需现场复验 | 已完成但需复验 |
| PC Web 或 App 可视化界面 | Vue + Element Plus PC Web 工作台，展示检索、资料、审核、RAG、图谱 | `frontend/src/App.vue` | Windows 和 LoongArch/Kylin 前端构建通过 | 已完成 |
| 文本、故障图片、设备型号输入 | 支持设备型号、故障描述、检修等级、故障图片；图片走 OCR/多模态线索分析 | `/api/search`、`/api/rag/answer`、`/api/multimodal/diagnosis` | `tests/test_multimodal_diagnosis.py`、API 冒烟 | 已完成 |
| 精准语义检索与跨模态匹配 | 关键词 + RRF + Evidence Pack；图片/OCR/多模态线索转文本进入 query context；向量增强可选 | `backend/app/retrieval/`、`vector_store.py`、`main.py` | eval runner、搜索冒烟、fallback 测试 | 部分完成 |
| 快速调取检修手册等资源 | approved 手册、文档 chunk、案例可检索并保留 citation | `backend/app/services.py`、`evidence_pack.py` | 后端全量测试、RAG smoke | 已完成 |
| 标准化作业指引 | RAG 输出初步判断、检修等级说明、作业前准备、检查步骤、维修步骤、风险控制、合规校验、安全、验收、引用、不确定信息 | `backend/app/evidence_pack.py`、`maintenance_guidance.py` | `tests/test_maintenance_workflow_guidance.py` | 已完成 |
| 按设备类型与检修等级个性化推送流程 | `maintenanceLevel` / `riskLevel` / `deviceType` 进入请求模型，影响作业前准备、风险控制、合规校验 | `schemas.py`、`rag.py`、`llm_adapter.py` | RAG smoke、官方 smoke | 已完成 |
| 降低操作失误率 | high/critical 风险提示人工复核；证据不足明确“不确定”；禁止编造参数 | `evidence_pack.py`、`llm_adapter.py` | evidence pack 测试 | 已完成 |
| 一线人员上传案例/经验总结 | 案例提交支持 `experienceSummary`、`lessonsLearned`、`maintenanceLevel`，默认 pending_review | `services.py`、`CaseCreateRequest` | `tests/test_case_experience_review_flow.py` | 已完成 |
| 审核后纳入知识库/知识图谱 | 案例、chunk 审核通过后进入检索；轻量关系网络只纳入 approved 对象 | `review_workbench.py`、`knowledge.py`、`knowledge_graph.py` | 审核流、approved-only 图谱测试 | 已完成 |
| 手动标注与修正大模型输出 | chunk revision 生成 revision、审计事件，并同步索引 | `knowledge.py` | `tests/test_chunk_revision_audit.py` | 已完成 |
| 知识图谱能力 | 轻量知识关系网络/知识图谱原型，节点含 device、component、fault、chunk、case、document、review | `knowledge_graph.py` | `tests/test_knowledge_graph_approved_only.py` | 已完成 |
| LoongArch / 银河麒麟部署运行 | 默认依赖改为 `uvicorn==0.34.0` + `pydantic<2`；VM 可迁移主测试集、前端构建和 API 冒烟已通过 | `scripts/loongarch-final-verify.sh`、`docs/testing/loongarch-final-verification.md` | `105 passed in 170.44s`，前端 `built in 21.41s` | 已完成但需复验 |

## 风险边界

- 真实 LLM：已具备 OpenAI-compatible 接入能力，但最终比赛现场必须使用目标 Key 复验。
- 真实 OCR/多模态：当前不作为主链路硬依赖；不可用时 mock/OCR fallback 保证诊断和审核链路不断。
- 跨模态匹配：当前为 OCR/多模态线索转文本进入 RAG；生产级图文向量检索是后续增强，不在本次硬承诺内。
- 向量能力：SQLite/hash fallback 是比赛稳定兜底；Qdrant、sqlite-vec、Chroma 均为可选增强。
- 知识图谱：当前是轻量知识关系网络/知识图谱原型，不宣称完整工业知识图谱平台。
- 外部维修 PDF：只做本地临时测试，不提交官方 PDF 或来源不明资料。
