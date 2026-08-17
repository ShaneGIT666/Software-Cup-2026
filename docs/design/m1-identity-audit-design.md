# M1 身份与审计模块设计方案

> 文档性质：M1 稳定设计与公共接入契约；主责模块：M1；协作模块：M0、M2～M7。<br>
> 当前实现状态、验证证据、迁移 head 和未关闭问题只在[现行需求追踪矩阵](../requirements/current-traceability-matrix.md)维护。

本文定义本地身份、可扩展 OIDC 边界、服务器会话、RBAC、受管服务主体、职责分离、实例生命周期和不可变审计。测试数量、阶段完成度、最新日志清单和精确文件清单不得复制到本文；只有需求语义、稳定端口、数据不变量或模块所有权变化时才修改本文。

## 1. 目标与边界

M1 为业务模块提供：

- `CurrentUser`：已登录交互用户的请求身份、角色、权限和会话标识。
- `AuthenticatedActor`：交互写入或受管内部任务的可审计主体，可携带原始发起用户。
- 后端授权、本人复核隔离和审核容量查询。
- 本地账户、会话、CSRF、密码、登录限流、用户/角色管理。
- 单例身份实例生命周期、bootstrap、activation 和 identity readiness。
- 与调用方事务同生共死、只追加且不泄露 ORM 的审计写端口。

M1 不拥有文档、知识、案例、设备、工作流、RAG 或反馈数据，不建立跨领域通用审核 ORM，也不迁移旧 `/api` 的业务语义。领域模块不得导入 M1 ORM、Repository、Cookie 或节流实现。

## 2. 所有权与依赖方向

M1 所有权按稳定目录而非逐文件清单界定：

| 所有者 | 目录/表面 | 责任 |
| --- | --- | --- |
| M1 identity | `backend/app/domains/identity/` | 身份模型、Repository、服务、公共身份 DTO、授权、生命周期和 readiness contributor |
| M1 audit | `backend/app/domains/audit/` | 审计模型、事件输入、Writer 和只读查询 |
| M1 HTTP | `backend/app/api/v1/auth.py`、`users.py`、`audit.py` | `/api/v1` 身份与审计路由 |
| M1 migrations | 新增 Alembic revision | 仅修改 M1 表及其约束；不得改写已登记或已应用的历史 revision |
| M0 | `core/`、`db/`、v1 根路由、`main.py` | 公共信封、错误、Session、readiness 聚合、幂等和 outbox |
| M2～M5 | 各自领域或 Worker 目录 | 审核对象、提交者、领域事务，以及事件级审计 metadata DTO；M4 仅通过公开命令端口回写领域结果 |
| M7 | `deploy/`、CI 和验收工件 | PostgreSQL、代理、provisioning 入口、服务管理和跨平台验证 |

依赖方向固定为“业务模块 -> M1 公共身份/审计端口 -> M1 私有实现”。M1 可以依赖 M0 公共端口，但不能读取 M0 私有 Session factory、复制数据库配置或修改总路由。

## 3. 数据模型与数据库不变量

所有主键为与操作系统和部署节点无关的稳定不透明 ID；数据库时间使用带时区 UTC。任何结构变化必须新增迁移并附回滚说明。

| 表 | 核心字段 | 强制不变量 |
| --- | --- | --- |
| `users` | `id`、规范化用户名、显示名、`password_hash`、`auth_source`、`service_key`、`is_active`、`auth_version`、`must_change_password`、`version`、时间与逻辑删除 | `auth_source in {local, oidc, service}`；local 必须有密码且无 service key；oidc/service 无本地密码；service 必须有唯一 service key，非 service 不得有 |
| `roles` / `user_roles` | 固定角色、系统标记、授予人和授予时间 | 角色码唯一；服务主体不通过客户端管理接口授予或修改 |
| `auth_sessions` | token/CSRF 摘要、用户、`auth_version`、绝对/空闲期限、活动与撤销字段 | 不保存明文 token；每次授权重新检查会话、用户状态和版本 |
| 登录限流表 | 规范化账号主体与可信来源的独立 HMAC bucket、窗口、计数和锁定时间 | 账号维度和来源维度均独立生效；不能只使用二者组合 |
| `identity_instance_state` | 单例 ID、`lifecycle`、`version`、激活时间和激活用户 | ID 固定为 `identity`；生命周期只允许 `uninitialized -> bootstrapped -> active`；仅 active 可填写激活字段 |
| `audit_events` | `id`、时间、非空 `actor_user_id`、可空 `initiator_user_id`、动作、目标、结果、request ID、JSON metadata | actor 外键非空且 `RESTRICT`；initiator 若有也 `RESTRICT`；只追加，普通业务接口不得更新、删除或截断 |

`audit_events.metadata` 在存储层使用 JSON，不代表调用方可传任意映射。每个事件必须先由封闭的事件级 metadata DTO 构造；通用敏感键过滤只作为最后一道防线。

## 4. 角色、权限与审核容量

### 4.1 稳定角色与权限

目标权限码及基础角色映射如下。新增、重命名或移除权限属于 M1 公共契约及种子数据变化，必须附迁移/兼容策略和授权测试。

~~~text
technician:
  knowledge:read, workflow:read, case:create, feedback:create

reviewer:
  knowledge:read, workflow:read,
  knowledge:review, workflow:review, case:review, feedback:review

knowledge_manager:
  knowledge:read, workflow:read,
  document:write, knowledge:write, workflow:write, device:write

system_admin:
  iam:users:read, iam:users:write, iam:roles:write,
  ops:read, ops:write

auditor:
  audit:read, ops:read
~~~

`system_admin` 不隐含任何内容审核权限。`auditor` 不隐含业务知识、流程或附件读取权；确需读取时必须显式叠加 `technician`，并按安全访问规则审计。角色在服务端解析，禁止根据前端隐藏、Cookie 内容或请求体中的角色/权限授权。

### 4.2 不得自审与容量门禁

`ensure_not_self_review()` 只负责单次决定中的“当前用户 != 提交者”。每个拥有审核/发布能力的领域还必须通过 M1 公共 reviewer capacity 端口检查至少两名不同、启用、未删除、非服务主体且具有相应审核权限的交互用户：

~~~python
class ReviewCapability(str, Enum):
    KNOWLEDGE = "knowledge"
    WORKFLOW = "workflow"
    CASE = "case"
    FEEDBACK = "feedback"

@dataclass(frozen=True)
class ReviewerCapacity:
    capability: ReviewCapability
    eligible_user_ids: tuple[str, ...]

class ReviewerCapacityPort(Protocol):
    def get(self, session, capability: ReviewCapability) -> ReviewerCapacity: ...
    def require_publish_capacity(self, session, capability: ReviewCapability) -> None: ...
~~~

M1 只根据身份、状态和权限计算资格，不读取领域审核表。`require_publish_capacity()` 固定执行 SRS 的两人下限，不接受可下调的请求参数。M2/M3/M5 负责把能力映射到审核对象，并在启用/发布该能力前调用容量门禁；少于两人时必须失败关闭，基础版没有配置绕过。

## 5. 身份、会话与安全

### 5.1 运行配置

~~~text
APP_AUTH_MODE=local|oidc
APP_AUTH_SECRET=<独立高熵密钥>
APP_PASSWORD_PEPPER=<独立高熵密钥>
APP_SESSION_COOKIE_NAME=repair_session
APP_SESSION_ABSOLUTE_MINUTES=<正整数>
APP_SESSION_IDLE_MINUTES=<正整数>
APP_LOGIN_WINDOW_SECONDS=<正整数>
APP_LOGIN_MAX_FAILURES=<正整数>
APP_TRUSTED_PROXY_CIDRS=<显式 CIDR 列表>
~~~

生产配置缺失、密钥不足或请求的认证模式没有可用 Provider 时必须失败关闭，不得降级为匿名、本地回退或 Mock。密钥不得进入代码库、前端、普通日志、readiness details 或 API 响应。

### 5.2 本地账户与登录事务

- 用户名先执行唯一规范化策略，再查询和限流；匿名失败统一返回 `INVALID_CREDENTIALS`，不得泄露账号存在、锁定或删除状态。
- 密码使用成熟的 Argon2id 实现。凭据短读完成后在数据库事务外校验哈希；成功后在写事务内重新验证用户启用、未删除、密码凭据未变化且 `auth_version` 一致，再签发会话。
- 登录失败必须在受控短事务中同时更新账号/来源独立限流 bucket，并以 authentication 服务主体写脱敏审计，然后才返回匿名错误。抛出 HTTP 错误不得回滚已决定持久化的失败记录。
- Cookie 只保存随机会话令牌；数据库保存摘要。会话具有绝对和空闲期限、`Secure`、`HttpOnly`、`SameSite=Lax` 和固定 Path。
- 所有建立或使用 Cookie 会话的浏览器写请求先复用 M0 Trusted Origin 校验；已登录写请求还必须校验与当前原始会话令牌绑定的 CSRF token。
- 改密、禁用、角色变化和管理员重设密码在同一事务内递增 `auth_version`、撤销受影响会话、写审计和必要幂等记录。本人改密可以推进当前会话版本并仅撤销其他会话。
- `must_change_password=true` 时，后端只允许本人信息、CSRF、改密和登出；前端限制不能替代后端门禁。

`get_current_user()` 必须从同一数据库一致性快照读取会话、用户活动状态、两侧 `auth_version` 和角色集合，只构造 `CurrentUser`，不得提交或回滚调用方业务事务。被动会话活动续期使用独立短事务，只做条件更新并记录结构化日志/指标，不逐次写业务审计事件。

### 5.3 OIDC 扩展

`APP_AUTH_MODE=oidc` 只有在完整 OIDC Provider 适配器交付后才可启用。适配器必须包含授权发起/回调、state、nonce、PKCE、签名与 issuer/audience 校验、稳定用户映射、登出/会话策略、依赖锁定和迁移。M1 不假定某个 `oidc.py` 文件已经存在，也不以接口桩、配置枚举或本地回退冒充 OIDC 能力。

## 6. 受管服务主体、生命周期与 provisioning

### 6.1 固定服务主体

受管服务账户是 M1 数据，不是各模块自行约定的 UUID：

| service key | 稳定用户 ID | 用途 |
| --- | --- | --- |
| `authentication` | `20000000-0000-0000-0000-000000000001` | 匿名登录失败与认证子系统记账 |
| `bootstrap` | `20000000-0000-0000-0000-000000000002` | 激活前一次性实例引导 |
| `worker` | `20000000-0000-0000-0000-000000000003` | 后台任务与异步延续 |

三者必须满足 `auth_source=service`、对应唯一 `service_key`、启用、未删除、无密码凭据且不可建立交互会话。调用方通过 M1 resolver 按 service key 获得 `AuthenticatedActor`，不得复制固定 ID、直接构造服务 actor 或创建第二套系统用户。Worker 延续用户发起的任务时，把原始用户放入 `initiator_user_id`；无真实发起人的周期任务保持为空。

identity readiness 除运行配置和实例 lifecycle 外，还必须验证三条服务账户逐项满足稳定 ID、service key、认证来源、活动/删除状态和无密码不变量。任一缺失或漂移都必须使生产 readiness 失败，响应只返回 M0 白名单内的脱敏信息。

### 6.2 bootstrap、provisioning 与 activation

1. `uninitialized`：bootstrap 仅通过本地受控 CLI 执行，持有生命周期行锁，要求交互用户数为零且 bootstrap 服务主体有效；创建首个 `local system_admin`，强制临时密码更换，并推进到 `bootstrapped`。不提供 HTTP 注册、默认账号或默认密码。
2. `bootstrapped`：这是受限 provisioning 阶段，不是正常生产就绪状态。`live` 可成功而 `ready` 必须失败；只允许 [SRS 10.1](../requirements/software-requirements-spec.md#101-windows-默认部署)规定的本机或显式可信管理来源访问受限设置页，以及登录、本人信息、CSRF、改密、登出最小接口。其他业务接口和旧兼容表面必须阻断。
3. `active`：activation 只通过受控 CLI，先在事务外验证本地密码，再在持锁事务内复验用户仍为 `auth_source=local`、启用、未删除、`must_change_password=false` 且具有 `system_admin`。满足条件的任一本地系统管理员都可以激活；首个管理员只是常规路径，不是唯一合法激活人。激活写入用户、时间和审计。
4. 实例达到 `active` 后仍须全部必需 readiness contributor 成功，代理才可放行正常业务流量。部署脚本只能编排这些端口，不得复制生命周期判断或在未激活时报告部署完成。

激活后 bootstrap 永久拒绝再次执行。并发 bootstrap/activation 依赖 PostgreSQL 行锁和数据库约束，不能用“先查后改”或文件锁代替。

## 7. 对外 HTTP 契约

所有接口位于 `/api/v1` 并使用 M0 具体响应 DTO、错误信封、request ID、游标、ETag 和幂等契约。除表中匿名入口外均依赖 `CurrentUser`；Cookie 状态变更要求 Trusted Origin 和 CSRF。身份错误码只在 M0 公共错误目录登记，本文不复制错误码清单。

| 方法与路径 | 认证与权限 | 请求/响应要点 | 审计与并发 |
| --- | --- | --- | --- |
| `POST /auth/login` | 匿名，仅当前启用模式 | 本地模式接收用户名/密码；成功设置 Cookie 并返回具体会话/用户 DTO | 成功/失败按主体规则审计；限流；不幂等 |
| `POST /auth/logout` | 当前用户 + CSRF | 撤销当前会话并清 Cookie | 显式登出审计；不发布业务 outbox |
| `GET /auth/me` | 当前用户 | 用户 ID、显示名、角色、权限、期限、是否需改密 | 只读 |
| `GET /auth/csrf` | 当前用户 | 当前会话 CSRF token | 只读 |
| `PUT /auth/password` | 当前用户 + CSRF | 当前密码、新密码；保留当前会话并撤销其他会话 | 审计；幂等 |
| `GET /users` | `iam:users:read` | 游标列表和白名单过滤；不返回凭据、令牌或限流明细 | 只读 |
| `POST /users` | `iam:users:write` + CSRF | 本地用户、临时密码、基础角色 | 审计；幂等 |
| `PATCH /users/{id}` | `iam:users:write` + CSRF + `If-Match` | 仅非安全资料 | 审计 |
| `PATCH /users/{id}/status` | `iam:users:write` + CSRF + `If-Match` | 启用/禁用；保护本人和最后启用管理员 | 审计；幂等 |
| `PUT /users/{id}/roles` | `iam:roles:write` + CSRF + `If-Match` | 服务端替换角色集合；保护本人和最后管理员 | 审计；幂等 |
| `PUT /users/{id}/password` | `iam:users:write` + CSRF + `If-Match` | 管理员设置临时密码并强制改密 | 审计；幂等 |
| `GET /roles` | `iam:users:read` | 固定角色和权限的具体 DTO | 只读 |
| `GET /audit-events` | `audit:read` | 脱敏游标列表；仅白名单过滤和稳定时间顺序 | 只读 |

provisioning 阶段的路由暴露以第 6.2 节和 [SRS 10.1](../requirements/software-requirements-spec.md#101-windows-默认部署)为准；表中存在路由不表示 `bootstrapped` 阶段全部可访问。

## 8. 供业务模块使用的公共端口

### 8.1 身份与授权

~~~python
@dataclass(frozen=True)
class CurrentUser:
    id: str
    roles: frozenset[str]
    permissions: frozenset[str]
    session_id: str

@dataclass(frozen=True)
class AuthenticatedActor:
    user_id: str
    kind: ActorKind
    initiator_user_id: str | None = None

def get_current_user(...) -> CurrentUser: ...
def require_permissions(*permissions: str): ...
def ensure_not_self_review(current_user: CurrentUser, submitter_user_id: str) -> None: ...
def resolve_managed_actor(service_key: ManagedServiceKey, initiator_user_id: str | None = None) -> AuthenticatedActor: ...
~~~

交互写入从 `CurrentUser` 派生 `AuthenticatedActor(kind=interactive)`；受管内部写入只能由 resolver 从数据库中验证过的服务账户生成。API 不接受 `actorId`、`initiatorId`、`reviewer`、角色或权限字段来决定授权或审计归属。

### 8.2 强类型审计门面

业务模块接入生产写事务时使用如下目标门面，不直接提交裸 actor/initiator ID 或任意 metadata：

~~~python
class AuditMetadata(Protocol):
    def to_safe_dict(self) -> dict[str, JsonScalar | list[JsonScalar]]: ...

@dataclass(frozen=True)
class AuditEventInput:
    action: str
    target_type: str
    target_id: str
    result: str
    request_id: str
    actor: AuthenticatedActor
    metadata: AuditMetadata

class AuditWriter(Protocol):
    def append(self, session, event: AuditEventInput) -> AuditAppendResult: ...
~~~

Writer 把 `actor.user_id` 和 `actor.initiator_user_id` 映射到非空 actor/可空 initiator 列，返回不可变 `AuditAppendResult(event_id)`，不 commit/rollback、不返回 ORM。每个 action 使用专用构造器和 metadata 白名单；禁止把请求体、原始用户名/IP、Cookie、令牌、密码、连接串或路径直接写入目标或 metadata。需要关联账号/来源时使用独立 purpose 的 HMAC 摘要。

### 8.3 领域事务与 outbox

- 普通生产 HTTP 写操作使用服务端认证的 `CurrentUser`；内部任务使用 M1 resolver 产生的受管 actor，并按需保留 initiator。
- 领域状态、审计、必要幂等记录，以及适用的 outbox append 必须在调用方拥有的同一事务中写入。
- 只有[事件目录](event-catalog.md)中生命周期已冻结且登记实际消费者的事件才追加 outbox。预期消费者、Mock 或尚未实现的消费者不满足条件。
- M1 安全状态、会话、登录尝试、限流、bootstrap 和 heartbeat/lease 在没有上述事件消费者时不为形式统一发布业务 outbox；它们仍遵守主体、事务、审计或日志/指标规则。

## 9. readiness、错误与日志边界

- M1 contributor 只能返回 M0 `ReadinessDetails` 白名单字段；不得输出服务账户 ID、用户名、连接串、路径、异常文本或堆栈。
- M1 路由抛出已登记的 `AppError`，由 M0 统一形成响应。M1 不创建第二套错误信封，也不自行把显式 5xx 的内部 message/details 暴露给客户端。
- 普通结构化日志只记录 request ID、脱敏用户/主体标识和登记字段；原始凭据、token、Cookie、请求体与异常秘密不得写入。响应脱敏不等于日志脱敏。
- 审计事件用于安全事实，不替代运行日志/指标；被动会话续期和 Worker heartbeat/lease 不逐次写业务审计。

## 10. 验收与变更门禁

### 10.1 自动化测试范围

- 密码策略、用户名规范化、会话绝对/空闲期限、CSRF、强制改密与 `auth_version`。
- 匿名响应不可枚举、账号/来源独立限流、可信代理解析和登录事务外哈希/事务内复验。
- 用户/角色/最后管理员保护、权限码迁移、`device:write`/`ops:write` 和不得自审。
- 每类审核能力的两名合格用户容量门禁，包括不足、禁用、删除、服务用户和并发角色变化。
- 三类服务账户的固定 ID/service key/认证来源/状态/无密码不变量，以及 identity readiness 失败关闭。
- bootstrap、受限 provisioning、任一合格本地 system_admin activation、重复/并发执行与激活后阻断。
- `AuthenticatedActor`、强类型审计输入、initiator 继承、metadata 白名单、敏感字段拒绝和 Writer 事务所有权。
- 审计不可变、游标/过滤、显式 5xx 响应与普通日志脱敏。

### 10.2 集成与发布门禁

- 专用 PostgreSQL 16 完成空库、存量库升级、受控降级/再升级、服务账户种子、回填、外键/非空/检查约束、触发器、行锁、并发和回滚验证；SQLite 和离线 SQL 不替代这些证据。
- IIS/Caddy 或目标代理验证 HTTPS、Cookie、Trusted Origin、CSRF、可信代理链、`bootstrapped` 白名单和激活后正常放流。
- M2/M3/M5 在强类型审计门面、审核容量、服务 readiness 和 PostgreSQL 门禁关闭前，只能使用版本化公共契约 Mock 开发纯领域逻辑，不得把 M1 私有实现作为生产依赖。
- M6 使用具体 OpenAPI DTO 完成登录、强制改密、权限守卫、用户管理和错误恢复 E2E；前端不得传 reviewer/actor/roles 作为授权依据。

每个逻辑变更前读取 `docs/change-log/INDEX.md` 及受影响模块最近记录；完成后在 `docs/change-log/` 新增日志并更新 `INDEX.md`。修复缺陷必须增加对应测试。当前门禁状态和证据只更新追踪矩阵，不回填到本文。
