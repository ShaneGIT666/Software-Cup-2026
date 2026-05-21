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
    "summary": "可能与燃油供给、点火系统或进气系统异常有关。",
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
        "reason": "命中手册字段：启动困难, 怠速不稳"
      }
    ]
  },
  "message": ""
}
```

说明：

1. `sourceType` 当前支持 `manual`、`case` 和 `document`。
2. `document` 表示由资料入库接口解析生成的本地知识片段。
3. `matchedTerms` 和 `reason` 用于展示命中原因，支撑后续 RAG 引用解释。

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

1. 当前迭代只启用 `mock` provider，用于稳定演示“检索上下文 -> 带引用回答”闭环。
2. `provider` 请求字段允许 `mock`、`openai`、`anthropic`，但 `openai` 和 `anthropic` 当前会降级到 mock provider。
3. 未配置任何模型密钥时接口仍可用，返回 `fallback: true` 和 `fallbackReason`。
4. 真实 OpenAI/Anthropic 调用留待后续迭代实现，不在本接口第一版中承诺。

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
    "summary": "可能与燃油供给、点火系统或进气系统异常有关。",
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
        "reason": "命中手册字段：启动困难"
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
      "燃油供给不足",
      "火花塞积碳",
      "进气系统漏气"
    ],
    "recommendedActions": [
      "检查燃油滤清器",
      "检查火花塞间隙和积碳",
      "检查进气管路密封"
    ],
    "safetyNotes": [
      "作业前断开电源或确认设备处于安全状态",
      "佩戴防护手套和护目镜"
    ],
    "fallback": true
  },
  "message": "当前为模拟诊断结果"
}
```

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
