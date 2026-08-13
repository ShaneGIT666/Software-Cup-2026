# Backend

FastAPI 后端正在从演示原型迁移为模块化单体。旧业务接口保留在 `/api`，用于前端与测试兼容；所有新增生产接口使用 `/api/v1`。

## 模块 0：已提供的基础能力

- `core/`：`APP_` 前缀配置、请求 ID、稳定 v1 响应与错误模型。
- `core/`：受控 CORS/浏览器来源、可信代理客户端地址、敏感身份响应 `no-store`、列表分页信封和公共错误码契约。
- `db/`：SQLAlchemy 2、PostgreSQL 连接/就绪状态、独立短事务、脱敏数据库 503、共享元数据根和关键写操作的幂等记录服务。
- `alembic/`：基础迁移、幂等记录和 M1 身份迁移；领域模型通过 M0 的发现入口登记到 `Base.metadata`。
- `/api/v1/health/live`：进程存活检查。
- `/api/v1/health/ready`：数据库就绪检查。生产环境设置 `APP_DATABASE_REQUIRED=true` 后，数据库未配置或不可连接时返回 `503`。

M1 已有本地账户、会话/CSRF、独立账号/来源限流、同一授权快照、事务外 Argon2 校验与签发前复验、用户/角色管理、审计查询和 bootstrap CLI 代码。`/api/v1/auth/*`、`/users*`、`/roles`、`/audit-events` 已由预留注册表自动装配，Cookie、可信来源、权限、ETag/`If-Match`、幂等和 `no-store` 已有进程内 API 测试。真实 PostgreSQL 16 在线迁移、触发器、锁/并发和回滚测试仍未执行，前端也未接入；知识、文件、审核、Worker 和检索领域仍未迁移，旧 `/api` 与静态目录依旧绕过 M1。当前状态是“代码已搭建、进程内已验证，功能未完成”，不能据此宣称生产认证、授权或用户管理已上线。

M1 及后续领域模块只能新增自己的 `domains/<domain>/`、`api/v1/<domain>.py`、迁移和测试文件。v1 根路由会从 M0 的可选领域注册表加载 `auth`、`users`、`audit` 等模块；领域团队不得直接编辑 `main.py`、`api/v1/router.py`、`db/models.py` 或 `alembic/env.py`。

`APP_TRUSTED_ORIGINS` 使用逗号分隔的完整浏览器 Origin。开发和测试未设置时仅允许本机 Vite 来源；生产必须配置明确 HTTPS 来源，且不接受 `*`、路径、查询参数或凭据。关键 v1 写操作通过 `Idempotency-Key` 使用共享 `idempotency_records`；启用前必须从部署密钥存储设置 `APP_IDEMPOTENCY_SECRET`，请求指纹使用 HMAC，列表接口统一返回 `data.items` 与 `meta.nextCursor`。详见 [M0 公共契约](../docs/design/m0-public-contract.md)。

## Windows 本地运行

在仓库根目录执行：

```powershell
python -m venv backend\.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
powershell -ExecutionPolicy Bypass -File .\scripts\init-config.ps1 -Mode offline
.\dev.bat start
```

M1 本地账户基础依赖已包含 `argon2-cffi`。开发环境配置示例见仓库根目录 `.env.example`；运行 M1 前必须配置 PostgreSQL、执行 Alembic、设置 `APP_AUTH_SECRET` 和 `APP_IDEMPOTENCY_SECRET`，生产环境还必须使用 `Secure` 的 `__Host-` 会话 Cookie。首次管理员使用 `python -m app.domains.identity.bootstrap --username <name> --display-name <name>` 在空用户库中创建，不提供 HTTP 注册入口。真实数据库验收完成前不得将 M1 标记为生产可用或完成。

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

连接串只放在 `.env`、Windows Service 环境或企业密钥管理系统中，禁止提交到 Git。迁移先创建基础元数据和 outbox；后续领域模块会各自增加用户、文档、知识和流程表。

## 验证

```powershell
.\backend\.venv\Scripts\python.exe -m pytest tests\test_module0_foundation.py tests\test_configuration_contract.py -q
```
