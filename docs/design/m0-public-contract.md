# M0 公共 HTTP、数据与装配契约

> 文档性质：M0 稳定公共契约；主责模块：M0。<br>
> 当前实现状态、验证证据和未关闭问题只在[现行需求追踪矩阵](../requirements/current-traceability-matrix.md)维护。

本文件定义模块化单体的公共接缝。领域模块可以依赖本文件中的接口，但不得直接修改 M0 所有的 `core/`、`db/`、`api/v1/router.py`、`main.py` 或 Alembic 环境文件。

只有公共端口、信封、错误码、readiness 白名单或其他稳定契约语义变化时才修改本文；测试数量、迁移 head、阶段状态和最新日志清单不得复制到本文。

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
operations  M4
```

每个模块必须公开名为 `router` 的 `APIRouter`。M1 只添加 `auth.py`、`users.py`、`audit.py`，禁止改动总路由或 `main.py`。

## 2. 响应、分页与错误码

普通 v1 响应：

```json
{"success": true, "data": {}, "error": null, "meta": {"requestId": "..."}}
```

上述 JSON 只说明公共信封形状，不是可供所有操作复用的最终模型。每个 v1 操作必须声明具体的成功 `data` DTO；列表操作还必须声明具体的 item DTO；每个允许非空错误 details 的错误码必须声明封闭 schema。公共 OpenAPI、生成客户端或正式领域响应中不得以 `Any`、任意映射或未约束对象代替具体模型。

M0 提供必须绑定类型参数的 `V1Response[DataT]` 与 `V1PageResponse[ItemT]`，但未绑定的泛型只允许在内部 helper 中使用，不得直接作为路由 `response_model`。当前及后续每个 v1 路由都必须使用命名的具体响应模型；即使路由需要返回 `JSONResponse` 以设置 Cookie、ETag 或缓存头，也必须在序列化前用同一个具体模型校验。所有 v1 DTO 禁止未声明字段，OpenAPI consumer-contract 测试必须递归拒绝空 schema、自由 object 和泛型分页项。

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

M0 冻结以下公共错误码：`HTTP_ERROR`、`VALIDATION_ERROR`、`INTERNAL_ERROR`、`DEPENDENCY_UNAVAILABLE`、`AUTHENTICATION_REQUIRED`、`FORBIDDEN`、`IDEMPOTENCY_KEY_REQUIRED`、`IDEMPOTENCY_CONFLICT`、`REQUEST_IN_PROGRESS`、`VERSION_CONFLICT`、`INVALID_CURSOR`、`PRECONDITION_REQUIRED`、`INVALID_PRECONDITION`、`TRUSTED_ORIGIN_REQUIRED`。

所有未捕获异常、显式 `HTTPException` 5xx 和显式 `AppError` 5xx 都必须经过同一外部脱敏边界。除经公共契约明确登记、使用固定消息与字段白名单的 `DEPENDENCY_UNAVAILABLE/503` 外，v1 5xx 统一返回 `INTERNAL_ERROR/500`、固定用户消息、`details=null` 和 request ID；异常文本、堆栈、连接串、路径及任意内部 details 不得进入响应。所有 v1 操作必须在 OpenAPI 中声明统一 500 信封，但该声明不能替代各显式 5xx 分支的运行时测试。

错误模型按以下边界冻结：

- 未单列的 4xx/业务错误使用 `V1ErrorResponse`，`details` 必须为 `null`；`AppError.details` 是内部属性，不得由公共 handler 透传。
- 框架请求校验错误使用 `ValidationErrorResponse`，固定消息为“请求参数校验失败”；每项只允许有界 `loc`、固定公共 `msg`、有界 `type` 和可选 `ctx.limit_value`，不得返回请求 `input/body`、原 validator 消息或任意上下文。
- readiness 的 `DEPENDENCY_UNAVAILABLE/503` 使用 `ReadinessErrorResponse` 和本文第 7.1 节白名单；其他显式 503 不得自行携带 details。
- 内部错误使用 `InternalErrorResponse`，固定 `INTERNAL_ERROR/500`、固定消息和空 details。

普通结构化日志只允许 `event`、`request_id`、`component`、`operation`、`outcome`、`code`、`method`、`status_code`、`duration_ms`、`count`、`attempt`、`consumer_id`、`event_id`、`diagnostic_id` 这些安全标量扩展字段；其他 `extra` 字段在合并后按拒绝策略脱敏。不得直接写入未经清洗的异常文本、请求体/载荷/headers、Cookie、令牌、密码、连接串或绝对路径；敏感键赋值整条普通日志失败关闭。异常对象必须作为 logger 参数交给集中边界，禁止先用 f-string 或 `str(exc)` 拼入普通消息。确需保留诊断堆栈时，必须进入与普通日志分离、受访问控制且有保留策略的诊断通道。响应脱敏和日志脱敏是两个独立验收对象；当前合规状态只见追踪矩阵。

M1 身份与审计错误码已登记为：`INVALID_CREDENTIALS`、`ACCOUNT_LOCKED`、`ACCOUNT_DISABLED`、`SESSION_EXPIRED`、`CSRF_INVALID`、`SELF_REVIEW_FORBIDDEN`、`LAST_ADMIN_PROTECTED`、`PASSWORD_POLICY_VIOLATION`、`AUTH_MODE_UNAVAILABLE`。匿名登录对不存在用户、密码错误和已锁定账户统一返回 `INVALID_CREDENTIALS`，不得利用其他错误码泄露账户是否存在；领域模块不得改变这些代码的含义。

## 3. 受控 CORS 与可信来源

公共配置键为 `APP_TRUSTED_ORIGINS`，值为完整 Origin 的逗号分隔列表，例如：

```text
APP_TRUSTED_ORIGINS=https://repair.example.com,https://repair-admin.example.com
```

开发/测试未设置时，M0 仅允许 `http://localhost:5173` 和 `http://127.0.0.1:5173`。生产未设置时以空列表启动，浏览器跨源请求将被拒绝；部署不得将其视为有效生产配置。所有版本共用一个凭据 CORS 策略，允许的方法和请求头为显式列表，禁止 `*`；响应必须显式暴露 `X-Request-ID` 和 `ETag`。目标代理上的真实跨域浏览器行为必须独立验收。

Cookie 会话由 M1 实现，但必须复用该来源列表；M1 不得自行添加第二套 CORS 中间件。

M0 另提供 `require_trusted_browser_origin()`，供所有建立或使用 Cookie 会话的浏览器写端点执行服务端来源校验。它优先读取 `Origin`，仅在缺失时使用 `Referer` 的 origin 部分，并按规范化 scheme/host/effective-port 与 `APP_TRUSTED_ORIGINS` 精确比较；缺失或不可信返回 `TRUSTED_ORIGIN_REQUIRED`。该函数不信任代理头、不建立身份，也不替代已登录请求的 CSRF 校验。

## 4. 关键写操作幂等

需要防重复的 v1 写接口必须要求 `Idempotency-Key`。键为 8～128 位 ASCII 字符串，首字符为字母或数字，其余字符限字母、数字、`.`、`_`、`:`、`-`。写接口启用前，部署环境必须从密钥存储提供非空 `APP_IDEMPOTENCY_SECRET`；它仅用于 HMAC 指纹，禁止进入前端、日志或响应。

领域服务在同一个 PostgreSQL 事务中执行以下顺序：

1. 根据 `actor_id`、HTTP 方法、路径、DTO payload 和 `APP_IDEMPOTENCY_SECRET` 调用 `request_fingerprint()`。该函数持久化 HMAC-SHA-256 指纹而非普通哈希，允许密码等敏感写入字段参与重复请求检测而不形成可离线猜测的普通摘要。
2. 使用 `IdempotencyService.begin()` 以稳定的业务 `scope` 预约记录。
3. 若返回 `IdempotencyReplay`，通过 `v1_success(..., status_code=replay.status_code)` 直接返回其中的状态码和 data，不得再次调用领域写服务。
4. 若返回 `IdempotencyReservation`，执行领域写入、审计和必要幂等记录；只有满足[事件目录](event-catalog.md)“生产启用门禁”的操作才在启用环境追加 outbox。随后调用 `complete()` 保存成功响应并提交事务。

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

每个领域模型继承 `app.db.base.Base`，领域迁移使用独立 revision，并在合并前以执行时最新迁移头为 `down_revision`。所有数据库结构变化必须附新迁移和回滚说明；下一次修改前先执行 `alembic heads` 并读取相关模块最近记录，不得把文档中的日期化 revision 永久当作目标。领域模块不得修改 `app.db.models`、任何已经登记或应用的历史 revision 或 `alembic/env.py`。当前 head 与在线验证状态只见追踪矩阵。

## 6. M1 公共协作端口

本节只定义 M0 提供给 M1 及后续模块的稳定协作边界，不陈述实现或验证状态。

### 6.1 独立数据库短事务

`db/session.py` 的公开 `new_session()` 上下文端口负责 commit/rollback/close；M1 的身份快照、活动续期和命令用例通过该端口拥有独立短事务。领域 Repository 和请求业务 Session 不得自行结束事务，M1 不得读取 `_session_factory`、重建 Engine 或复制数据库配置。具体测试和在线数据库证据只见追踪矩阵。

### 6.2 数据库依赖错误映射

数据库未配置、初始化失败、连接失败或连接池不可用必须映射为不含连接串和驱动堆栈的 `DEPENDENCY_UNAVAILABLE/503`，健康检查只报告脱敏状态。领域路由不得各自捕获并形成不同错误码；测试和真实中断/恢复证据只见追踪矩阵。

### 6.3 可信客户端地址

`core/client_address.py` 的 `ClientAddressResolver` 使用 `APP_TRUSTED_PROXY_CIDRS`：默认采用 `request.client.host`，只有直接上游位于显式可信代理 CIDR 时才从右向左剥离可信代理链；非法、过长或未受信代理提供的头不能覆盖直连地址。M1 登录限流和审计只消费解析结果，不直接读取 `X-Forwarded-For`。具体测试和代理拓扑证据只见追踪矩阵。

## 7. 部署就绪与旧兼容表面

### 7.1 Readiness contributor

`core/readiness.py` 由 M0 统一聚合数据库、基础配置和领域检查。领域 contributor 只能返回 `ReadinessProbe(healthy, reason, details)`，其中 `details` 必须是 M0 定义的 `ReadinessDetails`；任意映射、连接串、URL、文件路径、密钥、异常文本或堆栈不得返回。`reason` 只允许短的脱敏摘要；M0 聚合器对可疑文本统一替换为通用描述。

冻结的精确白名单如下：

| Python 字段 | JSON 字段 | 允许值/类型 | 所有者 |
| --- | --- | --- | --- |
| `configured` | `configured` | `bool`；返回 `dialect` 时必须同时提供 | M0 数据库检查 |
| `dialect` | `dialect` | `postgresql`、`postgresql+psycopg`、`postgresql+psycopg2` | M0 数据库检查 |
| `mode` | `mode` | `local`、`oidc` | M1 identity |
| `latency_ms` | `latencyMs` | 非负整数 | 经 M0 评审的依赖延迟 |
| `violations` | `violations` | `idempotency_secret`、`trusted_https_origins`、`legacy_surface` | M0 foundation |

M2～M5 不得把模块私有状态塞入现有字段。新增字段或允许值必须先修改 M0 代码、本文、OpenAPI/消费者测试和对应修改日志；不得恢复任意 `Mapping`。

领域 contributor 不得声明自身是否为必需依赖；`required` 策略只由 M0 的 `ReadinessRegistration` 决定，避免领域模块通过返回 `required=false` 降低生产门槛。预留登记表完整覆盖 `identity`、`documents`、`knowledge`、`devices`、`workflows`、`workers`、`indexing` 和 `rag`。导入发现可以在开发环境跳过未交付模块，但八类目标模块在生产环境均为必需依赖；“可选发现”不得写成“生产可选”。

后续模块只新增预留位置中的 `readiness.py`，不得修改 `api/v1/system.py`。未交付模块在开发环境安全跳过；已存在模块的内部导入错误必须暴露。生产环境中数据库及八类目标模块不可被配置降为可选，任一必需检查失败时规范路径 `/api/v1/health/ready` 返回脱敏的 `DEPENDENCY_UNAVAILABLE/503`。`live` 仅表示进程存活；`ready` 是 API、Windows Service、Linux 适配层和代理共用的唯一正常生产流量预检契约。

实例处于 `bootstrapped` 时，`live` 可以成功而 `ready` 必须失败。此阶段仅允许 [SRS 10.1](../requirements/software-requirements-spec.md#101-windows-默认部署)定义的本机或显式可信管理来源访问受限设置页，以及登录、本人信息、CSRF、改密和登出的最小认证接口；其他业务接口和旧兼容表面继续阻断。任一符合 M1 激活条件的本地 `system_admin` 完成受控 CLI 激活后，仍须达到 `active` 且全部必需 readiness 检查通过，代理才可放行正常业务流量。部署脚本不得复制或放宽这套 provisioning 规则。

`APP_ENV` 只允许 `development|test|production`，未知值必须在设置装配时失败关闭，不得以开发默认继续启动。

### 7.2 旧表面保护

`APP_LEGACY_SURFACE_MODE` 取值为 `enabled|loopback|disabled`。开发默认 `enabled`；生产默认且只允许 `disabled`。M0 中间件统一拦截旧 `/api`（不含 `/api/v1`）、`/uploads` 和 `/knowledge`，因此 M1～M3 不得逐路由复制阻断逻辑。`loopback` 只判断直连客户端地址，不信任转发头。任何遗留静态挂载在物理退役前都必须受此守卫；M2 受控下载迁移完成后移除挂载，具体退役状态只见追踪矩阵。

## 8. 事务 Outbox 公共端口

### 8.1 Append 写端口

M0 公开以下不可变 append 输入契约：

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

`OutboxEventInput` 是生产者调用 `append()` 的输入，不包含 `event_id`。Writer 在持久化时生成稳定 `event_id`；持久化记录和投递 envelope 由该 ID 加上输入字段组成，消费者不得要求生产者预先生成或伪造 ID。`OutboxWriter` 只向调用方拥有的事务追加记录，不 commit/rollback，也不返回 ORM 实体。

M2/M3/M5 在事件处于“提议”或仅“已冻结”阶段时可依赖 `app.db` 公共写端口编写生产者契约测试和受控实现，但只有满足事件目录“生产启用门禁”后，才允许对应环境的生产路径实际调用 `append()`。当前实现状态只见追踪矩阵。

### 8.2 Claim、租约与重放端口

M4 只能从无 ORM 副作用的 `app.core.ports` 导入 `OutboxClaimPort` 及其不可变值对象，不得从 `app.db` 导入该端口、接收 SQLAlchemy `Session` 或直接读写 `db.models.OutboxEvent`。冻结的方法为：

```python
OutboxClaimPort.claim(OutboxClaimInput) -> OutboxClaimResult
OutboxClaimPort.renew_lease(OutboxLeaseRenewalInput) -> OutboxLeaseRenewalResult
OutboxClaimPort.acknowledge_success(OutboxAcknowledgeSuccessInput) -> OutboxAcknowledgeSuccessResult
OutboxClaimPort.schedule_retry(OutboxRetryInput) -> OutboxRetryResult
OutboxClaimPort.dead_letter(OutboxDeadLetterInput) -> OutboxDeadLetterResult
OutboxClaimPort.replay(OutboxReplayInput) -> OutboxReplayResult
```

端口语义如下：

1. `claim` 在一个原子持久化操作中，只把 `(consumer_id, event_id)` 交给一个有效租约；允许一次领取 1～100 项，租期为 1 秒～24 小时。数据存储时钟是到期判断的唯一事实源，调用方时间不得覆盖它。
2. `OutboxLease` 同时携带 `consumer_id`、`event_id`、`owner_id`、不透明 `lease_token`、单调递增 `fencing_token`、`delivery_attempt`、`replay_generation`、`acquired_at` 和 `expires_at`。续租、成功确认、重试和 dead-letter 必须比较完整租约证据；过期后重领必须生成新 token，并提高 fencing token 与 attempt。
3. `renew_lease` 是 heartbeat，只能延长当前未过期租约；`acknowledge_success` 是终态；`schedule_retry` 释放租约且不得早于 `available_at` 再次可领取；`dead_letter` 生成当前 dead-letter token，只有携带匹配 token 的显式 `replay` 才能重开。
4. replay 保留原 `event_id` 和事件信封、增加 `replay_generation`、创建新的投递尝试，绝不再次调用生产者。事件 payload 必须是有限 JSON 值并在领取信封中深度不可变；失败元数据只允许稳定 `code` 与可选 `diagnostic_id`，禁止异常原文。
5. 所有命令使用 `operation_id`，幂等范围为 `(consumer_id, operation_name, operation_id)`。相同规范输入重试返回已存结果并标记 `idempotent_replay=true`；同 ID 不同输入返回 `idempotency_conflict` 且不改变状态。
6. 失败结果只使用 `not_found`、`ownership_conflict`、`lease_expired`、`stale_fence`、`invalid_state`、`idempotency_conflict`；被拒绝的命令不得附带已应用状态，也不得修改投递记录。

本节只冻结 M0 公共契约。M0 的持久化适配器、M4 Worker、租约/投递表迁移、真实消费者与恢复验证仍分别按模块计划实施；端口冻结本身不满足事件目录的生产启用门禁。

outbox 范围按以下矩阵执行：

| 写操作类型 | 同事务要求 | outbox 要求 |
| --- | --- | --- |
| M2/M3/M5 可对外观察，且对应事件满足生产启用门禁的关键领域状态变更 | 业务状态 + 已认证 `CurrentUser`；异步延续使用受管服务用户并保留发起身份 + 审计 + 必要幂等记录 | 在启用环境必须追加版本化事件 |
| M5 查询、回答或反馈等未满足事件生产启用门禁的状态变更 | 已认证 `CurrentUser`；异步延续使用受管服务用户并保留发起身份 + 审计/调用记录 + 必要幂等记录 | 不发布业务 outbox |
| M1 用户、角色、密码等安全状态变更 | 安全状态 + 已认证 `CurrentUser` + 审计 + 必要幂等记录 | 仅在对应安全事件满足生产启用门禁时追加 |
| 登录成功后的会话签发、显式注销 | 已认证用户 + 独立短事务 + 适用的安全审计 | 不发布业务 outbox |
| 被动会话活动续期 | 已认证用户 + 独立短事务 + 结构化日志/指标 | 不发布业务 outbox，也不逐次写业务审计事件 |
| 登录失败、限流等认证子系统记账 | 认证子系统受管服务用户 + 独立短事务 + 安全审计 | 不发布业务 outbox |
| 首次 bootstrap | 仅限 `uninitialized`；bootstrap 受管服务用户 + 生命周期锁 + 审计 + 独立 CLI 操作标识 | 不属于正常生产流量写入；激活后拒绝再次执行 |
| Worker heartbeat/lease/retry 等运行维护 | 受管服务用户 + 任务上下文 + 运行日志/指标 | 不发布业务 outbox；事件目录登记的显式领域结果事件除外 |

新增事件及其生产启用条件只在[事件目录](event-catalog.md)登记，并更新生产者/消费者契约、追踪矩阵及事务/集成测试。只有需求语义或 M0 公共端口变化时才修改 SRS 或本文；新增具体事件不再要求重复改写多个说明文档。
