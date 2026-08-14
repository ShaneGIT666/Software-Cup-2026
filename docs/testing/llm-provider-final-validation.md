# 真实 LLM Provider 最终验证记录

> [!WARNING]
> **历史快照（非现行基线）**：本文记录 2026 年前期竞赛原型、阶段调研、验证或交付准备，仅用于追溯当时事实。文内“当前”“最终”“正式”“已完成”“必须”“一键部署”等表述均限定于当时范围，不构成现行产品状态、开发顺序、生产要求或交付承诺。现行口径以[根 README](../../README.md)、[软件需求规格说明书](../requirements/software-requirements-spec.md)和[修改日志索引](../change-log/INDEX.md)为准；发生冲突时，以这些现行文件及相关模块最新记录为准。本文中的命令、测试数量和部署结论未经当前版本复验，不得作为当前验收证据。

## 配置原则

- 使用 OpenAI-compatible 协议接入比赛提供的 Qwen 服务。
- API Key 只写入目标环境 `.env`，不得提交到仓库、文档、截图或日志。
- 模型名、base_url、API key 均按 provider-specific 配置读取，不把 OpenAI 模型名强行套到 DashScope/Qwen。

## 建议环境变量

```bash
REMOTE_API_MODE=auto
LLM_PROVIDER=openai
OPENAI_BASE_URL=https://maas-api.cn-huabei-1.xf-yun.com/v2
OPENAI_API_STYLE=chat_completions
OPENAI_MODEL=xopqwen36v35b
LLM_TIMEOUT_SECONDS=60
RAG_USE_STRUCTURED_LLM_ANSWER=true
```

说明：仓库不提交 API Key。真实 LLM 需要在比赛现场或目标环境把 Key 写入未提交的 `.env` 后，再执行 `/api/providers/llm/validate` 和 `/api/rag/answer` 复验。代码当前只支持 `REMOTE_API_MODE=auto` 和 `REMOTE_API_MODE=off`，`auto` 表示优先尝试真实 provider，失败后自动回退 mock/offline 链路。

## 2026-06-27 本地真实 Qwen 验证记录

- 验证方式：仅把 Key 注入当前 PowerShell 进程环境变量，未写入仓库、文档、日志或 `.env`。
- 文本 LLM：`remoteOk=true`，`provider=openai`，`model=xopqwen36v35b`，`apiStyle=chat_completions`，`fallback=false`。
- 延迟：约 `7539ms`。
- 回答形态：返回包含【初步判断】【检修等级说明】等结构化 RAG 标题的中文检修建议。
- Embedding 边界：同一服务的 `/embeddings` 请求返回 `400 Bad Request`，系统按设计降级为 hash embedding；这不影响文本 LLM RAG 主链路，但不要宣称该 Qwen 服务已提供可用 embedding。
- 现场要求：如果比赛环境更换 Key、base_url、模型名或网络出口，仍需重新执行 `/api/providers/llm/validate` 与 `/api/rag/answer` 并留存截图。

## 必验接口

1. `GET /api/providers/status`
2. `POST /api/providers/llm/validate`
3. `POST /api/rag/answer`
4. `POST /api/multimodal/diagnosis`

## 通过标准

- Provider status 中 LLM `effectiveProvider` 不是 `mock`。
- `/api/providers/llm/validate` 返回 success。
- `/api/rag/answer` 至少一次返回非 mock 结构化建议，或返回 `llmAnswerMode=structured_evidence_answer`。
- 如果外部服务异常，系统返回检索结果和标准模板，不抛 500。

## 截图清单

- Provider status JSON。
- `/api/providers/llm/validate` 成功结果。
- RAG 建议页面，包含【初步判断】【引用证据】【不确定信息】。
- fallback 截图，说明降级链路可运行。
