# 预设目标完成状态

更新时间：2026-05-27
范围：除 PPT、汇报材料和最终视频外的比赛作品工程目标。

## 1. 已完成

功能闭环：

1. 设备型号 + 故障现象检索。
2. 检索结果来源、命中词、命中原因、排序分和 `scoreBreakdown` 解释。
3. 标准化作业流程展示，包括工具、安全提醒、步骤和验收标准。
4. 案例提交、审核、审核通过后进入检索结果。
5. 文件上传安全边界，包括扩展名、MIME、空文件和大小限制。
6. 资料入库，支持 `pdf/txt/md/jpg/jpeg/png/webp`。
7. 多模态资料分析接口，支持 `mock/openai/anthropic` provider 和 fallback。
8. RAG 辅助回答，支持 citations、真实 provider、小样本 Qwen 验收和本地 fallback。
9. 轻量知识关系网络，展示设备、故障、资料、案例、流程和来源之间的关系。
10. Chroma 可选向量索引增强，默认关闭；hash embedding 明确为兜底占位，可选 OpenAI-compatible embedding。
11. FastAPI 可选托管 `frontend/dist`，用于 LoongArch 无 npm/nginx 场景。

工程闭环：

1. Windows 一键启动脚本：`start-dev.bat`。
2. Windows 一键停止脚本：`stop-dev.bat`。
3. 后端测试脚本：`scripts/run-backend-tests.ps1`。
4. 本地总体验证脚本：`scripts/run-local-verification.ps1`。
5. 前端构建脚本：`scripts/build-frontend.ps1`。
6. LoongArch 上传包准备脚本：`scripts/package-demo.ps1`。
7. API 配置脚本：`configure-api.bat` / `scripts/configure-api.ps1`，支持 Qwen、DeepSeek、SiliconFlow 和自定义 OpenAI-compatible 网关。
8. Playwright 冒烟测试文件已接入；依赖需联网安装 `@playwright/test` 后执行。
9. `.env.example` 包含 LLM、多模态、弱网兜底、前端托管、Chroma 和 embedding 配置示例。
10. 运行时目录 `data/uploads/`、`data/knowledge/`、`.env`、`node_modules/`、`dist/` 已通过 `.gitignore` 排除。

文档闭环：

1. 官方赛题基线：`docs/requirements/official-problem-baseline.md`。
2. 软件需求规格说明：`docs/requirements/software-requirements-spec.md`。
3. 软件设计文档：`docs/design/software-design-doc.md`。
4. API 契约：`docs/design/api-contract-draft.md`。
5. 产品说明书：`docs/product/product-manual.md`。
6. 本地演示运行手册：`docs/product/local-demo-runbook.md`。
7. 软件功能测试报告：`docs/testing/software-test-report.md`。
8. 部署文档：`docs/deployment/deployment-guide.md`。
9. LoongArch + 银河麒麟验证记录：`docs/deployment/loongarch-kylin-verification.md`。
10. 当前交接文档：`docs/project-management/current-handoff.md`。

## 2. 已验证

本地 Windows：

```powershell
.\backend\.venv\Scripts\python.exe -m pytest tests/ -q
cd frontend
npm.cmd run build
```

最近记录：

```text
后端测试：78 passed in 18.67s
前端构建：通过，存在 Vite chunk size warning，不阻塞
Qwen 文本 RAG：真实 API 小样本验收通过，fallback=false，citations 保留
```

LoongArch / 银河麒麟 V11：

```text
后端最小依赖测试子集：39 passed
/api/health：通过
/api/providers/status：通过
```

说明：LoongArch 前端完整访问将采用 FastAPI 静态托管 `frontend/dist` 的方案继续复验。

## 3. 仍需赛前复验

| 项目 | 状态 | 后续动作 |
| --- | --- | --- |
| LoongArch 前端静态托管 | 已实现方案，待 VM 复验 | 上传最新源码和 `frontend/dist` 后访问 `http://VM:8000/` |
| 真实多模态 API | 已有验收接口，未消耗真实多模态 token | 仅做小图片样本验收，不承诺所有兼容网关可用 |
| Chroma 真实依赖 | Windows 代码链路可测，LoongArch 默认不启用 | 如需展示，单独安装 `backend/requirements-rag.txt` 验收 |
| Playwright E2E | 测试文件已提交，依赖未安装 | 网络可用时执行 `npm install -D @playwright/test` 后运行 `npm run test:e2e` |
| PPT / 汇报 / 视频 | 不在本文范围 | 进入最终提交阶段后制作 |

## 4. 答辩口径

1. 不把 mock 多模态分析表述为生产级 OCR。
2. 不把轻量知识关系网络表述为完整生产级知识图谱。
3. 不把 hash embedding 表述为真实语义 embedding；它是断网和无 Key 场景的 Chroma 兜底占位。
4. 可以说明 Qwen/DashScope OpenAI-compatible 文本 RAG 已完成真实 API 小样本验收。
5. 可以说明 LoongArch/Kylin V11 后端已完成最小依赖正向验证，前端托管采用本地构建 dist + FastAPI StaticFiles 方案。
