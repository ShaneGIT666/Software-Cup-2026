# API 契约草案

本文档用于前后端在正式编码前对齐接口。字段可在开发中调整，但每次变更必须同步更新本文档。

## 1. 通用约定

基础路径：

```text
/api
```

通用响应格式：

```json
{
  "success": true,
  "data": {},
  "message": ""
}
```

错误响应格式：

```json
{
  "success": false,
  "data": null,
  "message": "错误说明"
}
```

错误状态码约定：

1. 业务输入不符合 MVP 规则时返回 `400`。
2. 资源不存在时返回 `404`。
3. 请求结构或字段枚举校验失败时返回 `422`。

## 2. 健康检查

```text
GET /api/health
```

响应：

```json
{
  "success": true,
  "data": {
    "status": "ok",
    "version": "0.1.0"
  },
  "message": ""
}
```

约束：

1. `deviceModel` 和 `faultText` 不能同时为空或只包含空白字符。
2. 空查询返回 `400`，并使用通用错误响应格式。

## 3. 知识检索

```text
POST /api/search
```

请求：

```json
{
  "deviceModel": "发动机-示例型号 A",
  "faultText": "启动困难，怠速不稳",
  "inputType": "text",
  "topK": 5
}
```

响应：

```json
{
  "success": true,
  "data": {
    "queryId": "q-001",
    "summary": "已按字段权重、来源类型和短语命中排序，返回手册 2 条、案例 1 条。当前首要参考《发动机启动困难检查流程》，主要命中：启动困难、怠速不稳。",
    "results": [
      {
        "id": "doc-001",
        "title": "发动机启动困难检查流程",
        "sourceType": "manual",
        "sourceName": "示例检修手册",
        "confidence": 0.86,
        "snippet": "检查燃油、火花塞、进气管路和怠速控制部件。",
        "workflowId": "wf-001",
        "chapter": "故障诊断",
        "page": 15,
        "matchedTerms": ["启动困难", "怠速不稳"],
        "reason": "命中手册字段：启动困难、怠速不稳；来源位置：故障诊断 / p.15",
        "scoreBreakdown": {
          "score": 24,
          "sourceType": "manual",
          "sourceWeight": 3,
          "phraseBonus": 0,
          "fieldMatches": [
            {
              "field": "title",
              "terms": ["启动困难"],
              "weight": 5,
              "score": 5
            }
          ]
        }
      }
    ]
  },
  "message": ""
}
```

说明：

1. `sourceType` 当前支持 `manual`、`case` 和 `document`。
2. `document` 表示由资料入库接口解析生成的本地知识片段。
3. `matchedTerms`、`reason` 和 `scoreBreakdown` 用于展示命中原因，支撑后续 RAG 引用解释。
4. 当前排序仍是 MVP 级关键词方案，不引入向量库；排序依据为字段权重、来源类型基础权重和连续短语命中加分。

## 4. 故障诊断建议

```text
POST /api/diagnosis
```

请求：

```json
{
  "deviceModel": "发动机-示例型号 A",
  "faultText": "启动困难，怠速不稳",
  "evidenceIds": ["doc-001", "case-001"]
}
```

## 4.1 RAG 辅助回答

```text
POST /api/rag/answer
```

说明：

1. `provider` 请求字段允许 `mock`、`openai`、`anthropic`，不传时读取 `LLM_PROVIDER`，仍未配置则使用 `mock`。
2. `openai` provider 默认使用 OpenAI Responses API 形态，读取 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL`。
3. `anthropic` provider 使用 Anthropic Messages API 形态，读取 `ANTHROPIC_API_KEY`、`ANTHROPIC_BASE_URL`、`ANTHROPIC_MODEL`。
4. 未配置密钥、调用失败、模型返回空内容时自动降级到 mock provider，返回 `fallback: true` 和 `fallbackReason`。
5. 真实 provider 调用仅作为可选增强，不影响无 Key 演示路径。
6. 若第三方服务兼容 OpenAI Chat Completions，可设置 `OPENAI_API_STYLE=chat_completions`，此时请求路径为 `{OPENAI_BASE_URL}/chat/completions`。

请求：

```json
{
  "deviceModel": "发动机-示例型号 A",
  "faultText": "启动困难，怠速不稳",
  "topK": 5,
  "provider": "mock"
}
```

响应：

```json
{
  "success": true,
  "data": {
    "queryId": "q-001",
    "summary": "已按字段权重、来源类型和短语命中排序，返回手册 2 条、案例 1 条。",
    "answer": "基于已检索到的 3 条资料，发动机-示例型号 A 的“启动困难，怠速不稳”优先按来源资料进行排查...",
    "recommendedActions": [
      "优先查看引用来源中的手册页码或资料片段，确认安全前置条件。"
    ],
    "citations": [
      {
        "id": "doc-001",
        "title": "发动机启动困难检查流程",
        "sourceType": "manual",
        "sourceName": "示例检修手册",
        "snippet": "检查燃油、火花塞、进气管路和怠速控制部件。",
        "confidence": 0.86,
        "page": 15,
        "reason": "命中手册字段：启动困难；来源位置：故障诊断 / p.15",
        "scoreBreakdown": {
          "score": 18,
          "sourceType": "manual",
          "sourceWeight": 3,
          "phraseBonus": 0,
          "fieldMatches": []
        }
      }
    ],
    "provider": "mock",
    "requestedProvider": "mock",
    "fallback": true,
    "fallbackReason": "当前迭代仅启用 mock provider，真实 OpenAI/Anthropic 调用留待后续接入。"
  },
  "message": "当前为 Mock RAG 回答"
}
```

响应：

```json
{
  "success": true,
  "data": {
    "possibleCauses": [
      "命中手册字段：启动困难；来源位置：故障诊断 / p.15"
    ],
    "recommendedActions": [
      "优先查看引用来源中的手册页码或资料片段，确认安全前置条件。"
    ],
    "safetyNotes": [
      "检修前确认设备停机、断电或处于安全隔离状态。",
      "佩戴防护手套、护目镜等必要防护装备。"
    ],
    "citations": [],
    "answer": "基于已检索到的资料生成诊断建议。",
    "provider": "mock",
    "model": "mock",
    "fallback": true,
    "fallbackReason": "",
    "queryId": "q-001",
    "summary": "已按字段权重、来源类型和短语命中排序。"
  },
  "message": "诊断建议已生成"
}
```

说明：`/api/diagnosis` 已复用现有检索和 RAG 管道，不再返回固定硬编码诊断。`evidenceIds` 可用于限定引用证据；未传或未命中时使用当前检索结果。

## 5. 作业流程

```text
GET /api/workflows/{workflowId}
```

响应：

```json
{
  "success": true,
  "data": {
    "id": "wf-001",
    "title": "发动机启动困难标准检查流程",
    "deviceType": "发动机",
    "faultType": "启动困难",
    "level": "常规检修",
    "tools": ["万用表", "火花塞套筒", "压力表"],
    "safetyNotes": ["确认设备停止运行", "保持作业区域通风"],
    "steps": [
      {
        "order": 1,
        "title": "安全确认",
        "description": "确认设备停止运行，现场无高温和泄漏风险。",
        "checkRequired": true,
        "warning": "未完成安全确认不得拆检。"
      }
    ],
    "acceptanceCriteria": [
      "设备可正常启动",
      "怠速稳定",
      "无异常报警"
    ]
  },
  "message": ""
}
```

## 6. 案例提交

```text
POST /api/cases
```

请求：

```json
{
  "deviceModel": "发动机-示例型号 A",
  "faultText": "启动困难，怠速不稳",
  "cause": "火花塞积碳",
  "solution": "清理并更换火花塞",
  "result": "启动恢复正常",
  "tags": ["启动困难", "点火系统"]
}
```

响应：

```json
{
  "success": true,
  "data": {
    "id": "case-001",
    "status": "pending_review"
  },
  "message": "案例已提交，等待审核"
}
```

说明：

1. MVP 阶段案例保存到本地 JSON 数据文件。
2. 新提交案例默认进入 `pending_review`。
3. 审核通过后，案例进入检索范围。

## 7. 案例列表

```text
GET /api/cases?status=pending_review
```

响应：

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "case-001",
        "deviceModel": "发动机-示例型号 A",
        "faultTitle": "启动困难",
        "faultText": "启动困难，怠速不稳",
        "status": "pending_review",
        "tags": ["启动困难", "点火系统"],
        "createdAt": "2026-05-19T00:00:00Z"
      }
    ],
    "total": 1
  },
  "message": ""
}
```

## 8. 案例审核

```text
PATCH /api/cases/{caseId}/review
```

请求：

```json
{
  "action": "approve",
  "reviewNote": "内容完整，可入库",
  "normalizedTags": ["启动困难", "点火系统", "火花塞"]
}
```

字段约束：

1. `action` 仅允许 `approve` 或 `reject`。
2. 非法 `action` 返回 `422`，并且不得改变案例状态。

响应：

```json
{
  "success": true,
  "data": {
    "id": "case-001",
    "status": "approved"
  },
  "message": "审核完成"
}
```

## 9. 文件上传

```text
POST /api/uploads
```

说明：

1. 使用 `multipart/form-data`。
2. MVP 阶段仅支持 `jpg`、`jpeg`、`png`、`webp` 和 `pdf`。
3. 单文件大小上限为 `10MB`。
4. 空文件、无扩展名、扩展名不在白名单、扩展名与 MIME 类型明显不匹配时返回 `400`。
5. 上传后返回文件 ID 和访问路径。

响应：

```json
{
  "success": true,
  "data": {
    "id": "file-001",
    "fileName": "fault-image.jpg",
    "fileType": "image/jpeg",
    "url": "/uploads/file-001.jpg"
  },
  "message": ""
}
```

开发和测试环境可通过 `APP_UPLOAD_DIR` 覆盖上传目录。

## 10. 资料入库

```text
POST /api/knowledge/documents
```

说明：

1. 使用 `multipart/form-data`。
2. MVP 阶段支持 `pdf`、`txt` 和 `md`。
3. 单文件大小上限为 `20MB`。
4. 空文件、无扩展名、扩展名不在白名单、扩展名与 MIME 类型明显不匹配时返回 `400`。
5. 资料入库不同于现场材料上传：入库资料会解析为知识片段，并进入 `/api/search` 检索范围。
6. 开发和测试环境可通过 `APP_KNOWLEDGE_DIR` 覆盖资料库目录，避免污染真实数据。

请求字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `file` | file | 是 | PDF/TXT/Markdown 资料 |
| `source_name` | string | 否 | 资料来源名称，例如“摩托车检修手册” |

响应：

```json
{
  "success": true,
  "data": {
    "id": "kdoc-001",
    "fileName": "motorcycle-manual.md",
    "fileType": "text/markdown",
    "suffix": "md",
    "sourceName": "摩托车检修手册",
    "status": "indexed",
    "chunkCount": 3,
    "parser": "plain-text",
    "uploadedAt": "2026-05-21T00:00:00Z",
    "url": "/knowledge/files/kdoc-001.md",
    "chunks": [
      {
        "id": "kdoc-001-chunk-001",
        "title": "motorcycle-manual",
        "sourceName": "摩托车检修手册",
        "page": null,
        "snippet": "摩托车发动机无法启动时，应检查火花塞、高压包和燃油供给。"
      }
    ]
  },
  "message": "资料已入库"
}
```

资料状态：

| 状态 | 含义 |
| --- | --- |
| `indexed` | 已解析并生成知识片段 |
| `needs_parser` | PDF 解析器未安装或当前环境暂不支持解析 |
| `needs_ocr` | PDF 可能为扫描件，后续需要 OCR |
| `empty` | 文本文件无可解析内容 |

列表接口：

```text
GET /api/knowledge/documents
```

响应：

```json
{
  "success": true,
  "data": {
    "items": [],
    "total": 0
  },
  "message": ""
}
```

详情接口：

```text
GET /api/knowledge/documents/{documentId}
```

响应：

```json
{
  "success": true,
  "data": {
    "id": "kdoc-001",
    "fileName": "motorcycle-manual.md",
    "status": "indexed",
    "chunkCount": 3,
    "chunkTotal": 3,
    "chunks": []
  },
  "message": ""
}
```

片段列表接口：

```text
GET /api/knowledge/documents/{documentId}/chunks
```

响应：

```json
{
  "success": true,
  "data": {
    "items": [],
    "total": 0
  },
  "message": ""
}
```

删除接口：

```text
DELETE /api/knowledge/documents/{documentId}
```

说明：

1. 删除资料时同步删除该资料对应的知识片段和本地原始文件。
2. 删除不存在的资料返回 `404`。
3. 删除后该资料不再进入 `/api/search` 检索结果。

响应：

```json
{
  "success": true,
  "data": {
    "id": "kdoc-001",
    "deleted": true
  },
  "message": "资料已删除"
}
```

开源方案引用：

1. 当前 MVP 自研轻量入库接口和 JSON 存储，避免引入重依赖破坏现有演示闭环。
2. 后续文档解析优先评估 Docling 与 MinerU，OCR 优先评估 PaddleOCR，RAG 框架优先评估 LlamaIndex 或 LangChain。
3. 相关开源方案来源记录在 `docs/research/open-source-architecture-research.md`，实现前必须复核许可证、依赖体积和 Windows/国产化环境兼容性。
## 11. 多模态资料分析

```text
POST /api/knowledge/documents/{documentId}/analyze
```

说明：
1. 对已上传的 PDF 或图片资料执行多模态分析，并将分析结果转为可检索知识片段。
2. 默认使用 `mock` provider，保证无网络、无 API Key 时仍可演示。
3. 可选 provider 为 `mock`、`openai`、`anthropic`；不传时读取 `MULTIMODAL_PROVIDER`，仍未配置则使用 `mock`。
4. OpenAI provider 参考 Responses API 的 PDF/图片输入能力；Anthropic provider 参考 Claude PDF support 与 Vision Messages API。
5. 真实 provider 调用失败、未配置 Key 或模型返回空内容时，自动 fallback 到 mock，并返回 `fallbackReason`。
6. 官方样例 `摩托车发动机维修手册.pdf` 作为本地演示输入，不进入 Git 仓库；若页数或大小导致真实 API 成本过高，应优先使用 mock 或抽样页分析。

请求：
```json
{
  "provider": "mock"
}
```

响应：
```json
{
  "success": true,
  "data": {
    "id": "kdoc-001",
    "status": "analyzed",
    "chunkCount": 3,
    "parser": "multimodal-mock",
    "analysis": {
      "summary": "资料多模态分析摘要",
      "keyComponents": ["发动机", "火花塞"],
      "faultSymptoms": ["启动困难"],
      "inspectionSteps": ["检查点火系统"],
      "safetyNotes": ["检修前确认发动机冷却"],
      "provider": "mock",
      "requestedProvider": "mock",
      "fallback": true,
      "fallbackReason": "未配置真实多模态模型，已使用 mock provider"
    },
    "chunks": []
  },
  "message": "资料多模态分析完成"
}
```

新增资料状态：

| 状态 | 含义 |
| --- | --- |
| `needs_multimodal_analysis` | PDF 或图片需要多模态/视觉分析后才能生成知识片段 |
| `analyzing` | 分析进行中 |
| `analyzed` | 多模态分析完成，并已生成可检索知识片段 |

## 12. 轻量知识关系网络

## 13. Provider 状态与弱网兜底

```text
GET /api/providers/status
```

说明：

1. 用于前端和演示人员确认当前 RAG 与多模态能力处于“云端增强”还是“本地兜底”。
2. `REMOTE_API_MODE=auto` 时，系统优先尝试真实 `openai/anthropic` provider，失败后自动降级到 `mock`。
3. `REMOTE_API_MODE=off` 时，系统不访问外网，RAG 与多模态分析均强制使用本地 mock 结果，适合比赛现场网络不佳时演示。
4. `keyConfigured` 仅表示环境变量中存在 Key，不代表真实网络或额度已验收。

响应示例：

```json
{
  "success": true,
  "data": {
    "remoteApiMode": "auto",
    "offlineFallback": false,
    "llm": {
      "provider": "mock",
      "remoteCapable": false,
      "keyConfigured": false,
      "effectiveProvider": "mock",
      "lastFallbackReason": ""
    },
    "multimodal": {
      "provider": "mock",
      "remoteCapable": false,
      "keyConfigured": false,
      "effectiveProvider": "mock",
      "lastFallbackReason": ""
    }
  },
  "message": ""
}
```

相关环境变量：

```env
REMOTE_API_MODE=auto
PROVIDER_RETRY_COUNT=1
PROVIDER_BACKOFF_SECONDS=0.5
LLM_TIMEOUT_SECONDS=20
MULTIMODAL_TIMEOUT_SECONDS=30
OPENAI_API_STYLE=responses
```

OpenAI-compatible RAG 接入示例：

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your-compatible-provider-key
OPENAI_BASE_URL=https://api.example.com/v1
OPENAI_MODEL=provider-model-name
OPENAI_API_STYLE=chat_completions
REMOTE_API_MODE=auto
```

说明：DeepSeek、Qwen/DashScope 兼容模式、SiliconFlow、火山方舟等服务若提供 OpenAI Chat Completions 兼容接口，可按上述方式接入 RAG 文本回答。多模态 PDF/图片输入在不同厂商之间差异较大，当前仍优先使用 OpenAI Responses 或 Anthropic Messages 的已封装路径，未实测前不要承诺所有兼容网关都支持多模态入库分析。

错误和 fallback 约定：

1. 真实 provider 缺少 Key、网络超时、HTTP 错误、响应为空或解析失败时，业务接口保持成功响应并返回 `fallback: true`。
2. `fallbackReason` 必须说明实际降级原因，前端可直接展示给演示者。
3. 本策略不替代生产级 SLA、熔断中心或监控系统，仅作为比赛 MVP 的弱网兜底边界。

```text
POST /api/knowledge/graph
```

说明：
1. 基于当前查询和 `/api/search` 结果生成轻量知识关系网络，用于展示设备、故障、资料、案例、流程和来源之间的关系。
2. 该接口是比赛 MVP 的“知识沉淀/知识图谱原型”，不依赖 Neo4j、图数据库或向量数据库。
3. 空查询沿用 `/api/search` 的校验规则，返回 `400`。

请求：
```json
{
  "deviceModel": "发动机 示例型号 A",
  "faultText": "启动困难 火花塞",
  "inputType": "text",
  "topK": 6
}
```

响应：
```json
{
  "success": true,
  "data": {
    "queryId": "q-001",
    "summary": "围绕当前查询生成 10 个知识节点、12 条关系",
    "nodes": [
      { "id": "device:发动机 示例型号 A", "label": "发动机 示例型号 A", "type": "device", "weight": 5 }
    ],
    "edges": [
      { "id": "device:...->出现故障->fault:...", "source": "device:...", "target": "fault:...", "relation": "出现故障", "evidence": "用户当前查询" }
    ]
  },
  "message": ""
}
```
## 附录：Chroma 向量检索增强

当前 Chroma 作为可选 RAG 检索增强，不改变 `/api/search` 和 `/api/rag/answer` 的请求结构。

启用方式：

```text
RAG_VECTOR_STORE=chroma
APP_CHROMA_DIR=./data/knowledge/chroma
RAG_VECTOR_DIMENSION=384
```

依赖安装：

```bash
pip install -r backend/requirements-rag.txt
```

行为约定：

1. 资料入库或多模态分析生成 `document` chunks 后，后端会尝试同步到 Chroma collection。
2. `/api/search` 会先执行现有关键词检索，再合并 Chroma 向量召回结果；是否是真实语义 embedding 由 `scoreBreakdown.embeddingProvider` 标记。
3. Chroma 召回结果仍使用 `sourceType=document`，并保留 `documentId`、`chunkId`、`snippet` 和 `scoreBreakdown`。
4. `scoreBreakdown.vectorDistance` 表示 Chroma 返回的向量距离，距离越小越相似。
5. `/api/rag/answer` 会复用 `/api/search` 的混合检索结果，因此 Chroma 召回的资料片段会进入真实 OpenAI/Anthropic LLM prompt，并作为 citations 返回。
6. 真实 LLM 调用可通过 `LLM_MAX_TOKENS`、`LLM_TEMPERATURE` 和 `RAG_CONTEXT_MAX_CHARS` 控制输出成本、随机性和上下文长度。
7. 如果未安装 Chroma、`RAG_VECTOR_STORE=off`、索引不可用或查询失败，接口自动退回关键词检索，不影响比赛演示。
8. LoongArch/银河麒麟环境优先保证默认关键词检索链路可用，Chroma 只作为增强能力单独验收。

## 2026-05-27 补充：embedding 与多模态验收

### Chroma embedding 字段

Chroma 检索结果的 `scoreBreakdown` 新增：

```json
{
  "vectorDistance": 0.12,
  "embeddingProvider": "hash"
}
```

说明：

1. `embeddingProvider=hash` 表示离线兜底 embedding，只用于比赛现场和无 Key 场景的可运行占位，不应宣称为生产级语义 embedding。
2. `embeddingProvider=openai` 表示使用 OpenAI-compatible `/embeddings` 接口生成向量。
3. 真实 embedding 可通过 `RAG_EMBEDDING_PROVIDER=openai`、`OPENAI_EMBEDDING_MODEL`、`OPENAI_API_KEY` 启用。
4. 真实 embedding 调用失败、Key 缺失或 `REMOTE_API_MODE=off` 时，自动回退 `hash`，不影响关键词检索和 RAG 兜底链路。

### 多模态 provider 验收接口

```http
POST /api/providers/multimodal/validate
Content-Type: application/json
```

请求体：

```json
{
  "provider": "openai",
  "documentId": "kdoc-xxxx"
}
```

响应体：

```json
{
  "success": true,
  "data": {
    "remoteOk": false,
    "provider": "openai",
    "model": "gpt-4.1-mini",
    "fallback": true,
    "fallbackReason": "OPENAI_API_KEY 未配置。",
    "summaryPreview": "",
    "latencyMs": 3
  },
  "message": ""
}
```

约束：

1. 请求体不允许传 API Key，只读取服务端环境变量。
2. `documentId` 可选；不传时后端使用极小样本图片验证，避免消耗大文件 token。
3. `REMOTE_API_MODE=off`、Key 缺失、网络失败或模型空响应时，返回 `remoteOk=false` 和明确原因。
4. 该接口用于赛前验收，不作为普通用户高频功能入口。

真实 LLM 验收接口：

```text
POST /api/providers/llm/validate
```

说明：

1. 该接口只读取服务端环境变量中的 Key，不允许请求体传入 Key。
2. 响应包含 `remoteOk`、`provider`、`model`、`apiStyle`、`latencyMs`、`fallback`、`fallbackReason`、`answerPreview` 和 `contextCount`。
3. `REMOTE_API_MODE=off` 时不会访问真实 API，会返回 `remoteOk=false` 和离线原因。
