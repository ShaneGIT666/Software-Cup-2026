# 软件功能测试报告

项目名称：基于多模态大模型技术的设备检修知识检索与作业系统  
版本：0.3
更新时间：2026-05-27

## 1. 测试结论

当前项目已覆盖比赛 MVP 的核心后端链路：检索、资料入库、上传安全、RAG、provider fallback、多模态 mock、知识关系网络、Chroma 可选召回、官方 PDF 流程、LoongArch 后端最小部署验证。

最近确认事实：

1. Windows 本地后端完整测试最新结果：`78 passed in 18.67s`。
2. 前端 `npm.cmd run build` 通过，存在 Vite chunk size warning，不阻塞。
3. Qwen / DashScope OpenAI-compatible 文本 RAG 小样本真实 API 验收通过，`fallback=false`，citations 保留。
4. LoongArch / 银河麒麟 V11 后端最小依赖测试子集通过：`39 passed`。
5. 前端 LoongArch 托管方案已调整为：Windows 本地构建 `frontend/dist`，FastAPI 在 VM 上静态托管。

## 2. 推荐回归命令

后端：

```powershell
.\backend\.venv\Scripts\python.exe -m pytest tests/ -q
# 78 passed in 18.67s
```

前端：

```powershell
cd frontend
npm.cmd run build
# 通过；Vite chunk size warning 不阻塞
```

本地总体验证：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-local-verification.ps1
```

前端冒烟测试：

```powershell
cd frontend
npm install -D @playwright/test
npm run test:e2e
```

说明：当前环境无法联网安装 `@playwright/test`，因此 E2E 自动执行需在网络可用后补充。

## 3. 后端自动化测试覆盖

| 编号 | 范围 | 说明 |
| --- | --- | --- |
| T-BE-001 | 健康检查 | `/api/health` 返回服务状态 |
| T-BE-002 | Provider 状态 | `/api/providers/status` 返回 LLM、多模态、embedding 和 fallback 状态 |
| T-BE-003 | 检索 | 正常查询返回 seed 数据、命中词、来源和排序解释 |
| T-BE-004 | 空查询 | 设备型号和故障现象都为空时返回 400 |
| T-BE-005 | RAG mock | mock RAG 返回回答和 citations |
| T-BE-006 | RAG 真实 provider fallback | Key 缺失、离线模式、网络异常时自动 fallback |
| T-BE-007 | LLM validate | OpenAI-compatible `/chat/completions` mock 验收 |
| T-BE-008 | 上传安全 | 空文件、非法扩展名、MIME 不匹配、超大文件均拒绝 |
| T-BE-009 | 资料入库 | TXT/Markdown/PDF/图片等资料生命周期 |
| T-BE-010 | 多模态分析 | 图片/PDF 可进入 mock 多模态分析并生成 chunks |
| T-BE-011 | 多模态 validate | mock、离线跳过、真实 provider mock 成功 |
| T-BE-012 | 知识关系网络 | 生成 device/fault/document/case/workflow 节点和关系 |
| T-BE-013 | Chroma 可选召回 | Chroma 结果合并进 `/api/search` |
| T-BE-014 | embedding provider | `hash`/`openai` 标记进入 `scoreBreakdown.embeddingProvider` |
| T-BE-015 | embedding fallback | 真实 embedding 失败时回退 hash，不影响检索 |
| T-BE-016 | FastAPI 前端托管 | `SERVE_FRONTEND=auto` 时 `/` 返回 SPA，API 不受影响 |
| T-BE-017 | 动态诊断 | `/api/diagnosis` 复用检索/RAG citations，不再返回固定硬编码结果 |
| T-BE-018 | JSON 原子写 | `save_cases()` 等写入先写临时文件再 `os.replace()` |
| T-BE-019 | Chroma 降级 | Chroma 初始化失败或查询失败时返回空召回，不影响主链路 |
| T-BE-020 | 官方 PDF | 官方摩托车维修手册入库、检索、RAG、删除、Chroma 流程 |

## 4. LoongArch / 银河麒麟验证

已验证环境：

```text
Kylin Linux Advanced Server V11 (Swan25)
Python 3.11.6
node 存在
npm/git 不存在
```

已验证内容：

1. 后端最小依赖可安装。
2. 后端测试子集 `39 passed`。
3. Uvicorn 可启动。
4. `/api/health` 正常。
5. `/api/providers/status` 正常。

待复验内容：

1. 上传最新源码和 `frontend/dist`。
2. 设置 `SERVE_FRONTEND=auto`、`FRONTEND_DIST_DIR=../frontend/dist`。
3. 访问 `http://VM:8000/`，确认前端由 FastAPI 返回。

## 5. 已知风险

| 风险 | 影响 | 兜底 |
| --- | --- | --- |
| 真实 API 网络不稳 | RAG 或多模态增强失败 | `REMOTE_API_MODE=off` 强制 mock/local fallback |
| Chroma 在 LoongArch 未验收 | 可选向量增强不可用 | 默认 `RAG_VECTOR_STORE=off`，关键词检索不受影响 |
| hash embedding 非真实语义 | 答辩术语风险 | 文档和返回字段明确标记 `embeddingProvider=hash` |
| 真实多模态 payload 差异 | 不同 provider 兼容性不确定 | 只通过 `/api/providers/multimodal/validate` 做小样本验收 |
| 前端 E2E 依赖未安装 | 自动化演示防线不完整 | 网络可用后安装 `@playwright/test` 并执行 |
| JSON 文件并发写 | 多请求写入可能覆盖 | 已改为原子替换降低写坏文件风险；比赛 MVP 低并发可接受，后续可引入文件锁或数据库 |

## 6. 结论

项目已具备比赛演示所需的主要工程闭环。后续最重要的是在 LoongArch VM 上复验 FastAPI 静态托管前端，并在最终提交前重新执行后端测试、前端构建和演示路径冒烟。
