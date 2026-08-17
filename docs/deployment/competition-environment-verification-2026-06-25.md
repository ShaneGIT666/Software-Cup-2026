# 比赛环境部署复验记录

> [!WARNING]
> **历史快照（非现行基线）**：本文记录 2026 年前期竞赛原型、阶段调研、验证或交付准备，仅用于追溯当时事实。文内“当前”“最终”“正式”“已完成”“必须”“一键部署”等表述均限定于当时范围，不构成现行产品状态、开发顺序、生产要求或交付承诺。现行文档的适用范围和来源优先级只以[根 README](../../README.md)第 1 节为入口；需求语义、动态状态、公共契约、领域事件和变更证据分别遵循该节指向的唯一事实源。本文中的命令、测试数量和部署结论未经当前版本复验，不得作为当前验收证据。

更新时间：2026-06-25

本文记录龙芯/Kylin 虚拟机上的实际部署复验结果。文档不记录 API Key、密码或内网敏感地址。

## 1. 环境信息

```text
访问方式：SSH，经映射端口访问
操作系统：Kylin Linux Advanced Server V11 (Swan25)
CPU 架构：loongarch64
主机名：win000k10481
Python：Python 3.11，venv 可用
Node：已安装
npm：未安装或不可用
Git：未安装或不可用
Docker：Docker 24.0.9 已安装，但服务 inactive，sudo 需要密码
磁盘：约 93G，总剩余约 83G
内存：约 11Gi，总可用约 8Gi
```

采集命令：

```bash
uname -m
cat /etc/os-release
python3 --version
python3 -m venv --help
node --version || true
npm --version || true
git --version || true
docker --version || true
systemctl is-active docker || true
df -h
free -h
```

结论：目标环境满足 Python venv + FastAPI 静态托管部署；Docker 路线因服务未启动且需要 sudo 密码，本次未作为主部署路线。

## 2. 部署方式

本次选择：

```text
[ ] Docker 一体化部署
[x] Python venv + FastAPI 静态托管 frontend/dist
[ ] 其他
```

部署摘要：

```bash
# 本地打包
powershell -ExecutionPolicy Bypass -File .\scripts\package-demo.ps1

# 上传 release zip 到目标环境
scp -i <ssh-key> -P <mapped-port> release/software-cup-demo-*.zip <user>@<host>:/home/vmuser/software-cup-demo-latest.zip

# 目标环境解压
mkdir -p /home/vmuser/software-cup-final-20260625
unzip -q /home/vmuser/software-cup-demo-latest.zip -d /home/vmuser/software-cup-final-20260625

# 创建 venv 并安装最小运行依赖
cd /home/vmuser/software-cup-final-20260625
python3 -m venv .venv-final
. .venv-final/bin/activate
python -m pip install --upgrade pip
python -m pip install pydantic\<2 fastapi==0.115.6 uvicorn==0.34.0 python-multipart==0.0.20 pytest==8.3.4 httpx==0.28.1 pypdf
```

说明：为降低 LoongArch 现场依赖风险，本次没有在 VM 上安装 ChromaDB、MinerU、OCR 重型依赖或 `uvicorn[standard]`。这些能力保留为可选增强，默认以 fallback 方式保证演示闭环。

## 3. Provider 配置摘要

```text
SERVE_FRONTEND=auto
FRONTEND_DIST_DIR=/home/vmuser/software-cup-final-20260625/frontend/dist
APP_EXAMPLES_DIR=/home/vmuser/software-cup-final-20260625/data/examples
APP_KNOWLEDGE_DIR=/home/vmuser/software-cup-final-20260625/runtime/knowledge
APP_UPLOAD_DIR=/home/vmuser/software-cup-final-20260625/runtime/uploads
REMOTE_API_MODE=off
LLM_PROVIDER=mock
MULTIMODAL_PROVIDER=mock
OCR_PROVIDER=mock
MINERU_ENABLED=false
RAG_VECTOR_STORE=off
RAG_EMBEDDING_PROVIDER=hash
RAG_RERANK_PROVIDER=heuristic
```

真实 LLM 复验配置另行通过运行时环境变量注入，不写入仓库或文档明文：

```text
REMOTE_API_MODE=auto
LLM_PROVIDER=openai
OPENAI_API_STYLE=chat_completions
OPENAI_BASE_URL=https://maas-api.cn-huabei-1.xf-yun.com/v2
OPENAI_MODEL=xopqwen36v35b
```

当前真实模型状态：已在 LoongArch/Kylin VM 上完成 Qwen3.6-35B-A3B OpenAI-compatible 接口验证。HTTP APIKey 只作为临时进程环境变量注入，未提交到仓库。

## 4. 复验结果

本地包内脚本复验：

| 项目 | 结果 | 证据 |
| --- | --- | --- |
| `scripts/production_readiness_check.py` | 通过 | 7 项检查全部 passed，耗时约 600.88ms |
| `scripts/json_store_maintenance.py` | 通过 | 4 个 JSON 文件 ok，0 issue，0 repaired |

HTTP 接口复验：

| 项目 | 结果 | 证据 |
| --- | --- | --- |
| `GET /` | 通过 | 返回前端 HTML，标题为“设备检修知识检索与作业指挥台” |
| `GET /api/health` | 通过 | `status=ok`，`version=0.1.0` |
| `GET /api/providers/status` | 通过 | 离线模式：`remoteApiMode=off`、LLM mock；真实模式：`remoteApiMode=auto`、`effectiveProvider=openai`、`keyConfigured=true` |
| `POST /api/providers/llm/validate` | 通过 | 真实模式轻量验证：`remoteOk=true`、provider `openai`、model `xopqwen36v35b`、`fallback=false`、latencyMs 约 12516 |
| `POST /api/search` | 通过 | 返回 4 条结果，首条 `doc-001` |
| `POST /api/rag/answer` | 通过 | 真实模式：provider `openai`、model `xopqwen36v35b`、`fallback=false`、3 条 citations、evidenceCount=3；离线模式 fallback 仍可用 |
| `POST /api/knowledge/documents/async` | 通过 | 上传任务返回 `queued` |
| `GET /api/review/items` | 通过 | pending_review 返回 2 条，首条类型 `knowledge_chunk` |
| `GET /api/review/events` | 通过 | 接口可访问；当前本次运行无审核动作，返回 0 条 |

## 5. 演示结论

```text
真实 LLM：已验证 Qwen3.6-35B-A3B，OpenAI-compatible chat_completions，RAG 返回 fallback=false
真实 embedding/Chroma：本次关闭，使用 hash fallback
OCR/MinerU：本次关闭，使用 mock/fallback
离线 fallback：可用
前端访问：可用，由 FastAPI 托管 frontend/dist
核心闭环：上传解析、pending_review、审核工作台、检索、RAG、citation/evidence、安全规则均可运行
主要风险：真实 LLM 长上下文首次请求可能接近 60s 超时，演示建议使用稳定问题和 topK=3；Docker 服务 inactive，现场需优先采用 venv 路线
```
