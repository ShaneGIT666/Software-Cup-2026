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

1. `docs/pre-development-index.md`：开发前期准备总览。
2. `docs/project-management/development-workflow.md`：完整开发流程与三人分工。
3. `docs/project-management/pre-development-checklist.md`：正式编码前检查清单。
4. `docs/project-management/technical-decision-record.md`：技术选型记录。
5. `docs/requirements/mvp-scope.md`：MVP 功能范围。
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

## 当前状态

当前仓库已完成：

1. 基础目录结构初始化。
2. 开发流程与三人分工文档。
3. 开发前期准备清单。
4. MVP 范围定义。
5. API 契约草案。
6. 数据模型草案。
7. 样例数据准备计划。
8. 开源项目与技术架构调研。

下一步建议：

1. 团队确认技术栈和参赛信息。
2. 初始化前端工程。
3. 初始化后端工程。
4. 准备第一批样例设备、故障案例和手册片段。
5. 三天内完成最小可运行闭环。
