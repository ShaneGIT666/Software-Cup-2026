# M0 公共 HTTP、数据与装配契约

> 状态对象：M0 公共契约代码；实现状态：`单元已验证`。真实 PostgreSQL、代理和生产部署尚未验收，不表示 M0 或 M1 已完成。<br>
> 主责模块：M0；首次记录：`2026-08-13-003-m0-m1-prerequisites`；当前相关记录：`2026-08-17-016-stage0-contract-alignment`、`2026-08-17-017-m0-foundation-hardening`。

本文件定义模块化单体的公共接缝。领域模块可以依赖本文件中的接口，但不得直接修改 M0 所有的 `core/`、`db/`、`api/v1/router.py`、`main.py` 或 Alembic 环境文件。

页首状态是 2026-08-17 契约复核快照；后续功能状态只更新现行需求追踪矩阵和修改日志。只有公共端口、信封、错误码、readiness 白名单或其他契约语义变化时才修改本文。

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

M0 提供 `encode_cursor()`/`decode_cursor()`。游标使用 `v1.` 版本前缀和 URL-safe Base64 JSON 信封，仅用于隐藏 keyset 分页位置，不是签名、授权或过滤条件；Repository 每页都必须重新应用当前用户、状态和数据范围过滤。损坏、超长、未知版本或非对象 payload 返回 `INVALID_CURSOR`。领域模块不得解析编码内部或复制 codec。

并发修改统一使用强 ETag：响应 ETag 和请求 `If-Match` 均为 `"v<正整数>"`，例如 `"v3"`。M0 提供 `etag_for_version()`、`parse_if_match()` 和 `require_matching_version()`；缺少条件返回 `PRECONDITION_REQUIRED`/428，格式非法返回 `INVALID_PRECONDITION`/400，版本过期返回 `VERSION_CONFLICT`/412。不接受裸整数、弱 ETag、`*` 或多 ETag 列表。

M0 当前冻结以下公共错误码：`HTTP_ERROR`、`VALIDATION_ERROR`、`INTERNAL_ERROR`、`DEPENDENCY_UNAVAILABLE`、`AUTHENTICATION_REQUIRED`、`FORBIDDEN`、`IDEMPOTENCY_KEY_REQUIRED`、`IDEMPOTENCY_CONFLICT`、`REQUEST_IN_PROGRESS`、`VERSION_CONFLICT`、`INVALID_CURSOR`、`PRECONDITION_REQUIRED`、`INVALID_PRECONDITION`、`TRUSTED_ORIGIN_REQUIRED`。未捕获异常的 v1 响应只返回 `INTERNAL_ERROR/500`、固定脱敏消息和 request ID；原始异常仅记录到服务端日志，不得进入响应体。`api_v1_router` 已为全部 v1 操作统一声明 `500/V1Response`，运行时脱敏和逐操作 OpenAPI 契约测试均已通过；真实客户端和代理行为仍待 M6/M7 集成验证。

M1 身份与审计错误码已登记为：`INVALID_CREDENTIALS`、`ACCOUNT_LOCKED`、`ACCOUNT_DISABLED`、`SESSION_EXPIRED`、`CSRF_INVALID`、`SELF_REVIEW_FORBIDDEN`、`LAST_ADMIN_PROTECTED`、`PASSWORD_POLICY_VIOLATION`、`AUTH_MODE_UNAVAILABLE`。匿名登录对不存在用户、密码错误和已锁定账户统一返回 `INVALID_CREDENTIALS`，不得利用其他错误码泄露账户是否存在；领域模块不得改变这些代码的含义。

## 3. 受控 CORS 与可信来源

公共配置键为 `APP_TRUSTED_ORIGINS`，值为完整 Origin 的逗号分隔列表，例如：

```text
APP_TRUSTED_ORIGINS=https://repair.example.com,https://repair-admin.example.com
```

开发/测试未设置时，M0 仅允许 `http://localhost:5173` 和 `http://127.0.0.1:5173`。生产未设置时以空列表启动，浏览器跨源请求将被拒绝；部署不得将其视为有效生产配置。所有版本共用一个凭据 CORS 策略，允许的方法和请求头为显式列表，禁止 `*`；响应必须显式暴露 `X-Request-ID` 和 `ETag`，但真实跨域浏览器验收仍是“集成已验证”的独立证据。

Cookie 会话由 M1 实现，但必须复用该来源列表；M1 不得自行添加第二套 CORS 中间件。

M0 另提供 `require_trusted_browser_origin()`，供所有建立或使用 Cookie 会话的浏览器写端点执行服务端来源校验。它优先读取 `Origin`，仅在缺失时使用 `Referer` 的 origin 部分，并按规范化 scheme/host/effective-port 与 `APP_TRUSTED_ORIGINS` 精确比较；缺失或不可信返回 `TRUSTED_ORIGIN_REQUIRED`。该函数不信任代理头、不建立身份，也不替代已登录请求的 CSRF 校验。

## 4. 关键写操作幂等

需要防重复的 v1 写接口必须要求 `Idempotency-Key`。键为 8～128 位 ASCII 字符串，首字符为字母或数字，其余字符限字母、数字、`.`、`_`、`:`、`-`。写接口启用前，部署环境必须从密钥存储提供非空 `APP_IDEMPOTENCY_SECRET`；它仅用于 HMAC 指纹，禁止进入前端、日志或响应。

领域服务在同一个 PostgreSQL 事务中执行以下顺序：

1. 根据 `actor_id`、HTTP 方法、路径、DTO payload 和 `APP_IDEMPOTENCY_SECRET` 调用 `request_fingerprint()`。该函数持久化 HMAC-SHA-256 指纹而非普通哈希，允许密码等敏感写入字段参与重复请求检测而不形成可离线猜测的普通摘要。
2. 使用 `IdempotencyService.begin()` 以稳定的业务 `scope` 预约记录。
3. 若返回 `IdempotencyReplay`，通过 `v1_success(..., status_code=replay.status_code)` 直接返回其中的状态码和 data，不得再次调用领域写服务。
4. 若返回 `IdempotencyReservation`，执行领域写入、审计和必要幂等记录；只有[事件目录](event-catalog.md)已登记消费者的操作才追加 outbox。随后调用 `complete()` 保存成功响应并提交事务。

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

每个领域模型继承 `app.db.base.Base`，领域迁移使用独立 revision，并在合并前以执行时最新迁移头为 `down_revision`。M1 的 `20260813_0003/0004` 后，M0 以 `20260814_0005` 补齐共享 outbox 事件字段；D1.2 又以 M1 后继迁移 `20260817_0006` 增加受管服务用户、实例生命周期和审计主体约束。未来步骤必须先执行 `alembic heads`，使用 `upgrade head` 并记录实际 revision，不得把任一日期化 head 永久当作目标。领域模块不得修改 `app.db.models`、任何已经登记或应用的历史 revision 或 `alembic/env.py`。

## 6. M1 公共协作端口及实现记录

本节端口已经由 M0 搭建，M1 路由也已按契约注册并通过进程内测试。真实 PostgreSQL、反向代理和部署配置尚未验收，因此这些路由仍不是生产可用结论。

### 6.1 独立数据库短事务

M0 已在 `db/session.py` 提供公开的 `new_session()` 上下文端口，负责 commit/rollback/close；M1 的身份快照、活动续期和命令用例通过该端口拥有独立短事务。测试已覆盖提交、异常回滚和关闭；真实连接池故障与 PostgreSQL 事务行为仍待在线验证。领域 Repository 和请求业务 Session 仍不得自行结束事务，M1 不得读取 `_session_factory`、重建 Engine 或复制数据库配置。

### 6.2 数据库依赖错误映射

M0 已将数据库未配置、初始化失败、连接失败或连接池不可用映射为不含连接串和驱动堆栈的 `DEPENDENCY_UNAVAILABLE/503`，健康检查只报告脱敏状态。进程内异常映射测试已通过；真实 PostgreSQL 中断/恢复场景仍待 M7 验收。领域路由不得各自捕获并形成不同错误码。

### 6.3 可信客户端地址

M0 已新增 `core/client_address.py` 的 `ClientAddressResolver` 和 `APP_TRUSTED_PROXY_CIDRS`。它默认使用 `request.client.host`，只有直接上游位于显式可信代理 CIDR 时才从右向左剥离可信代理链；非法、过长或未受信代理提供的头不能覆盖直连地址。M1 登录限流和审计只消费解析结果，不直接读取 `X-Forwarded-For`。代理欺骗进程内测试已通过；实际 IIS/Caddy/Nginx 拓扑仍由 M7 验收。

## 7. 部署就绪与旧兼容表面

### 7.1 Readiness contributor

`core/readiness.py` 由 M0 统一聚合数据库、基础配置和领域检查。领域 contributor 只能返回 `ReadinessProbe(healthy, reason, details)`，其中 `details` 必须是 M0 定义的 `ReadinessDetails`；任意映射、连接串、URL、文件路径、密钥、异常文本或堆栈不得返回。`reason` 只允许短的脱敏摘要；M0 聚合器对可疑文本统一替换为通用描述。

当前精确白名单如下：

| Python 字段 | JSON 字段 | 允许值/类型 | 当前所有者 |
| --- | --- | --- | --- |
| `configured` | `configured` | `bool`；返回 `dialect` 时必须同时提供 | M0 数据库检查 |
| `dialect` | `dialect` | `postgresql`、`postgresql+psycopg`、`postgresql+psycopg2` | M0 数据库检查 |
| `mode` | `mode` | `local`、`oidc` | M1 identity |
| `latency_ms` | `latencyMs` | 非负整数 | 经 M0 评审的依赖延迟 |
| `violations` | `violations` | `idempotency_secret`、`trusted_https_origins`、`legacy_surface` | M0 foundation |

M2～M5 不得把模块私有状态塞入现有字段。新增字段或允许值必须先修改 M0 代码、本文、OpenAPI/消费者测试和对应修改日志；不得恢复任意 `Mapping`。

领域 contributor 不得声明自身是否为必需依赖；`required` 策略只由 M0 的 `ReadinessRegistration` 决定，避免领域模块通过返回 `required=false` 降低生产门槛。预留登记表完整覆盖 `identity`、`documents`、`knowledge`、`devices`、`workflows`、`workers`、`indexing` 和 `rag`。导入发现可以在开发环境跳过未交付模块，但八类目标模块在生产环境均为必需依赖；“可选发现”不得写成“生产可选”。

后续模块只新增预留位置中的 `readiness.py`，不得修改 `api/v1/system.py`。未交付模块在开发环境安全跳过；已存在模块的内部导入错误必须暴露。生产环境中数据库及八类目标模块不可被配置降为可选，任一必需检查失败时规范路径 `/api/v1/health/ready` 返回脱敏的 `DEPENDENCY_UNAVAILABLE/503`。`live` 仅表示进程存活；`ready` 是 API、Windows Service、Linux 适配层和代理共用的唯一生产预检契约。

`APP_ENV` 只允许 `development|test|production`，未知值必须在设置装配时失败关闭，不得以开发默认继续启动。

### 7.2 旧表面保护

`APP_LEGACY_SURFACE_MODE` 取值为 `enabled|loopback|disabled`。开发默认 `enabled`；生产默认且只允许 `disabled`。M0 中间件统一拦截旧 `/api`（不含 `/api/v1`）、`/uploads` 和 `/knowledge`，因此 M1～M3 不得逐路由复制阻断逻辑。`loopback` 只判断直连客户端地址，不信任转发头。旧静态挂载尚未从代码删除，M2 受控下载迁移后仍需移除挂载；当前只证明生产配置可在应用层拒绝访问。

## 8. 事务 Outbox 公共写端口

M0 公开以下不可变契约：

```python
OutboxEventInput(
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    version_id: str,
    request_id: str,
    occurred_at: datetime,
    payload: Mapping[str, Any],
)
OutboxWriter.append(session, event) -> OutboxAppendResult(event_id: str)
```

`OutboxWriter` 只向调用方拥有的事务追加记录，不 commit/rollback，也不返回 ORM 实体。迁移 `20260814_0005` 为共享表增加 `version_id`、`request_id`、`occurred_at`；历史原型行使用明确的 `legacy:<id>` 回填，不能伪装成真实业务版本或请求。M2/M3/M5 只有在事件目录登记了消费者时才从 `app.db` 公共导出导入写端口；M4 的 claim/lease 端口尚未搭建，不得通过导入 `db.models.OutboxEvent` 提前实现消费者。

outbox 范围按以下矩阵执行：

| 写操作类型 | 同事务要求 | outbox 要求 |
| --- | --- | --- |
| M2/M3/M5 可对外观察且已在事件目录登记消费者的关键领域状态变更 | 业务状态 + 已认证 `CurrentUser`；异步延续使用受管服务用户并保留发起身份 + 审计 + 必要幂等记录 | 必须追加版本化事件 |
| M5 查询、回答或反馈等当前未登记消费者的状态变更 | 已认证 `CurrentUser`；异步延续使用受管服务用户并保留发起身份 + 审计/调用记录 + 必要幂等记录 | 当前不发布业务 outbox |
| M1 用户、角色、密码等安全状态变更 | 安全状态 + 已认证 `CurrentUser` + 审计 + 必要幂等记录 | 仅在事件目录已冻结消费者时追加；当前无此契约 |
| 登录成功后的会话签发/续期/注销 | 已认证用户 + 独立短事务 + 安全审计 | 不发布业务 outbox |
| 登录失败、限流等认证子系统记账 | 认证子系统受管服务用户 + 独立短事务 + 安全审计 | 不发布业务 outbox；主体代码和迁移已单元验证，真实 PostgreSQL 待 D2 |
| 首次 bootstrap | 仅限 `uninitialized`；bootstrap 受管服务用户 + 生命周期锁 + 审计 + 独立 CLI 操作标识 | 不属于生产运行写入；激活后拒绝再次执行，真实行锁/迁移待 D2 |
| Worker heartbeat/lease/retry 等运行维护 | 受管服务用户 + 任务上下文 + 运行日志/指标 | 不发布业务 outbox；事件目录登记的显式领域结果事件除外 |

新增事件前必须在[事件目录](event-catalog.md)冻结事件名、版本、生产者、消费者、payload 白名单、幂等与回滚语义，并更新生产者/消费者契约及事务测试。只有需求语义或 M0 公共端口变化时才修改 SRS 或本文；新增具体事件不再要求重复改写多个说明文档。
