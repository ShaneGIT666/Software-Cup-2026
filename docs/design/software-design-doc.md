# 软件功能设计文档

> [!WARNING]
> **历史快照（非现行基线）**：本文记录 2026 年前期竞赛原型、阶段调研、验证或交付准备，仅用于追溯当时事实。文内“当前”“最终”“正式”“已完成”“必须”“一键部署”等表述均限定于当时范围，不构成现行产品状态、开发顺序、生产要求或交付承诺。现行文档的适用范围和来源优先级只以[根 README](../../README.md)第 1 节为入口；需求语义、动态状态、公共契约、领域事件和变更证据分别遵循该节指向的唯一事实源。本文中的命令、测试数量和部署结论未经当前版本复验，不得作为当前验收证据。

> 项目：基于多模态大模型技术的设备检修知识检索与作业系统
> 版本：v0.1.0
> 日期：2026-05-21

## 1. 引言

### 1.1 编写目的

本文档描述"基于多模态大模型技术的设备检修知识检索与作业系统"的系统架构、模块设计、数据设计和接口设计，作为开发实现和后期维护的技术依据。

### 1.2 设计目标

1. **轻量化**：MVP 阶段采用 JSON 文件存储，不引入重型数据库和框架依赖
2. **可替换**：LLM Provider 通过适配层解耦，支持 Mock/OpenAI/Anthropic 切换
3. **可解释**：检索结果带有命中原因、来源位置和排序分，提升用户信任
4. **可降级**：大模型不可用时自动回退到本地规则，确保系统可用
5. **可部署**：前后端分离，支持开发模式和生产模式部署

### 1.3 参考资料

| 序号 | 资料 | 说明 |
|------|------|------|
| 1 | 软件功能需求分析文档 | 本文档对应的需求规格说明 |
| 2 | API 契约草案 | `docs/design/api-contract-draft.md` |
| 3 | 数据模型草案 | `docs/design/data-model-draft.md` |
| 4 | 开源架构调研 | `docs/research/open-source-architecture-research.md` |
| 5 | FastAPI 官方文档 | https://fastapi.tiangolo.com/ |
| 6 | Vue 3 官方文档 | https://cn.vuejs.org/ |

## 2. 系统架构

### 2.1 整体架构

系统采用经典的三层 B/S 架构：

```
┌──────────────────────────────────────────────────────────────────┐
│                         客户端（浏览器）                           │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │  Vue 3 + TypeScript + Vite + Element Plus                     │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────────┐  │ │
│  │  │QueryPanel│ │ResultPanel│ │Workflow  │ │CasePanel/       │  │ │
│  │  │          │ │          │ │Panel     │ │ReviewPanel      │  │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └─────────────────┘  │ │
│  └──────────────────────────────────────────────────────────────┘ │
└──────────────────────────┬───────────────────────────────────────┘
                           │ HTTP REST API (JSON)
┌──────────────────────────┴───────────────────────────────────────┐
│                       应用服务器（FastAPI）                         │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │  路由层 (main.py)                                               │ │
│  │  GET /api/health  POST /api/search  POST /api/rag/answer     │ │
│  │  GET /api/workflows/{id}  POST /api/cases  GET /api/cases    │ │
│  │  PATCH /api/cases/{id}/review  POST /api/uploads              │ │
│  │  POST /api/knowledge/documents  GET /api/knowledge/documents  │ │
│  │  DELETE /api/knowledge/documents/{id}                         │ │
│  └──────────────┬───────────────────────────────────────────────┘ │
│                 │                                                  │
│  ┌──────────────┴───────────────────────────────────────────────┐ │
│  │  服务层 (services.py)                                          │ │
│  │  search_knowledge()  find_workflow()  create_repair_case()   │ │
│  │  list_repair_cases()  review_repair_case()                    │ │
│  └──────┬──────────────────────────────────┬────────────────────┘ │
│         │                                   │                      │
│  ┌──────┴──────────┐              ┌────────┴──────────┐          │
│  │ RAG 层 (rag.py)  │              │ 知识入库层          │          │
│  │ answer_with_rag()│              │ (knowledge.py)     │          │
│  │ search → prompt  │              │ ingest/list/delete │          │
│  │  → LLM → answer  │              └────────┬──────────┘          │
│  └──────┬──────────┘                       │                      │
│         │                                   │                      │
│  ┌──────┴──────────┐                        │                      │
│  │ LLM 适配层       │                        │                      │
│  │ (llm_adapter.py) │                        │                      │
│  │ mock/openai/     │                        │                      │
│  │ anthropic        │                        │                      │
│  └─────────────────┘                        │                      │
│                                              │                      │
│  ┌───────────────────────────────────────────┴──────────────────┐ │
│  │  数据访问层 (data_store.py)                                     │ │
│  │  load_seed_data()  load_cases()  save_cases()                 │ │
│  │  load_documents()  save_documents()                            │ │
│  │  load_document_chunks()  save_document_chunks()               │ │
│  └───────────────────────────────┬──────────────────────────────┘ │
└──────────────────────────────────┼────────────────────────────────┘
                                   │ 文件读写
┌──────────────────────────────────┴────────────────────────────────┐
│                        数据存储层（JSON 文件）                       │
│  ┌─────────────────────┐  ┌──────────────────────────────────────┐ │
│  │ data/examples/        │  │ data/knowledge/                       │ │
│  │ devices.json         │  │ documents.json                        │ │
│  │ manuals.json         │  │ document-chunks.json                  │ │
│  │ repair-cases.json    │  │ files/ (上传的原始资料)                 │ │
│  │ workflows.json       │  │                                       │ │
│  └─────────────────────┘  └──────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────┘
```

### 2.2 技术选型说明

| 模块 | 技术 | 选型理由 |
|------|------|----------|
| 前端框架 | Vue 3 + TypeScript | 响应式数据绑定、类型安全、生态成熟 |
| 构建工具 | Vite 7 | 极快的开发启动和 HMR，原生 ESM 支持 |
| UI 组件库 | Element Plus | 企业级组件库，中文文档完善，风格适合工业场景 |
| 图标库 | @lucide/vue | 轻量、树摇优化、图标风格统一 |
| 后端框架 | FastAPI | 高性能异步框架，自动生成 OpenAPI 文档，Pydantic 校验 |
| 异步服务器 | Uvicorn | FastAPI 推荐的 ASGI 服务器 |
| 数据校验 | Pydantic v2 | 类型安全的数据模型定义和请求校验 |
| HTTP 客户端 | httpx | 异步 HTTP 客户端，用于 LLM API 调用 |
| PDF 解析 | pypdf | 纯 Python 实现，无系统依赖，适合国产化环境 |
| 开发数据库 | SQLite / JSON 文件 | MVP 阶段零部署成本 |
| 向量库（规划） | Chroma | 轻量级嵌入式向量数据库 |
| OCR（规划） | PaddleOCR / MinerU | 国产化支持好，中文识别精度高 |

### 2.3 部署架构

```
┌────────────────────────────────────────────────────────────────┐
│  LoongArch 服务器 (银河麒麟 V10/V11)                             │
│                                                                │
│  ┌─────────────────────┐    ┌─────────────────────────────┐    │
│  │  Nginx (静态文件服务)  │    │  Uvicorn (ASGI 应用服务器)    │    │
│  │  dist/              │    │  backend/app/main.py        │    │
│  │  :80 → :5173 代理   │    │  :8000                      │    │
│  └────────┬────────────┘    └──────────────┬──────────────┘    │
│           │                                │                     │
│           │  前端 SPA 静态文件               │  REST API            │
│           │                                │                     │
│  ┌────────┴────────────────────────────────┴──────────────┐    │
│  │  Python 3.10+ + Node.js 20+                              │    │
│  │  文件系统 JSON 数据存储（data/examples/ + data/knowledge/）  │    │
│  └──────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────┘
```

MVP 开发模式下，Vite dev server (:5173) 直接代理 API 请求到 FastAPI (:8000)，无需 Nginx。生产模式使用 `npm run build` 生成的静态文件，由 Nginx 或 FastAPI StaticFiles 提供服务。

## 3. 模块设计

### 3.1 前端模块

#### 3.1.1 组件树

```
App.vue (根组件，管理全局状态和页面布局)
├── QueryPanel.vue (检索输入区)
│   - 设备型号输入
│   - 故障现象输入
│   - 检索触发按钮
│   - 文件上传入口
│   - 结果/步骤计数指标
├── ResultsPanel.vue (知识结果区)
│   - 检索摘要展示
│   - 结果列表（可点击查看关联流程）
│   - 来源标签（手册/案例/资料）
│   - 命中原因和排序分展示
│   - 空状态提示
├── WorkflowPanel.vue (作业指导区)
│   - 流程元信息（设备类型、故障类型、等级）
│   - 所需工具标签
│   - 步骤列表（Element Plus Steps 垂直布局）
│   - 安全提醒
│   - 空状态提示
├── CasePanel.vue (案例提交区)
│   - 可能原因输入
│   - 处理方案输入
│   - 处理结果输入
│   - 标签输入
│   - 提交按钮
├── ReviewPanel.vue (案例审核区)
│   - 待审核案例列表
│   - 案例详情展示
│   - 通过/拒绝操作
│   - 确认对话框
│   - 空状态/加载状态提示
├── KnowledgePanel.vue (资料入库区)
│   - 资料来源名称输入
│   - 文件上传入口
│   - 入库资料列表
│   - 解析状态展示
│   - 空状态/加载状态提示
└── RagPanel.vue (RAG 辅助建议区)
    - 生成按钮
    - Provider 状态标签
    - 回答正文
    - 建议动作列表
    - 引用来源列表
    - Fallback 说明
    - 空状态/加载状态提示
```

#### 3.1.2 数据流

```
App.vue (状态中心)
  │
  ├── deviceModel, faultText ────────→ QueryPanel (v-model)
  ├── searchPayload ───────────────→ ResultsPanel (props)
  │     └── selectedWorkflow ──────→ WorkflowPanel (props)
  ├── caseForm ────────────────────→ CasePanel (v-model)
  ├── ragAnswer ───────────────────→ RagPanel (props)
  │
  └── API 调用 (api.ts)
        ├── searchKnowledge() → SearchPayload
        ├── fetchWorkflow() → WorkflowPayload
        ├── submitCase() → { id, status }
        ├── uploadFaultFile() → UploadPayload
        ├── requestRagAnswer() → RagAnswerPayload
        ├── fetchCases() → CaseListPayload
        ├── reviewCase() → { id, status }
        ├── uploadKnowledgeDocument() → KnowledgeDocument
        └── fetchKnowledgeDocuments() → KnowledgeDocumentListPayload
```

### 3.2 后端模块

#### 3.2.1 路由层 (main.py)

`backend/app/main.py` 定义了所有 REST API 端点、中间件配置和异常处理。

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/search` | POST | 知识检索 |
| `/api/diagnosis` | POST | 诊断建议 |
| `/api/rag/answer` | POST | RAG 辅助回答 |
| `/api/workflows/{id}` | GET | 获取作业流程 |
| `/api/cases` | POST | 提交维修案例 |
| `/api/cases` | GET | 查询案例列表 |
| `/api/cases/{id}/review` | PATCH | 审核案例 |
| `/api/uploads` | POST | 上传现场材料 |
| `/api/knowledge/documents` | POST | 上传入库资料 |
| `/api/knowledge/documents` | GET | 查询资料列表 |
| `/api/knowledge/documents/{id}` | GET | 查询资料详情 |
| `/api/knowledge/documents/{id}/chunks` | GET | 查询资料片段 |
| `/api/knowledge/documents/{id}` | DELETE | 删除入库资料 |

中间件：
- CORS：允许 localhost:5173 和 127.0.0.1:5173 跨域访问
- StaticFiles：`/uploads` 和 `/knowledge` 静态文件挂载

异常处理：
- HTTPException：统一返回 ApiResponse 格式
- RequestValidationError：提取 Pydantic 校验错误信息

#### 3.2.2 服务层 (services.py)

核心业务逻辑的实现模块。

**search_knowledge()** — 知识检索函数

```
输入: SearchRequest { deviceModel, faultText, inputType, topK }
流程:
  1. tokens() — 中文分词，按标点切分查询关键词
  2. 遍历 manuals / approved cases / approved document chunks 三类数据
  3. score_item() — 对每条数据计算加权匹配分：
     - 字段权重: title(5) > deviceModel/tags(4) > content(2) + 来源基础分(3/2/2)
     - 短语加分: 连续短语命中 +4
     - 匹配词记录: matchedTerms[] + fieldMatches[]
  4. confidence_from_score() — 将排序分映射为 0.5-0.95 置信度
  5. 三类结果合并，按 score 降序排列，取 topK 条
  6. build_search_summary() — 生成中文检索摘要
输出: { queryId, summary, results[] }
```

**create_repair_case()** — 案例创建函数

```
输入: CaseCreateRequest { deviceModel, faultText, cause, solution, result, tags }
流程:
  1. 生成 case-{uuid8} 唯一 ID
  2. 构建案例对象（含状态 pending_review、时间戳）
  3. 追加到 repair-cases.json
输出: { id, status: "pending_review" }
```

**review_repair_case()** — 案例审核函数

```
输入: case_id, CaseReviewRequest { action, reviewNote, normalizedTags }
流程:
  1. 校验 action ∈ {approve, reject}（Pydantic 层校验）
  2. 查找对应案例
  3. 更新 status 和 reviewedAt
  4. 如果审核通过且提供了 normalizedTags，则更新标签
输出: { id, status }
```

#### 3.2.3 RAG 层 (rag.py)

**answer_with_rag()** — RAG 回答生成函数

```
输入: RagAnswerRequest { deviceModel, faultText, topK, provider }
流程:
  1. 调用 search_knowledge() 获取检索结果作为上下文
  2. 调用 generate_rag_answer() 生成回答
  3. 合并 queryId、summary 和 RAG 结果
输出: { queryId, summary, answer, recommendedActions, citations[], provider, fallback }
```

#### 3.2.4 LLM 适配层 (llm_adapter.py)

Provider 适配器，实现多模型可替换接入。

```
generate_rag_answer(device_model, fault_text, contexts, requested_provider)
  │
  ├── provider == "mock"
  │     └── mock_rag_answer()
  │           生成模板化中文回答 + 引用来源列表
  │
  ├── provider == "openai"
  │     └── real_rag_answer()
  │           build_context_prompt() → POST /v1/responses
  │           → parse_openai_response()
  │
  ├── provider == "anthropic"
  │     └── real_rag_answer()
  │           build_context_prompt() → POST /v1/messages
  │           → parse_anthropic_response()
  │
  └── 失败 → mock_rag_answer(..., fallback_reason="调用失败原因")
```

**降级策略**：
- 未配置 API Key → 自动使用 Mock Provider
- 网络超时 → 捕获异常，回退到 Mock
- 模型返回空内容 → 捕获异常，回退到 Mock
- fallback_reason 字段记录降级原因，前端展示给用户

#### 3.2.5 知识入库层 (knowledge.py)

资料入库流水线：

```
uploadKnowledgeDocument(file, source_name)
  │
  ├── Step 1: 文件校验
  │     validate_knowledge_file() — 检查扩展名、MIME、大小(20MB)、空文件
  │
  ├── Step 2: 文件保存
  │     写入 data/knowledge/files/kdoc-{uuid8}.{suffix}
  │
  ├── Step 3: parser_router 解析
  │     parse_document(file_path, suffix, content)
  │     ├── PDF/DOCX/PPTX/XLSX → 优先 mineru_adapter
  │     │     ├── MinerU 可用 → status: "parsed"
  │     │     ├── PDF 且 MinerU 不可用 → fallback 到 pypdf
  │     │     └── Office 文档且 MinerU 不可用 → mock-parser / needs_parser
  │     ├── JPG/JPEG/PNG/WebP → needs_multimodal_analysis
  │     └── TXT/Markdown → decode_text() (尝试 utf-8 → gb18030 → latin1)
  │           ├── 有内容 → status: "parsed"
  │           └── 无内容 → status: "empty"
  │
  ├── Step 4: 文本分块
  │     split_text(text, size=700, overlap=120)
  │     └── 按固定大小分割，保留 overlap 上下文
  │
  ├── Step 5: 关键词提取
  │     build_keywords(text) — 按标点分词，取前 12 个长度≥2 的词
  │
  └── Step 6: 持久化
        documents.json ← 资料元数据
        document-chunks.json ← review_status=pending_review 的知识片段
        parsed/{document_id}/raw_parse_result.json、parsed.md、assets/ ← 解析产物
```

说明：自动解析、OCR 和多模态分析产生的知识片段默认不进入正式检索/RAG/Chroma。只有 `review_status=approved` 的 document chunks 会被 `services.search_knowledge()` 和 `vector_store.sync_chunks()` 使用。

### 3.3 检索排序引擎

当前 MVP 版本的排序算法设计如下：

**排序公式**：

```
score = sourceWeight + Σ(fieldMatches * fieldWeight) + phraseBonus

其中:
  sourceWeight: manual=3, case=2, document=2
  fieldWeight: title=5, deviceModel=4, tags=4, content=2
  phraseBonus: 连续短语命中 = 4
  confidence = min(cap, 0.5 + score * 0.045)
```

**可解释性输出**：

每条检索结果包含：
- `matchedTerms`：命中的检索词列表
- `reason`：中文命中说明（"命中手册字段：火花塞、怠速；来源位置：故障诊断 / p.15"）
- `scoreBreakdown`：{ score, sourceType, sourceWeight, phraseBonus, fieldMatches[] }
- `confidence`：0.50-0.95 的置信度值

**二阶段演进**：
- 替换关键词匹配为向量语义检索（Chroma/Qdrant embedding similarity）
- 添加 Reranker 精排（Cross-Encoder）
- 支持多模态输入（图片 embedding）

## 4. 数据设计

### 4.1 数据模型

#### Device（设备）

```json
{
  "id": "dev-001",
  "type": "发动机",
  "model": "发动机-示例型号 A",
  "name": "四冲程汽油发动机",
  "manufacturer": "示例设备厂",
  "tags": ["启动困难", "怠速", "点火系统"]
}
```

#### Manual（检修手册片段）

```json
{
  "id": "doc-001",
  "title": "发动机启动困难检查流程",
  "deviceType": "发动机",
  "deviceModel": "发动机-示例型号 A",
  "chapter": "故障诊断",
  "page": 15,
  "content": "启动困难时，应依次检查...",
  "sourceName": "示例检修手册",
  "tags": ["启动困难", "燃油", "点火"],
  "workflowId": "wf-001"
}
```

#### RepairCase（维修案例）

```json
{
  "id": "case-001",
  "deviceModel": "发动机-示例型号 A",
  "faultTitle": "冷机启动困难",
  "faultText": "冷机启动困难，启动后怠速波动明显。",
  "symptoms": ["启动困难", "怠速不稳"],
  "possibleCauses": ["火花塞积碳", "燃油滤清器堵塞"],
  "solution": "清理并更换火花塞，检查燃油滤清器通畅性。",
  "result": "启动恢复正常，怠速稳定。",
  "status": "approved",
  "tags": ["启动困难", "点火系统"],
  "workflowId": "wf-001",
  "createdAt": "2026-05-19T00:00:00Z",
  "reviewedAt": "2026-05-19T02:00:00Z"
}
```

案例状态流转：

```
pending_review ──approve──→ approved (进入知识库，可被检索)
       │
       └──reject──→ rejected (不入库，保留记录)
```

#### Workflow（标准化作业流程）

```json
{
  "id": "wf-001",
  "title": "发动机启动困难标准检查流程",
  "deviceType": "发动机",
  "faultType": "启动困难",
  "level": "常规检修",
  "tools": ["万用表", "火花塞套筒", "燃油压力表"],
  "safetyNotes": ["确认设备停止运行", "保持作业区域通风"],
  "steps": [
    {
      "order": 1,
      "title": "安全确认",
      "description": "确认设备停止运行，现场无高温、泄漏和明火风险。",
      "checkRequired": true,
      "warning": "未完成安全确认不得拆检。"
    }
  ],
  "acceptanceCriteria": ["设备可正常启动", "怠速稳定"]
}
```

#### KnowledgeDocument（入库资料）

```json
{
  "id": "kdoc-a1b2c3d4",
  "fileName": "motorcycle-manual.pdf",
  "fileType": "application/pdf",
  "suffix": "pdf",
  "sourceName": "摩托车检修手册",
  "status": "indexed",
  "chunkCount": 15,
  "parser": "pypdf",
  "uploadedAt": "2026-05-21T10:00:00Z",
  "url": "/knowledge/files/kdoc-a1b2c3d4.pdf"
}
```

#### KnowledgeChunk（知识片段）

```json
{
  "id": "kdoc-a1b2c3d4-chunk-001",
  "documentId": "kdoc-a1b2c3d4",
  "title": "motorcycle-manual",
  "sourceType": "document",
  "sourceName": "摩托车检修手册",
  "page": 3,
  "chunkIndex": 1,
  "content": "发动机无法启动时，应检查火花塞、高压包和燃油供给...",
  "snippet": "发动机无法启动时，应检查火花塞...",
  "keywords": ["发动机", "无法启动", "火花塞", "高压包", "燃油供给"]
}
```

### 4.2 存储方案

| 存储内容 | 当前方案 | 路径 | 二阶段方案 |
|----------|----------|------|------------|
| 种子数据 | JSON 文件 | `data/examples/*.json` | SQLite 或保留 JSON |
| 案例数据 | JSON 文件 | `data/examples/repair-cases.json` | SQLite 持久化 |
| 上传文件 | 本地文件系统 | `data/uploads/` | 对象存储 |
| 入库资料 | JSON 文件 | `data/knowledge/documents.json` | 向量数据库 |
| 知识片段 | JSON 文件 | `data/knowledge/document-chunks.json` | 向量嵌入 + Chroma |
| LLM 配置 | 环境变量 | `.env` 文件 | 管理后台配置 |

### 4.3 关键数据流

#### 检索流程

```
用户输入(deviceModel + faultText)
  → SearchRequest (Pydantic 校验)
  → tokens() 中文分词
  → 并行查询三类数据源:
      ├── manuals.json → field_weights 匹配
      ├── repair-cases.json (status=approved) → 加权匹配
      └── document-chunks.json → 加权匹配
  → 合并排序 (score DESC)
  → topK 截断
  → build_search_summary()
  → 返回 SearchPayload
```

#### 案例审核入库流程

```
用户提交 CaseCreateRequest
  → create_repair_case()
  → repair-cases.json 追加记录(status=pending_review)
  → 返回 { id, status: "pending_review" }

管理员审核 PATCH /api/cases/{id}/review
  → review_repair_case()
  → 更新 status = approved | rejected
  → 更新 reviewedAt 时间戳
  → 返回 { id, status }

再次检索
  → search_knowledge() 仅查询 status=approved 的案例
  → 新审核通过的案例出现在结果中
```

## 5. 接口设计

### 5.1 接口规范

所有接口遵循 RESTful 风格，请求和响应使用 JSON 格式。

#### 统一响应格式

```json
{
  "success": true,
  "data": {},
  "message": ""
}
```

- `success`: 请求是否成功
- `data`: 业务数据（任意 JSON 类型）
- `message`: 提示信息（成功为空，失败为错误描述）

#### 统一错误响应

```json
{
  "success": false,
  "data": null,
  "message": "设备型号和故障现象不能同时为空"
}
```

### 5.2 API 详细说明

#### GET /api/health

健康检查接口，用于验证服务是否正常运行。

响应示例：
```json
{
  "success": true,
  "data": { "status": "ok", "version": "0.1.0" }
}
```

#### POST /api/search

知识检索接口，根据设备型号和故障文本搜索相关知识。

请求体：
```json
{
  "deviceModel": "发动机-示例型号 A",
  "faultText": "启动困难，怠速不稳",
  "inputType": "text",
  "topK": 5
}
```

参数说明：
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| deviceModel | string | 否 | 设备型号 |
| faultText | string | 否 | 故障现象描述 |
| inputType | string | 否 | 输入类型，默认 "text"（预留多模态扩展） |
| topK | int | 否 | 返回结果数量，1-20，默认 5 |

约束：deviceModel 和 faultText 不能同时为空。

响应：
```json
{
  "success": true,
  "data": {
    "queryId": "q-a1b2c3d4",
    "summary": "已按字段权重、来源类型和短语命中排序，返回 手册 3 条、案例 1 条。当前首要参考《发动机启动困难检查流程》，主要命中：启动困难、怠速。",
    "results": [
      {
        "id": "doc-001",
        "title": "发动机启动困难检查流程",
        "sourceType": "manual",
        "sourceName": "示例检修手册",
        "confidence": 0.95,
        "snippet": "启动困难时，应依次检查燃油供给...",
        "workflowId": "wf-001",
        "chapter": "故障诊断",
        "page": 15,
        "matchedTerms": ["启动困难", "怠速"],
        "reason": "命中手册字段：启动困难、怠速；来源位置：故障诊断 / p.15",
        "scoreBreakdown": {
          "score": 12,
          "sourceType": "manual",
          "sourceWeight": 3,
          "phraseBonus": 0,
          "fieldMatches": [
            { "field": "title", "terms": ["启动困难"], "weight": 5, "score": 5 },
            { "field": "tags", "terms": ["启动困难", "怠速"], "weight": 4, "score": 8 }
          ]
        }
      }
    ]
  }
}
```

#### POST /api/rag/answer

RAG 辅助回答接口，基于检索结果生成带引用的诊断建议。

请求体：
```json
{
  "deviceModel": "发动机-示例型号 A",
  "faultText": "启动困难",
  "topK": 5,
  "provider": "mock"
}
```

参数说明：
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| deviceModel | string | 否 | 设备型号 |
| faultText | string | 否 | 故障现象 |
| topK | int | 否 | 检索数量，1-10，默认 5 |
| provider | string | 否 | LLM Provider: mock/openai/anthropic |

响应：
```json
{
  "success": true,
  "data": {
    "queryId": "q-a1b2c3d4",
    "summary": "已返回手册 3 条、案例 1 条...",
    "answer": "基于已检索到的 4 条资料，发动机-示例型号 A 的"启动困难"优先按来源资料进行排查...",
    "recommendedActions": [
      "优先查看引用来源中的手册页码或资料片段，确认安全前置条件。",
      "按标准作业流程逐项检查，不跳过安全确认和验收标准。"
    ],
    "citations": [
      {
        "id": "doc-001",
        "title": "发动机启动困难检查流程",
        "sourceType": "manual",
        "sourceName": "示例检修手册",
        "snippet": "启动困难时...",
        "confidence": 0.95,
        "chapter": "故障诊断",
        "page": 15
      }
    ],
    "provider": "mock",
    "requestedProvider": "mock",
    "fallback": true,
    "fallbackReason": "未配置真实模型或真实模型调用不可用，已使用 mock provider 保证演示不断线。"
  }
}
```

#### GET /api/workflows/{workflow_id}

获取标准化作业流程。

路径参数：workflow_id (string) — 流程唯一标识

#### POST /api/cases

提交维修案例。

请求体：
```json
{
  "deviceModel": "发动机-示例型号 A",
  "faultText": "热机后偶发熄火",
  "cause": "怠速控制阀积碳",
  "solution": "清洁怠速控制阀并复测",
  "result": "热机后未再熄火",
  "tags": ["偶发熄火", "怠速控制"]
}
```

#### GET /api/cases

查询案例列表。查询参数：status (可选) — 过滤状态

#### PATCH /api/cases/{case_id}/review

审核案例。action 枚举：approve / reject

#### POST /api/uploads

上传现场材料（multipart/form-data，10MB 上限）。

#### POST /api/knowledge/documents

上传入库资料（multipart/form-data，20MB 上限，PDF/TXT/MD）。

#### 其他端点

GET /api/knowledge/documents、GET /api/knowledge/documents/{id}、GET /api/knowledge/documents/{id}/chunks、DELETE /api/knowledge/documents/{id}

### 5.3 错误处理策略

| HTTP 状态码 | 场景 | 响应示例 |
|-------------|------|----------|
| 200 | 成功 | `{"success": true, "data": {...}}` |
| 400 | 参数校验失败 | `{"success": false, "data": null, "message": "设备型号和故障现象不能同时为空"}` |
| 404 | 资源不存在 | `{"success": false, "data": null, "message": "案例不存在"}` |
| 422 | Pydantic 类型校验失败 | `{"success": false, "data": null, "message": "action: 非法值"}` |

## 6. 关键流程设计

### 6.1 知识检索流程

```
用户点击"开始检索"
  │
  ▼
App.vue: runSearch()
  │
  ▼
api.ts: searchKnowledge(deviceModel, faultText)
  │
  ▼
POST /api/search         ┌─────────────────────────┐
  │                       │  校验: 输入不能同时为空    │
  ▼                       └────────────┬────────────┘
services.py:                        │ (400 Bad Request)
  search_knowledge()                 │
  │                                  │
  ├── tokens(deviceModel, faultText)
  │   中文分词 → query_tokens[]
  │
  ├── 种子数据查询
  │   ├── manuals → score_item(field_weights, source_weight=3)
  │   └── workflows (按需)
  │
  ├── 案例查询
  │   └── cases (status=approved) → score_item(field_weights, source_weight=2)
  │
  ├── 入库资料查询
  │   └── document_chunks → score_item(field_weights, source_weight=2)
  │
  ├── 合并排序 (score DESC, confidence DESC)
  │
  ├── topK 截断
  │
  ├── build_search_summary()
  │
  ▼
返回 SearchPayload → App.vue → ResultsPanel 渲染
```

### 6.2 案例审核入库流程（状态机）

```
                    ┌──────────┐
                    │  用户提交  │
                    │  维修案例  │
                    └─────┬────┘
                          │
                          ▼
                   ┌──────────────┐
                   │ pending_review│ (待审核)
                   └──┬────────┬──┘
                      │        │
              approve │        │ reject
                      │        │
                      ▼        ▼
                 ┌─────────┐ ┌──────────┐
                 │approved │ │ rejected  │
                 │(已入库)  │ │(已拒绝)   │
                 └────┬────┘ └──────────┘
                      │
                      ▼
               ┌──────────────┐
               │ 再次检索可命中 │
               └──────────────┘
```

### 6.3 LLM 调用与降级流程

```
POST /api/rag/answer
  │
  ▼
rag.py: answer_with_rag()
  │
  ├── search_knowledge() → contexts[]
  │
  └── llm_adapter.py: generate_rag_answer()
        │
        ├── provider == "mock"?
        │     └── mock_rag_answer() → 返回模板化回答
        │
        ├── provider == "openai"?
        │     ├── 检查 OPENAI_API_KEY?
        │     │     └── 未配置 → mock fallback
        │     ├── build_context_prompt()
        │     ├── POST {base_url}/v1/responses
        │     │     └── 超时/网络错误 → mock fallback
        │     ├── parse_openai_response()
        │     │     └── 返回空 → mock fallback
        │     └── 返回真实 LLM 回答 + citations
        │
        ├── provider == "anthropic"?
        │     ├── 检查 ANTHROPIC_API_KEY?
        │     │     └── 未配置 → mock fallback
        │     ├── build_context_prompt()
        │     ├── POST {base_url}/v1/messages
        │     │     └── 超时/网络错误 → mock fallback
        │     ├── parse_anthropic_response()
        │     │     └── 返回空 → mock fallback
        │     └── 返回真实 LLM 回答 + citations
        │
        └── fallback → mock_rag_answer(fallback_reason="...")
```

## 7. 二阶段演进规划

### 7.1 向量语义检索

**当前状态**：关键词加权匹配

**规划方案**：
1. 接入 Chroma 嵌入式向量数据库
2. 使用 text-embedding-3-small 或 BGE 中文模型生成文本 embedding
3. 入库时自动计算 embedding 并存入向量库
4. 检索时先做向量相似度搜索，再叠加字段权重精排
5. 增加混合检索模式（关键词 + 向量）的加权融合

**风险**：
- LoongArch 架构上 Chroma 编译兼容性待验证
- BGE 模型下载和推理对内存的要求

### 7.2 多模态识别

**当前状态**：图片上传仅存储，不识别

**规划方案**：
1. 故障图片 OCR：接入 PaddleOCR，识别图片中的仪表读数、故障码等文字信息
2. 文档深度解析：接入 MinerU 或 Docling，支持复杂 PDF 的版式分析
3. 图片视觉诊断：结合多模态大模型（GPT-4V / Qwen-VL），输入故障图片获得视觉诊断建议

**风险**：
- PaddleOCR 依赖体积大，在 8GB 内存环境下需评估
- MinerU/Docling 的 Python 依赖在麒麟系统上的安装兼容性

### 7.3 知识图谱构建

**当前状态**：数据以独立 JSON 文件存储，无关系挖掘

**规划方案**：
1. 实体抽取：从手册和案例中抽取设备、部件、故障、症状、原因、方案等实体
2. 关系构建：建立"设备-包含-部件""故障-对应-症状""原因-导致-故障"等关系
3. 图存储：使用 Neo4j 或 NetworkX 存储知识图谱
4. 图检索：支持基于知识图谱的多跳推理查询

### 7.4 其他规划

| 功能 | 当前状态 | 规划 |
|------|----------|------|
| 权限管理 | 无 | 增加用户登录、角色权限、操作审计 |
| 本地大模型部署 | 未部署 | 在 LoongArch 上评估 Ollama/llama.cpp 的可行性 |
| Docker 容器化 | 未使用 | 需要验证 Docker 在 LoongArch 上的支持 |
| 系统监控与日志 | 无 | 增加请求日志、性能监控和告警 |
| 移动端适配 | PC Web 为主 | 增加 App 或 PWA 移动端支持 |
