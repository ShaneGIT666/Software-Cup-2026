# LoongArch / 银河麒麟最终复验说明

## 目标

所有比赛交付能力以 LoongArch/银河麒麟目标环境可运行为准。无法在目标环境稳定运行的增强能力不得作为主链路承诺，应降级为可选或替换技术路线。

## 推荐执行

```bash
bash scripts/loongarch-final-verify.sh
```

脚本只执行本地健康检查、依赖检查、后端测试、前端构建和接口冒烟，不写入 API Key。

## 成功标准

- 后端测试通过。
- 前端构建通过。
- `GET /api/health` 可用。
- `GET /api/providers/status` 可用。
- 检索、RAG、图片诊断、上传审核链路可执行。

## 技术路线约束

- Docker 可用时优先 Docker 部署。
- Docker 不可用时使用 Python venv + FastAPI 静态托管 `frontend/dist`。
- MinerU、OCR、向量增强、视觉模型必须有 fallback。
- 真实 LLM 使用比赛提供的 OpenAI-compatible Qwen 服务。
