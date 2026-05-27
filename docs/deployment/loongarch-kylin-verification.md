# LoongArch + 银河麒麟 V11 部署验证记录

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
