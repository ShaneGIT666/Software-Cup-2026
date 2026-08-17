# 最终架构说明

> [!WARNING]
> **历史快照（非现行基线）**：本文记录 2026 年前期竞赛原型、阶段调研、验证或交付准备，仅用于追溯当时事实。文内“当前”“最终”“正式”“已完成”“必须”“一键部署”等表述均限定于当时范围，不构成现行产品状态、开发顺序、生产要求或交付承诺。现行文档的适用范围和来源优先级只以[根 README](../../README.md)第 1 节为入口；需求语义、动态状态、公共契约、领域事件和变更证据分别遵循该节指向的唯一事实源。本文中的命令、测试数量和部署结论未经当前版本复验，不得作为当前验收证据。

版本日期：2026-06-27

## 1. 架构目标

系统以比赛可交付为优先，围绕设备检修形成“输入 -> 检索 -> 指引 -> 审核 -> 沉淀 -> 再检索”的闭环。架构要求是轻量、可部署、可降级、可解释，并能在 LoongArch / 银河麒麟目标环境中尽量保持主链路可运行。

## 2. 前端结构

前端为 Vue 3 + Element Plus PC Web，采用单页内部状态切换，不引入 Vue Router。

顶层区域：

- 检修助手：默认首页，面向一线人员。
- 管理中心：面向管理员、班组长和知识维护人员。
- 系统状态：面向运维和答辩展示。

检修助手链路：

```text
描述故障 -> 查看依据 -> 生成指引 -> 复核修正 -> 提交经验
```

## 3. 后端结构

后端为 FastAPI，主要模块：

- `main.py`：API 路由。
- `services.py`：业务服务。
- `retrieval/`：检索流程。
- `rag.py`：RAG 回答。
- `knowledge.py`：资料入库、解析和资产分析。
- `review_workbench.py`：审核工作台。
- `knowledge_graph.py`：轻量知识关系图。
- `provider_policy.py` / adapters：LLM、OCR、多模态和 embedding provider。

## 4. 数据流

```text
故障输入 / 图片 / 资料
-> OCR / 多模态线索 / 文档解析
-> pending_review
-> 人工审核
-> approved 知识片段 / 案例 / 回答修正
-> approved-only 检索
-> Evidence Pack
-> 智能检修建议
-> 回答修正和案例回流
-> 知识关系图
```

## 5. 知识关系图

知识关系图由 approved 内容生成，包含：

- 设备。
- 故障。
- 手册。
- 资料片段。
- 案例。
- 流程。
- 术语。
- 回答修正。
- 模型分析来源。

前端使用原生 SVG 绘制轻量网络图，最多展示 24 个重要节点，保留完整节点和关系列表。点击节点可查看属性和相关关系。

## 6. Provider 与降级策略

真实 LLM 通过 OpenAI-compatible 配置接入。默认允许离线演示：

- LLM 不可用时回退 mock/offline。
- OCR 或多模态不可用时回退 OCR/mock/文本线索。
- 向量增强不可用时回退本地轻量检索。
- MinerU 不可用时回退普通解析或 mock parser。

系统状态页展示当前 provider、fallback 和初始化配置指引，但不保存 API Key。

## 7. 初始化配置

新增脚本：

- `scripts/init-config.ps1`
- `scripts/init-config.sh`
- `scripts/validate-provider.ps1`
- `scripts/validate-provider.sh`

脚本支持离线演示模式和真实 LLM 模式。写入 `.env` 前备份旧文件，API Key 只脱敏显示。

## 8. 国产化部署边界

LoongArch / 银河麒麟环境以主链路可运行为硬约束。Chroma、Qdrant、sqlite-vec、MinerU 和真实多模态 provider 均视目标环境可用性启用，不作为不可降级硬依赖。Docker 优先，venv + FastAPI 静态托管作为兜底。

## 9. 安全边界

- 正式检索和 RAG 引用默认只使用 approved 内容。
- pending_review、rejected、deprecated、replaced 不进入正式检索。
- API Key 不通过 Web 保存，不提交到仓库。
- mock、hash、fallback 不夸大为生产级能力。
