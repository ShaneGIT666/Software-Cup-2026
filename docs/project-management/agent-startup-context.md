# Coding Agent 初始化入口

本文档是所有 Coding Agent 接手本项目时的第一阅读入口。无论 Agent 是否拥有前文对话上下文，都必须先阅读本文件，再决定是否继续阅读更细的设计、开发和任务文档。

本文件必须在后续开发中动态更新：每次完成可运行闭环、提交重要代码、发现新风险、调整任务优先级或改变验证方式后，都要同步修改本文档。
在开始任何实现、答辩材料编写或“是否偏题”判断前，必须先对照 `docs/requirements/official-problem-baseline.md`。

## 1. 当前项目一句话

项目是“设备检修知识检索与作业辅助系统”的软件杯 MVP。当前重点是稳定演示以下闭环：

```text
输入设备型号和故障现象
-> 检索手册片段和历史案例
-> 查看标准作业流程
-> 上传现场材料
-> 上传检修手册等资料并生成本地知识片段
-> 提交维修经验案例
-> 审核案例
-> 审核通过后再次检索命中新案例
```

当前系统可以演示，但仍处于 MVP 骨架阶段，不应宣称已经具备生产级 RAG、多模态诊断、权限系统或国产化完整部署能力。

## 2. 当前仓库状态

最近确认时间：2026-05-21。

当前分支：`main`。

最近确认状态：

1. 本迭代提交后，本地 `main` 预计领先 `origin/main` 2 个提交。
2. 当前代码已完成后端可信边界迭代、前端工业控制台风格优化、Windows 批处理统一启动入口、资料入库 MVP、Mock RAG 辅助回答、可选 OpenAI/Anthropic Provider 和 MVP 级检索排序解释。
3. 后端测试通过：`27 passed`。
4. 前端构建通过：`vue-tsc -b && vite build`。
5. 当前 Vite 版本固定为 `7.3.3`。

最近关键提交：

1. `fix: harden api validation and upload boundaries`
2. `chore: add windows batch dev entrypoints`
3. `style: refine industrial cockpit interface`
4. `feat: add knowledge document ingestion and management APIs`
5. `feat: add mock rag answer workflow`
6. `feat: add optional openai and anthropic rag providers`
7. `feat: improve search ranking explainability`

## 3. 当前技术栈

前端：

1. Vue 3
2. TypeScript
3. Vite
4. Element Plus
5. `@lucide/vue`

后端：

1. FastAPI
2. Pydantic
3. 本地 JSON 数据
4. Anaconda Python + 项目本地 `backend/.venv`
5. 资料入库 MVP 使用本地 JSON 和可选 PDF 解析器，不强依赖大型 RAG/OCR 框架

数据目录：

1. `data/examples/devices.json`
2. `data/examples/manuals.json`
3. `data/examples/repair-cases.json`
4. `data/examples/workflows.json`
5. `data/knowledge/documents.json`
6. `data/knowledge/document-chunks.json`

## 4. 首次接手必读顺序

最小必读：

0. `docs/requirements/official-problem-baseline.md`
1. `docs/project-management/agent-startup-context.md`
2. `README.md`
3. `docs/project-management/development-plan.md`
4. `docs/project-management/model-task-classification.md`
5. `docs/project-management/ordinary-agent-development-guide.md`

涉及 API 或后端时继续读：

1. `docs/design/api-contract-draft.md`
2. `docs/design/data-model-draft.md`
3. `backend/app/main.py`
4. `backend/app/schemas.py`
5. `backend/app/services.py`
6. `backend/app/data_store.py`
7. `backend/app/knowledge.py`
8. `tests/test_backend_api.py`

涉及前端时继续读：

1. `frontend/src/App.vue`
2. `frontend/src/api.ts`
3. `frontend/src/styles.css`
4. `frontend/src/components/QueryPanel.vue`
5. `frontend/src/components/ResultsPanel.vue`
6. `frontend/src/components/WorkflowPanel.vue`
7. `frontend/src/components/CasePanel.vue`
8. `frontend/src/components/ReviewPanel.vue`

涉及演示或答辩时继续读：

1. `docs/product/demo-script-outline.md`
2. `docs/deployment/local-development-environment.md`
3. `docs/research/open-source-architecture-research.md`

## 5. 当前已实现能力

后端：

1. `GET /api/health`
2. `POST /api/search`
3. `POST /api/diagnosis`
4. `GET /api/workflows/{workflow_id}`
5. `POST /api/cases`
6. `GET /api/cases?status=...`
7. `PATCH /api/cases/{case_id}/review`
8. `POST /api/uploads`
9. `POST /api/knowledge/documents`
10. `GET /api/knowledge/documents`
11. `GET /api/knowledge/documents/{document_id}`
12. `GET /api/knowledge/documents/{document_id}/chunks`
13. `DELETE /api/knowledge/documents/{document_id}`
14. `POST /api/rag/answer`

检索能力说明：

1. `POST /api/search` 当前支持 `manual`、`case`、`document` 三类来源统一排序。
2. 排序依据为字段权重、来源类型基础权重和连续短语命中加分。
3. 每条结果返回 `matchedTerms`、`reason` 和 `scoreBreakdown`，用于前端解释、RAG prompt 和 citations 展示。

前端：

1. 检索输入区。
2. 知识结果区。
3. 作业流程区。
4. 案例提交区。
5. 案例审核区。
6. 图片/PDF 上传入口。
7. 资料入库面板：上传 PDF/TXT/Markdown，显示解析状态、chunk 数量和解析器策略。
8. RAG 辅助建议面板：基于当前检索上下文生成回答，展示引用来源和 fallback 状态。
9. 基础空状态、加载状态、焦点可访问性和 reduced-motion 支持。
10. 工业控制台风格界面：深色顶部、状态芯片、来源标签、流程元信息和更清晰的卡片层级。
11. Windows 统一入口：`start-dev.bat` / `stop-dev.bat` 可直接拉起或停止前后端开发服务。

验证：

1. 后端接口测试覆盖健康检查、检索排序解释、空查询、流程查询、上传目录配置、上传成功、空文件、非法扩展名、MIME 不匹配、超大文件、案例提交审核再检索闭环、非法审核 action、资料入库成功、资料列表、资料详情、chunk 列表、删除资料、资料入库后检索命中、Mock RAG 回答、OpenAI/Anthropic provider、provider 降级和资料 citation 边界。
2. 前端生产构建通过。

## 6. 当前主要风险

高优先级风险：

1. 官方赛题把 LoongArch + 银河麒麟运行作为硬约束，不满足视为 0 分；当前项目仍主要完成本地 Windows 演示闭环，最终部署证明尚未落地。
2. 当前多模态能力仍偏弱，不能把图片上传入口或资料入库直接表述为“已完成跨模态检索”。
3. 检索已具备 MVP 级加权排序和解释字段，但仍是关键词方案，不是语义向量检索；OpenAI/Anthropic provider 已可选接入，但尚未使用真实密钥做端到端联网验证。
4. 新建案例默认绑定 `wf-001`，多故障类型扩展时需要改为可推断或可选择流程。
5. 演示材料仍需要从“大纲”升级为“逐步检查清单 + 兜底输入 + 截图点”。
6. 上传接口已具备 MVP 级类型/大小/空文件/MIME 校验，但仍不是生产级安全方案，不包含鉴权、病毒扫描或对象存储治理。
7. 资料入库当前是轻量 MVP：TXT/Markdown 可直接解析，PDF 依赖后续可选解析器；扫描 PDF/OCR、向量库和真实 RAG 尚未接入。

中优先级风险：

1. 生产构建存在 chunk size 警告，当前不阻塞 MVP，但后续可优化。
2. 浏览器插件曾出现 localhost/127.0.0.1 被拦截的情况，必要时用构建和接口测试作为替代验证。
3. 引入 Docling、MinerU、PaddleOCR、LlamaIndex/LangChain 前必须先做小样本验证，避免依赖体积、模型下载和国产化兼容风险拖垮演示。

## 7. 当前推荐下一步

优先级从高到低：

1. `PLAN-01-07`：编写 3 到 5 分钟端到端演示检查清单，包含固定输入和失败兜底。
2. `PLAN-02-02 / PLAN-02-03`：用真实 API Key 做一次可控联网验证，记录模型、超时、失败降级和费用风险。
3. `PLAN-02-05`：基于 Docling、MinerU、PaddleOCR 做文档解析/OCR 小样本验证，记录许可证、依赖体积和环境风险。
4. 继续补充 mock 数据和可入库资料样例，让至少 3 条演示路径都有手册、案例、流程和验收标准。
5. 评估是否需要在前端增加 provider 选择器；当前前端默认走后端环境变量或 mock fallback。

普通 Agent 可执行：

1. 测试扩展。
2. 文档同步。
3. mock 数据补充。
4. 演示检查清单初稿。
5. 小范围前端状态和样式优化。

必须升级给高智能模型或人工确认：

1. 架构变更。
2. API 契约变更。
3. 数据模型和状态流转变更。
4. RAG/LLM/OCR/多模态技术路线。
5. 上传安全策略。
6. 国产化部署承诺。
7. 最终答辩材料和参赛信息。

## 8. 标准验证命令

查看状态：

```powershell
git status --short --branch
```

后端测试：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-backend-tests.ps1
```

前端构建：

```powershell
cd frontend
npm.cmd run build
```

前端依赖安装：

```powershell
cd frontend
npm.cmd install
```

后端环境初始化：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup-anaconda.ps1
```

Windows 一键启动：

```bat
start-dev.bat
```

## 9. 工作规则

所有 Agent 必须遵守：

1. 先读本文档，再读任务相关文件。
2. 开始前运行 `git status --short --branch`。
3. 不使用 `git reset --hard`、`git checkout --` 等破坏性命令。
4. 不提交 `node_modules/`、`dist/`、`.venv/`、`.npm-cache/`、`data/uploads/`、`.claude/` 等生成物或外部工具目录。
5. 不提交密钥、真实账号、token 或敏感信息。
6. 不为了通过测试而删除测试或降低断言。
7. 不改变当前轻量 B/S 架构，除非获得明确批准。
8. 不提前扩展完整权限系统、知识图谱、多租户、自动报告生成或生产级多模态诊断。
9. 测试不得污染 `data/examples/repair-cases.json` 或 `data/knowledge/`，必须使用 `APP_EXAMPLES_DIR` 和 `APP_KNOWLEDGE_DIR` 隔离。
10. 完成任务后更新本文档中对应状态、风险或下一步。

## 10. 每次任务完成后的动态更新要求

完成以下任一事件后，必须更新本文档：

1. 新增或删除核心功能。
2. 新增、删除或修改 API。
3. 改变数据结构、状态流转或 mock 数据。
4. 新增重要测试或改变验证命令。
5. 修复高优先级风险。
6. 发现新阻塞问题。
7. 完成一次提交。
8. 改变下一步优先级。

更新位置建议：

1. `第 2 节`：更新分支状态、提交号、验证结果。
2. `第 5 节`：更新已实现能力。
3. `第 6 节`：新增或移除风险。
4. `第 7 节`：调整下一步任务队列。
5. `第 8 节`：更新验证命令。

更新时不要写空泛描述。必须写清楚“发生了什么、影响什么、如何验证、剩余风险是什么”。

## 11. Agent 输出报告模板

每个 Agent 完成工作后，应输出：

```text
任务：
修改文件：
验证命令：
验证结果：
本文档更新位置：
未完成事项：
剩余风险：
建议下一步：
```

如果没有修改代码，也要说明为什么没有验证或为什么只做文档更新。

## 12. 当前交接判断

当前项目适合继续小步推进。最稳妥的路径不是立刻接真实大模型，而是先把“能跑的演示闭环”打磨成“能解释、能复现、能抗追问”的比赛作品：

1. 让每条检索结果更可解释。
2. 让上传和审核边界更安全。
3. 让演示脚本更稳定。
4. 让文档状态与代码状态一致。
5. 让 UI 更像工业检修辅助系统，而不是普通 CRUD 面板。
