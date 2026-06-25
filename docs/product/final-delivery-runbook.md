# 两天比赛最终交付 Runbook

更新时间：2026-06-25

## 1. 交付目标

两天内优先交付“比赛可演示、可部署、可答辩”的准生产级原型。核心要求是稳定展示：

1. 文本故障检索、证据卡片、标准作业流程和结构化 RAG 建议。
2. 资料上传、解析、`pending_review`、审核通过、正式检索命中。
3. 案例提交、审核、再次检索命中和审核流水追溯。
4. 真实 OpenAI-compatible LLM 至少一次 `fallback=false` 验收。
5. LoongArch/Kylin 或比赛提供环境的部署复验证据。

## 2. 本地最终验收

在仓库根目录执行：

```powershell
$env:MINERU_ENABLED="false"
.\backend\.venv\Scripts\python.exe -m pytest tests -q

cd frontend
npm.cmd run build
cd ..

powershell -ExecutionPolicy Bypass -File .\scripts\run-production-readiness-check.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\run-json-store-maintenance.ps1
git diff --check
git status --short --branch
```

当前已知可接受警告：

1. VueUse pure annotation warning。
2. Vite chunk size warning。

## 3. 真实模型复验

`.env` 推荐最小配置：

```env
REMOTE_API_MODE=auto
LLM_PROVIDER=openai
OPENAI_API_STYLE=chat_completions
OPENAI_BASE_URL=<比赛可用 OpenAI-compatible base_url>
OPENAI_MODEL=<文本模型名>
OPENAI_API_KEY=<不要提交>

MULTIMODAL_PROVIDER=mock
OCR_PROVIDER=mock
MINERU_ENABLED=false
RAG_VECTOR_STORE=off
RAG_EMBEDDING_PROVIDER=hash
```

验收接口：

```text
GET  /api/providers/status
POST /api/providers/llm/validate
POST /api/rag/answer
```

验收标准：

1. provider status 中 LLM effectiveProvider 不是 `mock`。
2. validate 返回成功。
3. RAG 回答中 `fallback=false`，且 citations/evidencePack 存在。

## 4. 比赛环境复验

优先 Docker 路线：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\package-demo.ps1
```

在目标环境记录：

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

必须验证：

```text
GET /
GET /api/health
GET /api/providers/status
POST /api/search
POST /api/rag/answer
POST /api/knowledge/documents/async
GET /api/review/items
GET /api/review/events
```

## 5. 演示主线

主线 A：文本检修

```text
发动机-示例型号 A
启动困难，怠速不稳，排气异常
```

展示顺序：检索结果 -> evidence cards -> 作业流程 -> RAG 建议 -> 安全提醒。

主线 B：资料入库

上传 Markdown/TXT 小资料，展示 pending_review -> 审核通过 -> 再次检索命中。

主线 C：知识沉淀

提交维修案例 -> 审核通过 -> 审计流水 -> 再次检索命中新案例。

## 6. 答辩口径

可以说：

1. 系统具备上传、解析、审核、检索、证据引用、结构化 RAG、流程指引、案例沉淀和审计追溯闭环。
2. 支持 OpenAI-compatible 云端模型，也支持离线 mock 兜底。
3. 自动解析结果默认不进入正式知识库，必须审核通过才参与检索和 RAG。
4. Chroma 和真实 OCR/MinerU 是可选增强，目标环境可按依赖情况开启。

不要说：

1. mock OCR 或 mock 多模态等同生产级视觉诊断。
2. hash embedding 是真实语义 embedding。
3. JSON 文件存储等同高并发生产数据库。
4. 当前系统已经具备商用级权限、审计防篡改和工业安全认证。
