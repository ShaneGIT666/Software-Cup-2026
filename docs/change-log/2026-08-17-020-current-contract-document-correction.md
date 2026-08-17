# 现行契约与文档冲突修正

- 变更标识：`2026-08-17-020-current-contract-document-correction`
- 日期：`2026-08-17`
- 记录状态：`变更已结束`（只描述本次修改记录，不表示需求功能完成）
- 状态对象：`仅文档治理；现行 SRS/追踪矩阵/公共契约/事件目录与脚本证据边界`
- 功能验证状态：`已设计`
- 所属模块：`M7`；协作模块：`M0～M6`
- 需求追踪：`SRS 162 个需求编号的动态映射；重点修正 AUTH-04、AUTH-13、DATA-02、DATA-08、API-02、API-04～API-06、NFR-PORT-01～06、NFR-REL-01～06、NFR-SEC-04、NFR-OBS-01～03、NFR-MNT-01～06`
- 关联记录：`2026-08-17-018-current-document-baseline-closure`、`2026-08-17-019-d1-2-production-contract-closure`
- 规范来源影响：`需求语义、动态状态、领域事件、公共契约`

## 改动内容

- 按运行时代码、迁移、路由、脚本和现有测试重建现行追踪矩阵：以提交 `11bd05ba94b4`为代码证据基线，分开不同状态对象，修正 DATA-08、API-06、NFR-REL-01 等错误映射，不再用局部单元证据提升整项需求。
- 更正记录 019 被现行文档过度外推的证据边界：通用 500 OpenAPI 声明和未捕获异常脱敏不能证明显式 `HTTPException`/`AppError` 5xx 或普通异常日志已脱敏；后两者仍是 P0，成功 `data/items` 中的 `Any` 仍是 M6 前置契约缺口。
- 重写 M0/M1 稳定契约：对齐实际 M1 服务账户、实例生命周期、非空 actor/可空 initiator 和数据表；明确 `AuthenticatedActor` 尚未接入 `AuditEventInput`、事件级 metadata 白名单、服务账户 readiness、审核容量端口及 `device:write`/`ops:write` 仍待实现。
- 区分 outbox append 输入与持久化/投递 envelope，`eventId` 由 Writer 生成；只有“生命周期已冻结且登记实际消费者”的事件可在生产路径发布。提议阶段允许生产者/M4 并行编写契约和 handler，完成实际消费者登记后再冻结，消除“先冻结还是先实现消费者”的循环依赖。
- 冻结长期模块所有权：审核表归 M2/M3 各领域，`RepairCaseVersion` 归 M2，`RagQueryAttachment` 归 M5，`api/v1/operations.py` 归 M4，M4 仅通过生产者公开幂等命令端口回写。M7 拥有跨模块验收/CI，不独占各模块单元与契约测试。
- 补齐受限 provisioning：`bootstrapped` 时 `live=200`/`ready=503`，仅对本机或明确可信管理来源开放最小改密通道；任一有效、已改密且具有 `system_admin` 的本地账户符合现行 activation 主体契约，`active` 且完整 readiness 成功后才开放正常业务流量。
- 减少后续重复维护：SRS 只保留需求语义，追踪矩阵独占动态状态，事件目录独占具体事件，M0/M1 文档只保留稳定契约，`scripts/README.md` 独占脚本分类与证据边界。历史日志和带非现行声明的历史材料保持原文。
- 为旧 `production_readiness`/`final`/Docker/LoongArch 脚本和容器材料增加持久边界提示；旧离线检查报告显式输出 `scope=legacy-prototype-offline-smoke` 和 `productionReady=false`。`init-config.*` 不再输出错误或未受支持的启动命令。

## 文件与数据影响

- `README.md`、`backend/README.md`、`frontend/README.md`、`.env.example`、`backend/requirements-{rag,ocr,mineru}.txt`：修改说明或注释。
- `docs/requirements/software-requirements-spec.md`、`current-traceability-matrix.md`：修改；前者仅保留稳定需求，后者重建动态状态与缺口映射。
- `docs/design/m0-public-contract.md`、`m1-identity-audit-design.md`、`event-catalog.md`、`module-build-progress-and-interface-plan.md`、`m0-m1-deployment-readiness-plan.md`：修改契约、所有权、集成顺序与历史证据边界。
- `scripts/README.md`：新增；作为脚本类别和证据边界的唯一索引。
- `Dockerfile`、`scripts/init-config.*`、`scripts/*production-readiness*`、`scripts/run-local-verification.ps1`、Docker/LoongArch/demo/benchmark 脚本：只修改边界警告、引导文字和旧检查报告的证据范围字段；不改变业务检查算法。
- 数据库表、迁移、生产 API/DTO、领域事件实现和前后端业务代码：无变更。`001`～`019` 历史日志正文：无变更。

## 依赖与冲突检查

- 已检查：`docs/change-log/INDEX.md`、`TEMPLATE.md`、记录 016～019、根/后端/前端 README、SRS、追踪矩阵、M0/M1 设计、事件目录、模块/部署方案，以及 M0/M1 路由、异常处理、OpenAPI 契约、审计输入/Writer、身份模型/迁移/readiness/activation、outbox、前端客户端和部署/依赖脚本。
- 结论：记录 019 保持其当时证据原文；它只证明通用 500 OpenAPI 声明和明确的 M1 主体子范围，不再被用于证明全部运行时 5xx、NFR-REL-01 服务自启或 typed actor 审计闭环。历史材料内部的旧口径由顶部“非现行基线”声明隔离，不改写历史事实。
- 状态与证据：本次没有修复 P0 运行时缺陷、接入真实 PostgreSQL 或建立部署/CI；因此只把文档治理记为“已设计”，不提升任何代码功能、模块或需求的实现状态。

## 验证与回滚

- 验证：全仓库 `124` 份 Markdown 的相对链接检查为 `0` 断链；变更的 Markdown 表格列数一致；`84` 份历史 Markdown 顶部非现行声明仍存在。
- 验证：机械展开矩阵区间后，SRS 唯一需求编号 `162/162` 已映射，缺失 `0`；`git diff --check` 通过，仅有 Windows LF/CRLF 提示。
- 验证：7 份变更 PowerShell 脚本语法解析 `0` 错误；2 份 Python 脚本 AST 解析通过。当前环境无 Bash，`init-config.sh`/`loongarch-final-verify.sh` 未执行 `bash -n`，仅复核本次新增的注释与 `echo` 文本。
- 验证：旧离线原型检查 7 项通过，同时明确输出 `scope=legacy-prototype-offline-smoke`、`productionReady=false`；该结果不是生产 readiness 证据。
- 验证：`.\backend\.venv\Scripts\python.exe -m pytest -q`，结果 `271 passed, 25 skipped in 18.62s`；3 项 PostgreSQL 和 22 项外部手册测试仍跳过。该回归不得提升真实依赖状态。
- 验证：从 `backend/` 执行 `alembic heads` 返回唯一 `20260817_0006 (head)`；本次无数据库结构变更，未新增迁移。
- 验证：`npm run build` 成功，仍有约 `1.05 MB` 主 chunk 警告；本次未改前端业务代码。
- 回滚：按本记录的文件清单恢复文档、注释和旧脚本输出，删除 `scripts/README.md` 及本日志/索引行即可；无数据库降级或数据恢复步骤。

## 后续开发提示

- 下一次修改前必须读取 `INDEX.md`、本记录、现行追踪矩阵及受影响模块最近记录；涉及事件时同时读取事件目录。
- 动态完成状态只更新追踪矩阵和新日志；具体事件只更新事件目录；脚本用途变化只更新 `scripts/README.md`。只有需求语义、公共契约、模块所有权或验收口径真正变化时，才再改 SRS/设计文档。
- 下一个代码门禁是：修复显式 5xx 响应与普通异常日志脱敏，冻结 typed actor 到事件级审计输入的强类型桥接，且缺陷修复必须新增对应测试。随后在一次性或明确独占的 PostgreSQL 16 测试库完成 D2；此前 M2/M3/M5 只使用版本化契约 Mock 开发纯领域逻辑。
