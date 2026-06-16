# 软件安装包及部署文档

> 项目：基于多模态大模型技术的设备检修知识检索与作业系统
> 版本：v0.1.0
> 日期：2026-05-21

## 1. 环境要求

### 1.1 硬件要求

| 配置项 | 最低要求 | 推荐配置 |
|--------|----------|----------|
| CPU 架构 | LoongArch 自主指令集 | LoongArch 4 核+ |
| CPU 核数 | 4 核 | 8 核 |
| 内存 | 8 GB | 16 GB |
| 硬盘 | 256 GB | 512 GB SSD |
| 网络 | 可访问局域网 | 可访问互联网（用于 LLM API 调用） |

### 1.2 软件要求

| 软件 | 版本要求 | 用途 |
|------|----------|------|
| 银河麒麟高级服务器操作系统 | V10 / V11 | 操作系统（赛题要求） |
| Python | 3.10+ | 后端运行环境 |
| Node.js | 20 LTS+ | 前端构建运行环境 |
| npm | 9+ | 前端包管理 |
| Git | 2.0+ | 源码管理 |

### 1.3 依赖软件包

#### Python 依赖（backend/requirements.txt）

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
python-multipart==0.0.20
pytest==8.3.4
httpx==0.28.1
```

可选依赖（PDF 解析）：`pypdf`

#### Node.js 依赖（frontend/package.json）

```
vue 3.5.13
element-plus 2.9.3
vite 7.3.3
typescript 5.7.2
@lucide/vue 1.16.0
```

## 2. 安装步骤

### 2.1 获取源码

```bash
git clone <仓库地址>
cd Software-Cup-2026
```

### 2.2 后端环境初始化

#### 方式一：使用 conda 环境（推荐）

```bash
conda create -n maintenance-copilot python=3.10 -y
conda activate maintenance-copilot
cd backend
pip install -r requirements.txt
pip install pypdf  # 可选：PDF 解析支持
```

#### 方式二：使用系统 Python + venv

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2.3 前端依赖安装

```bash
cd frontend
npm install
```

### 2.4 配置文件

复制环境变量模板并进行配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```ini
APP_ENV=development
APP_PORT=8000
FRONTEND_PORT=5173
DATABASE_URL=sqlite:///./data/app.db
UPLOAD_DIR=./data/uploads
LLM_PROVIDER=mock
```

#### 接入大模型（可选）

**OpenAI Provider：**

```ini
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4.1-mini
LLM_TIMEOUT_SECONDS=20
```

**Anthropic Provider：**

```ini
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxx
ANTHROPIC_BASE_URL=https://api.anthropic.com/v1
ANTHROPIC_MODEL=claude-3-5-haiku-latest
LLM_TIMEOUT_SECONDS=20
```

**国内兼容 API（DeepSeek / Qwen 等）：**

```ini
LLM_PROVIDER=openai
OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-chat
```

## 3. 启动与运行

### 3.1 开发模式启动

#### Windows 一键启动

```bat
start-dev.bat
```

#### 手动分别启动

**启动后端（终端 1）：**

```bash
cd backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

验证后端启动：

```bash
curl http://127.0.0.1:8000/api/health
# 返回: {"success":true,"data":{"status":"ok","version":"0.1.0"}}
```

**启动前端（终端 2）：**

```bash
cd frontend
npm run dev
```

访问：http://localhost:5173

### 3.2 生产模式部署

生产模式需要同时提供前端静态文件和后端 API 服务。仅启动 FastAPI 后端不会自动托管 `frontend/dist`，因此推荐使用 Nginx 提供前端静态文件，并将 `/api/`、`/uploads/`、`/knowledge/` 反向代理到后端。

```bash
cd frontend
npm run build

cd ../backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

#### Nginx 反向代理配置（推荐）

```nginx
server {
    listen 80;
    server_name localhost;
    root /path/to/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /uploads/ {
        proxy_pass http://127.0.0.1:8000;
    }

    location /knowledge/ {
        proxy_pass http://127.0.0.1:8000;
    }
}
```

如果比赛演示只需要验证生产构建结果，也可以在前端目录临时运行：

```bash
cd frontend
npm run preview -- --host 127.0.0.1 --port 4173
```

此方式适合本地演示，不等同于最终 LoongArch + 银河麒麟生产部署证明。

### 3.3 停止服务

```bat
:: Windows
stop-dev.bat
```

```bash
# Linux/Mac
pkill -f uvicorn
pkill -f vite
```

## 4. 安装验证

### 4.1 健康检查

```bash
curl http://127.0.0.1:8000/api/health
```

预期输出：

```json
{"success":true,"data":{"status":"ok","version":"0.1.0"},"message":""}
```

### 4.2 核心功能走查

| 序号 | 验证项 | 操作 | 预期结果 |
|------|--------|------|----------|
| 1 | 知识检索 | POST /api/search，填入设备型号和故障文本 | 返回至少 1 条结果，含 matchedTerms 和 scoreBreakdown |
| 2 | 流程查看 | GET /api/workflows/wf-001 | 返回 4 个步骤、3 个工具、3 个安全提醒和 3 个验收标准 |
| 3 | 案例提交 | POST /api/cases，填入案例信息 | 返回 id 和 status=pending_review |
| 4 | 案例审核 | PATCH /api/cases/{id}/review，action=approve | 返回 status=approved |
| 5 | 前端访问 | 浏览器打开 http://localhost:5173 | 显示工业控制台风格界面，自动执行初始检索 |
| 6 | 资料入库 | POST /api/knowledge/documents，上传 txt 文件 | 返回 status=pending_review，chunkCount≥1，pendingReviewCount≥1 |
| 7 | 资料片段查看 | GET /api/knowledge/documents/{id}/chunks | 返回 pending_review 知识片段；审核通过前不进入正式检索 |

## 5. 常见问题排查

### 5.1 端口占用

```bash
lsof -i :8000   # 查看占用 8000 端口的进程
lsof -i :5173   # 查看占用 5173 端口的进程
kill -9 <PID>   # 终止进程
```

### 5.2 Python 依赖冲突

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 5.3 LoongArch 兼容性注意事项

1. **pypdf**：纯 Python 实现，无原生依赖，可在 LoongArch 上直接安装使用
2. **Python 3.10+**：需确认银河麒麟软件源中有对应版本，或从源码编译
3. **Node.js**：需确认 LoongArch 架构的 Node.js 二进制包可用，或从源码编译
4. **向量数据库（Chroma/Qdrant）**：二阶段规划，需验证在 LoongArch 上的安装和运行
5. **大模型推理**：LoongArch 上运行本地大模型（llama.cpp/Ollama）需专项评估

### 5.4 PDF 解析问题

- **状态显示 "needs_parser"**：安装 pypdf（`pip install pypdf`）
- **状态显示 "needs_ocr"**：PDF 为扫描件（图片型），需 OCR 支持（二阶段规划）

## 6. 附录

### 6.1 源文件结构

```
Software-Cup-2026/
├── backend/                  # 后端源码
│   ├── app/
│   │   ├── main.py          # FastAPI 路由和中间件
│   │   ├── schemas.py       # Pydantic 数据模型
│   │   ├── services.py      # 业务逻辑层
│   │   ├── rag.py           # RAG 回答生成
│   │   ├── llm_adapter.py   # LLM Provider 适配器
│   │   ├── knowledge.py     # 知识入库管理
│   │   └── data_store.py    # 数据访问层
│   └── requirements.txt
├── frontend/                 # 前端源码
│   ├── src/
│   │   ├── App.vue          # 根组件
│   │   ├── api.ts           # API 调用封装
│   │   ├── main.ts          # 入口文件
│   │   ├── styles.css       # 全局样式
│   │   └── components/      # Vue 组件（7 个面板组件）
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.json
├── data/
│   ├── examples/            # 种子数据（devices/manuals/cases/workflows）
│   ├── knowledge/           # 入库资料（运行期生成）
│   └── uploads/             # 上传文件（运行期生成）
├── docs/                    # 项目文档
├── tests/                   # 测试代码
├── scripts/                 # 辅助脚本
├── .env.example             # 环境变量模板
├── start-dev.bat            # Windows 一键启动
└── stop-dev.bat             # Windows 一键停止
```

### 6.2 打包说明

提交参赛作品时，按以下步骤打包：

1. 清理生成文件：

```bash
rm -rf frontend/node_modules frontend/dist
rm -rf backend/.venv backend/__pycache__
rm -rf data/uploads/* data/knowledge/files/*
rm -rf .claude
```

2. 打包：

```bash
tar -czf Software-Cup-2026.tar.gz Software-Cup-2026/
```

3. 确保包含以下提交材料：
   - 软件源文件（backend/ + frontend/）
   - 软件安装包（项目根目录可直接运行）
   - 部署文档（本文档）
   - 其他参赛文档（需求分析、功能设计、产品说明书、测试报告）
