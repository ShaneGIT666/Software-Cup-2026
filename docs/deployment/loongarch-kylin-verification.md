# LoongArch + 银河麒麟部署验证清单

状态：待官方开发/测试环境开放后执行。  
重要性：官方赛题硬约束，不满足可能导致作品无效。

## 1. 验证目标

在 LoongArch 架构 CPU + 银河麒麟高级服务器操作系统 V10/V11 上证明系统可安装、可构建、可启动、可访问、可完成核心功能。

## 2. 基础环境记录

环境开放后记录以下命令输出：

```bash
uname -m
cat /etc/os-release
python3 --version
node --version
npm --version
git --version
```

期望：
1. `uname -m` 能体现 LoongArch 架构。
2. 操作系统信息能体现银河麒麟 V10 或 V11。
3. Python 版本不低于 3.10。
4. Node.js 建议 20 LTS 或可兼容版本。

## 3. 后端验证

安装依赖：

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

可选 PDF 文本解析：

```bash
pip install pypdf
```

启动后端：

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

健康检查：

```bash
curl http://127.0.0.1:8000/api/health
```

预期：

```json
{"success":true,"data":{"status":"ok","version":"0.1.0"},"message":""}
```

## 4. 前端验证

安装依赖并构建：

```bash
cd frontend
npm install
npm run build
```

预期：
1. `vue-tsc -b` 通过。
2. `vite build` 通过。
3. 生成 `frontend/dist/`。

## 5. 生产部署验证

推荐路径：
1. 使用 Nginx 托管 `frontend/dist`。
2. 使用 FastAPI/Uvicorn 提供后端 API。
3. Nginx 将 `/api/`、`/uploads/`、`/knowledge/` 反向代理到后端。

必须截图或记录：
1. 浏览器访问首页。
2. 后端健康检查。
3. 一次知识检索。
4. 一次 RAG mock 回答。
5. 一次资料入库。
6. 一次多模态 mock 分析。
7. 一次知识关系网络生成。

## 6. 自动化测试

在目标环境执行：

```bash
python -m pytest tests/
```

若 Windows PowerShell 脚本不可用，应使用 Linux shell 命令直接运行 pytest。

预期：所有后端测试通过。

## 7. 风险记录

| 风险 | 处理 |
| --- | --- |
| Node.js LoongArch 包不可用 | 尝试系统源、官方二进制或源码编译；必要时在其他环境构建前端静态文件后部署 |
| Python 依赖安装失败 | 优先保留纯 Python 依赖，避免引入重型 OCR/向量库 |
| pypdf 不可用 | 使用 mock 多模态分析和 TXT/Markdown 入库兜底 |
| 云模型 API 不可访问 | 使用 mock provider 完成演示 |
| 性能不足 | 降低上传文件大小、减少并发，仅保留演示路径 |

## 8. 验证完成后需补充

环境开放并验证完成后，必须补充：
1. 实测日期。
2. 机器配置。
3. 系统版本截图或命令输出。
4. 构建和测试结果。
5. 浏览器演示截图。
6. 遇到的问题和解决方案。
