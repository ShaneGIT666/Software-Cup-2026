# RAG 评测执行器开源借鉴记录

日期：2026-06-16

本文记录第二轮“RAG 评测执行器与现有检索基线测量”的外部参考。结论是：借鉴成熟框架的指标和组织方式，但不直接引入它们作为运行时依赖，先保持离线、轻量、可重复运行。

## 借鉴 Ragas 的内容

参考：[Ragas Metrics](https://docs.ragas.io/en/stable/concepts/metrics/) 与 [Ragas GitHub](https://github.com/explodinggradients/ragas)。

Ragas 把 RAG 指标拆成 retrieval/context 与 response/faithfulness 两类。本轮只评测检索，因此借鉴其中 retrieval/context 侧的思想：

1. 用数据集驱动评测，而不是靠单次人工提问判断效果。
2. 明确 expected context/source，用 Recall@K 观察应召回证据是否出现。
3. 把后续可扩展的生成质量指标（faithfulness、response relevancy）先留在 schema 和报告结构里，但本轮不计算。

本轮没有引入 Ragas 运行时，因为它通常需要 LLM-as-judge 或额外 evaluator 配置；当前目标是先测“检索基线”，避免真实模型、API Key 和网络把测试变成不稳定项。

## 借鉴 DeepEval 的内容

参考：[DeepEval Metrics Introduction](https://deepeval.com/docs/metrics-introduction) 与 [DeepEval GitHub](https://github.com/confident-ai/deepeval)。

DeepEval 的价值在于把评测组织成类似测试用例和指标断言的结构。本轮借鉴：

1. 每条评测样本是独立 case，包含输入、期望来源、禁止来源和备注。
2. 指标输出既有汇总分，也保留每条 case 的失败原因。
3. 报告可用于 CI 或人工 review，而不是只打印一次命令行结果。

本轮没有引入 DeepEval，因为它的完整能力偏 LLM 质量评估和平台化报告，本项目当前只需要离线 retrieval metrics。直接引入会增加依赖、登录/平台配置和国产化验证成本。

## 借鉴 Haystack 的内容

参考：[Haystack Evaluation](https://docs.haystack.deepset.ai/docs/evaluation) 与 [Haystack GitHub](https://github.com/deepset-ai/haystack)。

Haystack 的 Evaluation 设计强调 pipeline/component 层面的可测性。本轮借鉴：

1. 只评测 retrieval component，不混入 generator prompt 质量。
2. 输入数据、执行器和报告写入分层：`dataset_loader`、`retrieval_evaluator`、`report_writer`。
3. 保留以后扩展到 parser、reranker、generator 的接口位置。

本轮没有引入 Haystack，是因为当前系统已经有 FastAPI 服务、JSON 数据和自研检索函数。引入 Haystack Pipeline 会导致运行时结构迁移，不符合“只测基线”的边界。

## 借鉴 LlamaIndex 的内容

参考：[LlamaIndex Evaluating](https://developers.llamaindex.ai/python/framework/module_guides/evaluating/) 与 [LlamaIndex GitHub](https://github.com/run-llama/llama_index)。

LlamaIndex 的评测结构强调 query、expected nodes/context 和 retriever 结果之间的映射。本轮借鉴：

1. 数据集中显式维护 `expected_source_ids` 和 `expected_chunk_ids`。
2. 结果匹配不仅看 answer 文本，还看 source id、document id、chunk id 和 workflow id。
3. 后续如果引入 document node/schema，可以把当前 case schema 平滑映射过去。

本轮没有引入 LlamaIndex，因为当前资料片段、种子手册、维修案例和流程已经有本地结构；为了评测现状，直接调用 `services.search_knowledge()` 更能保证基线没有被框架适配层改变。

## 当前轻量实现的限制

1. 只评测检索，不评测 RAG 自由生成答案质量。
2. 不计算 faithfulness、answer relevancy、context precision 等 LLM-as-judge 指标。
3. `fallback_count` 当前标记为 unavailable，因为 `/api/search` 和 `search_knowledge()` 不返回逐查询 fallback 事件。
4. `metadata_filters` 目前是评测数据中的期望约束，尚未驱动后端实际过滤。
5. 当前 source matching 依赖 `id/documentId/chunkId/workflowId`，后续 evidence pack 规范化后可以更精确。

## 后续何时值得接入完整框架

当系统进入以下阶段时，可以重新评估引入完整框架：

1. 已有稳定的 retrieval pipeline 和 evidence pack，需要评测 parser、retriever、reranker、generator 多组件链路。
2. 需要 LLM-as-judge 批量评估回答 faithful/relevant/safe。
3. CI 需要跨版本趋势图、实验追踪或团队共享仪表盘。
4. 已完成 LoongArch/Kylin 对新增依赖的安装、离线运行和 license 复核。

## 许可证与部署影响

| 项目 | 许可证口径 | 本轮影响 |
| --- | --- | --- |
| Ragas | GitHub 仓库显示 Apache-2.0 license | 只参考指标思想，不引入依赖 |
| DeepEval | GitHub 仓库显示 Apache-2.0 license | 只参考测试组织方式，不引入依赖 |
| Haystack | GitHub 仓库显示 Apache-2.0 license | 只参考分层评测结构，不引入依赖 |
| LlamaIndex | GitHub 仓库显示 MIT license | 只参考 query/context/source schema 思路，不引入依赖 |

因此本轮不会改变生产部署包、Docker 镜像、LoongArch/Kylin 最小部署链路，也不会新增外部网络依赖。
