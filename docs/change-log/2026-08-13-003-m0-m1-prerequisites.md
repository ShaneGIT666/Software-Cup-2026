# 完成 M1 所需的 M0 公共前置

- 变更标识：`2026-08-13-003-m0-m1-prerequisites`
- 日期：`2026-08-13`
- 状态：`已完成`
- 所属模块：`M0`；协作模块：`M7`
- 需求追踪：`API-01`、`API-02`、`API-03`、`API-04`、`AUTH-01`、`NFR-SEC-02`、`NFR-MNT-01`、`NFR-MNT-02`、SRS 14.1～14.4
- 关联记录：`2026-08-13-001-change-log`、`2026-08-13-002-auth-entry-exception`

## 改动内容

- 新增 M0 公共前置：可选领域路由装配、受控 CORS/可信来源配置、统一分页响应、共享幂等记录服务、领域 ORM 模型发现和公共错误码登记。
- 这些能力只提供给 M1 及后续领域模块复用；不实现任何用户、角色、会话、审计业务表或登录接口。

## 文件与数据影响

- `backend/app/core/config.py`、`backend/app/core/cors.py`、`backend/app/core/error_codes.py`、`backend/app/core/contracts.py`；新增/修改：公共配置、CORS 策略、错误码和分页契约。
- `backend/app/api/v1/domain_registry.py`、`backend/app/api/v1/router.py`、`backend/app/api/v1/responses.py`、`backend/app/main.py`；新增/修改：可选领域路由注册、分页响应助手和单一 CORS 装配。
- `backend/app/db/models.py`、`backend/app/db/idempotency.py`、`backend/app/db/domain_models.py`、`backend/app/db/__init__.py`、`backend/alembic/env.py`、`backend/alembic/versions/20260813_0002_m0_m1_prerequisites.py`；新增/修改：共享幂等记录、领域模型发现和迁移。
- `.env.example`、`backend/README.md`、`docs/design/m0-public-contract.md`、SRS、测试与日志；新增/修改：使用说明、冻结契约和验证证据。
- 数据库：新增 M0 共享表 `idempotency_records`；API：新增分页响应格式和 M1 路由自动装配约定；DTO：新增 `PageData`、`V1PageResponse`；事件：无；配置：新增 `APP_TRUSTED_ORIGINS`、`APP_IDEMPOTENCY_SECRET`。幂等指纹使用该密钥计算 HMAC-SHA-256，不持久化普通密码摘要。

## 依赖与冲突检查

- 已检查：M0 的 `core/`、`db/`、`api/v1/router.py`、`main.py`、Alembic 环境与初始迁移，SRS 14.1～14.5，M1 设计结论及前两条本地日志。
- 结论：当前不存在分页响应助手、通用幂等记录、领域模型发现或环境化 CORS；新增能力全部位于 M0 所有范围。未修改旧 `/api`、`schemas.py`、JSON 原型领域或 M1 私有目录，不存在重复实现。

## 验证与回滚

- 验证：`backend\\.venv\\Scripts\\python.exe -m compileall -q backend/app backend/alembic tests/test_module0_m1_prerequisites.py` 通过；`pytest tests/test_module0_m1_prerequisites.py tests/test_module0_foundation.py tests/test_configuration_contract.py -q` 为 26 passed；使用不含凭据的临时 PostgreSQL URL 执行 `alembic upgrade head --sql`，确认迁移从 `20260812_0001` 升级到 `20260813_0002` 并创建 `idempotency_records`；CORS 预检确认可信本机来源返回 200/精确 Origin，非可信来源返回 400/无允许 Origin；从仓库根目录和 `backend/` 目录分别导入领域发现入口均通过；完整 `pytest -q` 为 179 passed、22 skipped。
- 回滚：应用可回退代码；数据库执行迁移 `20260813_0002` 的 downgrade 删除 `idempotency_records`。该表尚无 M1 生产写入时可安全删除；上线后须先确认没有待回放的关键请求。

## 后续开发提示

- M1 只能添加 `app.api.v1.auth`、`users`、`audit` 以及 `app.domains.identity.models`、`app.domains.audit.models`；不得编辑 M0 根路由、CORS 中间件、共享表或 Alembic 环境。
- M1 首个迁移暂以 `20260813_0002` 为 `down_revision`，实施前必须重查迁移头；M1 的创建/状态/角色/重置密码写操作必须复用 `IdempotencyService` 与分页/错误契约。
