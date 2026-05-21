# 前期任务看板

本文档用于在正式使用 GitHub Issues 前进行任务管理。后续可以把每一行迁移为 Issue。

## 1. 状态说明

| 状态 | 含义 |
| --- | --- |
| Todo | 未开始 |
| Doing | 正在进行 |
| Review | 等待检查或联调 |
| Done | 已完成 |
| Blocked | 被阻塞 |

## 2. P0 开工任务

| 编号 | 任务 | 负责人 | 状态 | 截止建议 | 交付物 |
| --- | --- | --- | --- | --- | --- |
| PM-01 | 开启动会并确认角色 | C | Todo | 第 1 天 | 会议结论 |
| PM-02 | 确认技术栈 | 全员 | Todo | 第 1 天 | `technical-decision-record.md` |
| PM-03 | 确认 MVP 范围 | 全员 | Todo | 第 1 天 | `mvp-scope.md` |
| PM-04 | 确认第一批设备和故障场景 | 全员 | Todo | 第 1 天 | `sample-data-plan.md` |
| PM-05 | 建立 `dev` 分支 | C | Todo | 第 1 天 | Git 分支 |
| PM-06 | 初始化前端工程 | A | Done | 第 2 天 | `frontend/` 可启动，已通过生产构建 |
| PM-07 | 初始化后端工程 | B | Done | 第 2 天 | `backend/` 可启动，已通过接口测试 |
| PM-08 | 输出 API 契约第一版 | B | Done | 第 2 天 | `api-contract-draft.md` 已同步当前接口、错误响应和上传限制 |
| PM-09 | 准备第一批 mock 数据 | B/C | Done | 第 2 天 | `data/examples/` 已含设备、手册、案例、流程 |
| PM-10 | 输出本地启动说明 | C | Done | 第 3 天 | `docs/deployment/` 已记录 Anaconda 后端环境和启动命令 |

## 3. P1 增强任务

| 编号 | 任务 | 负责人 | 状态 | 交付物 |
| --- | --- | --- | --- | --- |
| FE-01 | 设计主要页面线框 | A | Todo | 页面草图或说明 |
| FE-02 | 准备前端 mock 数据结构 | A | Todo | mock 数据文件 |
| BE-01 | 设计数据模型草案 | B | Todo | 数据模型说明 |
| BE-02 | 设计大模型降级策略 | B | Todo | 降级响应说明 |
| DOC-01 | 需求分析文档大纲 | C | Todo | 文档大纲 |
| DOC-02 | 功能设计文档大纲 | C | Todo | 文档大纲 |
| DEMO-01 | 演示脚本第一版 | C | Todo | 演示步骤 |
| BE-03 | 后端可信边界测试 | B/C | Done | 12 个接口测试，覆盖非法审核、空查询、上传类型/大小/空文件/MIME 边界 |
| BE-04 | 资料入库 MVP | B/A | Done | `POST /api/knowledge/documents`、资料列表、chunk 检索、前端资料入库面板 |
| BE-05 | Mock RAG 辅助回答 | B/A | Done | `POST /api/rag/answer`，无 Key 返回带 citations 的 fallback 回答 |

## 4. 阻塞项记录

| 日期 | 阻塞项 | 影响 | 负责人 | 处理计划 |
| --- | --- | --- | --- | --- |
| 待补充 | 待补充 | 待补充 | 待补充 | 待补充 |

## 5. 后续开发计划入口

当前任务看板用于管理开工前任务，后续阶段性开发执行以 `development-plan.md` 为主线，并按 `model-task-classification.md` 将任务分为重点任务、普通任务和人工确认任务。

已纳入计划的近期重点：

1. 编写 3 到 5 分钟端到端演示检查清单。
2. 设计检索排序、命中原因和来源引用规则。
3. 设计 OpenAI-compatible 模型适配层和 mock 降级策略。
4. 评估 Docling、MinerU、PaddleOCR、LlamaIndex/LangChain 的后续集成成本、许可证和国产化风险。
5. 对国产化部署、答辩材料和最终参赛信息进行重点复审。
