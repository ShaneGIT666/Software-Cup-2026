# 全局收口审计与剩余缺口清单

更新时间：2026-06-24
适用对象：项目成员、指导老师、后续接手 Agent
审计方式：基于当前工作区代码、测试记录、提交历史和项目文档逐项核对，不以聊天上下文替代代码事实。

## 1. 当前 Git 与工程状态

当前分支状态：

```text
branch: main
remote: origin/main
ahead: 13 commits
head: ef66ad2 feat: add safety rule engine
working tree: clean before this audit document
```

最近 10 轮关键提交：

| 轮次 | Commit | 内容 |
| --- | --- | --- |
| 1 | `5262227` | 第一轮架构评估与评测模板 |
| 2 | `3a17a2c` | RAG evaluation runner 与 baseline |
| 3 | `caca435` | 抽取 retrieval pipeline，保持行为不变 |
| 4 | `2487c80` | 统一 RetrievalHit 协议与 metadata filter |
| 5 | `011c849` | RRF 检索融合 |
| 6 | `3707eb6` | reranker provider 与 fallback |
| 7 | `df8f01b` | evidence pack 与结构化 RAG 输出 |
| 8 | `918208e` | 前端 evidence cards |
| 9 | `32ee9e2` | Corrective RAG 证据质量控制 |
| 10 | `ef66ad2` | 安全规则引擎 |

第十轮提交前已验证：

```text
backend full tests: 124 passed in 21.89s
frontend build: passed, only existing Vite chunk size warning
rag baseline keyword:
  Hit@1/3/5 = 0.9 / 0.9 / 0.9
  Recall@5 = 0.7333
  MRR = 0.9
  forbidden violations = 0
  approved-only violations = 0
git diff --check: passed
```

## 2. 赛题要求对齐情况

| 赛题能力 | 当前实现状态 | 代码和接口落点 | 审计结论 |
| --- | --- | --- | --- |
| 本地或云端大模型服务 | 支持 mock、本地兜底、OpenAI-compatible 云端文本 RAG、多模态 provider 验证入口 | `backend/app/llm_adapter.py`、`backend/app/provider_policy.py`、`/api/providers/status`、`/api/providers/llm/validate` | 已形成可演示闭环；真实云端依赖网络、Key 和 provider payload，需要演示前复验 |
| PC Web 可视化界面 | 已有 Vue Web 控制台，覆盖检索、RAG、资料、流程、图谱、案例、审核、证据卡、安全提示 | `frontend/src/*`、FastAPI 静态托管 | 已满足原型展示；仍需最终视觉和演示路径 QA |
| 多模态知识检索 | 支持文本、设备型号、故障现象、图片/PDF 多模态分析、OCR provider、MinerU 文档解析、Chroma 可选向量召回 | `knowledge.py`、`parser_router.py`、`mineru_adapter.py`、`ocr_adapter.py`、`multimodal_adapter.py`、`retrieval/` | 准生产原型级。真实 OCR/视觉模型和跨模态语义质量仍是增强项，不能按生产稳定能力过度承诺 |
| 标准化作业指引 | 支持 workflow 查询、RAG 结构化输出、evidence pack、Corrective RAG、安全规则复核提示 | `/api/workflows/{id}`、`evidence_pack.py`、`corrective_rag.py`、`safety_rules.py` | 已从普通回答升级为“检索证据 + 步骤 + 风险复核”的作业辅助链路 |
| 知识沉淀与更新 | 案例 pending_review/approved/rejected 闭环；资料入库默认 pending_review；知识片段可人工修正并生成 revision；approved 才进检索/Chroma | `services.py`、`knowledge.py`、`vector_store.py` | 核心隔离规则成立；统一资料片段 approve/reject 工作台仍未补齐 |
| 生产级部署约束 | 有 Windows 本地开发、Docker/LoongArch/Kylin 文档和最小验证记录 | `docs/deployment/*`、`Dockerfile`、脚本 | 基础可部署性已验证；增强依赖 MinerU/OCR/Chroma 在 LoongArch/Kylin 上仍需单独验证 |

## 3. 当前主链路闭环

### 3.1 资料入库与解析

已实现链路：

```text
POST /api/knowledge/documents
-> file validation
-> parser_router
-> MinerU adapter for PDF/DOCX/PPTX/XLSX when enabled
-> fallback parser or multimodal-ready status
-> raw_parse_result.json / parsed.md / assets
-> document chunks with review_status=pending_review
```

审计结论：

1. 自动解析结果不会直接进入正式 RAG 检索。
2. `pending_review` 隔离在检索和 Chroma 同步层均有代码约束。
3. 当前资料片段支持查看、修正和 revision；缺少统一的资料片段 approve/reject API 和审核日志。

### 3.2 检索与证据

已实现链路：

```text
query normalization
-> keyword retrieval
-> vector retrieval
-> metadata filter
-> RRF fusion
-> reranker fallback
-> approved-only filter
-> evidence pack
-> RAG generation
```

审计结论：

1. 默认检索只应返回 approved 知识。
2. 设备型号、故障现象、部件、故障码等字段已进入 `RetrievalHit` 和前端 evidence cards。
3. Chroma 不可用时向量召回返回空结果，不阻断关键词主链路。
4. 检索评测 runner 已保存改造前 baseline，后续优化可以对比。

### 3.3 RAG 与作业辅助

已实现输出结构：

```text
【初步判断】
【建议检查步骤】
【建议维修步骤】
【安全提醒】
【验收标准】
【引用证据】
【不确定信息】
```

增强能力：

1. `evidencePack` 保留 chunk/source/page/section/version/reviewStatus/riskLevel。
2. Corrective RAG 会在无证据、单一来源、无验收标准、高风险证据等情况下提示谨慎或补充检索。
3. 安全规则引擎会对高风险、电气隔离、高温冷却、旋转部件、燃油通风、参数缺失等情况生成复核提示。
4. LLM 失败时回退到 mock/template，不阻断接口。

审计结论：

该链路已经从“普通 RAG Demo”推进到“证据驱动的检修建议原型”。但安全规则仍是轻量启发式规则，不是完整 EHS/行业规程引擎。

### 3.4 案例回流与知识沉淀

已实现链路：

```text
POST /api/cases
-> status=pending_review
-> GET /api/cases?status=pending_review
-> PATCH /api/cases/{case_id}/review
-> approved case enters retrieval
-> rejected case excluded
```

审计结论：

案例级审核闭环已成立。审核字段仍偏轻量，缺少统一 reviewer/action/review_time 审核事件表，不适合直接宣称生产审计追踪完备。

## 4. 仍需谨慎表述的能力边界

1. 真实多模态识别能力取决于外部 provider、模型、图片质量和网络，mock 只能证明链路不断。
2. OCR provider 已接入，但 RapidOCR/Tesseract/MinerU 等增强依赖需要在目标国产化环境逐项复验。
3. Chroma 与真实 embedding 已作为可选增强接入；hash embedding 是 fallback，不代表生产语义 embedding 质量。
4. 轻量知识图谱是关系展示和辅助上下文，不是完整图数据库或 GraphRAG 平台。
5. 当前资料片段没有统一 approve/reject 工作台，只有 pending_review 可见、人工修正 revision 和 approved-only 检索隔离。
6. 当前系统状态页以 provider 状态为主，知识库统计、最近解析任务、最近索引时间等运维信息仍需补齐。
7. JSON 文件持久化适合比赛原型和低并发演示；生产级场景建议迁移 SQLite/PostgreSQL 或加入文件锁与备份恢复。

## 5. 剩余缺口优先级

### P0: 赛题闭环补齐

1. 统一审核工作台：把资料解析结果、OCR 结果、多模态分析结果、知识片段、维修案例、人工修正放入统一审核列表。
2. 系统状态页增强：展示 LLM、Embedding、OCR、MinerU、Chroma、知识片段数量、状态计数、最近索引时间、最近解析任务和 fallback。
3. 资料片段状态机补全：`draft / pending_review / approved / rejected / deprecated / replaced` 需要统一 API 和前端操作。

### P1: 准生产韧性

1. 解析任务异步化：大 PDF、MinerU 和多模态分析不应长期占用同步请求。
2. 审核日志事件化：记录 reviewer、review_time、action、reason、before/after revision。
3. 存储层加固：从 JSON 文件迁移到 SQLite/PostgreSQL，或至少增加文件锁、备份和恢复脚本。
4. 配置一致性验证：把 `.env.example`、`provider_policy`、实际读取字段做成持续测试。

### P2: 效果与答辩材料

1. 将 RAG 评测集从 12 条扩充到 80-150 条，并按设备型号、故障码、安全规则、证据不足、pending_review 隔离分类统计。
2. 对 RRF、reranker、Corrective RAG、安全规则分别保存前后指标。
3. 完成最终演示脚本、PPT、视频脚本、部署复验记录。

## 6. 建议下一轮开发顺序

1. 第十二轮：完善系统状态页和 `/api/providers/status` 附带的知识库统计字段。
2. 第十三轮：统一审核工作台最小闭环，先支持资料片段 approve/reject/reason/reviewer/review_time。
3. 第十四轮：资料片段完整状态机和 revision 审核事件。
4. 第十五轮：存储层加固和配置一致性测试。
5. 第十六轮：LoongArch/Kylin 上的增强依赖复验记录。

## 7. 当前可对外讨论口径

可以说：

1. 项目已经具备上传、解析、待审核、检索、证据引用、RAG 建议、作业流程、案例回流和安全复核的闭环。
2. 系统支持本地兜底和 OpenAI-compatible 云端大模型服务，具备 PC Web 可视化界面。
3. 检索已从单一关键词升级为关键词、向量、metadata、RRF、reranker fallback 和 evidence pack 的轻量 pipeline。
4. 自动解析和模型输出默认不直接污染正式知识库，必须通过审核或人工修正后才能进入正式检索。
5. 当前定位是准生产级比赛原型，不是已经完成所有生产审计、并发、权限和工业安全认证的商用系统。

不要说：

1. 真实 OCR、真实视觉诊断、MinerU、Chroma、云端模型在所有国产化环境都已稳定可用。
2. 轻量知识图谱等同于完整图数据库或成熟 GraphRAG。
3. 12 条评测样例足以证明最终检索效果。
4. 当前资料片段已经拥有完整统一审核工作台。
