# M1 身份与审计模块设计方案

> 状态：实施中；基础内核已完成并经 `2026-08-13-007-m1-completion-audit` 复核，本地账户 HTTP/API 层待实现，OIDC 作为 M1.1 扩展。<br>
> 主责模块：M1；协作模块：M0、M7。<br>
> 关联记录：`2026-08-13-002-auth-entry-exception`、`2026-08-13-003-m0-m1-prerequisites`、`2026-08-13-004-m1-design`、`2026-08-13-005-m1-contract-gates`、`2026-08-13-006-m1-core-foundation`、`2026-08-13-007-m1-completion-audit`。

实施进度：已完成配置约束、领域包、RBAC/`CurrentUser`、Argon2id 适配、可恢复的会话/CSRF 密钥原语、身份与审计 ORM、角色种子、不可变审计迁移和 `AuditWriter`。第 6 节 HTTP 路由、Repository/业务服务、登录限流状态机、FastAPI 身份依赖、bootstrap CLI 与真实 PostgreSQL 集成测试仍待后续逻辑批次实现。完成度按能力状态追踪，不使用百分比推断可发布性，详见第 10 节。

## 1. 目标与实施边界

M1 为后续业务模块提供本地账户、服务器会话、RBAC、当前用户上下文、职责分离和不可变审计事件。第一阶段只实现 `APP_AUTH_MODE=local`；OIDC 仅定义扩展接口，不在本次本地账户交付中接入第三方 SDK 或回调。

M1 的目标需求范围为 AUTH-01～AUTH-10、FR-IAM-01～FR-IAM-05、DATA-02～DATA-05、API-01～API-04、NFR-SEC-02/04/07、NFR-OBS-01～OBS-03；当前实现并未全部满足这些需求。它不迁移旧 `/api` 的业务功能，也不负责 M2/M3 的知识审核、文档、附件或工作流数据。

```text
浏览器
  │  Cookie + X-CSRF-Token
  ▼
/api/v1/auth, /users, /audit ──> M1 API / DTO
  │                                  │
  │ CurrentUser / require_permissions│
  ▼                                  ▼
M2、M3、M5 公开端口            IdentityService / AuditWriter
                                     │
                                     ▼
                       PostgreSQL users / sessions / audit_events
```

## 2. 开工门禁与已确认前置

### 2.1 已确认可复用的 M0 前置

| 前置 | 复用方式 | 验证结论 |
| --- | --- | --- |
| v1 根路由和领域发现 | 新增 `api/v1/auth.py`、`users.py`、`audit.py` 的 `router` 即被自动装配 | 已加载 M1 预留模块名；未交付模块安全跳过 |
| 领域模型发现 | 新增 `domains/identity/models.py`、`domains/audit/models.py` 并继承 `Base` | Alembic 读取 `Base.metadata` 前会发现模型 |
| 迁移基础 | 首个 M1 revision 以 `20260813_0002` 为起点；生成前重查 head | 离线升级已生成 M0 两条迁移 |
| 响应与分页 | 普通接口用 `v1_success()`；列表用 `v1_page()` 和 `PageRequest` | `data.items` / `meta.nextCursor` 已冻结 |
| CORS | Cookie 会话复用 `APP_TRUSTED_ORIGINS` 与 M0 全局中间件 | 可信来源预检 200；非可信来源 400 |
| 幂等 | 关键写接口以同一事务调用 `IdempotencyService` | HMAC 指纹、冲突/回放语义已冻结 |
| 请求 ID 与错误处理 | 抛出 `AppError`，让 M0 返回 v1 错误信封 | request ID 已由中间件注入 |

### 2.2 已关闭的设计门槛

| 门禁 | 问题 | 解决方案 | 所有者 |
| --- | --- | --- | --- |
| G1：身份专用错误码 | M0 当前仅登记公共错误码，M1 不能绕过登记自行发布新语义 | 已在 M0 `ErrorCode` 与公共契约登记身份错误码；匿名登录仍统一使用 `INVALID_CREDENTIALS` 防止账户枚举 | 已关闭；M1 主责、M0 协作 |
| G2：审计查看者业务读取范围 | 角色矩阵允许审计查看者“只读查看有效知识和流程”，AUTH-09 却限制其只能读取审计和运行报告 | SRS 已以最小权限为准：基线 `auditor` 仅有 `audit:read`、`ops:read`；业务读取必须叠加 `technician` 并审计 | 已关闭；产品/SRS |

G1 和 G2 已关闭，M1 可按本文实施公开 API。后续若改变错误码或角色基线，必须作为 M0 公共契约变更另行评审并增加日志，不得在 M1 私有实现中静默修改。

## 3. 新建文件与所有权

M1 只能创建或修改下列文件。不得编辑 M0 的 `main.py`、`api/v1/router.py`、`core/`、`db/models.py`、`db/domain_models.py`、`alembic/env.py` 和 M0 迁移。

```text
backend/app/
  domains/
    __init__.py
    identity/
      __init__.py
      models.py              # User、Role、UserRole、AuthSession、LoginThrottle
      contracts.py           # 内部领域 DTO、权限码、CurrentUser
      repository.py          # IdentityRepository；只访问 M1 表
      passwords.py           # Argon2id 哈希与校验
      sessions.py            # 随机会话令牌、Cookie、CSRF、撤销和过期判断
      authorization.py       # require_permissions、职责分离断言
      dependencies.py        # get_current_user、require_permissions 的 FastAPI 依赖
      service.py             # 登录、登出、用户/角色/状态编排
      bootstrap.py           # 一次性初始管理员 CLI，不提供 HTTP 注册接口
      oidc.py                # M1.1 接口桩；M1.0 不导入 Authlib
    audit/
      __init__.py
      models.py              # AuditEvent
      contracts.py           # 审计事件输入/脱敏查询视图
      writer.py              # 同事务 AuditWriter
      repository.py          # 仅查询，游标分页
  api/v1/
    auth.py                  # 匿名登录、登出、me、CSRF、本人改密
    users.py                 # 用户、状态、角色、管理员重设密码
    audit.py                 # 审计只读查询
backend/alembic/versions/
  <timestamp>_m1_identity_audit.py
tests/
  test_m1_identity_passwords.py
  test_m1_identity_sessions.py
  test_m1_authorization.py
  test_m1_identity_api.py
  test_m1_audit_api.py
  test_m1_postgres_integration.py
docs/design/
  m1-identity-audit-design.md
docs/change-log/
  <本模块后续逻辑变更日志>
```

M1 可以修改的共享文件只有经过 M0 评审的 `core/error_codes.py`、`.env.example`、`backend/requirements.txt`、M0 公共契约和 SRS；这些修改必须注明“主责 M1、协作 M0”，单独记录并先更新消费者契约测试。

## 4. 数据模型与不变量

所有时间存 UTC，所有 ID 使用 UUID 字符串，不采用 Windows 用户名、磁盘路径或系统账户标识。

| 表 | 核心字段 | 不变量与索引 |
| --- | --- | --- |
| `users` | `id`、`username_normalized`、`display_name`、`password_hash`、`auth_source`、`is_active`、`auth_version`、`must_change_password`、`version`、时间戳、逻辑删除时间 | `username_normalized` 全局唯一；仅 `auth_source=local` 有密码哈希；禁用或安全变更递增 `auth_version` |
| `roles` | `id`、`code`、`display_name`、`is_system` | 固定种子角色代码唯一；不允许 API 删除系统角色 |
| `user_roles` | `user_id`、`role_id`、分配者、分配时间 | `(user_id, role_id)` 唯一；权限取并集，但职责分离规则优先 |
| `auth_sessions` | `id`、`token_digest`、`user_id`、`auth_version`、`csrf_digest`、绝对/空闲过期、最近活动、撤销信息 | 仅保存令牌和 CSRF 摘要；每请求检查用户启用状态及 `auth_version`；撤销后不可复用 |
| `login_throttles` | `subject_hmac`、`source_hmac`、失败计数、窗口、锁定时间 | 用户名/IP 不以明文存储；成功登录清除或重置失败计数 |
| `audit_events` | `id`、`occurred_at`、`actor_user_id` 可空、`action`、`target_type/id`、`result`、`request_id`、`metadata` | 只追加；无 HTTP 更新/删除接口；迁移阻止 `UPDATE`、`DELETE` 和 `TRUNCATE`；用户采用逻辑删除，审计外键使用 `RESTRICT` 保留操作人引用 |

角色种子及权限码：

```text
technician        knowledge:read, workflow:read, case:create, feedback:create
reviewer          knowledge:read, workflow:read, knowledge:review, workflow:review,
                  case:review, feedback:review
knowledge_manager knowledge:read, workflow:read, document:write, knowledge:write, workflow:write
system_admin      iam:users:read, iam:users:write, iam:roles:write, ops:read
auditor           audit:read, ops:read
```

`system_admin` 不隐含审核权限；同一自然人同时具有 `reviewer` 和提交能力时，仍由 `ensure_not_self_review()` 拒绝审核自身提交内容。M2/M3 接入时必须传入提交者 ID，禁止比较展示名。

## 5. 身份、安全与会话设计

### 5.1 配置

M1 增加以下 `APP_AUTH_*` 键；密钥只来自 Windows Service 环境、部署密钥存储或受控 `.env`，不得回传给浏览器。

```text
APP_AUTH_MODE=local                     # local | oidc，一次部署只启用一种
APP_AUTH_SECRET=<随机高熵密钥>             # 会话/CSRF HMAC，生产必填
APP_SESSION_COOKIE_NAME=repair_session            # HTTP 开发默认；生产改为 __Host-repair_session
APP_SESSION_TTL_MINUTES=480
APP_SESSION_IDLE_TIMEOUT_MINUTES=30
APP_SESSION_COOKIE_SECURE=true
APP_AUTH_MAX_LOGIN_FAILURES=5
APP_AUTH_LOGIN_WINDOW_SECONDS=900
APP_AUTH_LOCK_SECONDS=900
```

生产环境 Cookie 配置必须拒绝非安全 Cookie 和非 `__Host-` 名称；M1 任一登录或身份依赖入口必须调用 `validate_identity_runtime_settings()`，在 `APP_AUTH_SECRET` 缺失、少于 32 字节或配置为尚未交付的 OIDC 模式时返回稳定的 503 错误。M0 全局 CORS/健康检查装配不得因尚未交付的 M1 路由缺少密钥而阻断旧兼容进程启动；M1 对外启用后，M7 生产预检或 M0 就绪扩展必须把认证运行时校验纳入发布门槛。开发环境允许明确设置 `APP_SESSION_COOKIE_SECURE=false`，此时 Cookie 名不得使用浏览器要求 `Secure` 的 `__Host-` 前缀；该值不得成为生产默认。

### 5.2 本地账户

- 使用 `argon2-cffi` 的 Argon2id；参数由 M1 集中配置，密码哈希不得进入审计、日志、API 响应或幂等响应。
- `POST /auth/login` 对用户名、密码失败返回同一 `INVALID_CREDENTIALS`，不枚举账户状态；锁定时记录审计但对外仍使用泛化错误。
- 会话令牌使用 `secrets.token_urlsafe()` 生成，数据库仅保存 HMAC/SHA-256 摘要；Cookie 必须 `HttpOnly`、`SameSite=Lax`、`Path=/`，生产使用 `Secure`。若采用 `__Host-` 前缀，则不得设置 `Domain`。
- 对 Cookie 认证的所有状态变更接口要求 `X-CSRF-Token`。CSRF token 由服务器使用 `APP_AUTH_SECRET` 和当前原始会话令牌按独立 HMAC purpose 确定性派生，数据库只保存其摘要；因此 `GET /auth/csrf` 可在页面刷新后重新计算，而无需保存明文。比较必须使用常量时间函数。
- M0 CORS 白名单只作为浏览器响应策略；M1 登录及所有 Cookie 写请求还必须在执行业务前验证 `Origin`/受控 `Referer` 与 `APP_TRUSTED_ORIGINS`。匿名登录没有既有 CSRF token，因此尤其不能只依赖 CORS。生产浏览器来源必须显式配置；无 Origin 的非浏览器客户端若有需求，应另行定义非 Cookie 认证方式，不得静默绕过来源检查。
- 改密、账号禁用、角色变更和管理员重设密码递增 `auth_version`，撤销受影响会话；下一个请求立即失效。
- 初始管理员通过本地 CLI 创建，要求空用户库、显式用户名和密码输入；不提供公共注册、默认密码或 HTTP bootstrap。

### 5.3 OIDC 扩展（M1.1）

`oidc.py` 仅先定义 `IdentityProvider` 接口与 `LocalIdentityProvider`。后续启用 OIDC 时新增 `OidcIdentityProvider`、授权状态/nonce/PKCE 表和 `GET /auth/oidc/start`、`GET /auth/oidc/callback`；必须安装并锁定 OIDC 依赖后再实施。不得在 M1.0 添加伪 OIDC 回退或同时启用本地/OIDC 登录。

## 6. 对外 HTTP 接口

所有接口位于 `/api/v1`，返回 M0 信封。除表中标明的匿名接口外，一律依赖 `CurrentUser`。所有状态变更接口要求 CSRF；标有“幂等”的接口另要求 `Idempotency-Key`。`If-Match` 使用用户 `version`，并发冲突返回 `VERSION_CONFLICT`。

| 方法与路径 | 认证与权限 | 请求 / 响应要点 | 审计与幂等 |
| --- | --- | --- | --- |
| `POST /auth/login` | 匿名，仅 `local` 模式 | `{username,password}`；成功设置 Cookie，返回用户、权限、过期时间和 CSRF token | 登录成功/失败；限流；不幂等 |
| `POST /auth/logout` | 当前用户 + CSRF | 无正文；撤销当前会话并清 Cookie | 登出；不幂等 |
| `GET /auth/me` | 当前用户 | 返回用户 ID、显示名、角色、权限、会话到期、是否需改密 | 无 |
| `GET /auth/csrf` | 当前用户 | 返回当前会话 CSRF token | 无 |
| `PUT /auth/password` | 当前用户 + CSRF | `{currentPassword,newPassword}`；改密后撤销旧会话 | `password.changed`；幂等 |
| `GET /users?limit&cursor&status` | `iam:users:read` | `data.items`；不得返回密码哈希、令牌、限流明细 | 无 |
| `POST /users` | `iam:users:write` + CSRF | `{username,displayName,initialPassword,roles}` | `user.created`；幂等 |
| `PATCH /users/{id}` | `iam:users:write` + CSRF + `If-Match` | 仅展示名等非安全资料 | `user.updated`；不幂等 |
| `PATCH /users/{id}/status` | `iam:users:write` + CSRF + `If-Match` | `{isActive,reason}`；禁止禁用自己和最后一个启用管理员 | `user.disabled/enabled`；幂等 |
| `PUT /users/{id}/roles` | `iam:roles:write` + CSRF + `If-Match` | `{roles,reason}`；替换集合，禁止修改自己/移除最后管理员 | `user.roles_changed`；幂等 |
| `PUT /users/{id}/password` | `iam:users:write` + CSRF + `If-Match` | `{temporaryPassword,reason}`，标记强制改密 | `user.password_reset`；幂等 |
| `GET /roles` | `iam:users:read` | 固定角色及权限说明，不返回内部配置 | 无 |
| `GET /audit-events?limit&cursor&actorId&action&from&to` | `audit:read` | 脱敏 `data.items`；只允许白名单过滤与时间倒序 | 无 |

M1 已由 M0 登记的错误码：

```text
INVALID_CREDENTIALS        ACCOUNT_LOCKED          ACCOUNT_DISABLED
SESSION_EXPIRED            CSRF_INVALID            SELF_REVIEW_FORBIDDEN
LAST_ADMIN_PROTECTED       PASSWORD_POLICY_VIOLATION AUTH_MODE_UNAVAILABLE
```

## 7. 服务接口供 M2/M3/M5 复用

M1 只公开下列 Python 端口，领域消费者不得导入 M1 Repository、ORM 实体或 Cookie 实现：

```python
class CurrentUser:
    id: str
    roles: frozenset[str]
    permissions: frozenset[str]
    session_id: str

def get_current_user(...) -> CurrentUser: ...
def require_permissions(*permissions: str): ...
def ensure_not_self_review(current_user: CurrentUser, submitter_user_id: str) -> None: ...

class AuditWriter:
    def append(self, session, event: AuditEventInput) -> None: ...
```

M2/M3 的关键写操作在一个事务中写入领域状态、调用 `AuditWriter.append()`、写 M0 outbox，再提交。操作者、审核者、提交者均由服务器端 ID 确定；不得接受客户端 `reviewer`、`actorId`、角色或权限字段。

`AuditWriter` 的通用敏感键脱敏只是最后一道防线，不替代事件级白名单 DTO。M1 登录事件不得把原始用户名、IP、Cookie、令牌或密码放入 `target_id`/`metadata`，只允许通用目标标识及带独立 purpose 的 HMAC 主体/来源摘要；M2/M3 为每类安全事件定义允许的 metadata 字段，禁止把任意请求体直接传给 `AuditEventInput`。

## 8. 已知冲突与解决方案

| 冲突 | 当前证据 | 风险 | 解决方案 |
| --- | --- | --- | --- |
| 旧 API 信任 `reviewer="operator"` | `schemas.py`、`frontend/src/api.ts` 仍向旧 `/api` 传 reviewer | 可伪造审核身份 | M1 不修改旧契约；M2/M3 迁移到 v1 时删除该字段并改用 `CurrentUser`。生产发布前禁用或下线旧写接口。 |
| 旧 `main.py` 有业务路由、静态数据挂载和硬编码旧 CORS | 旧 `/api` 和 `/uploads`、`/knowledge` 仍存在 | M1 若继续堆逻辑会破坏边界；旧端点仍不满足 AUTH-01 | M1 仅加领域子路由；不改 `main.py`。M2 负责受控下载并迁移业务端点，M7 在生产入口禁用旧写 API/静态数据暴露。 |
| M0 公共错误码与 M1 语义 | 身份错误码已由 M0 登记并有契约测试 | 后续私自新增仍可能漂移 | G1 已关闭；新错误码继续走 M0 评审，不修改既有码含义。 |
| 审计查看者权限文本 | SRS 与角色种子均为 `audit:read`、`ops:read` | 后续角色扩权可能意外读取知识 | G2 已关闭；业务阅读必须额外授予 `technician` 并审计。 |
| 密码/OIDC 依赖状态 | `argon2-cffi==23.1.0` 已锁定并实测；OIDC SDK/接口尚未交付 | 配置 `oidc` 时不能建立身份 | M1.0 运行时显式返回 `AUTH_MODE_UNAVAILABLE`，不得回退本地或伪 OIDC；M1.1 另行设计迁移、依赖和路由。 |
| 现有测试无 PostgreSQL 集成实例 | 当前多为 TestClient/原型 JSON 测试 | 不能验证唯一约束、触发器、会话失效和事务原子性 | M7 提供 PostgreSQL 16 CI 服务；M1 的 API/迁移集成测试不得用 SQLite 替代。 |
| `auth_version` 与会话并发 | 账号禁用/角色调整时旧会话可能继续使用 | 权限变更不及时生效 | 每次 `get_current_user()` 联表检查用户活动状态和版本；安全修改同事务递增版本、撤销会话。 |
| 幂等 service 要求 HMAC 密钥 | M0 的 `request_fingerprint()` 要求 `APP_IDEMPOTENCY_SECRET` | 配置遗漏会在关键写操作时报 503 | M1 关键写路由调用前验证；M7 生产预检纳入发布门槛；测试显式注入测试密钥，不把密钥写入前端/日志。不得在 M0 全局装配阶段读取失败而阻断无 M1 路由的兼容进程。 |
| 路由/模型相对发现 | M0 同时支持 `backend.app` 与 `app` 包路径 | 写死绝对包名会在另一启动方式失效 | M1 仅使用 M0 预留相对文件名和相对导入；新增路由/模型后分别从仓库根和 `backend/` 启动路径验证。 |

## 9. 实施顺序与验收

1. 解决 G1、G2，新增 M1 配置契约与 `argon2-cffi` 锁定依赖，建立 `domains/` 骨架。
2. 实现模型、角色种子、迁移、审计触发器和 PostgreSQL 集成测试。
3. 实现密码、会话、CSRF、登录限流与 `CurrentUser`，完成单元测试。
4. 实现本地登录与 `me/logout/password` API，验证匿名 allowlist 不扩大。
5. 实现用户、角色与审计查询 API，接入 M0 分页、幂等、`If-Match` 和审计写入。
6. 提供 bootstrap CLI、OpenAPI/契约测试和 M2/M3 使用示例；OIDC 单独进入 M1.1。

最低验收：密码没有明文/可逆存储；登录失败不枚举用户；禁用/角色变更立即使会话失效；CSRF、CORS、限流、最后管理员保护、不得自审、审计追加写入和幂等回放均有 PostgreSQL 集成测试。每步完成后必须新建本地修改日志并更新索引。

## 10. 当前完成度与后续合并门槛

### 10.1 需求与实现对照

| 需求/设计能力 | 当前状态 | 已有证据 | 仍缺内容 |
| --- | --- | --- | --- |
| AUTH-07、密码安全基础 | 基础内核完成 | Argon2id 适配、密码策略、真实哈希单测 | 创建/改密/重置服务及密码历史等企业策略属于后续扩展 |
| RBAC、AUTH-05/09 基础 | 基础内核完成 | 固定角色/权限、`CurrentUser`、权限集合和禁止自审单测 | FastAPI `get_current_user()`/`require_permissions()`、最后管理员与角色变更服务 |
| 会话、AUTH-08 基础 | 部分完成 | 令牌/CSRF HMAC、绝对/空闲过期、会话表和配置测试 | Repository、Cookie 设置/清除、活动续期、撤销、账号/角色变更即时失效 |
| 登录限流、FR-IAM-05 | 仅模型/配置 | `login_throttles` 表与阈值配置 | 并发安全状态机、成功重置、失败提交、IP/用户名 HMAC 和集成测试 |
| 审计、FR-IAM-04/OBS-03 | 部分完成 | `audit_events`、不可变触发器、脱敏 `AuditWriter` | 登录/登出/用户变更实际写入、查询 Repository/API、保留策略、真实 PostgreSQL 触发器测试 |
| FR-IAM-01/02、AUTH-01/02/03 | 未完成 | 路由和模型发现接缝已预留 | 登录、本人信息、用户/角色管理接口及后端强制授权；旧写入口生产下线 |
| API-01～04 | 部分完成 | v1 路径、信封、错误码、分页/幂等公共能力 | M1 DTO/路由、游标、`If-Match`、幂等事务编排和 OpenAPI 契约测试 |
| bootstrap CLI | 未完成 | 无 | 空用户库检查、交互式密码输入、首个系统管理员和审计事件 |
| OIDC（AUTH-06 SHOULD） | 未开始 | 配置枚举和显式不可用校验 | M1.1 独立设计、SDK、state/nonce/PKCE 表和回调 |
| PostgreSQL 验收 | 未完成 | 单一迁移 head、离线升级/降级 SQL | PostgreSQL 16 在线迁移、约束/触发器、事务、并发、回滚和 API 集成测试 |

### 10.2 后续搭建不得突破的边界

1. `20260813_0003` 已进入历史，不再编辑；新增字段、约束或索引必须创建以当前最新 head 为 `down_revision` 的新迁移。若其他模块先增加 revision，M1 必须先重查 head，不得自行制造多头。
2. Repository 只访问 M1 表；API 通过 Repository/Service，不得直接查询 ORM。M2/M3/M5 只能导入 `CurrentUser`、授权断言和 `AuditWriter` 等公开端口，不得导入 M1 ORM/Repository。
3. `get_current_user()` 每次请求必须校验 Session 未撤销、绝对/空闲期限、用户启用/未删除和 `auth_version`，并从服务器端角色重新计算权限；不得信任 Cookie、请求体或前端传入角色。
4. 登录失败需要同时持久化限流计数和脱敏审计后再返回 `INVALID_CREDENTIALS`。实现不得因抛出 `AppError` 让失败记录随事务回滚；推荐服务返回失败结果，端点提交独立登录尝试事务后再构造 401。
5. 用户禁用、角色变更、本人改密和管理员重置必须在同一事务中递增 `auth_version`、撤销相关会话、追加审计并完成幂等记录；最后管理员判断和登录限流更新使用 PostgreSQL 行锁/等价原子语句，禁止“先查后改”的竞态。
6. 登录/身份依赖入口首先调用 `validate_identity_runtime_settings()`；本地模式密钥少于 32 字节或 M1.0 配置 OIDC 时失败关闭。登录和 Cookie 写端点还必须复用 M0 可信来源配置执行服务端 Origin/Referer 校验，不能把 CORS 当作防 CSRF。`scripts/init-config.*`、Windows Service 和 Docker/CI 的认证配置属于 M7 协作项，在 M1 API 联调前补齐，但不得在脚本中生成或提交生产密钥。
7. M1 路由只新增 `api/v1/auth.py`、`users.py`、`audit.py`，复用 M0 注册、CORS、错误信封、Session 和幂等服务；不得修改 `main.py` 或建立第二套路由/中间件/事务管理器。
8. 旧 `/api` 与静态目录是兼容层，不因 M1 路由出现而自动受保护。M1 可以继续开发，但 1.0 生产验收前必须由 M2/M3/M7 完成 v1 迁移或在部署入口禁用旧写接口和静态暴露，否则 AUTH-01/02/03 仍判失败。
9. 用户名必须在 M1 单一函数中执行长度/字符策略和 Unicode NFKC + `casefold()` 规范化；登录不存在用户时仍执行固定的 Argon2id dummy hash 验证，避免通过响应时间枚举账户。登录来源 IP 只能来自 M0/M7 冻结的可信代理解析结果，禁止直接信任客户端 `X-Forwarded-For`。
10. 空闲会话活动时间不得在每个读请求上无条件写库；Repository 使用可配置或冻结的最小刷新间隔做条件更新，并保证并发请求不会把 `idle_expires_at` 缩短，以降低热点会话行争用。
11. M0 当前只冻结了分页字段与 `VERSION_CONFLICT`，尚未提供不透明游标 codec，也未定义 `If-Match` 的引号/版本格式。M1 在实现 `/users`、`/audit-events` 前必须先通过 M0 协作冻结公共 cursor 编解码/非法游标错误，以及 `If-Match` 解析和响应 ETag 规则；M1 不得私自形成与 M2/M3 不同的第二套格式。
12. 身份相关响应（登录、`me`、CSRF、用户和审计数据）必须返回 `Cache-Control: no-store`；登录 Cookie 设置和清除统一由 M1 响应帮助函数生成，固定 `HttpOnly`、`SameSite=Lax`、`Path=/`、生产 `Secure` 且不设置 `Domain`，不得由各路由手写不同属性。

### 10.3 可继续开发的结论

M1 后续 Repository、Service、FastAPI 身份依赖和本地认证 API 可以在现有结构上继续搭建，不需要重构 M0 或回退现有表。M2/M3 可并行开发纯领域逻辑与契约 Mock；只有在 M1 发布真实身份依赖后才能接入生产写路由。M7 可并行准备 PostgreSQL 16、认证配置预检和双平台测试。满足第 10.2 节后，三条开发线不会直接修改同一私有目录；共享配置、错误码、迁移 head 或就绪检查的变化仍必须按 M0 契约单独评审并记录。
