# 最终答辩讲解要点

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
