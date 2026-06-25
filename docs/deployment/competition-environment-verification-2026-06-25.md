# 比赛环境复验记录模板

更新时间：2026-06-25

> 本文用于拿到比赛提供环境后填写实测结果。不要写入 API Key、密码或内网敏感地址。

## 1. 环境信息

```text
访问方式：
操作系统：
CPU 架构：
Python：
Node：
npm：
Docker：
磁盘：
内存：
网络：
```

采集命令：

```bash
uname -m
cat /etc/os-release
python3 --version || true
node --version || true
npm --version || true
docker --version || true
df -h
free -h
```

## 2. 部署方式

选择其一：

```text
[ ] Docker 一体化部署
[ ] Python venv + FastAPI 静态托管 frontend/dist
[ ] 其他：
```

部署命令摘要：

```bash
# 粘贴不含密钥的命令
```

## 3. Provider 配置摘要

```text
REMOTE_API_MODE=
LLM_PROVIDER=
OPENAI_BASE_URL=已配置/未配置，不写真实 Key
OPENAI_MODEL=
MULTIMODAL_PROVIDER=
OCR_PROVIDER=
MINERU_ENABLED=
RAG_VECTOR_STORE=
RAG_EMBEDDING_PROVIDER=
```

## 4. 接口复验

| 项目 | 结果 | 证据 |
| --- | --- | --- |
| `GET /` | 待填 | 截图或 curl 输出 |
| `GET /api/health` | 待填 | JSON |
| `GET /api/providers/status` | 待填 | JSON，隐藏敏感信息 |
| `POST /api/providers/llm/validate` | 待填 | 是否真实 provider |
| `POST /api/search` | 待填 | 命中数量 |
| `POST /api/rag/answer` | 待填 | fallback 与 citations |
| `POST /api/knowledge/documents/async` | 待填 | taskId / documentStatus |
| `GET /api/review/items` | 待填 | pending_review 数量 |
| `GET /api/review/events` | 待填 | 审计事件数量 |

## 5. 演示结论

```text
真实 LLM：
真实 embedding/Chroma：
OCR/MinerU：
离线 fallback：
前端访问：
主要风险：
```
