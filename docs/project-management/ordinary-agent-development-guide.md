# 普通模型 Agent 开发交接指南

本文档用于把当前项目交接给普通模型驱动的 Agent。目标不是让普通 Agent 重新设计系统，而是让它在边界清晰、风险可控的任务上稳定推进，并在遇到架构、模型、安全、部署和答辩相关问题时及时升级评审。

## 1. 项目速览

项目名称：设备检修知识检索与作业辅助系统。

当前目标：围绕“故障现象检索 -> 返回手册/案例/流程 -> 提交新案例 -> 审核通过 -> 再次可检索”的 MVP 闭环继续完善。

当前技术栈：

1. 前端：Vue 3 + TypeScript + Vite + Element Plus。
2. 后端：FastAPI。
3. 数据：`data/examples/` 下的本地 JSON mock 数据。
4. 环境：Windows + Anaconda Python，本地虚拟环境位于 `backend/.venv`。

当前已验证基线：

1. 后端接口测试通过，现有测试数量为 5 个。
2. 前端生产构建通过。
3. 案例提交、审核、审核后再检索已经形成可验证闭环。
4. 图片/PDF 上传入口已经接入后端上传接口。
5. Vite 当前固定在 `7.3.3`，不要随意升级或降级。

## 2. 必读顺序

普通 Agent 开始任何开发前，必须按以下顺序阅读：

1. `README.md`：了解项目入口、目录结构和启动方式。
2. `docs/project-management/development-plan.md`：了解当前阶段、已完成项和后续任务。
3. `docs/project-management/model-task-classification.md`：判断任务是否适合普通模型执行。
4. `docs/design/api-contract-draft.md`：确认接口字段和响应结构。
5. `docs/design/data-model-draft.md`：确认核心实体和状态字段。
6. `docs/deployment/local-development-environment.md`：确认本地环境与 Anaconda 使用方式。
7. `tests/test_backend_api.py`：确认后端当前行为和测试隔离方式。

如果任务涉及页面交互，还应阅读：

1. `frontend/src/App.vue`
2. `frontend/src/api.ts`
3. `frontend/src/components/QueryPanel.vue`
4. `frontend/src/components/ResultsPanel.vue`
5. `frontend/src/components/WorkflowPanel.vue`
6. `frontend/src/components/CasePanel.vue`

如果任务涉及后端行为，还应阅读：

1. `backend/app/main.py`
2. `backend/app/schemas.py`
3. `backend/app/services.py`
4. `backend/app/data_store.py`

## 3. 可执行命令

后端环境初始化：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup-anaconda.ps1
```

后端测试：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-backend-tests.ps1
```

前端依赖安装：

```powershell
cd frontend
npm.cmd install
```

前端构建：

```powershell
cd frontend
npm.cmd run build
```

启动后端：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-backend.ps1
```

启动前端：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-frontend.ps1
```

注意事项：

1. Windows 环境下优先使用 `npm.cmd`，不要直接假设 `npm` 一定可用。
2. PowerShell 脚本建议带 `-ExecutionPolicy Bypass -File`。
3. 临时启动服务时优先使用 PowerShell job，不要依赖 `Start-Process` 继承 PATH。
4. 本地浏览器插件曾出现 localhost/127.0.0.1 被拦截的情况，若无法浏览器验证，应至少保留构建、接口测试和命令输出证据。

## 4. 普通 Agent 适合执行的任务

以下任务边界清晰，适合普通模型执行：

1. 新增或整理非核心文档，例如本地启动说明、演示检查清单、任务状态表。
2. 在不改变接口契约的前提下补充前端页面区域，例如审核区域、空状态、加载状态和错误提示。
3. 补充 mock 数据，例如新增少量设备、手册片段、维修案例和作业流程。
4. 为现有 API 补充前端请求封装，不改变后端字段含义。
5. 为现有接口补充测试样例，例如拒绝审核、空查询、非法上传类型等。
6. 整理 README、项目管理文档和演示材料中的格式问题。
7. 按现有组件风格做小范围 UI 调整，避免重构整体视觉和交互架构。

推荐的下一批普通任务：

1. `GEN-FE-REVIEW-01`：补前端审核区域，接入 `GET /api/cases` 和 `PATCH /api/cases/{case_id}/review`。
2. `GEN-DOC-DEMO-01`：编写 3 到 5 分钟端到端演示检查清单，包含兜底数据。
3. `GEN-DATA-CASES-01`：补齐至少 2 条完整演示案例，包含手册来源、故障现象、处理步骤和验收标准。
4. `GEN-TEST-API-01`：补充后端测试，覆盖拒绝审核、空查询和上传异常。
5. `GEN-DOC-SETUP-01`：整理本地环境常见问题，特别是 Anaconda、PowerShell 和前后端启动顺序。

## 5. 必须升级评审的任务

以下任务不得由普通 Agent 独立决定，必须交给高智能模型或团队人工确认：

1. 改变技术栈、目录结构、前后端边界或部署方式。
2. 修改 API 契约、核心数据模型、案例状态流转和检索结果结构。
3. 设计或接入真实 LLM、RAG、向量数据库、OCR、多模态识别、知识图谱。
4. 调整检索排序、来源引用规则、模型提示词和降级策略。
5. 扩展上传安全、文件存储策略、权限系统或用户身份体系。
6. 承诺国产化部署能力，例如 LoongArch、银河麒麟或本地大模型适配。
7. 编写最终答辩 PPT、演示讲稿、商业价值、创新点和竞赛提交材料。
8. 填写或修改队伍信息、学校信息、参赛承诺和资料版权说明。

升级时必须提供：

1. 任务背景。
2. 已读文件。
3. 当前改动点或待决策点。
4. 可选方案。
5. 风险和影响范围。
6. 已执行的验证命令与结果。

## 6. 禁止事项

普通 Agent 不得执行以下操作：

1. 不得使用 `git reset --hard`、`git checkout --` 等破坏性命令回滚用户或他人改动。
2. 不得提交 `node_modules/`、`dist/`、`.venv/`、`.npm-cache/`、`data/uploads/` 等生成物。
3. 不得把密钥、真实账号、云服务 token 写入仓库。
4. 不得为了通过测试而删除测试或降低断言强度。
5. 不得直接覆盖 `data/examples/repair-cases.json` 作为测试数据；测试必须通过 `APP_EXAMPLES_DIR` 隔离。
6. 不得在未评审时引入数据库、鉴权、多租户、报表系统或完整知识图谱。
7. 不得随意升级 Vite 到新主版本；此前 Windows 路径兼容和安全版本已经专门处理过。
8. 不得把普通文档润色扩展成新的产品承诺。

## 7. 标准执行流程

普通 Agent 每次接收任务后按以下流程执行：

1. 查看工作区状态，确认是否存在未提交改动。
2. 阅读任务相关文档和代码，不做全仓库无目标重构。
3. 根据 `model-task-classification.md` 判断任务类型。
4. 如果任务属于重点任务或人工确认任务，停止实现并输出升级说明。
5. 如果任务属于普通任务，先列出输入文件、输出文件、允许改动和禁止改动。
6. 小步修改，优先保持现有架构、命名和组件边界。
7. 根据改动类型运行最小必要验证。
8. 如果行为变化，同步更新对应文档或测试。
9. 输出最终报告，包含修改文件、验证命令、结果、剩余风险。

## 8. 普通任务模板

给普通 Agent 派发任务时，建议使用以下模板：

```text
任务编号：
目标：
输入文件：
输出文件：
允许修改：
禁止修改：
验收标准：
验证命令：
失败时处理：
是否需要高智能模型复审：
```

示例：

```text
任务编号：GEN-FE-REVIEW-01
目标：在现有前端工作台中增加案例审核区域，演示提交案例、审核通过、再次检索闭环。
输入文件：frontend/src/App.vue、frontend/src/api.ts、frontend/src/components/CasePanel.vue、backend/app/schemas.py
输出文件：frontend/src/components/ReviewPanel.vue、frontend/src/App.vue、frontend/src/api.ts
允许修改：新增组件、补充 API wrapper、在 App.vue 中接入组件。
禁止修改：不得改变后端 API 字段，不得改案例状态枚举，不得引入路由系统。
验收标准：页面可查看 pending_review 案例，并能批准或拒绝。
验证命令：npm.cmd run build；后端接口测试如有相关修改则运行 run-backend-tests.ps1。
失败时处理：保留错误输出，不要扩大重构范围，交给高智能模型复审。
是否需要高智能模型复审：完成后建议抽样复审交互和接口字段。
```

## 9. 风险登记

| 风险 | 影响 | 控制方式 |
| --- | --- | --- |
| 本地 JSON 数据被测试或调试污染 | 演示数据不稳定 | 测试必须使用 `APP_EXAMPLES_DIR` 指向临时目录 |
| localhost 浏览器验证受插件拦截 | 页面人工验证不完整 | 使用构建、接口测试和命令输出作为替代证据 |
| Vite 版本变动 | Windows 构建或安全审计回退 | 固定当前可用版本，升级前单独评审 |
| Anaconda/虚拟环境路径差异 | 新机器无法启动后端 | 先运行 setup 脚本，并在文档中记录实际 Python 路径 |
| 普通 Agent 越界改架构 | 破坏前期轻量 B/S 路线 | 使用任务分类表和本指南的升级规则 |
| 上传接口被误当成安全完备能力 | 答辩或部署承诺过度 | 明确当前是 MVP 本地上传，不代表生产安全方案 |
| RAG/LLM 设计被过早实现 | 引入不可控依赖和演示失败点 | 先设计接口和降级策略，真实接入需重点评审 |
| 竞赛材料事实错误 | 影响提交与答辩可信度 | 队伍信息、版权和最终承诺必须人工确认 |

## 10. 交付报告格式

普通 Agent 完成任务后，应输出简短报告：

1. 完成了什么。
2. 修改了哪些文件。
3. 运行了哪些验证命令，结果是什么。
4. 没有运行哪些验证，原因是什么。
5. 剩余风险和建议下一步。

报告中不要只写“已完成”，必须保留可追溯证据。

## 11. 当前交接结论

当前项目可以交给普通 Agent 执行小步开发，但必须遵守以下边界：

1. 优先完成前端审核区域、演示检查清单、mock 数据补充和测试扩展。
2. 不改变现有轻量 B/S 架构。
3. 不提前承诺真实 RAG、OCR、多模态、权限系统和国产化生产部署。
4. 涉及 API、数据模型、模型路线、上传安全和答辩材料时立即升级评审。
5. 每次修改后至少运行与改动相关的最小验证，并更新任务进度文档。
