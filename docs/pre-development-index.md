# 开发前期准备总览

> [!WARNING]
> **历史快照（非现行基线）**：本文记录 2026 年前期竞赛原型、阶段调研、验证或交付准备，仅用于追溯当时事实。文内“当前”“最终”“正式”“已完成”“必须”“一键部署”等表述均限定于当时范围，不构成现行产品状态、开发顺序、生产要求或交付承诺。现行口径以[根 README](../README.md)、[软件需求规格说明书](requirements/software-requirements-spec.md)和[修改日志索引](change-log/INDEX.md)为准；发生冲突时，以这些现行文件及相关模块最新记录为准。本文中的命令、测试数量和部署结论未经当前版本复验，不得作为当前验收证据。

本页是竞赛原型开工前使用的历史材料入口，不是当前开发入口。以下顺序和准入项仅反映当时流程。

## 1. 先读这些

| 顺序 | 文档 | 用途 |
| --- | --- | --- |
| 0 | `requirements/official-problem-baseline.md` | 固定官方赛题题面、硬约束、当前对齐与差距，避免后续开发偏题 |
| 1 | `project-management/agent-startup-context.md` | 当时 Coding Agent 的入口，了解当时状态、风险和下一步 |
| 2 | `project-management/development-workflow.md` | 理解整体流程和三人分工 |
| 3 | `project-management/pre-development-checklist.md` | 确认开工准入项 |
| 4 | `project-management/kickoff-meeting-agenda.md` | 开启动会并形成结论 |
| 5 | `project-management/technical-decision-record.md` | 固化技术选型 |
| 6 | `requirements/mvp-scope.md` | 收敛第一版功能 |

## 2. 再确认这些

| 文档 | 确认内容 |
| --- | --- |
| `design/api-contract-draft.md` | 前后端接口字段和响应结构 |
| `design/data-model-draft.md` | 核心数据实体和字段 |
| `requirements/sample-data-plan.md` | 第一批样例数据和演示资料 |
| `requirements/official-problem-baseline.md` | 对照官方赛题要求，判断实现是否偏移 |
| `deployment/local-development-environment.md` | 本地环境、环境变量、国产化适配记录 |
| `product/demo-script-outline.md` | 比赛演示主线和兜底方案 |
| `project-management/agent-startup-context.md` | Coding Agent 动态交接入口和最新工作状态 |
| `project-management/task-board.md` | 开发前期任务认领 |
| `project-management/development-plan.md` | 后续开发阶段、任务分流与验收计划 |
| `project-management/model-task-classification.md` | 高智能模型任务与普通模型任务分流 |
| `project-management/ordinary-agent-development-guide.md` | 普通模型 Agent 交接、执行边界与风险管理 |
| `research/open-source-architecture-research.md` | 开源项目与技术栈调研结论 |

## 3. 当时的开工前最低标准

1. 当时计划中的三人角色已确认。
2. 技术栈已确认。
3. MVP 范围已确认。
4. 第一批接口草案已确认。
5. 第一批数据结构已确认。
6. 第一批样例设备和故障案例已确认。
7. 每个人已认领至少一个 P0 任务。
8. 项目可以进入前端和后端工程初始化。
