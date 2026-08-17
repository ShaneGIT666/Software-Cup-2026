# Backend

FastAPI 后端正在从演示原型迁移为模块化单体。旧业务接口保留在 `/api`，用于前端与测试兼容；所有新增生产接口使用 `/api/v1`。

## 模块 0：单元已验证的基础代码

- `core/`：严格 `APP_` 前缀配置、请求 ID、稳定 v1 响应、脱敏 `INTERNAL_ERROR/500` 与公共错误模型。
- `core/`：受控 CORS/浏览器来源及 `ETag` 暴露、可信代理客户端地址、M0-owned 强类型 readiness、旧表面集中保护、敏感身份响应 `no-store`、列表分页信封和公共错误码契约。
- `db/`：SQLAlchemy 2、PostgreSQL 连接/就绪状态、独立短事务、脱敏数据库 503、共享元数据根、事务 outbox 写端口和关键写操作的幂等记录服务。
- `alembic/`：基础、幂等、M1 身份、`0005` outbox 契约及 `0006` 受管服务身份/实例生命周期迁移；领域模型通过 M0 的发现入口登记到 `Base.metadata`。
- `/api/v1/health/live`：进程存活检查。
- `/api/v1/health/ready`：规范生产预检路径，聚合基础配置、数据库和领域 contributor；生产环境即使设置 `APP_DATABASE_REQUIRED=false` 也不能把 PostgreSQL 或关键模块降为可选。

M1 已有本地账户、会话/CSRF、独立账号/来源限流、同一授权快照、事务外 Argon2 校验与签发前复验、用户/角色管理、审计查询、固定受管服务身份、bootstrap 与 activation CLI 代码。`/api/v1/auth/*`、`/users*`、`/roles`、`/audit-events` 已由预留注册表自动装配，OpenAPI 可识别 Session Cookie、CSRF header、匿名登录、权限要求和全部 v1 操作的通用脱敏 500；`AuditWriter` 只返回不可变结果，不暴露 ORM。该范围的实现状态为“单元已验证”。`0006` 只完成离线 SQL 生成检查，真实 PostgreSQL 16 在线迁移、触发器、锁/并发和回滚测试仍未执行，前端也未接入。旧 `/api` 与静态挂载仍物理存在，但 `APP_LEGACY_SURFACE_MODE=disabled` 可在应用层统一拒绝；生产环境只允许该模式。

M1 及后续领域模块只能新增自己的 `domains/<domain>/`、`api/v1/<domain>.py`、迁移和测试文件。v1 根路由与 readiness 分别从 M0 的固定注册表加载领域路由/contributor；readiness 预留 identity、documents、knowledge、devices、workflows、workers、indexing 和 rag。模块发现可选不等于生产依赖可选；八类目标模块在生产环境均由 M0 标记为必需。领域 contributor 只返回 M0 `ReadinessDetails` 白名单中的脱敏状态，无权设置 `required` 或扩展白名单值。领域团队不得直接编辑 `main.py`、`api/v1/router.py`、`api/v1/system.py`、`db/models.py` 或 `alembic/env.py`，不得复制旧表面 guard 或 `OutboxWriter`。

`APP_TRUSTED_ORIGINS` 使用逗号分隔的完整浏览器 Origin。开发和测试未设置时仅允许本机 Vite 来源；生产必须配置明确 HTTPS 来源，且不接受 `*`、路径、查询参数或凭据。关键 v1 写操作通过 `Idempotency-Key` 使用共享 `idempotency_records`；启用前必须从部署密钥存储设置 `APP_IDEMPOTENCY_SECRET`，请求指纹使用 HMAC，列表接口统一返回 `data.items` 与 `meta.nextCursor`。详见 [M0 公共契约](../docs/design/m0-public-contract.md)。

## Windows 本地运行

在仓库根目录执行：

```powershell
python -m venv backend\.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
powershell -ExecutionPolicy Bypass -File .\scripts\init-config.ps1 -Mode offline
.\dev.bat start
```

M1 本地账户基础依赖已包含 `argon2-cffi`。开发环境配置示例见仓库根目录 `.env.example`；运行 M1 前必须配置 PostgreSQL、执行 Alembic、设置 `APP_AUTH_SECRET` 和 `APP_IDEMPOTENCY_SECRET`，生产环境还必须使用 `Secure` 的 `__Host-` 会话 Cookie。不提供 HTTP 注册或激活入口。

从仓库根目录执行：

```powershell
.\backend\.venv\Scripts\python.exe -m backend.app.domains.identity.bootstrap --username <name> --display-name <name>
# 首次管理员登录后必须先修改临时密码，再执行：
.\backend\.venv\Scripts\python.exe -m backend.app.domains.identity.activation --username <name>
```

从 `backend/` 目录执行时，将模块路径改为 `app.domains.identity.bootstrap` 和 `app.domains.identity.activation`。bootstrap 仅允许在无交互用户且实例状态为 `uninitialized` 时执行，并以受管 bootstrap 服务用户记账；它创建必须改密的首次管理员并把实例推进到 `bootstrapped`。activation 需要该管理员重新输入已修改的密码并持有 `system_admin` 角色，成功后把实例推进到 `active`；生产 readiness 在此前保持不健康。上述边界已通过单元测试，但尚未在真实 PostgreSQL 上验证，因此不能作为生产可用或集成完成证据。迁移期旧前端需要 `/api` 时保持 `APP_LEGACY_SURFACE_MODE=enabled`；仅本机直连可选 `loopback`；生产只允许 `disabled`。

健康检查：

```text
GET http://127.0.0.1:8000/api/health
GET http://127.0.0.1:8000/api/v1/health/live
GET http://127.0.0.1:8000/api/v1/health/ready
```

## PostgreSQL 初始化

1. 安装 PostgreSQL 16，并创建应用数据库与最小权限的应用账户。
2. 在本机 `.env` 设置连接串，示例：

   ```text
   APP_DATABASE_URL=postgresql+psycopg://repair_app:change-me@127.0.0.1:5432/repair_knowledge
   APP_DATABASE_REQUIRED=true
   ```

3. 从 `backend/` 目录执行迁移：

   ```powershell
   cd backend
   $env:APP_DATABASE_URL='postgresql+psycopg://repair_app:change-me@127.0.0.1:5432/repair_knowledge'
   .\.venv\Scripts\alembic.exe upgrade head
   ```

连接串只放在 `.env`、Windows Service 环境或企业密钥管理系统中，禁止提交到 Git。后续领域模块创建 revision 前必须执行 `alembic heads` 并在修改日志记录实际 head；不得修改已经登记或应用的历史迁移。记录 019 工作区的当前单一 head 为 `20260817_0006`，且仅完成离线 SQL 生成检查；后续 revision 必须基于执行时的实际 head 新增。

## 验证

```powershell
.\backend\.venv\Scripts\python.exe -m pytest tests\test_module0_foundation.py tests\test_configuration_contract.py -q
```

2026-08-17、提交 `7016029` 的阶段 1 工作区全量回归为 `259 passed, 25 skipped`；该结果是记录 017 的历史证据。记录 019 的 D1.2 工作区全量回归为 `271 passed, 25 skipped`，其中 3 项真实 PostgreSQL 和 22 项外部手册测试跳过；`20260817_0006` 只完成离线正向/反向 SQL 生成检查。当前未配置 PostgreSQL，因此对应范围的实现状态仍为“单元已验证”，不得作为真实数据库或生产集成证据。
