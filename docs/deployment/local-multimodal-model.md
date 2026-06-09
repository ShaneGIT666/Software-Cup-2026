# 本地多模态大模型接入说明

本项目已支持通过 OpenAI-compatible `/v1/chat/completions` 协议接入本地视觉大模型服务，用于故障图片、现场照片、扫描图片等资料的多模态分析。该能力面向 Ollama、LM Studio、vLLM、Xinference、LiteLLM 网关等本地或内网部署方案。

## 适用范围

- 文本 RAG：继续使用 `LLM_PROVIDER=openai` + `OPENAI_API_STYLE=chat_completions` 接入本地或云端 OpenAI-compatible 服务。
- 图片多模态分析：使用 `MULTIMODAL_PROVIDER=local` 接入本地视觉模型。
- PDF 资料：本地视觉 provider 当前不直接上传 PDF；PDF 优先走文本解析或 OCR 入库，图片页可转图片后再走本地多模态分析。

## Ollama 示例

先准备本地视觉模型服务：

```powershell
ollama pull llava:latest
ollama serve
```

在项目 `.env` 中配置：

```env
REMOTE_API_MODE=off
MULTIMODAL_PROVIDER=local
LOCAL_MULTIMODAL_BASE_URL=http://127.0.0.1:11434/v1
LOCAL_MULTIMODAL_MODEL=llava:latest
LOCAL_MULTIMODAL_API_KEY=ollama
LOCAL_MULTIMODAL_MAX_TOKENS=1200
LOCAL_MULTIMODAL_TEMPERATURE=0.2
```

说明：

- `REMOTE_API_MODE=off` 会禁用公网 provider，但不会禁用 `local` 本地 provider。
- `LOCAL_MULTIMODAL_API_KEY` 对 Ollama 可填写任意非空占位值。
- 若本地模型调用失败，业务接口会自动降级到 mock 多模态结果，保证比赛现场演示不断线。

## 配置脚本

也可以使用脚本写入本地 `.env`：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\configure-api.ps1 `
  -Provider local `
  -BaseUrl "http://127.0.0.1:11434/v1" `
  -Model "llava:latest"
```

## 验证接口

启动后端后执行：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/api/providers/multimodal/validate" `
  -ContentType "application/json" `
  -Body '{"provider":"local"}'
```

返回中重点查看：

- `provider=local`
- `fallback=false`
- `summaryPreview` 有本地模型输出
- `latencyMs` 记录本地推理耗时

## 答辩口径

系统通过统一 Provider 适配层同时支持云端大模型和本地部署大模型。文本 RAG 可接入本地 OpenAI-compatible 文本模型；故障图片分析可接入本地 OpenAI-compatible 视觉模型。比赛现场可使用 `REMOTE_API_MODE=off` 保持离线演示，同时保留 `MULTIMODAL_PROVIDER=local` 调用内网或本机模型服务。
