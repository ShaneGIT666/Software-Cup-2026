# 预设目标完成状态

更新时间：2026-05-25  
范围：除 PPT 和汇报材料外的项目预设目标

## 1. 已完成

功能闭环：
1. 设备型号 + 故障现象检索。
2. 检索结果来源、命中词、命中原因和评分解释。
3. 标准作业流程展示，包括工具、安全提醒、步骤和验收标准。
4. 案例提交、审核、审核通过后进入检索结果。
5. 现场文件上传，包含扩展名、MIME、空文件和大小边界校验。
6. 资料入库，支持 `pdf/txt/md/jpg/jpeg/png/webp`。
7. 多模态资料分析接口，支持 `mock/openai/anthropic` provider 和 fallback。
8. RAG 辅助回答，支持 citations 和 provider fallback。
9. 轻量知识关系网络，展示设备、故障、资料、案例、流程和来源之间的关系。

工程闭环：
1. Windows 一键启动脚本：`start-dev.bat`。
2. Windows 一键停止脚本：`stop-dev.bat`。
3. 后端测试脚本：`scripts/run-backend-tests.ps1`。
4. 本地总体验证脚本：`scripts/run-local-verification.ps1`。
5. `.env.example` 已包含 LLM 和多模态 provider 配置示例。
6. 运行时目录 `data/uploads/`、`data/knowledge/` 已通过 `.gitignore` 排除。

文档闭环：
1. 官方赛题基线：`docs/requirements/official-problem-baseline.md`。
2. 软件需求规格说明：`docs/requirements/software-requirements-spec.md`。
3. 软件设计文档：`docs/design/software-design-doc.md`。
4. API 契约：`docs/design/api-contract-draft.md`。
5. 产品说明书：`docs/product/product-manual.md`。
6. 本地演示运行手册：`docs/product/local-demo-runbook.md`。
7. 软件功能测试报告：`docs/testing/software-test-report.md`。
8. 部署文档：`docs/deployment/deployment-guide.md`。
9. LoongArch + 银河麒麟验证清单：`docs/deployment/loongarch-kylin-verification.md`。
10. 当前交接文档：`docs/project-management/current-handoff.md`。

## 2. 已验证

本地自动化验证：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-local-verification.ps1
```

该脚本会执行：
1. `git status --short --branch`
2. 后端测试
3. 前端生产构建

预期结果：
1. 后端测试 `33 passed`。
2. 前端构建通过。
3. 仅出现既有 Vite/Rollup 非阻塞 warning。

## 3. 暂缓或外部阻塞

| 项目 | 状态 | 原因 | 后续动作 |
| --- | --- | --- | --- |
| LoongArch + 银河麒麟实机验证 | 暂缓 | 官方环境未开放 | 环境开放后执行 `loongarch-kylin-verification.md` |
| 真实 OpenAI/Anthropic 联网验收 | 暂缓 | 需要真实 Key、网络和费用确认 | 单独做小样本验收，不影响 mock 演示 |
| 生产级 OCR | 暂缓 | 会引入重依赖和国产化风险 | 先评估 PaddleOCR/MinerU/Docling |
| 向量数据库 RAG | 暂缓 | 当前 MVP 已具备可解释检索和 citations | 后续评估 Chroma/Qdrant |
| 完整知识图谱 | 暂缓 | 当前采用轻量关系网络原型 | 如进入后续阶段再评估 Neo4j 或 GraphRAG |

## 4. 不在本次范围

按用户要求，本次不处理：
1. PPT。
2. 汇报材料。
3. 汇报讲稿。
4. 演示视频成片制作。

## 5. 后续协作者注意事项

1. 不要把当前 mock 多模态分析表述为真实 OCR。
2. 不要把轻量知识关系网络表述为生产级知识图谱。
3. 不要承诺国产化环境已通过实测。
4. 不要提交官方 PDF、`.env`、运行时上传文件或构建产物。
5. 如修改 API、数据状态或演示路径，必须同步更新 `current-handoff.md` 和本文件。

## 6. 2026-05-26 弱网兜底补充

已完成：

1. 新增 `REMOTE_API_MODE=auto|off`，默认 `auto`。
2. 新增 `GET /api/providers/status`，用于展示 LLM 与多模态 provider 配置、实际生效 provider、Key 配置状态和最近 fallback 原因。
3. RAG 与多模态分析在 `REMOTE_API_MODE=off` 时强制走本地 mock，不访问外网。
4. 真实 provider 调用失败时继续自动 fallback 到 mock，保证比赛演示不断链。
5. 前端顶部状态条显示 provider 运行状态，资料分析和 RAG 面板保留 fallback 原因。

验证要求：

1. 后端测试需覆盖 provider 状态、离线模式跳过真实 provider、模拟网络异常 fallback。
2. 前端构建需通过。
3. 本地总体验证脚本需通过。
