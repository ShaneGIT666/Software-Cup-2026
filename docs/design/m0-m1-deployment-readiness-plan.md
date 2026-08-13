# M0/M1 部署复核与后续无冲突接入方案

> 复核日期：2026-08-13  
> 文档状态：设计已形成，实施与真实依赖验收未完成  
> 主责模块：M7；协作模块：M0、M1  
> 关联记录：`2026-08-13-010-module-progress-audit`、`2026-08-13-011-m1-local-identity-http`、`2026-08-13-012-m0-m1-deployment-audit`

## 1. 目的与判定口径

本方案回答两个问题：

1. 当前 M0/M1 是否已经部署到可供后续模块安全接入的程度；
2. 后续 M2～M7 应通过哪些稳定端口接入，避免重复实现、修改共享文件或扩大旧原型的安全边界。

本文中的“可启动”只表示进程和页面能够运行；“代码已搭建”只表示实现文件存在并通过对应层级测试；只有真实 PostgreSQL、代理、Windows Service、安全/并发、备份恢复和系统接口闭环全部验证后，才能标记为“部署完成”或“生产可用”。

## 2. 当前部署检查结论

### 2.1 总体结论

| 范围 | 当前判定 | 说明 |
| --- | --- | --- |
| M0 代码装配 | 代码已搭建、进程内已验证 | v1 信封、错误、请求 ID、分页、ETag、CORS/可信来源、短事务、DB 503、可信客户端地址、幂等、路由/模型发现均已有代码 |
| M1 代码装配 | 代码已搭建、进程内已验证 | 本地登录、会话/CSRF、用户/角色、审计、双桶限流、bootstrap 和 13 条 v1 路由已装配 |
| 本机兼容运行 | 可启动，不等于 M0/M1 部署 | Uvicorn、旧 JSON API 和构建后的前端可运行；M1 登录因数据库/密钥未配置而失败关闭 |
| M0/M1 真实数据库 | 未部署、未验证 | 本机无 PostgreSQL 服务、`psql`、Docker 和 `M1_TEST_POSTGRES_URL`；3 项 M1 PostgreSQL 测试跳过 |
| Windows 生产服务 | 未实现 | `deploy/windows/`、Service 安装/升级/诊断/卸载、生产配置模板均不存在 |
| Linux 适配基线 | 未实现 | 没有 Ubuntu CI 或 systemd 工件；历史 Linux/LoongArch 文档不作为当前产品验收证据 |
| 前端 M1 接入 | 未实现 | 当前前端仍调用旧 `/api`，无登录路由、权限 store、CSRF/v1 客户端 |
| 生产旧入口隔离 | 未实现 | `/api` 匿名写接口以及 `/uploads`、`/knowledge` 静态目录仍存在 |

因此当前允许继续进行后续模块的契约 Mock 和私有领域开发，但不允许宣称 M0/M1 已部署，也不允许 M2/M3 生产写路由直接把 M1 当作已经验收的真实依赖。

### 2.2 本轮实测证据

- 后端完整回归：`239 passed, 25 skipped`；其中 M1 真实 PostgreSQL 3 项跳过，skip 不计为成功。
- 前端生产构建成功并生成 `frontend/dist`；存在约 1.05 MB 单块 JavaScript 警告，属于 M6 后续拆包问题，不阻止本轮兼容烟测。
- Alembic 保持单一 head `20260813_0004`；离线 `upgrade head --sql` 成功；未执行真实数据库在线升降级。
- 两种包导入路径均能发现 15 个 `/api/v1` 路由操作（14 个唯一路径）：2 个健康操作和 13 个 M1 操作。
- 真实 Uvicorn 进程烟测：`/api/v1/health/live=200`、当前可选依赖模式的 `ready=200`、前端首页 `200`、M1 登录 `503 DEPENDENCY_UNAVAILABLE`。
- 生产配置失败关闭烟测：数据库和身份标记为必需且未配置时，`ready=503 DEPENDENCY_UNAVAILABLE`。
- 旧 `production_readiness_check.py` 的 7 项离线 mock 原型检查通过，但它只检查旧 JSON/mock 链路，不是 M0/M1 生产就绪证据。

### 2.3 当前机器与配置差距

| 项目 | 当前状态 | 目标/处理 |
| --- | --- | --- |
| 后端虚拟环境 | 存在，Python 3.12.7，`pip check` 通过 | Windows 产品基线重建为 Python 3.11.x；当前环境只作开发验证 |
| Node/npm | Node 22.17.1、npm 10.9.2 | 满足当前前端构建要求 |
| PostgreSQL 16 | 未安装/未发现服务和 CLI | M7 提供专用集成数据库与正式运行数据库 |
| Docker | CLI 不存在 | 容器不是 Windows 基础版前置；不能用当前 Dockerfile 代替 M0/M1 验收 |
| `.env` | 存在，但只有旧原型配置；M0/M1 数据库、认证和幂等密钥均缺失 | 新增独立产品配置初始化/预检；不得让旧 `init-config.ps1` 覆盖产品配置 |
| 前端 `dist` | 本轮构建成功 | 作为可重建工件，不作为 M1 前端接入完成证据 |
| CI | `.github/` 不存在 | M7 增加 Windows/Ubuntu CI 和 PostgreSQL 16 服务 |

## 3. 已发现的部署与后续冲突

| 级别 | 冲突 | 后续风险 | 解决方向 |
| --- | --- | --- | --- |
| P0 | 生产环境允许 `APP_DATABASE_REQUIRED=false`；只配置认证密钥时，数据库不健康仍可能 `ready=200` | Service/代理把不能登录或写业务的数据节点标为可用 | 生产 readiness 强制 PostgreSQL 为关键依赖；不能由部署人员降为可选 |
| P0 | `api/v1/system.py` 直接导入 M1 `validate_identity_runtime_settings()` | M2/M3/M4/M5 若继续直接修改该文件，会形成反向依赖和多人冲突 | M0 提供可发现的 `ReadinessContributor` 注册端口；领域只新增自己的 readiness 文件 |
| P0 | 旧 `/api`、`/uploads`、`/knowledge` 仍可绕过 M1 | 即使 v1 有认证，系统整体仍不满足 AUTH-01/02/03 | M0/M7 提供生产默认关闭的旧表面保护；M2 迁移完成后删除静态数据访问 |
| P0 | 无真实 PostgreSQL 在线迁移、触发器、锁/并发和 API 集成 | 无法证明审计不可变、最后管理员、限流和会话失效 | 建立专用 `_test` 数据库验收流水线，先于 M2/M3 真实接入 |
| P1 | 旧 `init-config.ps1` 只生成 Provider/mock 配置，并覆盖 `.env` | 部署人员可能误以为已经生成 M0/M1 安全配置 | 保留为旧演示脚本；产品配置由 `deploy/windows/configure.ps1` 单独负责 |
| P1 | `start-backend.ps1` 使用 `--reload`，缺环境时调用含机器路径假设的旧 Anaconda 脚本 | 不能作为 Windows Service 或可移植安装入口 | M7 创建无 reload、固定 3.11 运行时、显式配置文件的 Service 启动工件 |
| P1 | 当前 Dockerfile 设置 production，却不提供 PostgreSQL、认证/幂等密钥、可信来源和旧入口隔离 | 传入部分密钥后可能产生 readiness 误判；默认仍是 mock 业务链 | 标为历史/开发容器；产品容器必须复用同一 preflight 和环境契约后再验收 |
| P1 | M0 已有 outbox 表，但没有公共 `OutboxWriter`/claim 端口 | M2/M3 可能直接写 M0 ORM，M4 可能复制 claim 实现 | M0 在 M2/M3 写服务合并前冻结 outbox 写入和消费端口 |
| P1 | M2、M3 若并行创建相同后继迁移会形成 Alembic 多头 | 合并时修改历史迁移或产生不可预测升级顺序 | 领域模型可并行；迁移 revision 由 M0 集成人员按最新 head 串行编号/重定向 |
| P2 | 前端尚无 M1 登录与 CSRF 客户端 | 不能执行真实浏览器认证验收 | M6 依据冻结 OpenAPI/DTO 开发，不解析 Cookie 内部格式 |

## 4. 目标部署拓扑

### 4.1 Windows 默认拓扑

```text
Browser
  -> HTTPS reverse proxy (IIS/Caddy; only trusted proxy CIDRs)
     -> API Windows Service (FastAPI/Uvicorn, one process initially)
        -> PostgreSQL 16
        -> controlled data directory outside program files
     -> Worker Windows Service (M4 delivered later)
```

- Windows Server 2022 x64、Python 3.11.x、PostgreSQL 16 为验收基线。
- API 与 Worker 使用独立最小权限系统账户；程序目录只读，日志、上传、知识文件和备份位于受控数据目录。
- 数据库迁移是安装/升级的独立步骤，只运行一次，不在每个 Uvicorn/Worker 进程启动时自动执行。
- 首个管理员只通过 M1 bootstrap CLI 创建；没有默认密码、HTTP 注册或匿名 bootstrap。
- 初期保持单 API 进程，待旧 JSON 存储全部迁移、数据库并发和多进程测试通过后再评估多 worker。

### 4.2 跨平台适配

- 业务模块只消费环境变量、文件存储端口、SQLAlchemy Session 和领域接口，不依赖盘符、PowerShell、Windows 用户名或注册表。
- `deploy/windows/` 拥有 PowerShell/Service 包装；可选 `deploy/linux/` 只拥有 shell/systemd 包装，两者调用相同的 Python preflight、Alembic、bootstrap 和健康接口。
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

需要在 M2/M3 写服务接入前补齐并冻结：

```python
@dataclass(frozen=True)
class OutboxEventInput:
    event_type: str
    aggregate_type: str
    aggregate_id: str
    aggregate_version: int
    request_id: str
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

`OutboxWriter` 只追加到调用方事务，不 commit；返回值只暴露不可变事件 ID，不返回 ORM 实体。M2/M3 不导入 `db.models.OutboxEvent`，M4 通过单独的 `OutboxClaimPort` 领取，不复用写端口修改领域状态。

### 5.2 M1 公共接口

后续业务模块只允许使用：

```text
app.domains.identity.CurrentUser
app.domains.identity.Permission / RoleCode（只读基线）
app.domains.identity.dependencies.get_current_user
app.domains.identity.dependencies.require_permissions
app.domains.identity.authorization.ensure_not_self_review
app.domains.audit.AuditEventInput / AuditWriter
```

- Route 层使用 `get_current_user()`/`require_permissions()`；Service 层显式接收 `CurrentUser`，不依赖 FastAPI Request。
- `AuditWriter` 与领域状态、幂等记录和 outbox 在同一 `new_session()` 事务中写入。
- M2～M5 不导入 M1 `models.py`、`repository.py`、Cookie、会话令牌、节流或密码实现。
- 用户 ID、审核人、角色和权限只来自服务端 `CurrentUser`；请求 DTO 不再接受 `reviewer`、`actorId` 或角色声明决定授权。
- `CurrentUser` 若将来增加站点/设备范围，必须版本化公共契约并更新所有消费者测试，不能让领域模块各自附加属性。

### 5.3 路由、模型和迁移所有权

- M2 只新增 `api/v1/documents.py`、`knowledge.py` 与 `domains/documents|knowledge/`。
- M3 只新增 `api/v1/devices.py`、`workflows.py` 与 `domains/devices|workflows/`。
- M4 只新增 `workers/`、`indexing/`；M5 只新增 `api/v1/search.py`、`rag.py` 与 `domains/rag/`。
- 上述模块名已在 M0 注册表预留，领域团队不得编辑 `api/v1/router.py`、`db/domain_models.py` 或把业务代码写入 `main.py`。
- 当前迁移基线冻结在 `20260813_0004`。领域模型和测试可以并行，正式 migration revision 由 M0 指定集成人员基于合并时最新 head 串行生成；任何人不得修改 `0001`～`0004`。

## 6. Readiness 无冲突扩展设计

### 6.1 问题

当前 `system.py` 直接依赖 M1。若后续数据库、文件目录、Worker、索引或 Provider 都继续写入该文件，M0 会依赖所有领域，并成为高冲突热点。

### 6.2 接口

M0 新增 `core/readiness.py`：

```python
@dataclass(frozen=True)
class ReadinessCheck:
    name: str
    required: bool
    healthy: bool
    reason: str = ""       # 只能是脱敏摘要
    details: Mapping[str, object] = field(default_factory=dict)

class ReadinessContributor(Protocol):
    def check(self, settings: AppSettings) -> ReadinessCheck: ...
```

M0 拥有固定可选发现列表，例如：

```text
domains.identity.readiness   M1
domains.documents.readiness  M2
workers.readiness            M4
indexing.readiness           M4
domains.rag.readiness        M5
```

领域只新增自己的 `readiness.py` 并返回脱敏结果；`system.py` 只调用 M0 聚合器，不导入任何领域模块。未交付模块安全跳过，已存在模块内部导入错误必须直接失败，规则与路由/模型发现一致。

### 6.3 生产不变量

当 `APP_ENV=production` 时：

- PostgreSQL 始终 `required=true`；`APP_DATABASE_REQUIRED=false` 不能把它降为可选。
- `APP_DATABASE_URL` 必须是 PostgreSQL；连接失败时 ready=503。
- `APP_AUTH_SECRET` 和 `APP_IDEMPOTENCY_SECRET` 至少 32 字节；不返回长度或值。
- Cookie 必须 `Secure` 且使用 `__Host-` 名称。
- `APP_TRUSTED_ORIGINS` 至少包含一个明确 HTTPS origin；禁止通配符。
- 旧兼容表面必须关闭；受控数据目录必须位于程序目录之外且可写。
- 任一 required contributor 不健康时统一返回 `DEPENDENCY_UNAVAILABLE/503` 和“关键依赖未就绪”，不错误声称只有数据库故障。

`live` 只表示进程存活，不检查外部依赖；`ready` 决定代理和 Service 是否接收业务流量。

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

在该保护实现前，M0/M1 只能进行 API/数据库集成验收，不能作为完整系统对外部署。

## 8. 需要新增的部署与测试工件

### 8.1 M0/M1 代码协作项

| 所属模块 | 文件/接口 | 目的 | 冲突规避 |
| --- | --- | --- | --- |
| M0 | `core/readiness.py`、`tests/test_module0_readiness.py` | contributor、生产不变量、聚合 503 | 后续领域不修改 `system.py` |
| M0 | `api/v1/system.py` | 只消费 readiness 聚合器 | 移除对 M1 的直接导入 |
| M1 | `domains/identity/readiness.py` | 校验认证模式、密钥和 Cookie 配置 | 只返回脱敏 `ReadinessCheck` |
| M0 | `core/legacy_surface.py`、配置和测试 | 生产关闭旧 API/静态目录 | 不把阻断逻辑散落到旧路由 |
| M0 | `db/outbox.py`、契约测试 | 冻结领域写入端口 | M2/M3/M4 不直接操作 M0 ORM |

以上是后续实施方案，不表示这些文件当前已创建。

### 8.2 M7 Windows 工件

```text
deploy/windows/
  config/application.env.example
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

- `preflight.ps1` 检查 Windows/Python/PostgreSQL 版本、端口、数据目录、配置项存在性和密钥长度，只输出布尔状态，不输出密钥或完整连接串。
- `migrate.ps1` 使用临时注入的迁移账户连接串执行 Alembic；Service 运行账户使用单独的最小 DML 账户。
- `install/upgrade/rollback` 在变更前备份数据库与文件，记录应用版本和迁移 head；失败时停止流量并恢复，不自动降级含不可逆业务数据的迁移。
- Service 启动不使用 `--reload`，不调用 Anaconda 引导脚本，不在启动时自动生成配置或迁移数据库。

### 8.3 集成测试工件

建议由 M7 建立 `tests/integration/m0_m1/`，领域现有 `test_m1_*` 仍由 M1 维护：

| 测试层 | 必须覆盖 |
| --- | --- |
| 迁移 | 空库 upgrade 到 head、角色种子、约束/索引/触发器、受控 downgrade、重复 upgrade |
| M0 | PostgreSQL 中断/恢复、连接池超时、production readiness、可信代理链、旧表面禁用 |
| M1 | bootstrap 单次/并发、登录成功/失败、独立双桶并发、Cookie/CSRF、改密和会话失效 |
| 权限 | 无认证 401、权限不足 403、临时密码限制、最后管理员并发保护、审计只读 |
| 原子性 | 用户安全变更、审计和幂等同事务；失败全部回滚；幂等重放不重复写 |
| 浏览器 | 同源/跨源、Secure `__Host-` Cookie、CSRF、缓存头和注销清 Cookie |

测试数据库名必须以 `_test` 结尾；测试前后校验目标，禁止连接生产数据库。在线测试失败时保留日志和 schema 版本，但不得输出密码、令牌、密钥或连接串。

## 9. 部署与验收顺序

```text
D0 当前代码/进程内基线
  -> D1 M0 readiness + 旧表面 + outbox 公共端口
  -> D2 PostgreSQL 16 在线迁移与 M1 集成/并发验收
  -> D3 Windows Service、代理、配置和备份恢复验收
  -> D4 M6 登录前端 E2E
  -> D5 允许 M2/M3 生产写路由接入真实 M1
```

### D0：当前已具备但未完成

- 保持 `0004` 单一 head、15 个 v1 操作（14 个唯一路径）和 `239 passed` 基线。
- 允许 M2/M3/M6 使用版本化 Mock 并行开发。

### D1：先消除共享冲突

- 实施 readiness contributor、生产不变量、旧表面保护和 `OutboxWriter`。
- 冻结 M0/M1 OpenAPI/DTO 与公开 Python import 路径。
- 此阶段由 M0 主责；不修改 M1 业务规则和历史迁移。

### D2：真实 PostgreSQL 验收

1. 创建空的 `*_test` 数据库和最小权限账户。
2. 在线 upgrade 到 `0004`，检查表、种子、唯一约束和审计不可变触发器。
3. 执行 bootstrap，运行 M1 API、事务、锁和并发测试。
4. 在隔离库验证受控 downgrade/再 upgrade；记录可逆性和数据影响。
5. 只有全部通过后，M1 状态才能升级为“PostgreSQL 集成已验证”；旧入口未关闭前仍不能标“系统完成”。

### D3：Windows 部署验收

- 使用生产配置运行 preflight、迁移、Service 安装和 HTTPS 代理。
- 验证重启恢复、ready 摘流、日志脱敏、备份/恢复、升级/回滚和卸载。
- Linux 只需要复用相同 Python/环境契约通过 Ubuntu CI；不阻塞 Windows 基础版，但平台差异必须记录。

### D4/D5：前端与领域接入

- M6 完成登录、CSRF、权限守卫和错误信封 E2E。
- D1～D4 通过后，M2/M3 才把生产写路由从身份 Mock 切换到真实 `CurrentUser`/`AuditWriter`/`OutboxWriter`。

## 10. 并行开发与合并条件

| 模块 | 现在可以并行 | 必须等待 | 禁止事项 |
| --- | --- | --- | --- |
| M0 | readiness、旧表面保护、outbox 公共端口 | 无 | 不加入领域业务；不修改历史迁移 |
| M1 | 补 PostgreSQL 集成测试、readiness contributor | M7 PostgreSQL 环境用于在线验收 | 不再扩展私有接口给 M2/M3；不修改 M0 root router |
| M2 | 领域模型、DTO、Service、存储端口和身份/outbox Mock 测试 | D1 公共端口、D2 M1 验收后接真实写路由 | 不修改 `knowledge.py`/静态挂载；不导入 M1 ORM/Repository |
| M3 | 设备/流程领域和 Mock 测试 | D1/D2 后接真实身份；迁移最终编号由 M0 集成 | 不默认绑定流程；不修改 M2 表 |
| M4 | claim/lease 接口设计、事件消费者样例 | M0 claim 端口及 M2/M3 事件冻结 | 不轮询/修改 M2/M3 私有表 |
| M5 | 基于版本化只读 Mock 重构证据与安全规则 | M2/M3 read port、M4 索引状态 | 不查询其他领域 ORM；mock 不进入生产 |
| M6 | 按 M1 OpenAPI/DTO 开发登录、CSRF 和权限客户端 | D2/D3 后做真实浏览器 E2E | 不解析 Cookie；不传 reviewer/actor/roles 决定授权 |
| M7 | PostgreSQL、Windows 工件、CI、代理和备份测试 | 各模块公开契约 | 不在脚本复制领域逻辑；不把旧 mock readiness 当生产验收 |

合并共同门槛：

1. 每个逻辑变更有模块归属、本地日志、测试证据和回滚说明；
2. 公共契约变化由 M0 评审，消费者测试同批更新；
3. migration 创建前重查 head，正式编号串行集成；
4. 不修改其他模块私有目录；跨模块需求优先新增公开端口或事件；
5. `git diff --check`、模块测试、双导入路径和 OpenAPI 装配检查通过；
6. 缺真实依赖、存在 skip 或旧入口未关闭时，不得标记“已完成/生产可用”。

## 11. 下一批可执行计划

建议下一批作为独立变更 `M0.1 部署就绪公共端口`，严格控制范围：

1. M0 实现 readiness contributor 与 production foundation check；
2. M1 仅新增 identity readiness contributor，不修改认证业务；
3. M0 实现 legacy surface guard；
4. M0 实现 `OutboxWriter` 公共端口和契约测试；
5. M7 建立 PostgreSQL 16 `_test` 环境和在线测试入口；
6. 全部通过后再开始 Windows Service 工件和 M1 在线验收。

该批次不创建 M2/M3 表、不修改前端、不调整 RAG，也不修改 `0001`～`0004`，因此可以与 M2/M3/M6 的契约 Mock 开发同时进行，并将共享文件冲突限制在 M0 指定集成人员范围内。
