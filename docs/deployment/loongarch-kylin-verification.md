# LoongArch + 银河麒麟 V11 部署验证记录

> [!WARNING]
> **历史快照（非现行基线）**：本文记录 2026 年前期竞赛原型、阶段调研、验证或交付准备，仅用于追溯当时事实。文内“当前”“最终”“正式”“已完成”“必须”“一键部署”等表述均限定于当时范围，不构成现行产品状态、开发顺序、生产要求或交付承诺。现行口径以[根 README](../../README.md)、[软件需求规格说明书](../requirements/software-requirements-spec.md)和[修改日志索引](../change-log/INDEX.md)为准；发生冲突时，以这些现行文件及相关模块最新记录为准。本文中的命令、测试数量和部署结论未经当前版本复验，不得作为当前验收证据。

更新时间：2026-05-27
当前状态：后端核心链路已在银河麒麟 V11 / LoongArch64 虚拟机完成正向验证；前端托管方案已补充为“本地构建 `frontend/dist` 后由 FastAPI 静态托管”。

## 1. 已验证环境

```bash
cat /etc/os-release
whoami
pwd
hostname -I
python3 --version
which python3
which curl
which unzip
which node
which npm
which git
```

记录结果：

```text
NAME="Kylin Linux Advanced Server"
VERSION="V11 (Swan25)"
ID="kylin"
VERSION_ID="V11"
PRETTY_NAME="Kylin Linux Advanced Server V11 (Swan25)"
Python 3.11.6
node: /usr/bin/node
npm: not found
git: not found
```

结论：目标环境满足后端 Python 运行条件，但不具备 npm/git，因此前端应在 Windows 本地构建后上传 `frontend/dist`。

## 2. 后端最小依赖验证

推荐 LoongArch 后端最小依赖路线：

```bash
cd backend
python3 -m venv .venv-min
source .venv-min/bin/activate
pip install "pydantic<2" fastapi==0.115.6 uvicorn==0.34.0 python-multipart pytest httpx pypdf
python -m pytest tests/
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

已完成记录：

```text
39 passed
/api/health 正常返回 success=true
/api/providers/status 正常返回 provider 状态
```

说明：39 个测试是当时上传到 VM 的后端测试子集。Windows 本地主线目前已扩展到 66+ 个后端测试；后续重新上传最新源码后应再次在 VM 执行完整测试。

## 3. 前端托管方案

目标环境没有 npm，因此不在 LoongArch 上构建前端。当前推荐流程：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-frontend.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\package-demo.ps1
```

上传 release zip 到 VM 后：

```bash
export SERVE_FRONTEND=auto
export FRONTEND_DIST_DIR=../frontend/dist
cd backend
source .venv-min/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

验收项：

```bash
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8000/api/providers/status
curl http://127.0.0.1:8000/
```

预期：`/` 返回前端 `index.html`，`/api/*` 仍返回 JSON API，不被 SPA fallback 截获。

## 4. 必须保留的风险说明

| 风险 | 当前处理 |
| --- | --- |
| LoongArch 无 npm/git | 本地构建前端并上传 dist；源码通过压缩包或 SFTP 上传 |
| `uvicorn[standard]` 可能触发原生依赖构建 | 使用 `uvicorn==0.34.0` 最小安装，不启用 `[standard]` |
| Chroma 在 LoongArch 上未验收 | Chroma 保持可选增强，默认关闭；关键词检索与 mock/RAG 兜底不依赖 Chroma |
| 真实云 API 受网络影响 | `REMOTE_API_MODE=off` 可强制本地兜底 |
| 中文命令行编码 | 正式演示优先使用浏览器前端或 UTF-8 JSON 文件提交请求 |

## 5. 赛前复验清单

1. 上传最新源码和 `frontend/dist` 到 VM。
2. 在 VM 重新执行后端测试。
3. 启动 FastAPI，确认 `/`、`/api/health`、`/api/providers/status` 可访问。
4. 通过浏览器完成检索、RAG、资料入库、多模态 mock 分析、案例提交与审核闭环。
5. 截图或录屏保存作为最终交付证据。
# 最新验证状态：Docker 一体化部署已通过（2026-06-06）

本节为最新事实记录，优先级高于下方历史记录。

## 已完成验证

在 LoongArch / Kylin V11 虚拟机上，已通过 Docker 完成前后端一体化部署验证。

环境信息：

```text
操作系统：Kylin Linux Advanced Server V11 (Swan25)
架构：loongarch64
Docker：24.0.9
Docker 服务：active
容器镜像：software-cup-demo:loongarch
基础镜像：cr.loongnix.cn/library/python:3.11
```

验证通过项：

1. Docker 镜像构建成功。
2. Docker 容器启动成功。
3. `/api/health` 返回 `success=true`。
4. `/api/providers/status` 返回 provider 状态，离线兜底开启。
5. `/` 返回前端 HTML 页面，说明 FastAPI 静态托管前端可用。

## LoongArch Docker 适配结论

实际验证暴露了三个 LoongArch 容器兼容点，并已在 Dockerfile 中修复：

1. `uvicorn[standard]` 会引入 `httptools` 原生构建，改为 `uvicorn==0.34.0`。
2. Pydantic 2 会引入 `pydantic-core` 原生构建，容器中追加 `pydantic<2`。
3. Uvicorn 默认 signal handler 在该容器环境中报 `OSError: [Errno 22] Invalid argument`，启动命令已清空 `uvicorn.server.HANDLED_SIGNALS`。

## 当前结论

LoongArch/Kylin 的后端最小依赖验证和 Docker 一体化部署验证均已完成。后续赛前重点不是再证明“能不能跑”，而是固化演示包、保留验证截图/日志，并按 `docs/deployment/docker-loongarch-deployment.md` 复现部署。
