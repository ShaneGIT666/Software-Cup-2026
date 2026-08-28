# Backend

> 本文件只维护后端开发入口、组件边界和代码证据说明。产品需求与验收语义只以 [SRS](../docs/requirements/software-requirements-spec.md) 为准，当前实现状态、验证证据和未关闭问题只以[现行需求追踪矩阵](../docs/requirements/current-traceability-matrix.md)为准，公共 API/事务契约只以 [M0 公共契约](../docs/design/m0-public-contract.md)为准。

FastAPI 后端正在从演示原型迁移为模块化单体。旧业务接口保留在 `/api`，用于前端与测试兼容；所有新增生产接口使用 `/api/v1`。

## 模块 0：当前代码入口（动态状态仍只查追踪矩阵）

- `core/`：严格 `APP_` 前缀配置、请求 ID、稳定 v1 信封、显式/未捕获 5xx 与验证错误脱敏、普通日志末端白名单，以及具体/封闭公共错误模型。
- `core/`：受控 CORS/浏览器来源及 `ETag` 暴露、可信代理客户端地址、M0-owned 强类型 readiness、旧表面集中保护、敏感身份响应 `no-store`、列表分页信封和公共错误码契约。
- `core/ports/`：无 ORM 副作用的 `OutboxClaimPort`，冻结 claim、lease/heartbeat、success、retry、dead-letter、replay、fencing 和 operation-id 幂等语义；不包含数据库适配器或 Worker。
- `db/`：SQLAlchemy 2、PostgreSQL 连接/就绪状态、独立短事务、脱敏数据库 503、共享元数据根、事务 outbox append 写端口和关键写操作的幂等记录服务。
- `alembic/`：基础、幂等、M1 身份、`0005` outbox 契约及 `0006` 受管服务身份/实例生命周期迁移；领域模型通过 M0 的发现入口登记到 `Base.metadata`。
- `/api/v1/health/live`：进程存活检查。
- `/api/v1/health/ready`：规范生产预检路径，聚合基础配置、数据库和领域 contributor；生产环境即使设置 `APP_DATABASE_REQUIRED=false` 也不能把 PostgreSQL 或关键模块降为可选。

当前 15 个 v1 操作均声明命名的具体 success DTO，用户/审计分页绑定具体 item DTO；通用 default、422、500 与 readiness 503 使用封闭错误模型。返回 `JSONResponse` 的身份/分页 helper 会先用同一个具体 DTO 校验。OpenAPI consumer-contract 测试拒绝空 schema、自由 object 和泛型分页项；M6 后续只从该输入选择一个生成器产生 TypeScript 类型，禁止手写重复接口。

v1 显式/未捕获 5xx 已统一脱敏，只有固定 `DEPENDENCY_UNAVAILABLE/503` 是登记例外；普通 4xx 不透传内部 details，校验错误只返回白名单字段。普通日志在结构化 `extra` 合并后执行集中白名单和失败关闭，异常对象不得先拼接进消息。真实代理、服务管理器、日志采集/保留与 PostgreSQL 行为仍以追踪矩阵中的后续集成门禁为准。

M1 已有本地账户、会话/CSRF、独立账号/来源限流、同一授权快照、事务外 Argon2 校验与签发前复验、用户/角色管理、审计查询、固定受管服务身份、bootstrap 与 activation CLI 代码。`/api/v1/auth/*`、`/users*`、`/roles`、`/audit-events` 已由预留注册表自动装配，OpenAPI 可识别 Session Cookie、CSRF header、匿名登录、权限要求和全部 v1 操作的通用 500 错误结构；`AuditWriter` 只返回不可变结果，不暴露 ORM。记录 019 覆盖范围的实现状态为“单元已验证”。`AuthenticatedActor` 值对象已存在，但 typed actor 到 `AuditWriter` 输入的强类型传播和事件级 metadata 白名单尚未闭环，后续生产写链不得绕过该门槛。`0006` 只完成离线 SQL 生成检查，真实 PostgreSQL 16 在线迁移、触发器、锁/并发和回滚测试仍未执行，前端也未接入。旧 `/api` 与静态挂载仍物理存在，但 `APP_LEGACY_SURFACE_MODE=disabled` 可在应用层统一拒绝；生产环境只允许该模式。

M1 及后续领域模块只能新增自己的 `domains/<domain>/`、`api/v1/<domain>.py`、迁移和测试文件。v1 根路由与 readiness 分别从 M0 的固定注册表加载领域路由/contributor；readiness 预留 identity、documents、knowledge、devices、workflows、workers、indexing 和 rag。模块发现可选不等于生产依赖可选；八类目标模块在生产环境均由 M0 标记为必需。领域 contributor 只返回 M0 `ReadinessDetails` 白名单中的脱敏状态，无权设置 `required` 或扩展白名单值。领域团队不得直接编辑 `main.py`、`api/v1/router.py`、`api/v1/system.py`、`db/models.py` 或 `alembic/env.py`，不得复制旧表面 guard、日志边界或 `OutboxWriter`。M4 只能从 `core/ports` 消费 ClaimPort，禁止从 `db` 包获取该端口或直接访问 outbox ORM。

`APP_TRUSTED_ORIGINS` 使用逗号分隔的完整浏览器 Origin。开发和测试未设置时仅允许本机 Vite 来源；生产必须配置明确 HTTPS 来源，且不接受 `*`、路径、查询参数或凭据。关键 v1 写操作通过 `Idempotency-Key` 使用共享 `idempotency_records`；启用前必须从部署密钥存储设置 `APP_IDEMPOTENCY_SECRET`，请求指纹使用 HMAC，列表接口统一返回 `data.items` 与 `meta.nextCursor`。详见 [M0 公共契约](../docs/design/m0-public-contract.md)。

## Windows 本地运行

在仓库根目录执行：

```powershell
python -m venv backend\.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
powershell -ExecutionPolicy Bypass -File .\scripts\init-config.ps1 -Mode offline
.\dev.bat start
```

`requirements.txt` 是当前开发/测试安装入口，仍含宽版本范围和测试依赖，不是已完成锁定与分层的生产依赖集。生产依赖锁定缺口以现行需求追踪矩阵为准。

M1 本地账户基础依赖已包含 `argon2-cffi`。开发环境配置示例见仓库根目录 `.env.example`；运行 M1 前必须配置 PostgreSQL、执行 Alembic、设置 `APP_AUTH_SECRET` 和 `APP_IDEMPOTENCY_SECRET`，生产环境还必须使用 `Secure` 的 `__Host-` 会话 Cookie。不提供 HTTP 注册或激活入口。

从仓库根目录执行：

```powershell
.\backend\.venv\Scripts\python.exe -m backend.app.domains.identity.bootstrap --username <name> --display-name <name>
# 标准首次引导中，首次管理员登录后先修改临时密码，再执行：
.\backend\.venv\Scripts\python.exe -m backend.app.domains.identity.activation --username <name>
```

从 `backend/` 目录执行时，将模块路径改为 `app.domains.identity.bootstrap` 和 `app.domains.identity.activation`。bootstrap 仅允许在无交互用户且实例状态为 `uninitialized` 时执行，并以受管 bootstrap 服务用户记账；它创建必须改密的首次管理员并把实例推进到 `bootstrapped`。activation 只接受有效、已完成强制改密且持有 `system_admin` 角色的本地账户；数据模型不另行绑定 bootstrap 创建者。成功后实例进入 `active`；生产 readiness 在此前保持不健康。实现状态与数据库证据只查现行需求追踪矩阵。

首次生产部署还必须执行 [SRS 第 10.1 节](../docs/requirements/software-requirements-spec.md)和 [M0/M1 部署就绪方案](../docs/design/m0-m1-deployment-readiness-plan.md)规定的受限 provisioning 阶段。`bootstrapped` 期间 `ready=503` 是预期状态，必须保留只供本机或明确可信管理来源完成登录、CSRF、本人改密和登出的最小身份路径；只有 activation 完成且 `ready=200` 后才开放普通业务流量。部署工件状态只查现行需求追踪矩阵。迁移期旧前端需要 `/api` 时保持 `APP_LEGACY_SURFACE_MODE=enabled`；仅本机直连可选 `loopback`；生产只允许 `disabled`。

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

连接串只放在 `.env`、Windows Service 环境或企业密钥管理系统中，禁止提交到 Git。后续领域模块创建 revision 前必须执行 `alembic heads` 并在修改日志记录实际 head；不得修改已经登记或应用的历史迁移。后续 revision 必须基于执行时重新查得的实际 head 新增，当前 head 与验证证据只查现行需求追踪矩阵及对应日志。

## 验证

```powershell
.\backend\.venv\Scripts\python.exe -m pytest tests\test_module0_error_sanitization.py tests\test_module0_v1_response_contracts.py tests\test_module0_outbox_claim.py -q
```

测试数量、skip、执行环境、提交与迁移 head 不在本文件复制；带日期证据只查修改日志，当前可采信状态与未关闭问题只查现行需求追踪矩阵。
