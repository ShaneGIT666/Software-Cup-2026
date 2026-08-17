# 最终答辩讲解要点

> [!WARNING]
> **历史快照（非现行基线）**：本文记录 2026 年前期竞赛原型、阶段调研、验证或交付准备，仅用于追溯当时事实。文内“当前”“最终”“正式”“已完成”“必须”“一键部署”等表述均限定于当时范围，不构成现行产品状态、开发顺序、生产要求或交付承诺。现行口径以[根 README](../../README.md)、[软件需求规格说明书](../requirements/software-requirements-spec.md)和[修改日志索引](../change-log/INDEX.md)为准；发生冲突时，以这些现行文件及相关模块最新记录为准。本文中的命令、测试数量和部署结论未经当前版本复验，不得作为当前验收证据。

版本日期：2026-06-27

## 一句话定位

这是一个面向设备检修场景的 PC Web 作业辅助系统，通过 approved-only 检索、Evidence Pack、结构化 RAG、多模态图片线索和审核后知识沉淀，帮助一线人员更快、更规范地完成检修。

## 核心卖点

1. 不是普通 RAG Demo：系统有资料入库、审核状态机、revision、审计、案例回流和知识关系网络。
2. 多模态可证明：故障图片转为 OCR 文本、视觉症状、识别部件和图片线索，并显示跨模态匹配说明。
3. RAG 可追溯：每条建议都能追溯到 Evidence Pack、chunk、source doc、page 和 section。
4. 作业更规范：输出检修等级、作业前准备、风险控制、合规校验、安全提醒和验收标准。
5. 知识可沉淀：案例、资料片段、RAG 回答修正均默认 pending_review，审核通过后进入知识网络。
6. 国产化优先：LoongArch/Kylin 主链路已验证，默认不硬依赖无法确认的 native-heavy 组件。

## 技术路线说明

- 前端：Vue 3 + Element Plus。
- 后端：FastAPI + JSON 原子存储。
- 检索：approved-only + 关键词 / 可选向量 + RRF + Evidence Pack。
- LLM：OpenAI-compatible Qwen 可接入，mock/offline 兜底。
- 向量：默认 SQLite python_scan / hash fallback，Chroma/Qdrant/sqlite-vec 可选。
- 多模态：OCR/视觉 provider 可选，失败不影响主链路。

## 答辩风险回答

- 问：是不是生产级图文向量检索？
  答：当前是原型级跨模态语义线索匹配，生产级图文向量检索是后续增强。

- 问：知识图谱是否完整？
  答：当前是轻量知识关系网络 / 知识图谱原型，用于展示审核后的知识沉淀和证据关系。

- 问：没有网络或 Key 怎么办？
  答：系统保留 offline/mock 主链路，现场可继续完成检索、RAG 模板、审核和图谱演示。

- 问：为什么不用 Chroma 作为默认？
  答：Chroma 的 native HNSW 依赖在 LoongArch/Kylin 目标环境不可稳定安装，因此降级为可选增强。
