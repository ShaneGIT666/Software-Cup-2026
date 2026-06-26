# 最终演示 Runbook

## 启动

1. 准备 `.env`，不要提交：

```env
APP_ENV=production
SERVE_FRONTEND=auto
REMOTE_API_MODE=auto
LLM_PROVIDER=openai
OPENAI_BASE_URL=<base-url>
OPENAI_MODEL=<model>
OPENAI_API_STYLE=chat_completions
OPENAI_API_KEY=<secret>
RAG_VECTOR_STORE=sqlite
RAG_VECTOR_SQLITE_ENGINE=python_scan
RAG_VECTOR_ENHANCER=off
RAG_VECTOR_FALLBACK_LOCAL=on
MINERU_ENABLED=false
```

2. Docker 启动：

```bash
docker run --rm -p 8000:8000 --env-file .env software-cup-demo:final
```

3. 浏览器访问：

```text
http://<host>:8000
```

## 演示主线一：检索诊断与证据追溯

1. 打开首页，输入设备型号和故障描述。
2. 点击检索，展示命中资料、案例和知识片段。
3. 展开结果，说明 `chunkId/sourceDocId/page/section` 可以追溯。
4. 说明检索结果只包含 `approved`，待审核内容不会进入正式回答。

## 演示主线二：RAG 建议

1. 使用同一故障问题调用 RAG 回答。
2. 展示固定结构：
   - 初步判断
   - 建议检查步骤
   - 建议维修步骤
   - 安全提醒
   - 验收标准
   - 引用证据
   - 不确定信息
3. 指出高风险 evidence 会提示人工复核。
4. 打开 `/api/providers/status` 或状态页，说明真实 LLM/provider/fallback 状态。

## 演示主线三：上传、解析、审核、入库

1. 上传 PDF/图片资料。
2. 解析产物进入 `pending_review`。
3. 如果 PDF 包含图片 assets，后台资产分析会生成 `ocr_result/image_analysis` 片段。
4. 在审核台批准一个片段。
5. 再次检索，展示审核通过片段可以被命中并出现在 citation 中。

## 演示主线四：目标环境 fallback

1. 将 `REMOTE_API_MODE=off` 或断开真实模型。
2. 系统仍可完成首页、检索、审核和模板化 RAG。
3. 说明 mock/offline 只用于现场稳定性兜底，真实能力以 provider validate 和真实 LLM 回答为准。

## 关键接口

```text
GET  /api/health
GET  /api/providers/status
POST /api/providers/llm/validate
POST /api/search
POST /api/rag/answer
POST /api/knowledge/documents/async
GET  /api/review/items
GET  /api/system/status
```

