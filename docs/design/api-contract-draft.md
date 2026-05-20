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
        "page": 15
      }
    ]
  },
  "message": ""
}
```

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
