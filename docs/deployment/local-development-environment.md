# 本地开发环境准备

本文档用于记录团队成员正式开发前需要准备的本地环境。当前仓库已按 MVP 推荐技术栈补充前后端工程骨架，后续可在此基础上继续细化依赖版本和部署说明。

## 1. 基础工具

| 工具 | 用途 | 状态 |
| --- | --- | --- |
| Git | 版本管理 | 已规划 |
| Node.js | 前端开发环境 | 已规划 |
| Anaconda | 后端 Python 环境来源 | 已规划 |
| Python | 后端和模型相关能力 | 已规划 |
| VS Code 或 JetBrains IDE | 开发工具 | 待确认 |
| API 调试工具 | 调试后端接口 | 待确认 |
| 浏览器 | 前端调试 | 待确认 |

## 2. 推荐版本

正式技术栈确认前，建议范围如下：

| 环境 | 推荐版本 |
| --- | --- |
| Node.js | 20 LTS 或更高 |
| Python | 3.10 或更高 |
| Git | 2.40 或更高 |
| SQLite | 3.x |

当前前端构建工具固定使用 Vite 7.3.3。Vite 8 在当前 Windows 环境下曾出现 HTML 构建路径异常，因此暂不升级。

## 3. 环境变量规划

后续开发可能需要：

```text
APP_ENV=development
APP_PORT=8000
FRONTEND_PORT=5173
DATABASE_URL=sqlite:///./data/app.db
LLM_PROVIDER=mock
LLM_API_KEY=
LLM_BASE_URL=
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4.1-mini
ANTHROPIC_API_KEY=
ANTHROPIC_BASE_URL=https://api.anthropic.com/v1
ANTHROPIC_MODEL=claude-3-5-haiku-latest
LLM_TIMEOUT_SECONDS=20
UPLOAD_DIR=./data/uploads
APP_EXAMPLES_DIR=./data/examples
APP_UPLOAD_DIR=./data/uploads
APP_KNOWLEDGE_DIR=./data/knowledge
```

原则：

1. `.env` 文件不提交到仓库。
2. 提交 `.env.example` 作为模板。
3. 模型密钥只放本地环境变量或部署环境中。
4. 默认提供 `mock` 模式，保证无密钥也能演示。
5. `LLM_PROVIDER=openai` 或 `LLM_PROVIDER=anthropic` 只在对应密钥存在时启用，调用失败会自动降级到 mock。

## 4. 本地运行目标

第一阶段需要实现：

```text
启动后端服务 -> 启动前端服务 -> 打开浏览器 -> 完成 MVP 演示路径
```

当前本地启动方式：

1. 启动后端：

```powershell
.\scripts\setup-anaconda.ps1
.\scripts\start-backend.ps1
```

2. 启动前端：

```powershell
.\scripts\start-frontend.ps1
```

3. 打开浏览器：

```text
http://127.0.0.1:5173
```

4. 后端健康检查：

```text
http://127.0.0.1:8000/api/health
```

5. 运行后端接口测试：

```powershell
.\scripts\run-backend-tests.ps1
```

## 5. 国产化环境记录

赛题要求关注 LoongArch 架构和银河麒麟高级服务器操作系统。开发期需要持续记录：

| 检查项 | 说明 |
| --- | --- |
| CPU 架构依赖 | 是否使用只支持 x86 的二进制依赖 |
| 系统包依赖 | 是否依赖特殊系统库 |
| Python 包兼容性 | 是否可在 LoongArch 编译或安装 |
| Node 包兼容性 | 是否包含原生模块 |
| 数据库部署 | SQLite/PostgreSQL/MySQL 在目标环境的可用性 |
| 模型部署 | 本地模型是否有 LoongArch 可运行版本 |

## 6. 开发机自检清单

每名成员开工前确认：

1. 可以访问 GitHub 仓库。
2. 可以拉取和提交代码。
3. 可以创建分支。
4. 可以运行前端开发服务。
5. 可以运行后端开发服务。
6. 可以访问接口调试工具。
7. 可以打开项目文档。
## API 配置脚本

Windows 本地可以使用脚本辅助生成 `.env`：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\configure-api.ps1
```

也可以双击或运行：

```bat
configure-api.bat
```

常用参数示例：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\configure-api.ps1 `
  -Provider compatible `
  -CompatiblePreset deepseek `
  -EnableChroma
```

Qwen / DashScope 示例：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\configure-api.ps1 `
  -Provider compatible `
  -CompatiblePreset qwen `
  -EnableChroma
```

自定义 OpenAI-compatible 网关示例：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\configure-api.ps1 `
  -Provider compatible `
  -CompatiblePreset custom `
  -BaseUrl "https://api.deepseek.com/v1" `
  -Model "deepseek-chat" `
  -EnableChroma
```

说明：

1. 脚本会写入本地 `.env`，该文件已被 Git 忽略，不应提交。
2. `compatible` 模式会配置 `LLM_PROVIDER=openai` 和 `OPENAI_API_STYLE=chat_completions`，适合 DeepSeek、Qwen/DashScope、SiliconFlow 或 OpenAI-compatible 网关。
3. `-CompatiblePreset deepseek` 默认使用 `https://api.deepseek.com/v1` 和 `deepseek-chat`。
4. `-CompatiblePreset qwen` 默认使用 `https://dashscope.aliyuncs.com/compatible-mode/v1` 和 `qwen-plus`。
5. 如果需要比赛现场离线兜底，选择 `mock` 或设置 `REMOTE_API_MODE=off`。
6. `scripts/start-backend.ps1` 会在启动后端时自动加载 `.env`。
7. 如需验证真实 API，先启动后端，再执行脚本时追加 `-Validate`。

已验收记录：

1. 2026-05-27 已使用 Qwen / DashScope compatible mode + `qwen-plus` 完成文本 RAG 小样本验收。
2. 验收结果为 `provider=openai`、`model=qwen-plus`、`fallback=false`，说明真实 API 链路可用。
3. 密钥不得写入文档或提交到 Git，只能保存在本地 `.env` 或部署环境变量中。

## 2026-05-27 补充：前端构建与 LoongArch 演示包

目标 LoongArch / 银河麒麟 V11 VM 当前无 npm/git，因此前端推荐在 Windows 本地构建后上传：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-frontend.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\package-demo.ps1
```

后端启动时保持：

```env
SERVE_FRONTEND=auto
FRONTEND_DIST_DIR=../frontend/dist
```

此时 FastAPI 会在 `frontend/dist/index.html` 存在时托管 SPA 首页，`/api/*`、`/uploads/*`、`/knowledge/*` 仍保持原有优先级。

前端冒烟测试已添加：

```powershell
cd frontend
npm install -D @playwright/test
npm run test:e2e
```

当前环境无法联网安装 Playwright，因此该项需要在网络可用后补验。
