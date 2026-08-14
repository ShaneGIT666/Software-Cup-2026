# 收紧历史文档与现行基线边界

- 变更标识：`2026-08-14-015-historical-document-baseline-boundary`
- 日期：`2026-08-14`
- 记录状态：`变更已结束`
- 功能验证状态：`未验证`（本次仅修正文档适用范围，不改变代码、数据、接口或既有功能验证状态）
- 所属模块：`M7`；协作模块：`M0`～`M6`
- 需求追踪：SRS 第 1 节状态定义、第 14.5 节强制变更说明与本地修改日志、`NFR-MNT-05`、`NFR-MNT-06`
- 关联记录：`2026-08-14-014-readme-baseline-alignment`

## 改动内容

- 以根 `README.md`、现行 SRS 和修改日志索引为优先基线，为 84 份竞赛原型、阶段调研、验证、测试、部署、交付和项目管理历史文档增加统一的“历史快照（非现行基线）”声明。
- 明确历史文件中的“当前”“最终”“正式”“已完成”“必须”“一键部署”等词只在当时语境内有效，不构成现行产品状态、开发顺序、生产要求或交付承诺。
- 保留历史测试数量、目标环境验证和竞赛交付事实，但要求命令、测试数字和部署结论在当前版本重新验证后才能作为验收证据。
- 直接撤销旧项目管理材料中的现行阅读优先级，改为先读根 README、`docs/change-log/INDEX.md` 及相关模块最新记录。
- 将旧 Docker/LoongArch 完成结论限定到原型版本和记录日期，不再覆盖当前 Dockerfile、配置、API、数据库及 Windows 基础交付方向。
- 扩充根 README 的历史文档范围说明，使混合目录中的旧设计、旧需求和根目录旧计划文件也有明确归属。

## 文件与数据影响

- `README.md`：修改；列明完整历史资料范围及其效力边界。
- `PRODUCT.md`、`findings.md`、`progress.md`、`task_plan.md`、`docs/pre-development-index.md`：修改；标记为历史快照并撤销旧入口效力。
- `docs/architecture/`、`docs/deployment/`、`docs/ppt-assets/`、`docs/product/`、`docs/project-management/`、`docs/research/`、`docs/submission/`、`docs/testing/`、`docs/superpowers/specs/` 下 72 份 Markdown：修改；增加统一历史声明，部分关键交接措辞进一步收紧。
- `docs/design/api-contract-draft.md`、`docs/design/data-model-draft.md`、`docs/design/software-design-doc.md`：修改；标记为旧原型设计，不再作为现行 API、数据或架构契约。
- `docs/requirements/mvp-scope.md`、`docs/requirements/official-compliance-matrix-final.md`、`docs/requirements/official-problem-baseline.md`、`docs/requirements/sample-data-plan.md`：修改；标记为竞赛/MVP 历史材料，其中 LoongArch 约束限定为当时竞赛提交要求。
- `docs/change-log/2026-08-14-015-historical-document-baseline-boundary.md`：新增；记录本逻辑变更单元。
- `docs/change-log/INDEX.md`：修改；登记第 015 号记录。
- 数据库、迁移、API、DTO、事件、运行配置、依赖和真实数据：无。

## 依赖与冲突检查

- 已检查：`docs/change-log/INDEX.md`、模板、第 014 号记录、根 README、现行 SRS、M0 公共契约、M1 设计、模块进度计划及 Alembic migration head。
- migration head：`20260814_0005`，本次没有数据库结构变更，也没有新增迁移。
- 结论：历史事实没有删除或改写；其适用范围、状态含义和优先级已被显式限定。旧修改日志作为不可静默改写的追溯记录继续保留，并由索引中的状态说明和第 010、014、015 号记录共同限定。
- 现行文档未降级：`README.md`、SRS、`m0-public-contract.md`、`m1-identity-audit-design.md`、`module-build-progress-and-interface-plan.md`、`m0-m1-deployment-readiness-plan.md`、`backend/README.md` 和变更日志机制仍按当前基线使用。

## 验证与回滚

- 验证：枚举目标历史文档共 84 份，`84/84` 均包含统一历史声明，无漏标。
- 验证：扫描仓库 Markdown 相对链接，结果为 `0` 个断链。
- 验证：复查“统一真源”“第一入口”“必须优先阅读”“任何后续开发前先读”“后续 agent 不应”等旧强制措辞，相关现行效力已撤销或改写为当时语境。
- 验证：`git diff --check` 通过；本次为纯文档变更，未运行后端、前端或数据库功能测试，也未提升任何功能验证状态。
- 回滚：移除 84 份历史文档顶部声明，恢复本记录中列明的关键措辞和 README 历史范围条目，删除第 015 号日志及索引项；不涉及代码、数据库或运行数据回滚。

## 后续开发提示

- 下一次修改仍必须先读 `docs/change-log/INDEX.md`、本记录及相关模块最新记录。
- 历史文件可以用于追溯需求来源、竞赛演示和旧验证证据，但不得复制其中的 `/api`、JSON、Mock、LoongArch/Docker、三人分工或旧测试完成状态作为现行设计。
- 如需恢复某份历史方案，必须先形成新的现行设计和验证记录，不得只删除历史声明或修改“当前/最终”字样。

