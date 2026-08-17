# Docker 一键部署与 LoongArch 验证说明

> [!WARNING]
> **历史快照（非现行基线）**：本文记录 2026 年前期竞赛原型、阶段调研、验证或交付准备，仅用于追溯当时事实。文内“当前”“最终”“正式”“已完成”“必须”“一键部署”等表述均限定于当时范围，不构成现行产品状态、开发顺序、生产要求或交付承诺。现行口径以[根 README](../../README.md)、[软件需求规格说明书](../requirements/software-requirements-spec.md)和[修改日志索引](../change-log/INDEX.md)为准；发生冲突时，以这些现行文件及相关模块最新记录为准。本文中的命令、测试数量和部署结论未经当前版本复验，不得作为当前验收证据。

更新时间：2026-06-06

本文是当时竞赛原型的 Docker 部署记录，不再是现行部署入口。相关方案只用于追溯国产化环境验证和比赛演示过程，当前版本使用前必须重新核对 Dockerfile、配置、前端 API 和数据库要求。

## 1. 目标

在目标虚拟机没有 `git`、没有 `npm` 的情况下，通过 Docker 在 LoongArch / Kylin V11 上运行本项目，并验证：

```text
GET /
GET /api/health
GET /api/providers/status
```

容器默认使用离线兜底配置，避免比赛现场网络不佳导致演示中断。

## 2. 前置条件

Windows 本地：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-frontend.ps1
```

LoongArch / Kylin VM：

```bash
uname -m
systemctl is-active docker
sudo docker info
which curl
which unzip
```

要求：

```text
uname -m = loongarch64
Docker daemon = active
curl/unzip 可用
sudo docker info 可执行
```

脚本不会保存 sudo 密码。如果 `sudo -n docker info` 不可用，请先在 VM 终端手动执行：

```bash
sudo systemctl start docker
sudo docker info
```

## 3. 一键部署命令

默认从 GitHub `main` 分支下载源码 zip：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy-docker-vm.ps1 `
  -HostName frp-use.com `
  -Port 21924 `
  -User vmuser `
  -IdentityFile "$env:USERPROFILE\.ssh\software_cup_kylin_vm"
```

脚本默认允许 SSH 交互登录。如果已经配置好 SSH key 免密，且希望脚本在 CI/无人值守场景中失败即退出，可追加：

```powershell
-NonInteractiveSsh
```

可覆盖基础镜像：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy-docker-vm.ps1 `
  -BaseImage cr.loongnix.cn/library/python:3.11
```

如果 GitHub 源码包不包含 `frontend/dist`，VM 因没有 npm 无法构建前端。此时应使用包含 `frontend/dist` 的 GitHub Release/Artifact zip，并传入：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy-docker-vm.ps1 `
  -PackageUrl "https://github.com/<owner>/<repo>/releases/download/<tag>/software-cup-demo.zip"
```

`-PackageUrl` 支持两种 zip 结构：GitHub archive 的“单顶层目录”结构，以及 `scripts/package-demo.ps1` 生成的“项目文件位于 zip 根目录”结构。

## 4. 容器默认配置

Dockerfile 默认配置：

```env
SERVE_FRONTEND=auto
FRONTEND_DIST_DIR=/app/frontend/dist
APP_EXAMPLES_DIR=/app/data/examples
APP_KNOWLEDGE_DIR=/app/runtime/knowledge
APP_UPLOAD_DIR=/app/runtime/uploads
REMOTE_API_MODE=off
LLM_PROVIDER=mock
MULTIMODAL_PROVIDER=mock
RAG_VECTOR_STORE=off
```

说明：

1. `/app/runtime` 使用 Docker volume 保存上传资料和知识库运行时数据。
2. `REMOTE_API_MODE=off` 表示不访问外网，RAG 和多模态走本地兜底。
3. Chroma 默认关闭，避免 LoongArch 最小部署被可选依赖阻塞。

## 5. 验证命令

在 VM 内执行：

```bash
sudo docker ps --filter name=software-cup-demo
curl -fsS http://127.0.0.1:8000/api/health
curl -fsS http://127.0.0.1:8000/api/providers/status
curl -fsS http://127.0.0.1:8000/ | head -c 160
```

预期：

```text
容器状态为 Up
/api/health 返回 success=true
/api/providers/status 返回 provider 和 offline/fallback 状态
/ 返回包含 `<!doctype html>` 的前端 HTML 响应
```

## 6. 常见失败

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `sudo -n docker info` 失败 | 当前用户没有免密 Docker 权限 | 先在 VM 手动执行 `sudo docker info`，或由管理员配置 docker 组 |
| `frontend/dist/index.html is missing` | GitHub 源码包不提交构建产物 | 使用包含 dist 的 GitHub Release/Artifact zip，并传 `-PackageUrl` |
| Docker build 拉不到基础镜像 | 镜像源不支持当前网络或架构 | 用 `-BaseImage` 替换为可访问的 LoongArch Python 镜像 |
| `/` 返回 404 | dist 未进入镜像或 `SERVE_FRONTEND=off` | 确认镜像内存在 `/app/frontend/dist/index.html` |
| RAG 没有真实 API 输出 | 容器默认离线兜底 | 比赛现场如需真实 API，显式传入环境变量并确认网络与 Key |

## 7. 交接注意

不要提交 `.env`、官方 PDF、`release/`、`frontend/dist/`、`data/uploads/`、`data/knowledge/`、`.venv/` 或 `node_modules/`。如果改变 Docker 部署流程，必须同步更新本文、`docs/project-management/current-handoff.md` 和 `docs/project-management/agent-startup-context.md`。
# 最新验证状态（2026-06-06）

本 Docker 部署方案已在 LoongArch / Kylin V11 虚拟机上完成真实验证。

验证环境：

```text
Kylin Linux Advanced Server V11 (Swan25)
loongarch64
Docker 24.0.9
基础镜像：cr.loongnix.cn/library/python:3.11
```

验证结果：

```text
Docker build：通过
Docker run：通过
GET /api/health：通过
GET /api/providers/status：通过
GET /：通过，返回前端 HTML
```

关键注意：LoongArch 容器内不要直接使用 `uvicorn[standard]` 或 Pydantic 2 原生核心依赖。当前 Dockerfile 会在容器内自动转换为最小运行依赖：`uvicorn==0.34.0` + `pydantic<2`，并使用兼容方式启动 uvicorn。
