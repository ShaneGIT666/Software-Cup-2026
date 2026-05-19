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

## 7. 数据关系

```text
Device 1 -> N ManualDocument
Device 1 -> N RepairCase
Device 1 -> N Workflow
RepairCase N -> N UploadedFile
Workflow 1 -> N WorkflowStep
```

