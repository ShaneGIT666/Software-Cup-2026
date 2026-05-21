# 数据模型草案

本文档用于开发前期对齐核心实体。字段不是最终数据库设计，但应支撑 MVP 功能。

## 1. 设备 Device

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 设备 ID |
| `type` | string | 设备类型 |
| `model` | string | 设备型号 |
| `name` | string | 设备名称 |
| `manufacturer` | string | 厂商 |
| `tags` | string[] | 标签 |

## 2. 手册片段 ManualDocument

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 文档片段 ID |
| `title` | string | 标题 |
| `deviceType` | string | 设备类型 |
| `deviceModel` | string | 设备型号 |
| `chapter` | string | 章节 |
| `page` | number | 页码 |
| `content` | string | 文本内容 |
| `sourceName` | string | 来源名称 |
| `tags` | string[] | 标签 |

## 3. 故障案例 RepairCase

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 案例 ID |
| `deviceType` | string | 设备类型 |
| `deviceModel` | string | 设备型号 |
| `faultTitle` | string | 故障标题 |
| `faultText` | string | 故障描述 |
| `symptoms` | string[] | 现象 |
| `possibleCauses` | string[] | 可能原因 |
| `solution` | string | 处理方案 |
| `result` | string | 处理结果 |
| `status` | string | `pending_review` / `approved` / `rejected` |
| `tags` | string[] | 标签 |
| `createdAt` | string | 创建时间 |
| `reviewedAt` | string | 审核时间 |

## 4. 作业流程 Workflow

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 流程 ID |
| `title` | string | 流程标题 |
| `deviceType` | string | 设备类型 |
| `faultType` | string | 故障类型 |
| `level` | string | 检修等级 |
| `tools` | string[] | 工具清单 |
| `safetyNotes` | string[] | 安全提醒 |
| `steps` | WorkflowStep[] | 步骤 |
| `acceptanceCriteria` | string[] | 验收标准 |

## 5. 作业步骤 WorkflowStep

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `order` | number | 步骤顺序 |
| `title` | string | 步骤标题 |
| `description` | string | 步骤说明 |
| `checkRequired` | boolean | 是否需要确认 |
| `warning` | string | 风险提示 |

## 6. 上传文件 UploadedFile

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 文件 ID |
| `fileName` | string | 原始文件名 |
| `fileType` | string | MIME 类型 |
| `path` | string | 本地存储路径 |
| `relatedType` | string | 关联对象类型 |
| `relatedId` | string | 关联对象 ID |
| `createdAt` | string | 上传时间 |

## 7. 入库资料 KnowledgeDocument

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 入库资料 ID |
| `fileName` | string | 原始文件名 |
| `fileType` | string | MIME 类型 |
| `suffix` | string | 文件扩展名 |
| `sourceName` | string | 资料来源名称 |
| `status` | string | `indexed` / `needs_parser` / `needs_ocr` / `empty` |
| `chunkCount` | number | 已生成知识片段数量 |
| `parser` | string | 使用的解析器或解析策略 |
| `uploadedAt` | string | 上传入库时间 |
| `url` | string | 本地访问路径 |

说明：

1. MVP 阶段入库资料保存到 `data/knowledge/documents.json`。
2. 真实资料文件保存到 `data/knowledge/files/`，该目录属于运行期数据，不提交 Git。
3. 测试环境通过 `APP_KNOWLEDGE_DIR` 指向临时目录。

## 8. 入库资料片段 DocumentChunk

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 片段 ID |
| `documentId` | string | 所属入库资料 ID |
| `title` | string | 片段标题，默认来自文件名 |
| `sourceType` | string | 固定为 `document` |
| `sourceName` | string | 资料来源名称 |
| `page` | number/null | 页码，文本资料可为空 |
| `chunkIndex` | number | 片段序号 |
| `content` | string | 完整片段文本 |
| `snippet` | string | 检索结果摘要 |
| `keywords` | string[] | 自动提取的轻量关键词 |

说明：

1. MVP 阶段片段保存到 `data/knowledge/document-chunks.json`。
2. 当前片段用于关键词检索，后续可作为向量化和 RAG 引用的原始语料。

## 9. 数据关系

```text
Device 1 -> N ManualDocument
Device 1 -> N RepairCase
Device 1 -> N Workflow
RepairCase N -> N UploadedFile
Workflow 1 -> N WorkflowStep
KnowledgeDocument 1 -> N DocumentChunk
```
