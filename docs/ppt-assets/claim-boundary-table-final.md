# 能力宣称边界表

版本日期：2026-06-27

| 能力 | 可以这样说 | 不要这样说 |
|---|---|---|
| 多模态 | 故障图片经 OCR/多模态语义线索进入检索，线索包含 OCR 文本、视觉症状、识别部件和图片摘要 | 已完成完整生产级图文向量跨模态检索 |
| RAG | 基于 approved evidence pack 输出结构化检修建议，保留 citations 和不确定信息 | 大模型可以独立给出所有正确维修参数 |
| 知识图谱 | 轻量知识关系网络 / 知识图谱原型，展示设备、故障、证据、案例、反馈关系 | 已实现完整工业图数据库平台 |
| LLM | 真实 Qwen 文本 LLM 已验证，mock/offline 可兜底 | 所有环境必然可连真实 LLM |
| Embedding | hash fallback 可运行，后续可接独立 embedding provider | 当前 Qwen embedding 已可用 |
| Qdrant/sqlite-vec/Chroma | 可选增强，目标环境验证后启用 | 主链路强依赖这些组件 |
| MinerU/OCR | 文档解析和 OCR 有 adapter / fallback，真实能力需环境验证 | 所有目标环境默认具备完整 OCR/MinerU |
| LoongArch | 主链路在 LoongArch/Kylin 有历史复验记录，最终提交前建议再跑验证脚本 | 任意增强依赖都已在 LoongArch 上生产验证 |
| RAG feedback | 支持标注/修正大模型输出，审核通过后进入知识关系网络 | feedback 会自动替代正式知识库证据 |
