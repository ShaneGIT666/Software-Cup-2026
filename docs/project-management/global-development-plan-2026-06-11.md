# 全局开发计划（基于 2026-06-11 现状）

本文用于后续团队讨论、任务拆分和 Coding Agent 接手。计划目标不是推倒重来，而是在现有 FastAPI + Vue + JSON/Chroma + MinerU/OCR/多模态 adapter 的基础上，把系统从“可演示 RAG 原型”推进到“准生产级检修知识检索与作业辅助原型”。

## 1. 当前基线

已确认能力：

1. PC Web 前端已具备检索、RAG、资料入库、知识片段查看/修正、案例提交审核、知识关系网络和 provider 状态展示的基础界面。
2. 后端已有 FastAPI 接口：`/api/search`、`/api/rag/answer`、`/api/diagnosis`、`/api/knowledge/documents`、`/api/knowledge/graph`、`/api/cases`、provider validate/status 等。
3. 文档解析已接入 `parser_router` 与 `mineru_adapter`，PDF/DOCX/PPTX/XLSX 优先 MinerU，失败 fallback；解析产物保存 `raw_parse_result.json`、`parsed.md`、`assets/`。
4. OCR 与本地/云端多模态 provider 已有 adapter 层，具备 mock fallback。
5. ChromaDB 与 embedding 已作为语义检索主方案之一，关键词检索保留为 fallback。
6. 解析生成的知识片段默认进入 `pending_review`，正式检索默认只使用 `approved` 或旧数据兼容片段。
7. 知识片段人工修正已有 revision 记录能力。
8. Windows 本地已验证 `tests/test_backend_api.py`：70 passed；前端 `npm.cmd run build` 通过。

当前暴露的问题：

1. 全量 `pytest tests -q` 在 240 秒内超时，并在 `tests/test_motorcycle_manual.py` 出现旧预期失败。
2. `tests/test_motorcycle_manual.py` 仍期望上传后 `status=indexed` 且立即可检索，但当前正确状态应为 `pending_review`。
3. 审核工作台只覆盖维修案例，资料解析结果、OCR 结果、多模态分析结果、知识片段、人工修正尚未形成统一审核动作。
4. 状态机字段已有雏形，但还没有完整统一 `draft / pending_review / approved / rejected / deprecated / replaced` 的 API 与前端操作。
5. RAG 输出还没有强制统一为“初步判断、检查步骤、维修步骤、安全提醒、验收标准、引用证据、不确定信息”。
6. 混合检索已经具备关键词 + Chroma，但流程、metadata filter、fusion、evidence pack、rerank 边界还需要显式化。
7. 系统状态页信息还不完整，缺少 MinerU、Chroma、索引时间、解析任务、知识状态计数等生产可观测字段。
8. MinerU 在 Windows 本地可用，但 LoongArch/Kylin 真实依赖尚未验收。
9. 运行期仍以 JSON 文件持久化为主，准生产场景下需要补充文件锁、SQLite 迁移或至少写入一致性保护。

## 2. 总体目标

短期目标：完成准生产级功能闭环，不急于做演示包装和评测内容。

核心闭环：

```text
资料上传
-> MinerU/OCR/多模态解析
-> pending_review
-> 审核/修正/拒绝
-> approved 后同步 Chroma
-> 混合检索召回 evidence pack
-> 标准化 RAG 检修建议
-> 一线案例沉淀
-> 再审核入库
-> 状态页可观测
```

工程原则：

1. 不做大范围重构，优先在现有模块上补接口、状态、测试。
2. 所有重依赖必须 fallback，不允许因为 MinerU、OCR、Chroma、LLM、embedding 不可用导致主流程崩溃。
3. 任何自动解析或模型输出默认不得进入正式知识库，必须 pending review。
4. 所有检修建议必须可追溯到 evidence。
5. 所有新增接口字段必须同步前端类型与展示。
6. 每个阶段完成后至少跑 `tests/test_backend_api.py` 和前端 build；涉及专项测试时同步修复测试口径。

## 3. 阶段计划

### P0：稳定现状与测试口径统一

周期：0.5 到 1 天  
优先级：最高  
目标：让仓库测试反映当前真实业务规则，避免后续开发踩旧预期。

任务：

1. 更新 `tests/test_motorcycle_manual.py`：
   - 上传文档后期望 `pending_review`。
   - 审核通过前不期望正式检索或 RAG citation。
   - 需要检索命中时，显式执行“审核通过”或构造 approved chunk。
2. 给 MinerU 真实解析相关测试加环境隔离：
   - 单元测试默认 `MINERU_ENABLED=false` 或 mock adapter。
   - 真实 MinerU 样本测试单独标记为 slow/integration。
3. 统一测试说明：
   - 当前稳定回归是 `tests/test_backend_api.py` 70 个用例。
   - 全量测试目标应恢复为全部通过。
4. 修正明显过期文档中的测试数量和状态描述。

验收：

```powershell
$env:MINERU_ENABLED="false"
.\backend\.venv\Scripts\python.exe -m pytest tests -q
cd frontend
npm.cmd run build
```

### P1：统一知识状态机与审核工作台

周期：2 到 3 天  
优先级：最高  
目标：把 pending_review 真正推进到可审核、可批准、可拒绝、可替换、可废弃。

后端任务：

1. 统一知识片段状态：
   - `draft`
   - `pending_review`
   - `approved`
   - `rejected`
   - `deprecated`
   - `replaced`
2. 新增审核对象模型或统一 review event：
   - 上传资料解析结果
   - OCR 结果
   - 多模态分析结果
   - 知识片段
   - 维修案例
   - 人工修正
3. 新增接口：
   - `GET /api/review/items?status=pending_review&type=...`
   - `POST /api/review/items/{id}/approve`
   - `POST /api/review/items/{id}/reject`
   - `POST /api/review/items/{id}/deprecate`
   - `POST /api/review/items/{id}/replace`
4. 审核记录必须包含：
   - `reviewer`
   - `review_time`
   - `action`
   - `reason`
   - `target_type`
   - `target_id`
   - `before`
   - `after`
5. 审核通过后自动同步 Chroma。
6. 拒绝必须记录原因，不同步 Chroma。
7. 修改后必须生成 revision；revision 后重新同步 approved chunk。

前端任务：

1. 扩展审核工作台，不再只审核维修案例。
2. 按对象类型筛选：资料、OCR、多模态、片段、案例、修正。
3. 展示 parsed markdown / OCR 文本 / 多模态分析摘要 / chunk evidence。
4. 审核按钮提供通过、拒绝、修正后通过。
5. 拒绝动作必须填写原因。

验收：

1. pending 片段不会出现在 `/api/search`。
2. approve 后能被关键词和 Chroma 检索。
3. reject/deprecated/replaced 不参与检索。
4. 每次修正都有 revision。
5. 前端能完成从上传到审核通过再检索的闭环。

### P2：混合检索流程产品化

周期：3 到 4 天  
优先级：高  
目标：让检索从“能搜到”升级为“流程清晰、证据可靠、可解释”。

后端任务：

1. 明确检索 pipeline：

```text
query normalization
-> metadata filter
-> keyword retrieval
-> vector retrieval
-> result fusion
-> optional rerank
-> evidence pack
-> RAG generation
```

2. Query normalization：
   - 提取设备型号
   - 提取故障码
   - 提取部件名
   - 标准化同义词和常见错别字
3. Metadata filter：
   - `device_model`
   - `component`
   - `fault_code`
   - `knowledge_type`
   - `risk_level`
   - `review_status=approved`
4. Retrieval 策略：
   - 设备型号、故障码、部件名优先关键词和 metadata。
   - 现象描述、经验总结优先向量召回。
5. Result fusion：
   - 按 `chunk_id + version` 去重。
   - 融合 keyword score、vector score、metadata boost。
6. Evidence pack：
   - `chunk_id`
   - `source_doc_id`
   - `version`
   - `page`
   - `section`
   - `content`
   - `score_breakdown`
7. Chroma 失败时自动回退关键词检索。
8. 为后续 rerank 预留接口，不强依赖真实 reranker。

前端任务：

1. 检索结果明确展示 evidence 来源。
2. 高亮设备型号、故障码、部件名命中。
3. 展示“关键词命中 / 向量召回 / metadata 加权”的解释。

验收：

1. Chroma 关闭时仍可搜索。
2. Chroma 开启时结果去重且 citations 保留。
3. 每条结果能追溯到 chunk/source/page/section。
4. 设备型号和故障码精确命中优先级高于泛语义召回。

### P3：RAG 输出标准化与安全约束

周期：2 到 3 天  
优先级：高  
目标：让检修建议可审计、可追溯、不胡编。

后端任务：

1. 统一 RAG 输出结构：

```text
【初步判断】
【建议检查步骤】
【建议维修步骤】
【安全提醒】
【验收标准】
【引用证据】
【不确定信息】
```

2. Prompt 中强制要求：
   - 所有建议必须基于 evidence。
   - 不允许编造参数。
   - 证据不足时写“不确定”。
   - high/critical 风险必须提示人工复核。
3. LLM 失败时返回：
   - 检索结果
   - 标准化空模板
   - fallback reason
4. citations 必须保留：
   - `chunk_id`
   - `source_doc_id`
   - `page`
   - `section`
   - `version`
5. 增加结构化 schema 测试。

前端任务：

1. RAG 结果按固定分区展示。
2. “引用证据”区域可点击定位到 chunk。
3. “不确定信息”必须明显展示，不要弱化。

验收：

1. 无 evidence 时不会输出确定性维修结论。
2. high/critical 风险时展示人工复核提醒。
3. LLM provider 失败时页面仍有可用结果。

### P4：文档解析、OCR 与多模态任务化

周期：3 到 5 天  
优先级：中高  
目标：把重解析从同步接口变成可观测任务，减少上传卡顿和现场风险。

任务：

1. 引入轻量 parse job：
   - `queued`
   - `running`
   - `completed`
   - `failed`
   - `fallback`
2. 上传后可选择：
   - 小文本同步解析。
   - MinerU/OCR/多模态异步解析。
3. 保存最近一次解析任务状态。
4. 为 MinerU 增加：
   - 单文件耗时
   - 输出页数
   - 输出 asset 数
   - fallback reason
5. OCR provider：
   - mock 保留
   - RapidOCR/Tesseract 小样本验收
   - 图片 OCR 结果进入 pending_review
6. 多模态 provider：
   - 本地 OpenAI-compatible 视觉模型验收入口
   - 失败 fallback 到 mock

验收：

1. 大文件解析不会让上传接口长时间阻塞。
2. 前端能看到解析中、失败、fallback。
3. 解析结果仍默认 pending_review。

### P5：系统状态页与可观测性

周期：2 天  
优先级：中高  
目标：让评委、协作者、现场操作员都能判断系统当前是否可靠。

后端状态字段：

1. LLM provider 状态。
2. Embedding provider 状态。
3. OCR provider 状态。
4. MinerU 是否启用、是否可执行、版本。
5. ChromaDB 是否正常。
6. 知识片段总数。
7. approved / pending_review / rejected 计数。
8. 最近一次索引时间。
9. 最近一次解析任务状态。
10. fallback 是否启用。
11. 当前运行模式：offline / mock / local / cloud。

前端任务：

1. 新增或完善“系统状态”页。
2. 状态分组：模型、解析、检索、知识库、部署。
3. 对 fallback 给出清晰但不夸张的说明。

验收：

1. 启动后无需看日志即可判断主链路状态。
2. Chroma/MinerU/LLM 任一不可用时页面能说明 fallback。

### P6：前端流程收敛与工作台体验

周期：2 到 4 天  
优先级：中  
目标：让界面从“功能都在”变成“现场用户知道下一步做什么”。

任务：

1. 首页保持检索优先，不铺满所有功能。
2. 导航按真实角色分区：
   - 检修助手
   - 资料入库
   - 审核工作台
   - 知识图谱
   - 系统状态
3. 资料入库页面：
   - 上传
   - 解析状态
   - pending chunks
   - parsed markdown 预览
4. 审核工作台：
   - 待审核队列
   - 证据预览
   - 修正后通过
   - 拒绝原因
5. 检索页：
   - metadata 过滤
   - evidence pack
   - RAG 标准化输出

验收：

1. 3 分钟内可以完成“上传资料 -> 审核 -> 检索 -> RAG 引用”的人工演练。
2. 移动/窄屏不出现明显重叠。
3. 前端 build 通过。

### P7：数据持久化与准生产硬化

周期：3 到 5 天  
优先级：中  
目标：降低 JSON 文件存储在准生产场景下的风险。

最小迁移方案：

1. 保留现有 JSON 文件作为兼容层。
2. 新增 SQLite 表：
   - documents
   - chunks
   - revisions
   - review_events
   - parse_jobs
   - provider_status_snapshots
3. 提供一次性导入脚本：JSON -> SQLite。
4. 新写入优先 SQLite；短期可双写 JSON 作为回滚。
5. 增加数据备份和导出。

如果时间不足：

1. 先加文件锁。
2. 保留 `os.replace()` 原子写。
3. 增加写入失败恢复和 `.bak`。

验收：

1. 并发审核/修正不容易写坏文件。
2. 数据可导出、可备份、可恢复。

### P8：部署与国产化复验

周期：3 到 4 天  
优先级：中  
目标：明确“最小可运行”和“增强能力”两套部署边界。

任务：

1. Windows 本地：
   - 一键启动
   - MinerU 可选安装
   - Chroma/embedding 可选配置
2. LoongArch/Kylin：
   - 最小依赖：FastAPI + mock + 关键词检索 + 前端静态托管。
   - 增强依赖：Chroma、MinerU、OCR 单独验收。
3. Docker：
   - 离线 fallback 镜像继续可运行。
   - 增强镜像可选，不和最小镜像混在一起。
4. 启动脚本：
   - `dev verify` 增加 provider 和知识库状态检查。
   - 失败时输出明确修复建议。

验收：

1. 最小部署不依赖 MinerU/Chroma/真实 LLM。
2. 增强部署有清晰安装文档和验收命令。

### P9：评测、演示与交付材料

周期：2 到 4 天  
优先级：后置  
目标：在功能闭环稳定后，再做评测和演示包装。

任务：

1. 构造 20 到 50 条检修问答/故障场景样本。
2. 评估指标：
   - top-k recall
   - citation traceability
   - unsafe answer rate
   - fallback success rate
   - upload-to-approval latency
3. 完善 runbook：
   - 离线演示
   - 云端 LLM 演示
   - 本地模型演示
   - MinerU 解析演示
4. 准备答辩表述：
   - 什么是已实现
   - 什么是可选增强
   - 什么是生产化边界

验收：

1. 演示脚本和功能实际一致。
2. 不把 mock/fallback 说成真实生产能力。

## 4. 推荐执行顺序

第一优先级：

1. P0 稳定测试口径。
2. P1 审核工作台与状态机。
3. P2 混合检索 evidence pack。
4. P3 RAG 标准化输出。

第二优先级：

1. P5 系统状态页。
2. P4 解析任务化。
3. P6 前端流程收敛。

第三优先级：

1. P7 数据持久化硬化。
2. P8 部署复验。
3. P9 演示评测。

## 5. 两周建议排期

第 1 到 2 天：

1. 修复全量测试口径。
2. 明确状态机 schema。
3. 新增 review event 存储。

第 3 到 5 天：

1. 完成统一审核接口。
2. 完成审核工作台基础 UI。
3. approve 后同步 Chroma。

第 6 到 8 天：

1. 重构 search pipeline 为显式混合检索流程。
2. 输出 evidence pack。
3. RAG 输出模板标准化。

第 9 到 10 天：

1. 系统状态页。
2. MinerU/OCR/Chroma/LLM 状态接入。

第 11 到 12 天：

1. 资料解析任务化。
2. 前端流程细化。

第 13 到 14 天：

1. Windows 完整回归。
2. LoongArch/Kylin 最小部署复验。
3. 更新文档和风险边界。

## 6. 关键文件地图

后端：

1. `backend/app/main.py`：API 路由入口。
2. `backend/app/knowledge.py`：资料入库、chunk、revision。
3. `backend/app/parser_router.py`：文件类型解析路由。
4. `backend/app/mineru_adapter.py`：MinerU 真实解析。
5. `backend/app/ocr_adapter.py`：OCR provider。
6. `backend/app/multimodal_adapter.py`：多模态 provider。
7. `backend/app/services.py`：搜索、案例、审核。
8. `backend/app/vector_store.py`：Chroma/embedding。
9. `backend/app/rag.py`：RAG 与诊断。
10. `backend/app/provider_policy.py`：provider 状态。
11. `backend/app/data_store.py`：JSON 持久化。

前端：

1. `frontend/src/App.vue`：页面组合。
2. `frontend/src/api.ts`：接口类型。
3. `frontend/src/components/KnowledgePanel.vue`：资料入库与修正。
4. `frontend/src/components/ReviewPanel.vue`：案例审核，后续扩展为统一审核。
5. `frontend/src/components/SearchPanel.vue`：检索主界面。
6. `frontend/src/components/RagPanel.vue`：RAG 输出。
7. `frontend/src/styles.css`：整体视觉与布局。

测试：

1. `tests/test_backend_api.py`：当前主回归。
2. `tests/test_motorcycle_manual.py`：专项 PDF/手册流程，需同步 pending_review 状态机。

文档：

1. `docs/deployment/mineru-document-parsing.md`
2. `docs/deployment/semantic-retrieval-primary.md`
3. `docs/deployment/local-multimodal-model.md`
4. `docs/project-management/current-handoff.md`
5. `docs/testing/software-test-report.md`

## 7. 风险与兜底

| 风险 | 影响 | 兜底 |
| --- | --- | --- |
| MinerU 首次解析慢或依赖不可用 | 上传体验变差 | 默认 fallback，后续任务化 |
| Chroma/embedding 失败 | 语义召回下降 | 关键词检索继续可用 |
| LLM 失败 | 无生成式建议 | 返回 evidence 和标准模板 |
| 审核状态不一致 | 未审内容污染知识库 | 统一状态机和检索过滤 |
| JSON 并发写入 | 数据损坏 | 短期文件锁，长期 SQLite |
| LoongArch 增强依赖不可用 | 国产化部署受限 | 最小部署与增强部署分离 |
| 前端功能过多 | 用户迷路 | 检索优先、审核/状态分区 |

## 8. Definition of Done

一个阶段完成必须满足：

1. 后端接口和前端字段一致。
2. 有 fallback，不因外部 provider 失败中断主流程。
3. 有自动化测试覆盖核心路径。
4. 文档更新风险边界和验收命令。
5. 前端 build 通过。
6. 涉及检索/RAG 的功能必须保留 evidence 可追溯。
