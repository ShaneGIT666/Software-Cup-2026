# 设备检修知识检索与作业辅助系统

本项目为第十五届中国软件杯 A 组赛题“基于多模态大模型技术的设备检修知识检索与作业系统”的参赛作品仓库。

系统面向工业、能源、制造等场景中的设备检修作业，目标是通过多模态大模型、知识检索、标准化作业流程和经验案例沉淀，帮助一线检修人员更快查找资料、诊断故障、规范作业，并让维修经验持续进入知识库。

## 参赛信息

| 项目 | 内容 |
| --- | --- |
| 参赛编号 | 65013181 |
| 队名 | �錕斤拷錕斤拷��� |
| 题号 | A 组赛题，具体题号待确认 |
| 队长 | 刘子翔 |
| 队伍成员 | 张倬然、周梓聪 |
| 指导老师 | 焦新涛 |
| 学校 | 华南师范大学 |

## 项目目标

第一阶段优先完成一个可演示、可部署、文档完整的 B/S 系统原型，覆盖以下核心能力：

1. 多模态知识检索：支持文本、设备型号、故障描述、图片等输入。
2. 标准化作业指引：按设备、故障和检修等级输出步骤化作业流程。
3. 知识沉淀更新：支持维修案例提交、审核、标注和入库。
4. 大模型辅助诊断：通过可替换模型适配层提供诊断建议和作业提醒。
5. 国产化部署说明：面向 LoongArch 架构和银河麒麟高级服务器操作系统保留适配记录。

## 推荐技术路线

根据前期调研，本项目推荐采用轻量、可替换、便于三人协作的架构：

| 模块 | 推荐方案 |
| --- | --- |
| 前端 | Vue 3 + TypeScript + Vite + Element Plus |
| 后端 | Python FastAPI |
| 开发数据库 | SQLite |
| 检索方案 | 关键词检索 + 来源引用起步，第二阶段接 Chroma |
| 向量库 | Chroma MVP，Qdrant 二阶段 |
| 模型接入 | OpenAI-compatible Adapter，默认 Mock 模式 |
| 文档解析 | Markdown/JSON/PDF 文本起步，后续接 PaddleOCR、MinerU、Docling |
| 部署 | 本地脚本 MVP，Docker Compose 二阶段 |

完整调研结论见：`docs/research/open-source-architecture-research.md`

## 仓库结构

```text
.
├── backend/                  # 后端 API、检索、模型适配、数据访问
├── frontend/                 # Web 前端页面、组件、接口调用
├── data/
│   ├── examples/             # 演示样例和种子数据
│   ├── manuals/              # 检修手册和知识资料
│   └── uploads/              # 开发期上传文件
├── deploy/                   # 部署配置和发布材料
├── docs/
│   ├── deployment/           # 本地运行、安装部署、国产化适配
│   ├── design/               # API、数据模型、系统设计
│   ├── product/              # 产品说明、演示脚本、PPT 材料
│   ├── project-management/   # 开发流程、任务分工、看板
│   ├── requirements/         # 需求分析、MVP 范围、样例数据计划
│   ├── research/             # 开源项目与技术架构调研
│   └── testing/              # 测试计划和测试报告
├── scripts/                  # 初始化、构建、测试等辅助脚本
└── tests/                    # 自动化测试和接口测试
```

## 开发前必读

建议团队成员按以下顺序阅读和确认：

1. `docs/project-management/agent-startup-context.md`：Coding Agent 第一入口，记录最新状态、风险、验证和下一步。
2. `docs/pre-development-index.md`：开发前期准备总览。
3. `docs/project-management/development-plan.md`：后续开发阶段、任务分流与验收计划。
4. `docs/project-management/model-task-classification.md`：高智能模型任务与普通模型任务分流。
5. `docs/project-management/ordinary-agent-development-guide.md`：普通模型 Agent 交接、执行边界与风险管理。
6. `docs/design/api-contract-draft.md`：前后端接口契约草案。
7. `docs/research/open-source-architecture-research.md`：开源项目与架构调研结论。

## MVP 演示主线

第一版系统优先跑通以下闭环：

```text
输入设备型号和故障描述
-> 返回知识检索结果、相关手册和历史案例
-> 查看标准化作业步骤、安全提醒和验收标准
-> 提交维修经验案例
-> 审核后进入知识库
-> 再次检索时可复用新案例
```

MVP 完成前，优先保证“能打开、能搜索、能看步骤、能提交案例、能演示”，暂缓完整权限系统、复杂知识图谱、高精度图片识别和本地大模型部署。

## 本地运行

一键启动前后端开发服务：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1
```

启动后访问：

```text
http://localhost:5173
```

停止后台服务：

```powershell
Stop-Job software-cup-* -WarningAction SilentlyContinue; Remove-Job software-cup-* -WarningAction SilentlyContinue
```

如果需要分别启动，也可以使用 `scripts/start-backend.ps1` 和 `scripts/start-frontend.ps1`。

## 当前状态

当前仓库已完成：

1. Vue 3 + TypeScript + Vite + Element Plus 前端工作台。
2. FastAPI 后端 API 骨架。
3. 本地 JSON 样例数据，包括设备、手册、案例和流程。
4. 检索、流程查看、上传、案例提交、案例审核、审核后再检索的 MVP 闭环。
5. 前端组件拆分：检索输入、结果列表、作业流程、案例提交、案例审核。
6. Anaconda 本地环境脚本、前端启动脚本、后端启动脚本和后端测试脚本。
7. 后端接口测试通过，前端生产构建通过。
8. Coding Agent 动态交接入口：`docs/project-management/agent-startup-context.md`。

下一步建议：

1. 扩展后端边界测试，覆盖非法审核 action、空查询、非法/空上传。
2. 设计检索排序和来源引用规则，让结果能解释命中原因、来源章节和页码。
3. 编写 3 到 5 分钟端到端演示检查清单，包含固定输入和失败兜底。
4. 同步更新 `development-plan.md` 和 `task-board.md` 的完成状态。
5. 设计 OpenAI-compatible 模型适配层和 mock 降级策略，先设计接口，不急于接真实模型。
