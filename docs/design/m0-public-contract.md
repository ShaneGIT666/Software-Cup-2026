# M0 公共 HTTP、数据与装配契约

> 状态：已冻结，供 M1～M7 使用。<br>
> 主责模块：M0；首次记录：`2026-08-13-003-m0-m1-prerequisites`。

本文件定义模块化单体的公共接缝。领域模块可以依赖本文件中的接口，但不得直接修改 M0 所有的 `core/`、`db/`、`api/v1/router.py`、`main.py` 或 Alembic 环境文件。

## 1. v1 路由装配

根路径固定为 `/api/v1`。M0 的 `api/v1/domain_registry.py` 按以下相对模块名加载已交付领域路由；模块未交付时不报错，模块内部导入失败时必须直接失败，不能被静默忽略。相对发现可同时兼容从仓库根目录导入 `backend.app` 的测试方式和从 `backend/` 目录导入 `app` 的部署方式。

```text
auth        M1
users       M1
audit       M1
documents   M2
knowledge   M2
devices     M3
workflows   M3
search      M5
rag         M5
operations  M7
```

每个模块必须公开名为 `router` 的 `APIRouter`。M1 只添加 `auth.py`、`users.py`、`audit.py`，禁止改动总路由或 `main.py`。

## 2. 响应、分页与错误码

普通 v1 响应：

```json
{"success": true, "data": {}, "error": null, "meta": {"requestId": "..."}}
```

游标分页 v1 响应必须由 `v1_page()` 生成：

```json
{
  "success": true,
  "data": {"items": []},
  "error": null,
  "meta": {"requestId": "...", "nextCursor": null}
}
```

请求统一使用 `limit`（1～100）与不透明 `cursor`。领域模块不得创造第二种分页字段或在普通响应中附加未登记的 `nextCursor`。

M0 当前冻结以下公共错误码：`HTTP_ERROR`、`VALIDATION_ERROR`、`DEPENDENCY_UNAVAILABLE`、`AUTHENTICATION_REQUIRED`、`FORBIDDEN`、`IDEMPOTENCY_KEY_REQUIRED`、`IDEMPOTENCY_CONFLICT`、`REQUEST_IN_PROGRESS`、`VERSION_CONFLICT`。

M1 身份与审计错误码已登记为：`INVALID_CREDENTIALS`、`ACCOUNT_LOCKED`、`ACCOUNT_DISABLED`、`SESSION_EXPIRED`、`CSRF_INVALID`、`SELF_REVIEW_FORBIDDEN`、`LAST_ADMIN_PROTECTED`、`PASSWORD_POLICY_VIOLATION`、`AUTH_MODE_UNAVAILABLE`。匿名登录对不存在用户、密码错误和已锁定账户统一返回 `INVALID_CREDENTIALS`，不得利用其他错误码泄露账户是否存在；领域模块不得改变这些代码的含义。

## 3. 受控 CORS 与可信来源

公共配置键为 `APP_TRUSTED_ORIGINS`，值为完整 Origin 的逗号分隔列表，例如：

```text
APP_TRUSTED_ORIGINS=https://repair.example.com,https://repair-admin.example.com
```

开发/测试未设置时，M0 仅允许 `http://localhost:5173` 和 `http://127.0.0.1:5173`。生产未设置时以空列表启动，浏览器跨源请求将被拒绝；部署不得将其视为有效生产配置。所有版本共用一个凭据 CORS 策略，允许的方法和请求头为显式列表，禁止 `*`。

Cookie 会话由 M1 实现，但必须复用该来源列表；M1 不得自行添加第二套 CORS 中间件。

## 4. 关键写操作幂等

需要防重复的 v1 写接口必须要求 `Idempotency-Key`。键为 8～128 位 ASCII 字符串，首字符为字母或数字，其余字符限字母、数字、`.`、`_`、`:`、`-`。写接口启用前，部署环境必须从密钥存储提供非空 `APP_IDEMPOTENCY_SECRET`；它仅用于 HMAC 指纹，禁止进入前端、日志或响应。

领域服务在同一个 PostgreSQL 事务中执行以下顺序：

1. 根据 `actor_id`、HTTP 方法、路径、DTO payload 和 `APP_IDEMPOTENCY_SECRET` 调用 `request_fingerprint()`。该函数持久化 HMAC-SHA-256 指纹而非普通哈希，允许密码等敏感写入字段参与重复请求检测而不形成可离线猜测的普通摘要。
2. 使用 `IdempotencyService.begin()` 以稳定的业务 `scope` 预约记录。
3. 若返回 `IdempotencyReplay`，通过 `v1_success(..., status_code=replay.status_code)` 直接返回其中的状态码和 data，不得再次调用领域写服务。
4. 若返回 `IdempotencyReservation`，执行领域写入、审计/outbox，调用 `complete()` 保存成功响应，再提交事务。

同一 `scope + actor_id + key` 但不同请求指纹返回 `IDEMPOTENCY_CONFLICT`；相同请求仍在事务中返回 `REQUEST_IN_PROGRESS`。失败事务回滚预约记录，不缓存错误响应。`idempotency_records` 是 M0 共享表，领域模块不得直接写表或创建副本。

## 5. 领域 ORM 模型与迁移

Alembic 在读取 `Base.metadata` 前调用 M0 的 `load_domain_models()`。已交付模块通过以下固定、相对于应用根包的模型模块名自动登记；未交付模块会被忽略。此发现方式同样兼容 `backend.app` 测试导入和 `app` 部署导入。

```text
domains.identity.models  M1
domains.audit.models     M1
domains.documents.models M2
domains.knowledge.models M2
domains.devices.models   M3
domains.workflows.models M3
domains.rag.models       M5
workers.models           M4
indexing.models          M4
```

每个领域模型继承 `app.db.base.Base`，领域迁移使用独立 revision，并在合并前以最新 M0 迁移头为 `down_revision`。M1 的首个迁移当前应依赖 `20260813_0002`；创建前必须再次检查迁移头。领域模块不得修改 `app.db.models` 或 `alembic/env.py`。
