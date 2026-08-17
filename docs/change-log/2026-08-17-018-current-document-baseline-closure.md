# 现行文档基线与冲突收口

- 变更标识：`2026-08-17-018-current-document-baseline-closure`
- 日期：`2026-08-17`
- 记录状态：`变更已结束`（只描述本次修改记录，不表示需求功能完成）
- 状态对象：`现行文档治理、需求追踪结构与后续模块边界`
- 功能验证状态：`已设计`
- 所属模块：`M7`；协作模块：`M0、M1、M2、M3、M4、M5、M6`
- 需求追踪：`BR-01～BR-13、AUTH-01～AUTH-13、FR-IAM/FR-QRY/FR-RET/FR-WF/FR-RAG/FR-DOC/FR-KNW/FR-CASE/FR-FB/FR-OPS 全部条款、DATA-01～DATA-08、API-01～API-07、NFR-PORT/PERF/REL/SEC/OBS/UX/MNT 全部条款`
- 关联记录：`2026-08-14-014-readme-baseline-alignment`、`2026-08-14-015-historical-document-baseline-boundary`、`2026-08-17-016-stage0-contract-alignment`、`2026-08-17-017-m0-foundation-hardening`
- 规范来源影响：`需求语义、动态状态、领域事件、公共契约`

## 改动内容

- 新增现行需求追踪矩阵，覆盖 SRS 的 160 个需求编号，分开记录状态对象、六级功能状态、代码/迁移、自动测试、验收/集成证据和未关闭问题。
- 新增领域事件唯一目录，将具体事件生命周期与功能状态分离，并按消费者是否登记收紧 outbox 范围。
- 将所有生产持久化写操作的身份规则补齐到 AUTH-13：普通请求使用 `CurrentUser`，异步/内部任务使用受管服务用户并保留发起身份，bootstrap 只允许在生产激活前执行。
- 将动态状态唯一来源收口到现行追踪矩阵；README 和设计文档中的状态表明确为 2026-08-17 快照，SRS 不再复制日志模板或动态状态表。
- 修正查询、检索、流程、RAG、案例和反馈的模块归属。维修案例作为 M2 knowledge 子域，回答反馈作为 M5 rag 子域，复用现有 M0 路由/模型预留点，避免后续新增平行注册机制。
- 修正 readiness 规范路径、迁移 head 动态获取方式、OpenAPI 通用 500 未关闭缺口、前端旧 `/api`/Playwright 边界、部署工件空缺和历史评测报告适用范围。
- 扩展变更日志模板，强制记录“状态对象”“规范来源影响”和“状态与证据”，减少同一进度在 README、SRS 和多个设计文档重复维护。

## 文件与数据影响

- `.env.example`、`README.md`、`backend/README.md`、`frontend/README.md`；修改配置示例说明、当前边界和开发约定。
- `data/external-test/README.md`；修改测试资料与生产事实边界。
- `data/evaluation/reports/README.md`；新增历史评测报告适用边界。
- `docs/requirements/software-requirements-spec.md`；修改需求语义、稳定模块边界和唯一来源规则。
- `docs/requirements/current-traceability-matrix.md`；新增动态状态唯一事实源。
- `docs/design/event-catalog.md`；新增具体领域事件唯一事实源。
- `docs/design/m0-public-contract.md`、`m1-identity-audit-design.md`、`module-build-progress-and-interface-plan.md`、`m0-m1-deployment-readiness-plan.md`；修改契约边界、日期化快照和后续接入顺序。
- `docs/change-log/README.md`、`TEMPLATE.md`、`INDEX.md`；修改日志治理并登记本记录。
- 数据库表、Alembic revision、运行时代码、生产 API/DTO：无变更。
- 领域事件：仅新增“提议”目录项，没有冻结或实现运行时事件，不授权生产者发布。

## 依赖与冲突检查

- 已检查：修改日志索引及 016/017；SRS 全部需求编号；M0/M1 公共契约与代码；当前 OpenAPI；Alembic head；readiness 代码和规范路径；M0 领域注册表；M1 认证主体；前端 API/依赖；`deploy/`；历史材料声明和评测报告原始元数据。
- 结论：需求语义、动态状态、具体事件、公共契约和执行证据已分配到不同唯一来源；案例和反馈复用既有 M2/M5 注册边界，不新增 M0 注册冲突；历史正文保持不可改写，只通过非现行声明和辅助边界阻止其覆盖当前基线。
- 状态与证据：本次没有修改运行时代码、数据库或迁移，只能把文档治理和后续边界记录为“已设计”；M0/M1 日期化代码证据仍只支持对应状态对象“单元已验证”，不提升任何需求或模块为“集成已验证”或“已完成”。

## 验证与回滚

- 验证：`git diff --check` 通过（仅有 Git 的 LF/CRLF 提示）；排除依赖目录后全部仓库 Markdown 相对链接检查通过。
- 验证：SRS 提取 160 个需求编号，追踪矩阵展开编号范围后覆盖 160/160，无缺失编号。
- 验证：`alembic heads` 返回单一 head `20260814_0005`；本次无数据库结构文件变化。
- 验证：当前 OpenAPI 有 15 个 v1 操作、14 个 v1 唯一路径，规范 readiness 路径存在；通用 `500` 声明为 0，已作为 D1.2 未关闭缺口记录。
- 验证：从仓库根执行 `.\backend\.venv\Scripts\python.exe -m pytest -q`，结果 `259 passed, 25 skipped in 18.21s`；3 项 PostgreSQL 和 22 项外部手册 skip 仍不计为集成成功。曾从 `backend/` 误执行同一无路径命令得到 `no tests ran`，该次空跑不作为证据。
- 验证：从 `frontend/` 执行 `npm run build` 成功，主 JavaScript `1,052.46 kB`，仍有大 chunk 警告；构建不作为浏览器 E2E 或 M6 集成证据。
- 验证：目标领域目录未检出 `subprocess`、`os.system`、`os.popen`、`Popen`、PowerShell 或 `cmd.exe` 依赖。
- 验证：前端源码仍调用旧 `/api`；Playwright 配置/用例存在但 `package.json` 和 lockfile 均无 `@playwright/test`；`deploy/` 仍只有 `.gitkeep`。这些事实均未被误写为已集成。
- 验证：从仓库根使用 `-m backend.app.domains.identity.bootstrap --help`、从 `backend/` 使用 `-m app.domains.identity.bootstrap --help` 均成功，README 的两种工作目录命令与实际包路径一致。
- 验证：工作区 diff 未包含 `.py`、`.ts`、`.vue`、`.js`、Alembic 或数据库模型文件。
- 回滚：还原本记录列出的文档和 `.env.example`，删除新增的追踪矩阵、事件目录、辅助 README 与本日志，并移除索引行；无数据库降级、数据恢复或运行时回滚步骤。

## 后续开发提示

- 下一次修改先读 `INDEX.md`、本记录、当前追踪矩阵，以及目标模块最近日志；动态状态升级只改追踪矩阵和日志。
- D1.2 先补 OpenAPI 通用 500、AUTH-13 受管服务用户/异步发起身份和生产激活前 bootstrap 契约及测试；完成前 M2/M3/M5 不得自建第二套主体。
- 创建任何迁移前运行 `alembic heads`，使用执行时最新 head，并记录实际 revision；不得把 `20260814_0005` 当作永久目标。
- 事件目录中的事件都只是“提议”。生产者、消费者、payload、幂等、重放、权限和契约测试冻结前不得发布。
- M2 案例复用 `domains/knowledge`/`api/v1/knowledge.py` 注册边界；M5 反馈复用 `domains/rag`/`api/v1/rag.py` 注册边界。确需新增 M0 注册项时，必须作为独立公共契约变更并先补契约测试。
