# 项目评分提升设计文档：从 7.2 到 8.4

> 版本：v1.0
> 日期：2026-05-27
> 目标：在当前约束下（3 人团队、2 周+、Vue 3 + FastAPI + JSON 存储、LoongArch 硬约束）将项目从 7.2/10 提升到 8.4/10 的理论天花板
> 方法：路径 C——高点优先，以赛题对齐为主线，每项独立可验证

---

## 1. 评分维度定义

本文档中的 1-10 分是针对**本项目的理论天花板**，而非绝对工业标准或比赛评审满分。

| 分数 | 含义 |
|------|------|
| 10 | 在三人团队、当前技术栈、比赛时间约束下，理论上能做到的最好状态 |
| 9 | 接近天花板，仅有固有架构约束或外部环境导致的微小缺口 |
| 8 | 充分且可靠，有一个明确可改进的方向未做 |
| 7 | 当前水平：可用，但有明显短板 |
| 6 | 功能性存在但薄弱，答辩追问时容易暴露 |
| 5 | 风险项，可能影响演示或评审结论 |
| <5 | 不可接受 |

### 1.1 各维度权重

| 维度 | 权重 | 理由 |
|------|------|------|
| 赛题对齐 | 25% | 比赛评审核心依据 |
| 功能完整度 | 20% | 直接影响演示效果和答辩质量 |
| 文档质量 | 15% | 比赛交付物之一，影响评审印象 |
| 架构设计 | 15% | 影响可维护性和扩展性 |
| 代码质量 | 15% | 影响协作效率和长期可靠性 |
| 测试覆盖 | 10% | 影响演示可靠性和代码可信度 |

---

## 2. 当前状态基线（2026-05-27）

### 2.1 已验证事实

| 项目 | 值 | 验证方式 |
|------|-----|----------|
| Git 状态 | `main` = `origin/main`，工作区干净 | `git status --short --branch` |
| 最新提交 | `24bbbee` — 32 files, +2700/-676 | `git log --oneline -3` |
| 后端测试总数 | 74 个 | `grep -c "def test_" tests/*.py` |
| 前端类型检查 | PASS | `npx vue-tsc -b` |
| 前端生产构建 | PASS (5.05s, chunk 1.01MB) | `npx vite build` |
| 代码总量 | 5353 行（后端 2208 + 前端 1939 + 测试 1906） | `wc -l` |
| LoongArch 后端 | Kylin V11/loongarch64, 39 passed, /api/health 正常 | `software-test-report.md` 第 4 节 |
| Qwen 真实 API | qwen-plus, fallback=false, contextCount=3 | `software-test-report.md` 第 3.4 节 |
| Playwright E2E | 1 条冒烟测试（首页→检索→RAG） | `frontend/e2e/smoke.spec.ts` |

### 2.2 当前各维度评分

| 维度 | 分数 | 主要扣分项 |
|------|------|-----------|
| 赛题对齐 | 7.0 | LoongArch 前端部署未完成；多模态只有 mock 入口；向量检索是哈希伪实现 |
| 功能完整度 | 6.5 | `/api/diagnosis` 返回硬编码；关键词+向量无混合排序；mock 数据仅 3 条流程 |
| 架构设计 | 7.0 | `services.py` 检索三路循环重复；`App.vue` 175 行平铺状态；无依赖注入 |
| 代码质量 | 7.0 | 3 处裸 `except Exception`；类型白名单各自定义；JSON 非原子写；无日志模块 |
| 测试覆盖 | 8.0 | 前端仅 1 条 E2E；无 Vitest 组件测试；无并发写测试；无 Chroma 初始化失败测试 |
| 文档质量 | 7.5 | LoongArch 验证文档状态与测试报告矛盾；测试数量过时；README 无状态信息 |
| **加权总分** | **7.2** | |

---

## 3. 天花板分析

### 3.1 为什么到不了 10

| 限制因素 | 影响的维度 | 说明 |
|----------|-----------|------|
| JSON 存储无并发保护 | 架构(8.5) | 迁移 SQLite 不是比赛阶段该做的事 |
| 哈希 embedding 不是语义 | 功能(8.0) | 替换为 API-based embedding 可行，但全文向量检索 + reranker 精排是生产级需求 |
| 多模态无 OCR/版式分析 | 功能(8.0)、赛题(9.0) | PaddleOCR/MinerU 依赖体积大，国产化兼容性待验证，不在 2 周范围 |
| 知识图谱是轻量关系网络 | 功能(8.0) | Neo4j 或 GraphRAG 需要额外基础设施 |
| 无前端组件测试历史 | 测试(9.0) | 可以加 Vitest，但组件测试套件的成熟度需要时间积累 |
| 文档与代码的天然滞后 | 文档(9.0) | 快速迭代中无法完全消除 |

### 3.2 各维度天花板

```
赛题对齐:   7.0 ──→ 9.0  (+2.0)  天花板 9.0（缺 OCR 和跨模态匹配扣 1 分）
功能完整度: 6.5 ──→ 8.0  (+1.5)  天花板 8.0（缺 OCR/多轮对话/报告生成扣 2 分）
架构设计:   7.0 ──→ 8.5  (+1.5)  天花板 8.5（JSON 存储是固有约束扣 1.5 分）
代码质量:   7.0 ──→ 8.0  (+1.0)  天花板 8.0（轻量设计的刻意选择扣 2 分）
测试覆盖:   8.0 ──→ 9.0  (+1.0)  天花板 9.0（缺性能/可访问性/跨浏览器测试扣 1 分）
文档质量:   7.5 ──→ 9.0  (+1.5)  天花板 9.0（迭代中的天然滞后扣 1 分）
─────────────────────────────────
加权总分:   7.2 ──→ 8.4  (+1.2)
```

---

## 4. 改进方案（路径 C：高点优先，24 项）

### 4.1 赛题对齐（7.0 → 9.0，权重 25%）

| # | 改进项 | 具体做法 | 工作量 |
|---|--------|---------|--------|
| A1 | LoongArch 前端部署 | FastAPI StaticFiles 挂载 `frontend/dist`，验证 Kylin V11 浏览器访问 `/` | 0.5 天 |
| A2 | 真实 embedding 接入 | 用已验证的 Qwen OpenAI-compatible 路径接 embedding API（`text-embedding-v3` 或 `bge-m3`），替换 `vector_store.py` 哈希实现，保留哈希作为 fallback | 1 天 |
| A3 | 真实多模态端到端 | 上传一张故障照片 → 真实 OpenAI/Anthropic multimodal API 分析 → 生成知识片段 → 入库 → 检索命中 → RAG 引用。至少一条完整通路 | 1 天 |

**小计**：3 项，2.5 天。完成后到 9.0（扣 1 分：缺少 OCR 和跨模态匹配）。

### 4.2 功能完整度（6.5 → 8.0，权重 20%）

| # | 改进项 | 具体做法 | 工作量 |
|---|--------|---------|--------|
| B1 | 动态诊断 API | 重构 `/api/diagnosis`：调用已有 RAG 管道（检索→LLM→citations），返回结构化诊断（可能原因列表 / 排查步骤 / 安全提醒）。不新增代码路径，复用已有基础设施 | 0.5 天 |
| B2 | 关键词+向量混合排序 | 对同一 chunk 的关键词 score 和向量 distance 做加权融合（如 `final = 0.6*keyword_score/10 + 0.4*(1-cosine_distance)`），去重后统一排序返回 | 0.5 天 |
| B3 | 扩展 mock 种子数据 | 从 3→6 条流程，新增：润滑异常(wf-004)、电路故障(wf-005)、传动异响(wf-006)。每条绑定手册片段+维修案例 | 0.5 天 |

**小计**：3 项，1.5 天。完成后到 8.0（扣 2 分：无 OCR/多轮对话记忆/自动报告生成）。

### 4.3 架构设计（7.0 → 8.5，权重 15%）

| # | 改进项 | 具体做法 | 工作量 |
|---|--------|---------|--------|
| C1 | 检索管道抽取 `SearchSource` 协议 | 定义 `SearchSource` 接口：`{name, search(tokens) → list[ScoredItem]}`。ManualSource / CaseSource / DocumentSource / VectorSource 各实现之。`search_knowledge()` 变为"遍历所有 source → 合并排序 → topK"。新增检索源只需实现一个接口 | 1 天 |
| C2 | 前端 `useSearch` composable | 从 `App.vue` 抽取：searchPayload、selectedWorkflow、ragAnswer、knowledgeGraph、deviceModel、faultText 状态 + runSearch / generateRagAnswer / refreshKnowledgeGraph 方法。`App.vue` script 从 175 行降到 ~80 行 | 0.5 天 |
| C3 | FastAPI 依赖注入 | 用 `Depends(get_data_store)` 替代每个请求裸调用 `load_seed_data()`。不改变底层 JSON 存储，但调用方不再关心数据来源 | 0.5 天 |

**小计**：3 项，2 天。完成后到 8.5（扣 1.5 分：JSON 存储是 MVP 固有约束）。

### 4.4 代码质量（7.0 → 8.0，权重 15%）

| # | 改进项 | 具体做法 | 工作量 |
|---|--------|---------|--------|
| D1 | 消除裸 `except Exception` | `vector_store.py` 3 处改为捕获 `(ImportError, RuntimeError)` 并记录异常类型+消息到 logging | 0.25 天 |
| D2 | 统一文件类型白名单 | 抽取 `ALLOWED_KNOWLEDGE_TYPES` / `ALLOWED_UPLOAD_TYPES` 到 `data_store.py`，main.py 和 knowledge.py 引用同一来源 | 0.25 天 |
| D3 | JSON 原子写 | `save_cases()` / `save_documents()` 改为先写临时文件 → `os.replace()` 覆盖 | 0.25 天 |
| D4 | 添加 logging 模块 | 至少记录：provider fallback 原因、上传校验失败详情、Chroma 连接/操作异常。统一使用 `logging.getLogger(__name__)` | 0.25 天 |
| D5 | 标注未验证的 API payload | `multimodal_adapter.py` 的 OpenAI 图片输入 `image_url` 字段名添加注释标注"待真实 API 验证" | 0.25 天 |

**小计**：5 项，1.25 天。完成后到 8.0（扣 2 分：环境变量散落、函数式而非类组织是刻意保持的轻量选择）。

### 4.5 测试覆盖（8.0 → 9.0，权重 10%）

| # | 改进项 | 具体做法 | 工作量 |
|---|--------|---------|--------|
| E1 | Playwright E2E 扩展到 5 条 | 新增：提交案例→审核通过→再检索命中；资料上传→入库列表→详情；RAG 生成→citations 展示→fallback 标签；知识图谱渲染→节点类型检查 | 0.5 天 |
| E2 | Vitest 组件测试 | QueryPanel（输入校验/emit 事件）、ResultsPanel（空状态/结果列表渲染/点击关联流程）、RagPanel（fallback 标签/citations 列表/空状态） | 1 天 |
| E3 | 并发写测试 | 同时提交两个案例 → 验证两个都被持久化到 repair-cases.json。测试即文档，暴露 JSON 无锁的已知限制 | 0.25 天 |
| E4 | Chroma 初始化失败降级测试 | `chromadb` 未安装时 `chroma_collection()` 返回 None → 检索/RAG/资料入库不崩 | 0.25 天 |

**小计**：4 项，2 天。完成后到 9.0（扣 1 分：无性能/可访问性/跨浏览器测试）。

### 4.6 文档质量（7.5 → 9.0，权重 15%）

| # | 改进项 | 具体做法 | 工作量 |
|---|--------|---------|--------|
| F1 | 修复 LoongArch 验证文档状态 | `loongarch-kylin-verification.md` 第 3 行从"待环境开放"改为"已完成（见 software-test-report.md §4）"，补充 Kylin V11 版本/内核版本/测试通过数量 | 0.25 天 |
| F2 | 更新完成状态文档 | `completion-status-2026-05-25.md`：测试数 39→74，LoongArch 从"暂缓"→"已完成"，新增真实 API 验收行 | 0.25 天 |
| F3 | 更新 Agent 入口文档 | `agent-startup-context.md`：测试数、新增文件说明（vector_store.py/e2e/smoke.spec.ts/playwright.config.ts）、当前风险重排 | 0.25 天 |
| F4 | 补充产品说明书 | `product-manual.md`：Qwen 真实 API 验收记录、LoongArch 后端验证截图/日志、弱网兜底说明 | 0.25 天 |
| F5 | 更新演示检查清单 | `demo-checklist.md`：新增 Playwright E2E 检查项、真实多模态演示步骤、混合检索验证项 | 0.25 天 |
| F6 | README 添加验证状态区 | 后端测试数徽章、前端构建状态、LoongArch 验证状态、真实 API 验收状态——用 emoji 或表格在 README 顶部展示 | 0.25 天 |

**小计**：6 项，1.5 天。完成后到 9.0（扣 1 分：快速迭代中文档与代码的天然滞后）。

---

## 5. 汇总

| 维度 | 当前 | 目标 | 改进项 | 工作量 |
|------|------|------|--------|--------|
| 赛题对齐 | 7.0 | 9.0 | A1-A3 | 2.5 天 |
| 功能完整度 | 6.5 | 8.0 | B1-B3 | 1.5 天 |
| 架构设计 | 7.0 | 8.5 | C1-C3 | 2 天 |
| 代码质量 | 7.0 | 8.0 | D1-D5 | 1.25 天 |
| 测试覆盖 | 8.0 | 9.0 | E1-E4 | 2 天 |
| 文档质量 | 7.5 | 9.0 | F1-F6 | 1.5 天 |
| **合计** | **7.2** | **8.4** | **24 项** | **10.75 天** |

---

## 6. 执行时间线与依赖

```
第 1 周（赛题对齐 + 功能完整度，4 天）
  Day 1: A1 LoongArch 前端部署 + B1 动态诊断 API
  Day 2: A2 真实 embedding 接入（前半）+ B2 混合排序
  Day 3: A2 真实 embedding 接入（后半）+ A3 真实多模态端到端
  Day 4: B3 扩展 mock 数据 + 缓冲/修整

第 2 周（架构 + 代码质量 + 测试扩展，5.25 天）
  Day 5: C1 SearchSource 协议抽取
  Day 6: C2 useSearch composable + C3 FastAPI DI
  Day 7: D1-D5 代码质量 5 项 + E1 Playwright E2E 扩展
  Day 8: E2 Vitest 组件测试 + E3 并发写测试
  Day 9: E4 Chroma 降级测试 + 修整

穿插全天（文档同步，1.5 天）
  - 每完成一个维度后立即更新对应的文档项（F1-F6）
  - D+4: F1-F3（赛题+功能完成后）
  - D+7: F4-F6（架构+代码完成后）
```

**依赖关系**：
- A2（真实 embedding）是 B2（混合排序）的前置条件——混合排序需要语义距离值
- C1（SearchSource）可以独立做，但 D1-D5（代码质量）中与 `services.py` 相关的改动应在 C1 之后
- 文档同步 (F1-F6) 在对应功能完成后立即做，不积压

**无依赖、可并行**：
- A1 + B1 可以同一天做（独立模块）
- E1 + E2 可以并行（Playwright 和 Vitest 不冲突）
- D1-D5 五小项可以并行

---

## 7. 风险与约束

| 风险 | 等级 | 应对 |
|------|------|------|
| 真实 embedding API 在 LoongArch 上网络不可达 | 中 | 保留哈希 fallback，LoongArch 上回归到关键词+哈希混合模式 |
| 真实多模态 API 调用成本/延迟过高 | 中 | 预设 1 张小图（<500KB），mock 路径同步保留，现场可切换 |
| SearchSource 重构破坏已有检索结果 | 低 | 重构后全量跑 74 个测试，特别是 `test_search_*` 和 `test_end_to_end_*` |
| Playwright 在 Windows 环境初始化耗时 | 低 | 复用已有 `playwright.config.ts`，仅扩展 spec |
| 文档同步滞后复发 | 低 | 每完成一个维度立即更新文档，不做批量更新 |

---

## 8. 不做的事项（YAGNI）

以下是被评估为"值得做但不在本路径范围"的事项，明确排除以避免范围蔓延：

1. ❌ SQLite 替代 JSON 存储——MVP 阶段够了，比赛后再说
2. ❌ Neo4j/GraphRAG 知识图谱——轻量关系网络对演示已足够
3. ❌ PaddleOCR/MinerU/Docling 集成——依赖体积和国产化兼容性风险太大
4. ❌ 多轮对话记忆——需要 session 管理和对话状态，超出 MVP
5. ❌ 自动报告生成（PDF/Word 输出）——不是赛题核心要求
6. ❌ Pinia store——当前组件层级不需要全局 store，useSearch composable 足够。如果后续加路由再考虑
7. ❌ Docker 容器化——LoongArch 上 Docker 支持未验证
8. ❌ 本地大模型部署（Ollama/llama.cpp）——内存和编译兼容性风险高

---

## 9. 验收标准

以下每项完成后即可确认达到目标分数：

**赛题对齐 9.0**：
- [ ] `curl http://<kylin-ip>:8000/` 返回前端 SPA 页面
- [ ] 向量检索结果中 `provider` 字段不为 `"hash"`
- [ ] 一张真实故障照片从上传到 RAG 引用走通完整链路

**功能完整度 8.0**：
- [ ] `/api/diagnosis` 对"启动困难 怠速不稳"返回结构化结果（可能原因/排查步骤/安全提醒）
- [ ] 混合排序对同一 chunk 返回 fused score 字段
- [ ] 6 条流程均可通过 workflowId 关联

**架构设计 8.5**：
- [ ] 新增检索源只需实现 `SearchSource` 协议，不修改 `search_knowledge()`
- [ ] `App.vue` script 块 <100 行
- [ ] `Depends(get_data_store)` 出现在至少一个端点中

**代码质量 8.0**：
- [ ] `grep "except Exception" backend/app/*.py` 返回空
- [ ] `ALLOWED_*_TYPES` 唯一定义在 `data_store.py`
- [ ] JSON 写入走临时文件+原子替换
- [ ] `logging.getLogger` 在至少 3 个模块中使用

**测试覆盖 9.0**：
- [ ] `npx playwright test` 5 条全通过
- [ ] `npx vitest run` 覆盖 3 个组件
- [ ] 并发写测试通过（两个案例均持久化）
- [ ] Chroma 未安装时检索不崩

**文档质量 9.0**：
- [ ] `grep "待环境开放\|暂缓\|33.*passed\|39.*passed" docs/` 返回空或仅有历史记录
- [ ] README 顶部有验证状态表格
- [ ] `loongarch-kylin-verification.md` 引用 `software-test-report.md` §4
