# 项目管理文档索引

> [!WARNING]
> **历史快照（非现行基线）**：本文记录 2026 年前期竞赛原型、阶段调研、验证或交付准备，仅用于追溯当时事实。文内“当前”“最终”“正式”“已完成”“必须”“一键部署”等表述均限定于当时范围，不构成现行产品状态、开发顺序、生产要求或交付承诺。现行口径以[根 README](../../README.md)、[软件需求规格说明书](../requirements/software-requirements-spec.md)和[修改日志索引](../change-log/INDEX.md)为准；发生冲突时，以这些现行文件及相关模块最新记录为准。本文中的命令、测试数量和部署结论未经当前版本复验，不得作为当前验收证据。

本目录保存开发前期和竞赛阶段的协作管理历史。它不记录现行开发状态，也不再承担开发入口或强制流程职能。

## 当时的文档编写规则

当时的协作规则要求项目文档保持上下文自包含，使后续 agent 或开发者不读取历史聊天记录也能理解当时进度、功能、风险和任务。现行文档规则以根 README、SRS 和修改日志机制为准。

当时曾要求涉及 API、数据状态、部署方式、演示路径、风险或任务优先级的变化同步写入 `agent-startup-context.md` 和 `current-handoff.md`。该同步要求已经失效；现行修改必须新增 `docs/change-log/` 记录并更新 `INDEX.md`。

以下仅为当时项目管理资料的历史阅读顺序，不是现行开发阅读顺序：

1. `agent-startup-context.md`：当时 Coding Agent 的入口，记录当时状态、风险、验证和下一步。
2. `development-workflow.md`：完整开发流程和三人分工。
3. `pre-development-checklist.md`：正式编码前检查清单。
4. `kickoff-meeting-agenda.md`：启动会议程和会后行动。
5. `technical-decision-record.md`：技术选型记录。
6. `task-board.md`：前期任务看板。
7. `development-plan.md`：后续开发阶段、任务分流与验收计划。
8. `model-task-classification.md`：模型能力分级与任务分类。
9. `ordinary-agent-development-guide.md`：普通模型 Agent 交接、执行边界与风险管理指南。

相关文档：

1. `../requirements/mvp-scope.md`：MVP 功能范围。
2. `../requirements/sample-data-plan.md`：样例数据准备计划。
3. `../design/api-contract-draft.md`：API 契约草案。
4. `../design/data-model-draft.md`：数据模型草案。
5. `../deployment/local-development-environment.md`：本地开发环境准备。
6. `../product/demo-script-outline.md`：演示脚本大纲。
7. `../research/open-source-architecture-research.md`：开源项目与技术栈调研结论。
