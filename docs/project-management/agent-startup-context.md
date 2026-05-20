# Coding Agent 初始化入口

本文档是所有 Coding Agent 接手本项目时的第一阅读入口。无论 Agent 是否拥有前文对话上下文，都必须先阅读本文件，再决定是否继续阅读更细的设计、开发和任务文档。

本文件必须在后续开发中动态更新：每次完成可运行闭环、提交重要代码、发现新风险、调整任务优先级或改变验证方式后，都要同步修改本文档。

## 1. 当前项目一句话

项目是“设备检修知识检索与作业辅助系统”的软件杯 MVP。当前重点是稳定演示以下闭环：

```text
输入设备型号和故障现象
-> 检索手册片段和历史案例
-> 查看标准作业流程
-> 上传现场材料
-> 提交维修经验案例
-> 审核案例
-> 审核通过后再次检索命中新案例
```

当前系统可以演示，但仍处于 MVP 骨架阶段，不应宣称已经具备生产级 RAG、多模态诊断、权限系统或国产化完整部署能力。

## 2. 当前仓库状态

最近确认时间：2026-05-20。

当前分支：`main`。

最近确认状态：

1. 本迭代提交后，本地分支预计领先 `origin/main` 7 个提交。
2. 当前代码已完成后端可信边界迭代：空查询拒绝、审核 action 枚举、上传类型/大小/空文件/MIME 校验和统一错误响应。
3. 后端测试通过：`12 passed`。
4. 前端构建通过：`vue-tsc -b && vite build`。
5. 当前 Vite 版本固定为 `7.3.3`。

最近关键提交：

1. `fix: harden api validation and upload boundaries`
2. `0d5ebac docs: add coding agent startup context`
3. `db21815 feat: add case review panel and handoff guidance`
4. `e66bc98 feat: complete mvp case workflow`
5. `f64786d chore: standardize backend anaconda setup`

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

数据目录：

1. `data/examples/devices.json`
2. `data/examples/manuals.json`
3. `data/examples/repair-cases.json`
4. `data/examples/workflows.json`

## 4. 首次接手必读顺序

最小必读：

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
7. `tests/test_backend_api.py`

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

前端：

1. 检索输入区。
2. 知识结果区。
3. 作业流程区。
4. 案例提交区。
5. 案例审核区。
6. 图片/PDF 上传入口。
7. 基础空状态、加载状态、焦点可访问性和 reduced-motion 支持。

验证：

1. 后端接口测试覆盖健康检查、检索、空查询、流程查询、上传目录配置、上传成功、空文件、非法扩展名、MIME 不匹配、超大文件、案例提交审核再检索闭环和非法审核 action。
2. 前端生产构建通过。

## 6. 当前主要风险

高优先级风险：

1. 检索仍是关键词匹配，摘要是固定文案，真实 RAG/LLM 能力尚未接入。
2. 新建案例默认绑定 `wf-001`，多故障类型扩展时需要改为可推断或可选择流程。
3. 演示材料仍需要从“大纲”升级为“逐步检查清单 + 兜底输入 + 截图点”。
4. 上传接口已具备 MVP 级类型/大小/空文件/MIME 校验，但仍不是生产级安全方案，不包含鉴权、病毒扫描或对象存储治理。

中优先级风险：

1. 前端首屏仍显示 `Mock 模型`、`关键词检索`，评委感知上可能削弱智能系统印象。
2. 生产构建存在 chunk size 警告，当前不阻塞 MVP，但后续可优化。
3. 浏览器插件曾出现 localhost/127.0.0.1 被拦截的情况，必要时用构建和接口测试作为替代验证。
4. 项目本地分支领先远端，若多人协作需尽快明确 push/分支策略。

## 7. 当前推荐下一步

优先级从高到低：

1. `PLAN-02-01`：设计检索排序和来源引用规则，让结果能解释命中原因、来源章节和页码。
2. `PLAN-01-07`：编写 3 到 5 分钟端到端演示检查清单，包含固定输入和失败兜底。
3. `PLAN-02-02 / PLAN-02-03`：设计 OpenAI-compatible 模型适配层和 mock 降级策略，先设计接口，不急于接真实模型。
4. UI 审美优化：保持现有轻量 B/S 架构，增强工业控制台质感，不做大规模主题重写。
5. 继续补充 mock 数据，让至少 3 条演示路径都有手册、案例、流程和验收标准。

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
9. 测试不得污染 `data/examples/repair-cases.json`，必须使用 `APP_EXAMPLES_DIR` 隔离。
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
