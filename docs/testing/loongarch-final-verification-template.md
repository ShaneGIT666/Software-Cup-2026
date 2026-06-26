# LoongArch / 银河麒麟最终复验模板

## 环境信息

- 日期：
- 机器：
- CPU 架构：
- OS：
- Python：
- Node：
- Docker：
- 内存：
- 磁盘：

## 部署方式

- [ ] Docker
- [ ] Python venv + FastAPI 静态托管

## 环境变量摘要

- `REMOTE_API_MODE=`
- `LLM_PROVIDER=`
- `OPENAI_BASE_URL=`
- `OPENAI_MODEL=`
- `MINERU_ENABLED=`
- `RAG_VECTOR_STORE=`
- `OCR_PROVIDER=`
- `MULTIMODAL_PROVIDER=`

## 验证结果

| 项目 | 命令/接口 | 结果 | 备注 |
|---|---|---|---|
| 后端健康 | `GET /api/health` |  |  |
| Provider 状态 | `GET /api/providers/status` |  |  |
| LLM 验证 | `POST /api/providers/llm/validate` |  |  |
| 检索 | `POST /api/search` |  |  |
| RAG | `POST /api/rag/answer` |  |  |
| 图片诊断 | `POST /api/multimodal/diagnosis` |  |  |
| 资料上传 | `POST /api/knowledge/documents/async` |  |  |
| 审核台 | `GET /api/review/items` |  |  |
| 知识图谱 | `GET /api/knowledge/graph` |  |  |

## 截图与日志

- Provider status：
- RAG 回答：
- 图片诊断：
- pending_review：
- 审核通过后检索命中：

## 结论

- 主链路：
- 增强功能：
- fallback：
- 未通过项：
