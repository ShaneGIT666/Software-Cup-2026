# M0/M1 部署复核与后续无冲突接入方案

> 复核日期：2026-08-17<br>
> 状态对象：记录 019 时点的 D1/D1.2 公共契约与 M1 生产身份边界。OpenAPI 通用 500 声明、未捕获异常脱敏和 M1 主体子范围具有单元证据；显式 5xx、异常日志脱敏和跨模块审计强类型桥接仍未关闭。D2～D4 尚未完成。<br>
> 主责模块：M7；协作模块：M0、M1  
> 关联记录：`2026-08-13-010-module-progress-audit`、`2026-08-13-011-m1-local-identity-http`、`2026-08-13-012-m0-m1-deployment-audit`、`2026-08-14-013-m0-m1-public-integration-gates`、`2026-08-17-016-stage0-contract-alignment`、`2026-08-17-017-m0-foundation-hardening`、`2026-08-17-018-current-document-baseline-closure`、`2026-08-17-019-d1-2-production-contract-closure`

本文中的状态和证据均为复核日快照，不是动态状态入口；后续最新记录、实际 migration head 和功能状态只更新现行需求追踪矩阵及修改日志。只有部署门禁、公共端口、拓扑或接入顺序改变时才修改本方案。

## 1. 目的与判定口径

本方案回答两个问题：

1. 当前 M0/M1 是否已经部署到可供后续模块安全接入的程度；
2. 后续 M2～M7 应通过哪些稳定端口接入，避免重复实现、修改共享文件或扩大旧原型的安全边界。

本文中的“可启动”只表示进程和页面能够运行；“代码已搭建”只表示实现文件存在；只有真实 PostgreSQL、代理、Windows Service、安全/并发、备份恢复、强制 Windows/Ubuntu CI 和系统接口闭环全部验证后，才能标记为“部署完成”或“生产可用”。

## 2. 记录 019 部署检查快照

### 2.1 总体结论

| 状态对象 | 实现状态 | 证据与未关闭边界 |
| --- | --- | --- |
| M0 公共代码的已覆盖子契约 | 单元已验证 | 严格环境枚举、未捕获异常脱敏、OpenAPI 通用 500 声明、CORS `ETag`、强类型 readiness、旧表面保护和 outbox 写端口有进程内/契约测试；真实 PostgreSQL/代理/浏览器未验收 |
| M0 显式 5xx 与异常日志脱敏 | 代码已搭建 | `HTTPException`/`AppError` 处理器及异常日志调用存在，但记录 019 未覆盖显式 5xx；原始 message/details 和异常文本仍可能泄漏 |
| M1 本地账户与审计代码 | 单元已验证 | 登录、会话/CSRF、用户/角色、审计、双桶限流、受管服务身份、实例激活边界和 identity readiness 有进程内测试；`0006` 仅完成离线 SQL 检查，真实 PostgreSQL 未验收 |
| M1 跨模块审计主体桥接 | 已设计 | `AuthenticatedActor` 值对象和低层 `AuditWriter` 分别存在；`AuditEventInput` 仍接受裸 ID 与任意 metadata，事件级白名单 DTO 未搭建 |
| 本机兼容原型运行 | 代码已搭建 | Uvicorn、旧 JSON API 和构建后的前端可运行；这不是生产部署或 M1 集成证据 |
| M0/M1 PostgreSQL 16 在线验收 | 未开始 | 本机无 PostgreSQL 服务、`psql`、Docker 和 `M1_TEST_POSTGRES_URL`；3 项在线测试跳过 |
| Windows 生产服务目标 | 已设计 | `deploy/windows/` 当前无 Service、安装/升级/诊断/卸载或生产配置工件 |
| Linux CI 适配目标 | 已设计 | 没有 Ubuntu CI；systemd 为可选交付物，历史 Linux/LoongArch 文档不是当前证据 |
| M6 认证前端目标 | 已设计 | 当前前端仍调用旧 `/api`，无登录路由、权限 store、CSRF/v1 客户端 |
| 生产旧入口应用层隔离代码 | 单元已验证 | `disabled` 模式进程内返回 404；旧路由/挂载、代理拒绝和物理退役仍未完成 |

因此可以继续进行后续模块的契约 Mock 和私有领域开发，但显式 5xx/日志脱敏、审计强类型桥接及 D2 仍是生产写联调前置；不允许宣称 M0/M1 已部署，也不允许 M2/M3/M5 生产写路由把当前 M1 当作已经验收的真实依赖。

### 2.2 分批验证证据

- 2026-08-17、提交 `7016029`、记录 017：后端 `259 passed, 25 skipped`，其中 M1 真实 PostgreSQL 3 项和外部手册 22 项跳过；前端构建成功但有约 1.05 MB 大 chunk 警告；两种包导入路径均发现 15 个 v1 操作（14 个唯一路径）；`alembic heads` 返回 `20260814_0005`。这组证据只支持“单元已验证”。
- 2026-08-17、记录 019 验证快照：D1.2 增加全部 v1 操作的通用 500 OpenAPI 声明、固定受管服务身份、非空数据库审计主体、实例生命周期和独立激活 CLI；当时 migration head 为 `20260817_0006`，离线 upgrade/downgrade SQL 与对应单元/契约测试通过。该证据不证明显式 `HTTPException`/`AppError` 5xx 已脱敏，也未连接真实 PostgreSQL。
- 2026-08-14、记录 013：占位 PostgreSQL URL 下离线 `upgrade 20260814_0005 --sql` 成功；真实 Uvicorn 烟测得到 `/api/v1/health/live=200`、开发可选依赖模式的 `/api/v1/health/ready=200`、前端首页 `200`、M1 登录 `503 DEPENDENCY_UNAVAILABLE`。该证据未在记录 017 重跑，不得描述为 2026-08-17 本轮结果。
- 2026-08-17、记录 017：进程内验证 `APP_DATABASE_REQUIRED=false` 不能把生产 PostgreSQL 降为可选；缺幂等密钥、HTTPS 来源、身份配置或目标关键 contributor 时 `/api/v1/health/ready=503 DEPENDENCY_UNAVAILABLE`。
- 旧 `production_readiness_check.py` 的 7 项离线 mock 原型检查只覆盖旧 JSON/mock 链路；无论何时通过都不是 M0/M1 生产就绪证据。

### 2.3 记录 019 复核机器与配置差距

| 项目 | 当前状态 | 目标/处理 |
| --- | --- | --- |
| 后端虚拟环境 | 存在，Python 3.12.7；记录 013 曾验证 `pip check`，记录 017 未重跑 | Windows 产品基线重建为 Python 3.11.x；当前环境只作开发验证 |
| Node/npm | Node 22.17.1、npm 10.9.2 | 满足当前前端构建要求 |
| PostgreSQL 16 | 未安装/未发现服务和 CLI | M7 提供一次性或明确独占的集成测试数据库，并与正式运行数据库严格分离 |
| Docker | CLI 不存在 | 容器不是 Windows 基础版前置；不能用当前 Dockerfile 代替 M0/M1 验收 |
| `.env` | 存在，但只有旧原型配置；M0/M1 数据库、认证和幂等密钥均缺失 | 新增独立产品配置初始化/预检；不得让旧 `init-config.ps1` 覆盖产品配置 |
| 前端 `dist` | 本轮构建成功 | 作为可重建工件，不作为 M1 前端接入完成证据 |
| CI | `.github/` 不存在 | M7 增加 Windows/Ubuntu CI 和 PostgreSQL 16 服务 |

## 3. 已发现的部署与后续冲突

| 级别 | 冲突 | 后续风险 | 解决方向 |
| --- | --- | --- | --- |
| P0（代码层已关闭） | 生产环境曾允许 `APP_DATABASE_REQUIRED=false`；数据库不健康可能 `ready=200` | Service/代理误收流量 | `database_is_required` 已固定生产必需，进程内 503 测试通过；真实数据库中断/恢复仍待 D2/D3 |
| P0（代码层已关闭） | `api/v1/system.py` 曾直接导入 M1 | 后续 contributor 会造成反向依赖和共享文件热点 | M0 聚合器和固定注册表已实现；领域只返回无 `required` 字段的 `ReadinessProbe` |
| P0（部分关闭） | 旧 `/api`、`/uploads`、`/knowledge` 可绕过 M1 | 即使 v1 有认证，系统整体仍不满足 AUTH-01/02/03 | 应用层 guard 已验证且生产只允许 disabled；物理移除、代理拒绝和真实部署验收仍待 M2/M7 |
| P0 | 无真实 PostgreSQL 在线迁移、触发器、锁/并发和 API 集成 | 无法证明审计不可变、最后管理员、限流和会话失效 | 建立一次性或明确独占、显式 opt-in 的 `*_test` 数据库验收流水线，先于 M2/M3/M5 真实接入 |
| P0（声明层已关闭） | OpenAPI 曾缺少通用 `INTERNAL_ERROR/500` 声明 | M6 生成的客户端无法获得公共错误类型 | v1 根路由已统一声明公共错误模型并由契约测试覆盖；该结论只涉及 OpenAPI，不代表所有运行时 5xx 已脱敏 |
| P0 | 显式 `HTTPException`/`AppError` 5xx 仍可能返回原始 message/details，异常日志也没有统一敏感值过滤 | 密钥、令牌、连接串或服务器路径可能进入响应或普通日志 | 所有显式 5xx 统一为固定 `INTERNAL_ERROR`、固定安全消息和空 details；日志只保留 request ID 与脱敏诊断，增加响应及日志回归测试 |
| P0（M1 主体子范围已关闭） | AUTH-13 曾缺少受管服务用户和生产激活前 bootstrap 边界 | 登录失败记账、Worker 或 bootstrap 可能缺少合规用户身份 | 固定服务身份、数据库审计主体约束、实例状态、bootstrap/activation 已单元验证；真实数据库行为待 D2 |
| P0 | `AuthenticatedActor` 尚未接入 `AuditEventInput`，通用 Writer 仍接受裸 ID 和任意 metadata | M2/M3/M5 可能绕过认证主体值对象或把请求体写入审计 | 在业务真实接入前冻结 actor 到审计输入的强类型桥接及事件级 metadata 白名单；领域不得自建系统 actor |
| P1 | 旧 `init-config.ps1` 只生成 Provider/mock 配置，并覆盖 `.env` | 部署人员可能误以为已经生成 M0/M1 安全配置 | 保留为旧演示脚本；产品配置使用 `deploy/windows/config/application.env.example`、外部密钥注入和 `preflight.ps1`，不承诺自动生成密钥的 `configure.ps1` |
| P1 | `start-backend.ps1` 使用 `--reload`，缺环境时调用含机器路径假设的旧 Anaconda 脚本 | 不能作为 Windows Service 或可移植安装入口 | M7 创建无 reload、固定 3.11 运行时、显式配置文件的 Service 启动工件 |
| P1 | 当前 Dockerfile 设置 production、mock Provider 和 `APP_LEGACY_SURFACE_MODE=disabled`，却不提供 PostgreSQL、认证/幂等密钥或可信来源；旧前端仍依赖被关闭的 `/api` | 容器不会形成可用整链，readiness 应失败；不能把“旧入口已关闭”误写成容器可交付 | 标为历史/开发容器；产品容器必须接入 PostgreSQL、v1 前端和同一 preflight/配置契约后另行验收 |
| P1（写端口子范围已关闭） | M0 原有 outbox 表缺公共 Writer 和版本/请求字段 | M2/M3/M5 直接写 M0 ORM，M4 复制消费者实现 | `OutboxWriter`、不可变结果和 `0005` 已搭建；只有满足事件目录“生产启用门禁”的事件才可在对应环境使用，当前没有；M4 claim/lease 仍须单独设计 |
| P1 | M2、M3 若并行创建相同后继迁移会形成 Alembic 多头 | 合并时修改历史迁移或产生不可预测升级顺序 | 领域模型可并行；正式迁移前执行 `alembic heads`，revision 由 M0 集成人员基于当次最新 head 串行编号/重定向 |
| P2 | 前端尚无 M1 登录与 CSRF 客户端 | 不能执行真实浏览器认证验收 | M6 依据冻结 OpenAPI/DTO 开发，不解析 Cookie 内部格式 |

## 4. 目标部署拓扑

### 4.1 Windows 默认拓扑

```text
Browser
  -> HTTPS reverse proxy (Caddy reference profile; only trusted proxy CIDRs)
     -> API Windows Service (FastAPI/Uvicorn, one process initially)
        -> PostgreSQL 16
        -> controlled data directory outside program files
     -> Worker Windows Service (M4 delivered later)
```

- Windows Server 2022 x64、Python 3.11.x、PostgreSQL 16 为验收基线。
- Caddy 是默认参考代理和静态前端配置；IIS 只作为另行完成配置、安全、客户端地址和真实代理链验收后的可选等价适配，不要求同时交付两套默认配置。
- API 与 Worker 使用独立最小权限系统账户；程序目录只读，日志、上传、知识文件和备份位于受控数据目录。
- 数据库迁移是安装/升级的独立步骤，只运行一次，不在每个 Uvicorn/Worker 进程启动时自动执行。
- 首个管理员只通过 M1 bootstrap CLI 创建；没有默认密码、HTTP 注册或匿名 bootstrap。
- 初期保持单 API 进程，待旧 JSON 存储全部迁移、数据库并发和多进程测试通过后再评估多 worker。

### 4.2 首次引导与受限 provisioning

生产 identity 在实例达到 `active` 前必须保持 `/api/v1/health/ready=503`，但 API 进程仍应运行且 `/api/v1/health/live=200`。代理或 Service 包装器不得因为 ready=503 而让首次管理员无法完成必须经过 HTTP 的登录和改密。

`bootstrapped` 阶段只允许可信管理来源访问：

```text
目标前端的首次设置页及其静态资源
/api/v1/auth/login
/api/v1/auth/me
/api/v1/auth/csrf
/api/v1/auth/password
/api/v1/auth/logout
```

其他业务 API、下载路径和全部旧表面继续阻断。管理员完成改密后运行 activation CLI；实例进入 `active` 且完整 readiness 健康后，代理才开放正常业务流量。`install/status` 必须把未激活实例报告为“provisioning 未完成”，不得报告安装成功或生产就绪。上述代理规则、M6 设置页和完整流程必须在 D3/D4 形成真实 E2E 证据；当前代码存在认证端点不等于该部署流程已完成。

### 4.3 跨平台适配

- 业务模块只消费环境变量、文件存储端口、SQLAlchemy Session 和领域接口，不依赖盘符、PowerShell、Windows 用户名或注册表。
- `deploy/windows/` 拥有 PowerShell/Service 包装；可选 `deploy/linux/` 只拥有 shell/systemd 包装。两者必须复用相同的 `APP_*` 配置语义、`get_settings()`/foundation readiness、Alembic、bootstrap 和健康接口，并通过共享验收用例证明语义一致；本方案不预设尚不存在的第二套 preflight 实现。
- 路径由 `pathlib` 和显式 `APP_*_DIR` 配置处理；配置示例分别给 Windows/Linux 路径，但字段语义一致。
- 容器、systemd 和 Windows Service 不得各自创建不同的认证、迁移或 readiness 规则。

## 5. 为避免后续冲突需要冻结的接口

### 5.1 M0 公共接口

后续模块可以依赖，不能复制或修改其语义：

```text
app.core.contracts              v1 success/error/page envelope
app.core.pagination             encode_cursor / decode_cursor
app.core.concurrency            ETag / If-Match
app.core.trusted_origins        browser Origin/Referer validation
app.core.client_address         trusted proxy client address
app.db.session                  new_session / get_session
app.db.idempotency              IdempotencyService / request_fingerprint
app.api.v1.domain_registry      fixed optional route discovery
app.db.domain_models            fixed optional ORM discovery
```

M0 写端口本身已经搭建；提议或仅冻结阶段可依赖它编写生产者契约测试，但只有满足事件目录“生产启用门禁”的领域事件，才允许对应环境的生产路径实际调用该端口。记录 019 时点尚无此类目标领域事件：

```python
@dataclass(frozen=True)
class OutboxEventInput:
    event_type: str
    aggregate_type: str
    aggregate_id: str
    version_id: str
    request_id: str
    occurred_at: datetime
    payload: Mapping[str, object]

@dataclass(frozen=True)
class OutboxAppendResult:
    event_id: str

class OutboxWriter:
    def append(
        self,
        session: Session,
        event: OutboxEventInput,
    ) -> OutboxAppendResult: ...
```

`OutboxWriter` 只追加到调用方事务，不 commit；返回值只暴露不可变事件 ID，不返回 ORM 实体。未满足事件目录生产启用门禁的事件不得进入对应环境的生产 outbox。M2/M3/M5 不导入 `db.models.OutboxEvent`，M4 通过单独的 `OutboxClaimPort` 领取，不复用写端口修改领域状态。

### 5.2 M1 公共接口

后续业务模块已经可以依赖的身份/权限子契约为：

```text
app.domains.identity.CurrentUser
app.domains.identity.AuthenticatedActor（值对象已存在；审计输入桥接尚待冻结）
app.domains.identity.Permission / RoleCode（只读基线）
app.domains.identity.dependencies.get_current_user
app.domains.identity.dependencies.require_permissions
app.domains.identity.authorization.ensure_not_self_review
app.domains.audit.AuditWriter（低层追加端口；跨模块强类型输入尚待冻结）
```

- Route 层使用 `get_current_user()`/`require_permissions()`；Service 层显式接收 `CurrentUser`，不依赖 FastAPI Request。
- `AuditWriter` 与领域状态和必要幂等记录在同一 `new_session()` 事务中写入；只有满足事件目录生产启用门禁的操作才在启用环境的该事务追加 outbox。
- M2～M5 不导入 M1 `models.py`、`repository.py`、Cookie、会话令牌、节流或密码实现。
- 普通业务的用户 ID、审核人、角色和权限只来自服务端 `CurrentUser`；请求 DTO 不再接受 `reviewer`、`actorId` 或角色声明决定授权。内部任务使用 M1 创建的 `AuthenticatedActor` 表示受管服务用户，并在异步延续时保留 `initiator_user_id`；M2/M3/M5 不得另造主体类型或固定 UUID。
- 当前 `AuditEventInput` 仍接受裸 `actor_user_id`、`initiator_user_id` 和任意 metadata。M2/M3/M5 接入真实生产写事务前，M1 必须冻结从 `AuthenticatedActor` 生成审计输入的强类型桥接，并为每类事件提供 metadata 白名单 DTO/构造器；通用按键名脱敏只能作为最后防线，不能替代该门槛。
- `CurrentUser` 若将来增加站点/设备范围，必须版本化公共契约并更新所有消费者测试，不能让领域模块各自附加属性。

### 5.3 路由、模型和迁移所有权

- M2 只新增 `api/v1/documents.py`、`knowledge.py` 与 `domains/documents|knowledge/`。
- M3 只新增 `api/v1/devices.py`、`workflows.py` 与 `domains/devices|workflows/`。
- M4 只新增 `workers/`、`indexing/` 和已经由 M0 注册表预留的 `api/v1/operations.py`；该路由拥有任务状态、dead-letter、受权手工重试和索引运行状态。M5 只新增 `api/v1/search.py`、`rag.py` 与 `domains/rag/`，查询图片的 `RagQueryAttachment` 元数据和生命周期也归 M5，不写 M2 私表。
- 上述模块名已在 M0 注册表预留，领域团队不得编辑 `api/v1/router.py`、`db/domain_models.py` 或把业务代码写入 `main.py`。
- 记录 019 验证时的单一 migration head 为 `20260817_0006`；它已经过离线 SQL 生成检查，尚未完成真实 PostgreSQL 在线验收。该值只是历史证据，不是永久“当前 head”。领域模型和测试可以并行；正式 revision 前先执行 `alembic heads`，基于执行时最新 head 串行生成。任何人不得修改已经登记或应用的历史 revision；`0001`～`0006` 均按历史 revision 保护，后续只能新增后继迁移。

## 6. Readiness 无冲突扩展设计

### 6.1 问题

原实现中 `system.py` 直接依赖 M1；本批已移除该反向依赖。后续数据库、文件目录、Worker、索引或 Provider 继续通过注册表扩展，禁止重新写入 `system.py`。

### 6.2 接口

M0 新增 `core/readiness.py`：

```python
@dataclass(frozen=True)
class ReadinessDetails:
    configured: bool | None = None
    dialect: str | None = None
    mode: str | None = None
    latency_ms: int | None = None
    violations: tuple[str, ...] = ()

@dataclass(frozen=True)
class ReadinessProbe:
    healthy: bool
    reason: str = ""       # 只能是脱敏摘要
    details: ReadinessDetails = field(default_factory=ReadinessDetails)

class ReadinessContributor(Protocol):
    def check(self, settings: AppSettings) -> ReadinessProbe: ...
```

M0 拥有固定发现列表；开发环境可跳过未交付模块，但生产环境八类目标模块均为必需：

```text
domains.identity.readiness   M1
domains.documents.readiness  M2
domains.knowledge.readiness  M2
domains.devices.readiness    M3
domains.workflows.readiness  M3
workers.readiness            M4
indexing.readiness           M4
domains.rag.readiness        M5
```

领域只新增自己的 `readiness.py` 并返回脱敏结果；详情必须遵守 M0 公共契约第 7.1 节的字段、JSON 名称和精确允许值，不得返回任意映射、连接串、URL、文件路径、密钥、原始异常或堆栈。它不能返回或降低 `required`，必需策略由 M0 `ReadinessRegistration` 独占。`system.py` 只调用 M0 聚合器，不导入任何领域模块。开发环境未交付模块可跳过；生产必需但缺失的模块报告不健康；已存在模块内部导入错误必须直接失败，规则与路由/模型发现一致。

### 6.3 目标生产不变量与当前覆盖

当 `APP_ENV=production` 时：

- PostgreSQL 始终 `required=true`；`APP_DATABASE_REQUIRED=false` 不能把它降为可选。
- `APP_DATABASE_URL` 必须是 PostgreSQL；连接失败时 ready=503。
- `APP_AUTH_SECRET` 和 `APP_IDEMPOTENCY_SECRET` 至少 32 字节；不返回长度或值。
- Cookie 必须 `Secure` 且使用 `__Host-` 名称。
- `APP_TRUSTED_ORIGINS` 至少包含一个明确 HTTPS origin；禁止通配符。
- 旧兼容表面必须关闭。
- 任一 required contributor 不健康时统一返回 `DEPENDENCY_UNAVAILABLE/503` 和“关键依赖未就绪”，不错误声称只有数据库故障。

受控数据目录位于程序目录之外且可写，是 M7 `preflight.ps1` 的目标发布门槛；当前 M0 `evaluate_foundation_readiness()` 尚未检查该条件。完成对应代码和测试前，不得把数据目录要求列为 D1 已验证生产不变量。

`APP_ENV` 仅允许 `development|test|production`，未知值失败关闭。`live` 只表示进程存活，不检查外部依赖；规范路径 `/api/v1/health/ready` 决定正常业务流量是否可接收，Windows/Linux 包装层不得实现另一套健康语义。唯一例外是第 4.2 节明确限定的 `bootstrapped` provisioning 路由：它不把 ready=503 解释为生产就绪，只为完成改密和激活保留受限管理通道。

## 7. 旧原型表面隔离设计

M0 新增生产兼容保护配置，建议字段为：

```text
APP_LEGACY_SURFACE_MODE=enabled|loopback|disabled
```

- development 默认 `enabled`，用于迁移期旧前端。
- test 必须由测试显式选择，避免隐藏依赖。
- production 默认且只允许 `disabled`；拒绝旧 `/api`（不含 `/api/v1`）、`/uploads` 和 `/knowledge`。
- 保护在 M0 中间件/装配层执行，不要求 M1、M2 或 M3 为每条旧路由增加权限判断。
- M2 完成受控下载和 v1 迁移后删除静态挂载；M7 的反向代理同时保留拒绝规则，形成纵深防御。

该保护现已通过进程内测试，但旧挂载尚未物理移除、反向代理规则尚未验收；因此 M0/M1 仍不能据此宣称完整系统已对外部署。

## 8. 已有代码协作项与待建部署/测试工件

### 8.1 M0/M1 代码协作项

| 所属模块 | 文件/接口 | 目的 | 冲突规避 |
| --- | --- | --- | --- |
| M0 | `core/readiness.py`、`tests/test_module0_readiness.py` | contributor、生产不变量、聚合 503 | 后续领域不修改 `system.py` |
| M0 | `api/v1/system.py` | 只消费 readiness 聚合器 | 移除对 M1 的直接导入 |
| M1 | `domains/identity/readiness.py` | 校验认证模式和密钥，Cookie 生产不变量由配置层统一校验 | 只返回脱敏 `ReadinessProbe`，无权设置 required |
| M0 | `core/legacy_surface.py`、配置和测试 | 生产关闭旧 API/静态目录 | 不把阻断逻辑散落到旧路由 |
| M0 | `db/outbox.py`、契约测试 | 冻结领域写入端口 | M2/M3/M4/M5 不直接操作 M0 ORM |

以上文件均已创建并通过对应进程内/契约测试；D1.2 另已补齐 OpenAPI 通用 500、AUTH-13 受管主体、实例激活边界及 `0006` 后继迁移，对应实现状态仍为“单元已验证”。数据目录 preflight、真实 PostgreSQL、代理、Windows Service 和浏览器验收仍未完成。

### 8.2 M7 Windows 工件

```text
deploy/windows/
  config/application.env.example
  proxy/caddy/Caddyfile.example
  proxy/iis/README.md              # 可选适配，不属于默认配置
  preflight.ps1
  migrate.ps1
  bootstrap-admin.ps1
  install.ps1
  start.ps1
  stop.ps1
  status.ps1
  upgrade.ps1
  rollback.ps1
  backup.ps1
  restore.ps1
  diagnose.ps1
  uninstall.ps1
  service/
```

- Caddy 配置是默认参考工件；IIS 目录只说明可选适配和独立验收条件，不得让安装程序同时修改两种客户代理。
- `preflight.ps1` 检查 Windows/Python/PostgreSQL 版本、端口、数据目录、配置项存在性和密钥长度，并复用应用配置/readiness语义；只输出布尔状态，不输出密钥或完整连接串。
- `migrate.ps1` 使用临时注入的迁移账户连接串执行 Alembic；Service 运行账户使用单独的最小 DML 账户。
- `install/upgrade/rollback` 在变更前备份数据库与文件，记录应用版本和迁移 head；失败时停止流量并恢复，不自动降级含不可逆业务数据的迁移。
- Service 启动不使用 `--reload`，不调用 Anaconda 引导脚本，不在启动时自动生成配置或迁移数据库。

### 8.3 集成测试工件

建议由 M7 建立 `tests/integration/m0_m1/`，领域现有 `test_m1_*` 仍由 M1 维护：

| 测试层 | 必须覆盖 |
| --- | --- |
| 迁移 | 空库 upgrade 到 head、角色种子、约束/索引/触发器、受控 downgrade、重复 upgrade |
| M0 | 未捕获及显式 5xx 响应/日志脱敏、PostgreSQL 中断/恢复、连接池超时、production readiness、可信代理链、旧表面禁用 |
| M1 | bootstrap 单次/并发、登录成功/失败、独立双桶并发、Cookie/CSRF、改密和会话失效 |
| 权限 | 无认证 401、权限不足 403、临时密码限制、最后管理员并发保护、审计只读 |
| 原子性 | 用户安全变更、审计和幂等同事务；失败全部回滚；幂等重放不重复写 |
| 浏览器 | 同源/跨源、Secure `__Host-` Cookie、CSRF、缓存头、注销清 Cookie，以及 bootstrapped 阶段受限 provisioning 到 active 的完整流程 |

破坏性迁移测试必须使用一次性或经人工确认独占的测试数据库，并要求显式 opt-in；数据库名以 `_test` 结尾只作为第二道保护，不能证明数据库独占。记录 019 时点的测试夹具只检查 PostgreSQL 类型和 `_test` 后缀，尚未自动证明独占性，因此不得直接指向共享测试库。测试前后校验目标，禁止连接生产数据库；在线测试失败时保留脱敏日志和 schema 版本，但不得输出密码、令牌、密钥、完整连接串或服务器绝对路径。

## 9. 部署与验收顺序

```text
D0 2026-08-17 / 7016029 历史代码里程碑
  -> D1 M0 readiness + 旧表面 + outbox 公共端口（单元已验证）
  -> D1.1 现行文档/追踪矩阵/事件目录收口（文档治理已设计）
  -> D1.2 OpenAPI 通用 500 声明 + AUTH-13 主体/bootstrap/activation 子契约（单元已验证）
  -> P0 显式 5xx/异常日志脱敏 + AuthenticatedActor 审计桥接
  -> D2 PostgreSQL 16 在线迁移与 M1 集成/并发验收
  -> D2A 允许 M2/M3/M5 后端写路由接入真实 M1（仍须满足各自业务上游和冻结事件门槛）
  -> D3 Windows Service、Caddy、配置、provisioning、备份恢复及 Windows/Ubuntu CI
  -> D4 全产品浏览器/故障/恢复/安全/性能验收与发布
```

### D0：历史基线里程碑

- 2026-08-17、提交 `7016029` 的基线为 `20260814_0005` 单一 head、15 个 v1 操作（14 个唯一路径）和 `259 passed, 25 skipped`。
- 允许 M2/M3/M5/M6 使用版本化 Mock 并行开发。

### D1/D1.1：公共代码单元验证与文档基线收口

- 记录 013、016、017 已搭建并单元验证 readiness contributor、当前代码已覆盖的生产不变量、旧表面保护和 `OutboxWriter`。
- M1 `AuditWriter` 返回不可变结果；OpenAPI 已声明 Cookie、CSRF、匿名面、权限扩展及通用 500 响应模型。该声明不证明显式运行时 5xx 或异常日志已经脱敏。
- `0005` 未修改 `0001`～`0004`；真实在线升级不属于本阶段证据。
- 记录 018 收口现行追踪矩阵、事件目录、状态、证据来源和后续执行顺序。

### D1.2：生产契约补缺（单元已验证）

1. v1 根路由已统一声明通用 500 响应和公共错误模型，契约测试覆盖全部 v1 操作。
2. M1 已实现固定受管服务用户、登录失败记账主体、非空审计 actor、可选发起用户、生产激活前 bootstrap 和独立 activation 边界。
3. `20260817_0006` 已完成离线 upgrade/downgrade SQL 检查；真实约束、触发器、种子、锁、并发与回滚行为仍由 D2 在线验证，D1.2 不据此提升到“集成已验证”。
4. M6 可把该 OpenAPI 声明作为公共错误类型输入；M2/M3/M5 必须复用 `AuthenticatedActor`/受管服务账户目录，不自行实现系统 actor。显式运行时 5xx 和 actor 到审计输入的桥接不属于记录 019 已验证范围。

### P0：真实联调前的契约修正

1. 所有显式 `HTTPException`/`AppError` 5xx 统一返回固定 `INTERNAL_ERROR`、固定安全消息、空 details 和 request ID；受控 503 仅保留经过白名单化的稳定契约。
2. 异常日志不得记录密码、密钥、令牌、完整连接串或服务器绝对路径；保留 request ID、受控错误类别和必要的脱敏诊断。
3. `AuthenticatedActor` 必须通过强类型桥接进入审计输入，每类事件使用 metadata 白名单 DTO/构造器；M2/M3/M5 不直接传裸 actor ID 或任意请求体。
4. 上述缺陷修复必须增加能在旧实现上失败的响应、日志和审计输入回归测试，并新增修改日志；完成前不允许真实业务写路由联调。

### D2：真实 PostgreSQL 验收

1. 创建一次性或明确独占、显式 opt-in 且名称以 `*_test` 结尾的数据库和最小权限账户；后缀不能替代独占确认。
2. 执行 `alembic heads`，记录实际 revision，再在线 `upgrade head`，检查 `0006` 实例状态/服务用户/审计主体变更以及 outbox 字段、表、种子、唯一约束和审计不可变触发器。
3. 在 AUTH-13 与生产激活前 bootstrap 契约完成后执行 bootstrap，运行 M1 API、事务、锁和并发测试。
4. 在隔离库验证受控 downgrade/再 upgrade；记录可逆性和数据影响。
5. 只有全部通过后，才能把“M1 PostgreSQL 16集成边界”升级为“集成已验证”；这不代表浏览器、代理、部署或整个 M1 已完成，旧入口未物理退役前也不能标“系统完成”。

### D3：Windows 部署验收

- 使用生产配置运行 preflight、迁移、API/Worker Service 安装和默认 Caddy HTTPS 代理；IIS 只有另行完成同等验收后才可替换默认配置。
- 验证重启恢复、正常业务 ready 摘流、受限 provisioning、日志脱敏、备份/恢复、升级/回滚和卸载。
- Windows 与 Ubuntu Server 24.04 LTS CI 都是发布强制门禁，并执行后端测试、前端类型检查/构建和核心 E2E；任何非预期 skip 或失败阻止发布。Linux生产发行包、systemd和OCI容器仍为可选交付物，不阻塞Windows基础版。

### D2A/D4：领域接入与全产品发布

- P0审计桥接和D2均通过后，M2/M3/M5后端写路由才可从身份Mock切换到真实`CurrentUser`/`AuthenticatedActor`/`AuditWriter`；只有满足事件目录生产启用门禁的事件才在对应环境使用`OutboxWriter`，当前提议事件不能发布。后端领域接入不错误等待Windows Service或M6页面，但仍等待自己的上游契约。
- D4不等于M6登录页面验收。产品发布还必须覆盖M2～M5核心业务E2E、受限provisioning、Provider/Worker/数据库故障、索引恢复、授权与越权、安全降级、备份恢复、性能目标，以及Windows/Ubuntu强制流水线。

## 10. 并行开发与合并条件

| 模块 | 现在可以并行 | 必须等待 | 禁止事项 |
| --- | --- | --- | --- |
| M0 | 已验证子契约可继续使用；可设计 M4 claim 端口并修复显式 5xx/日志脱敏 | P0 回归和 D2 在线验证 | 不把 OpenAPI 声明外推为运行时脱敏；不加入领域业务；不修改 `0001`～`0006` |
| M1 | 主体/bootstrap/activation 子范围已有单元证据；可补审计强类型桥和 PostgreSQL 集成测试 | P0 actor桥接及D2在线验收 | 不暴露裸ID审计门面给M2/M3/M5；不修改M0 root router/readiness聚合器 |
| M2 | 领域模型、DTO、Service、存储端口和身份/outbox Mock 测试 | P0+D2 后接真实写路由；迁移基于执行时最新 head | 具体文件/解析实现放基础设施适配层；不扩展旧 `knowledge.py`/静态下载；不导入 M1 ORM/Repository |
| M3 | 设备/流程领域和 Mock 测试 | D2 后接真实身份；迁移基于执行时最新 head | 不默认绑定流程；不修改 M2 表 |
| M4 | claim/lease 接口实现、事件 handler/去重/重放及 `api/v1/operations.py` 契约 | M0 claim 端口和生产者提议的 schema/样例；M4 完成可定位 handler 后登记为实际消费者，与生产者共同促成事件冻结和生产启用门禁 | 不轮询/修改 M2/M3/M5 私有表；未满足事件目录生产启用门禁前不作生产输入 |
| M5 | 基于版本化只读Mock重构证据/安全规则，并定义自有查询附件端口 | M2/M3 read port、M4索引状态 | 不查询其他领域ORM，不把查询图片写入M2私表；mock不进入生产 |
| M6 | 按已冻结Cookie/CSRF/权限和OpenAPI声明开发Mock客户端 | P0/D2/D3后做真实浏览器及provisioning E2E | 不把OpenAPI声明当运行时已验证；不解析Cookie或传reviewer/actor/roles决定授权 |
| M7 | PostgreSQL、Windows工件、强制双平台CI、Caddy、provisioning和备份测试 | 各模块公开契约 | 不在脚本复制领域逻辑；不把旧mock readiness或可选Linux发行包当发布证据 |

合并共同门槛：

1. 每个逻辑变更有模块归属、本地日志、测试证据和回滚说明；
2. 公共契约变化由 M0 评审，消费者测试同批更新；
3. migration 创建前重查 head，正式编号串行集成；
4. 不修改其他模块私有目录；跨模块需求优先新增公开端口或事件；
5. `git diff --check`、模块测试、双导入路径和 OpenAPI 装配检查通过；
6. 缺真实依赖、存在 skip 或旧入口未关闭时，功能状态不得标记为“已完成”，产品也不得描述为“生产可用”。

## 11. D2 最低进入条件

记录 013、016、017、018、019 只保存各自时点的子范围证据，不构成动态“下一批”状态。执行 D2 时至少满足：

1. M7 建立一次性或明确独占、显式 opt-in、名称以 `*_test` 结尾的 PostgreSQL 16 数据库和最小权限账户；
2. 运行 `alembic heads` 并记录执行时实际 revision，在线空库 `upgrade head`、受控 downgrade/再 upgrade，核对实际迁移链、outbox、限流和审计触发器；
3. M1 执行 bootstrap、HTTP改临时密码、activation、受限provisioning、API、锁/并发、事务回滚和数据库中断/恢复测试；
4. 显式5xx/异常日志脱敏和`AuthenticatedActor`审计桥接可以与D2环境准备并行，但必须在M2/M3/M5真实生产写路由联调前关闭；
5. D2和P0均通过后，M2/M3/M5才接入真实身份/审计端口，并且只为满足事件目录生产启用门禁的事件在对应环境调用outbox写端口；此前继续使用公开契约Mock；
6. M7持续实现Windows Service/Caddy/provisioning/备份恢复和Windows/Ubuntu CI；M6可并行开发Mock页面，但真实发布验收遵守D4全产品门槛。

后续模块不得重复创建 readiness 聚合器、旧路由守卫或 outbox 写端口，也不得修改任何已经登记或应用的历史 revision。M4 的 `OutboxClaimPort` 是尚未搭建的新端口，需由 M0 另行冻结。
