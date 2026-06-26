# 真实 LLM Provider 最终验证记录

## 配置原则

- 使用 OpenAI-compatible 协议接入比赛提供的 Qwen 服务。
- API Key 只写入目标环境 `.env`，不得提交到仓库、文档、截图或日志。
- 模型名、base_url、API key 均按 provider-specific 配置读取，不把 OpenAI 模型名强行套到 DashScope/Qwen。

## 建议环境变量

```bash
REMOTE_API_MODE=on
LLM_PROVIDER=openai
OPENAI_BASE_URL=https://maas-api.cn-huabei-1.xf-yun.com/v2
OPENAI_API_STYLE=chat_completions
OPENAI_MODEL=xopqwen36v35b
LLM_TIMEOUT_SECONDS=60
RAG_USE_STRUCTURED_LLM_ANSWER=true
```

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
