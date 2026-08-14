# 修正 M0/M1 公共接入门槛并冻结后续模块边界

- 变更标识：`2026-08-14-013-m0-m1-public-integration-gates`
- 日期：`2026-08-14`
- 记录状态：`变更已结束`
- 功能验证状态：`代码已搭建、进程内/离线验证通过；真实 PostgreSQL 与生产部署未验证`
- 所属模块：`M0`；协作模块：`M1`、`M2`～`M7`
- 需求追踪：`AUTH-01`～`AUTH-03`、`DATA-01`、`DATA-02`、`DATA-08`、`API-01`～`API-07`、`NFR-REL-01`、`NFR-SEC-01`、`NFR-SEC-03`、`NFR-OBS-02`
- 关联记录：`2026-08-13-012-m0-m1-deployment-audit`；本记录实施并更正其 D1 方案

## 改动内容

- M0 新增统一 readiness 聚合端口。数据库、基础配置和领域健康检查由 M0 注册表决定是否必需；领域只返回无 `required` 字段的脱敏 `ReadinessProbe`，不能自行降低生产门槛。
- M0 修正生产数据库可被配置为可选的问题，并校验生产幂等密钥、HTTPS 可信来源和旧兼容表面。`/health/ready` 不再直接导入 M1，也不再把所有失败错误描述为数据库故障。
- M0 新增 `APP_LEGACY_SURFACE_MODE=enabled|loopback|disabled` 及集中中间件。生产默认且只允许 `disabled`，统一拒绝旧 `/api`（不含 `/api/v1`）、`/uploads`、`/knowledge`；`loopback` 只信任直连客户端地址。
- M0 新增版本化 `OutboxEventInput/OutboxWriter/OutboxAppendResult` 公共写端口，并新增后继迁移 `20260814_0005` 补齐 `version_id`、`request_id`、`occurred_at`。Writer 只追加到调用方事务，不 commit/rollback，不返回 ORM。
- M1 新增 identity readiness contributor；`AuditWriter` 改为返回不可变 `AuditAppendResult(event_id)`，避免后续模块依赖 M1 ORM。
- M1 OpenAPI 增加会话 Cookie security scheme、`X-CSRF-Token` 参数、匿名/可信来源标记和 `x-required-permissions`，供 M6 按契约开发而不读取后端内部实现。
- 修正部署阶段定义：D1 只记录代码级验证；D2 真实 PostgreSQL 通过后即可允许 M2/M3 后端写路由接入真实 M1。Windows Service、代理/备份和 M6 E2E 仍是产品发布门槛，但不再错误阻塞后端领域接入。

## 文件与数据影响

- 所属 M0：`backend/app/core/config.py`、`readiness.py`、`legacy_surface.py`、`backend/app/api/v1/system.py`、`backend/app/db/session.py`、`models.py`、`outbox.py`、`db/__init__.py`、`backend/app/main.py`；新增/修改公共配置、就绪策略、中间件、outbox DTO/Writer 和装配。
- 所属 M0：`backend/alembic/versions/20260814_0005_outbox_event_contract.py`；新增迁移，当前单一 head 为 `20260814_0005`，未编辑 `0001`～`0004`。
- 所属 M1：`backend/app/domains/identity/readiness.py`、`dependencies.py`、`backend/app/domains/audit/contracts.py`、`writer.py`、公开导出及 `api/v1/auth.py`、`users.py`、`audit.py`；新增 contributor、不可变写入结果和 OpenAPI 安全声明。
- 所属 M0/M1 测试：新增 `tests/test_module0_readiness.py`、`test_module0_outbox.py`，扩展 foundation、前置、M1 API/依赖/审计及 PostgreSQL schema 测试。
- 配置：`.env.example` 新增 `APP_LEGACY_SURFACE_MODE`；历史 Dockerfile 显式设为 `disabled`，但 Docker 仍缺真实生产依赖，不因此变为可发布工件。
- 文档：更新根/后端 README、SRS、M0 公共契约、M1 设计、模块进度和 M0/M1 部署方案；所有状态仍区分代码验证与真实部署验收。
- 数据：未连接或修改任何真实数据库。离线迁移设计对已有 outbox 行以 `legacy:<id>` 回填版本/请求字段，并用原 `created_at` 回填发生时间；在线执行前仍需在专用 `_test` 数据库验证。

## 依赖与冲突检查

- 已检查：修改日志 001～012、SRS 第 1/14 节、M0/M1 设计、路由/模型发现、`main.py` 中间件/静态挂载、迁移 `0001`～`0004`、Outbox ORM、M1 AuditWriter 消费点、OpenAPI 和全量测试。
- 结论：readiness 必需策略、旧表面保护和 outbox 写入各保留唯一 M0 所有者；M1 contributor/AuditWriter 只通过公开 DTO 协作。M2/M3 无需修改 M0/M1 私有文件，可并行开发领域模型/服务和契约 Mock；正式迁移仍由 M0 基于最新 head 串行集成。
- 已关闭的代码级冲突：生产 DB 可选降级、`system.py` 反向依赖 M1、领域可降低 readiness、旧入口逐路由补丁风险、Outbox 字段/Writer 缺失、AuditWriter 泄露 ORM、OpenAPI 缺 Cookie/CSRF/权限说明。
- 未关闭：真实 PostgreSQL 在线迁移/触发器/并发/中断恢复、M4 `OutboxClaimPort`、旧静态挂载物理移除、反向代理纵深拒绝、Windows Service/备份恢复、M6 浏览器 E2E。因此 M0/M1 未标记“已完成”或“生产可用”。

## 验证与回滚

- 针对性回归：`backend/.venv/Scripts/python.exe -m pytest ... -q` → `55 passed`；在 Cookie/OpenAPI 最终调整前的扩大针对性回归另有 `60 passed`，最终以 55 项重跑结果为准。
- 全量后端：`backend/.venv/Scripts/python.exe -m pytest -q` → `250 passed, 25 skipped`；3 项 M1 PostgreSQL 和 22 项外部手册测试未执行，skip 不计为成功。
- 前端：`npm.cmd run build` 成功；仍有约 1.05 MB 单块 JavaScript 警告，归 M6，不影响本批后端契约检查。
- 迁移：`alembic heads` → `20260814_0005 (head)`；设置占位 PostgreSQL URL 后离线 `upgrade 20260814_0005 --sql` 成功；未执行在线 upgrade/downgrade。
- OpenAPI/装配：15 个操作、14 个唯一路径；SessionCookie、登录匿名面、用户权限/CSRF header 和审计权限扩展检查通过；后端导入成功。
- 独立进程烟测：test 模式 `live=200`、`ready=200`、旧入口 `404`；production 模式在 `APP_DATABASE_REQUIRED=false` 且无数据库时仍为 `live=200`、`ready=503`、旧入口 `404`；测试 Uvicorn 进程均已停止。
- 静态环境：`compileall`、`pip check`、`git diff --check` 通过；换行符转换提示不属于 diff 错误。
- 回滚：应用代码、配置和文档可整体恢复本记录涉及文件；若 `0005` 已在线应用，应先停止 outbox 生产/消费并受控 downgrade 到 `0004`，再部署旧代码。当前未对真实数据库执行迁移。

## 后续开发提示

- 下一批优先完成 D2：PostgreSQL 16 专用 `*_test` 数据库、在线 `upgrade 0005`、bootstrap、触发器、锁/并发、事务回滚和中断恢复。通过前 M2/M3 继续使用公开契约 Mock。
- M2/M3 只从 `app.db` 导入 Outbox 公共端口、从 `app.domains.audit` 导入审计端口；不得导入 `db.models.OutboxEvent`、M1 ORM/Repository，或修改 `0001`～`0005`。
- M2/M4/M5 readiness 只新增各自预留 `readiness.py`，不得修改 `api/v1/system.py`，不得返回 `required`。M4 claim/lease 需另起 M0 公共契约变更。
- 不得重复创建旧 API/静态目录 guard；M2 负责受控下载和物理移除，M7 负责代理纵深防御与生产验收。
