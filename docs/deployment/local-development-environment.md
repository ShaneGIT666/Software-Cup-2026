# 本地开发环境准备

本文档用于记录团队成员正式开发前需要准备的本地环境。当前仓库已按 MVP 推荐技术栈补充前后端工程骨架，后续可在此基础上继续细化依赖版本和部署说明。

## 1. 基础工具

| 工具 | 用途 | 状态 |
| --- | --- | --- |
| Git | 版本管理 | 已规划 |
| Node.js | 前端开发环境 | 已规划 |
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
UPLOAD_DIR=./data/uploads
```

原则：

1. `.env` 文件不提交到仓库。
2. 提交 `.env.example` 作为模板。
3. 模型密钥只放本地环境变量或部署环境中。
4. 默认提供 `mock` 模式，保证无密钥也能演示。

## 4. 本地运行目标

第一阶段需要实现：

```text
启动后端服务 -> 启动前端服务 -> 打开浏览器 -> 完成 MVP 演示路径
```

当前本地启动方式：

1. 启动后端：

```powershell
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
