# M0/M1 部署复核与后续无冲突接入方案

> 复核日期：2026-08-17<br>
> 状态对象：D1 公共端口代码；实现状态：`单元已验证`。D1.2、D2～D4 尚未完成。<br>
> 主责模块：M7；协作模块：M0、M1  
> 关联记录：`2026-08-13-010-module-progress-audit`、`2026-08-13-011-m1-local-identity-http`、`2026-08-13-012-m0-m1-deployment-audit`、`2026-08-14-013-m0-m1-public-integration-gates`、`2026-08-17-016-stage0-contract-alignment`、`2026-08-17-017-m0-foundation-hardening`、`2026-08-17-018-current-document-baseline-closure`

本文中的状态和证据均为复核日快照；后续动态状态只更新现行需求追踪矩阵和修改日志。只有部署门禁、公共端口、拓扑或接入顺序改变时才修改本方案。

## 1. 目的与判定口径

本方案回答两个问题：

1. 当前 M0/M1 是否已经部署到可供后续模块安全接入的程度；
2. 后续 M2～M7 应通过哪些稳定端口接入，避免重复实现、修改共享文件或扩大旧原型的安全边界。

本文中的“可启动”只表示进程和页面能够运行；“代码已搭建”只表示实现文件存在并通过对应层级测试；只有真实 PostgreSQL、代理、Windows Service、安全/并发、备份恢复和系统接口闭环全部验证后，才能标记为“部署完成”或“生产可用”。

## 2. 当前部署检查结论

### 2.1 总体结论

| 状态对象 | 实现状态 | 证据与未关闭边界 |
| --- | --- | --- |
| M0 公共代码 | 单元已验证 | 严格环境枚举、运行时脱敏 500、CORS `ETag`、强类型 readiness、旧表面保护和 outbox 写端口有进程内/契约测试；OpenAPI 通用 500、真实 PostgreSQL/代理/浏览器未验收 |
| M1 本地账户与审计代码 | 单元已验证 | 登录、会话/CSRF、用户/角色、审计、双桶限流和 identity readiness 有进程内测试；AUTH-13 服务用户/生产激活前 bootstrap 及真实 PostgreSQL 未验收 |
| 本机兼容原型运行 | 代码已搭建 | Uvicorn、旧 JSON API 和构建后的前端可运行；这不是生产部署或 M1 集成证据 |
| M0/M1 PostgreSQL 16 在线验收 | 未开始 | 本机无 PostgreSQL 服务、`psql`、Docker 和 `M1_TEST_POSTGRES_URL`；3 项在线测试跳过 |
| Windows 生产服务目标 | 已设计 | `deploy/windows/` 当前无 Service、安装/升级/诊断/卸载或生产配置工件 |
| Linux CI 适配目标 | 已设计 | 没有 Ubuntu CI；systemd 为可选交付物，历史 Linux/LoongArch 文档不是当前证据 |
| M6 认证前端目标 | 已设计 | 当前前端仍调用旧 `/api`，无登录路由、权限 store、CSRF/v1 客户端 |
| 生产旧入口应用层隔离代码 | 单元已验证 | `disabled` 模式进程内返回 404；旧路由/挂载、代理拒绝和物理退役仍未完成 |

因此当前允许继续进行后续模块的契约 Mock 和私有领域开发，但不允许宣称 M0/M1 已部署，也不允许 M2/M3/M5 生产写路由直接把 M1 当作已经验收的真实依赖。

### 2.2 分批验证证据

- 2026-08-17、提交 `7016029`、记录 017：后端 `259 passed, 25 skipped`，其中 M1 真实 PostgreSQL 3 项和外部手册 22 项跳过；前端构建成功但有约 1.05 MB 大 chunk 警告；两种包导入路径均发现 15 个 v1 操作（14 个唯一路径）；`alembic heads` 返回 `20260814_0005`。这组证据只支持“单元已验证”。
- 2026-08-14、记录 013：占位 PostgreSQL URL 下离线 `upgrade 20260814_0005 --sql` 成功；真实 Uvicorn 烟测得到 `/api/v1/health/live=200`、开发可选依赖模式的 `/api/v1/health/ready=200`、前端首页 `200`、M1 登录 `503 DEPENDENCY_UNAVAILABLE`。该证据未在记录 017 重跑，不得描述为 2026-08-17 本轮结果。
- 2026-08-17、记录 017：进程内验证 `APP_DATABASE_REQUIRED=false` 不能把生产 PostgreSQL 降为可选；缺幂等密钥、HTTPS 来源、身份配置或目标关键 contributor 时 `/api/v1/health/ready=503 DEPENDENCY_UNAVAILABLE`。
- 旧 `production_readiness_check.py` 的 7 项离线 mock 原型检查只覆盖旧 JSON/mock 链路；无论何时通过都不是 M0/M1 生产就绪证据。

### 2.3 当前机器与配置差距

| 项目 | 当前状态 | 目标/处理 |
| --- | --- | --- |
| 后端虚拟环境 | 存在，Python 3.12.7；记录 013 曾验证 `pip check`，记录 017 未重跑 | Windows 产品基线重建为 Python 3.11.x；当前环境只作开发验证 |
| Node/npm | Node 22.17.1、npm 10.9.2 | 满足当前前端构建要求 |
| PostgreSQL 16 | 未安装/未发现服务和 CLI | M7 提供专用集成数据库与正式运行数据库 |
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
| P0 | 无真实 PostgreSQL 在线迁移、触发器、锁/并发和 API 集成 | 无法证明审计不可变、最后管理员、限流和会话失效 | 建立专用 `_test` 数据库验收流水线，先于 M2/M3/M5 真实接入 |
| P0 | 运行时已有脱敏 `INTERNAL_ERROR/500`，但 OpenAPI 无通用 500 声明 | M6 生成的客户端无法获得完整错误契约 | D1.2 同批补 OpenAPI 响应、错误模型引用和契约测试，完成前只标运行时“单元已验证” |
| P0 | AUTH-13 所需受管服务用户和生产激活前 bootstrap 尚未实现 | 登录失败记账、Worker 或 bootstrap 可能缺少合规用户身份 | D1.2 先冻结主体 DTO/激活边界并实现测试；M2/M3/M5 不得自建系统 actor |
| P1 | 旧 `init-config.ps1` 只生成 Provider/mock 配置，并覆盖 `.env` | 部署人员可能误以为已经生成 M0/M1 安全配置 | 保留为旧演示脚本；产品配置使用 `deploy/windows/config/application.env.example`、外部密钥注入和 `preflight.ps1`，不承诺自动生成密钥的 `configure.ps1` |
| P1 | `start-backend.ps1` 使用 `--reload`，缺环境时调用含机器路径假设的旧 Anaconda 脚本 | 不能作为 Windows Service 或可移植安装入口 | M7 创建无 reload、固定 3.11 运行时、显式配置文件的 Service 启动工件 |
| P1 | 当前 Dockerfile 设置 production，却不提供 PostgreSQL、认证/幂等密钥、可信来源和旧入口隔离 | 传入部分密钥后可能产生 readiness 误判；默认仍是 mock 业务链 | 标为历史/开发容器；产品容器必须复用同一 preflight 和环境契约后再验收 |
| P1（写端口已关闭） | M0 原有 outbox 表缺公共 Writer 和版本/请求字段 | M2/M3/M5 直接写 M0 ORM，M4 复制消费者实现 | `OutboxWriter`、不可变结果和 `0005` 已搭建；M4 claim/lease 仍须单独设计，不得直接操作 ORM |
| P1 | M2、M3 若并行创建相同后继迁移会形成 Alembic 多头 | 合并时修改历史迁移或产生不可预测升级顺序 | 领域模型可并行；正式迁移前执行 `alembic heads`，revision 由 M0 集成人员基于当次最新 head 串行编号/重定向 |
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

已搭建并冻结供 M2/M3/M5 中已登记消费者的写服务消费：

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

`OutboxWriter` 只追加到调用方事务，不 commit；返回值只暴露不可变事件 ID，不返回 ORM 实体。M2/M3/M5 不导入 `db.models.OutboxEvent`，M4 通过单独的 `OutboxClaimPort` 领取，不复用写端口修改领域状态。

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
- `AuditWriter` 与领域状态和必要幂等记录在同一 `new_session()` 事务中写入；只有事件目录已登记消费者的操作才在该事务追加 outbox。
- M2～M5 不导入 M1 `models.py`、`repository.py`、Cookie、会话令牌、节流或密码实现。
- 普通业务的用户 ID、审核人、角色和权限只来自服务端 `CurrentUser`；请求 DTO 不再接受 `reviewer`、`actorId` 或角色声明决定授权。内部任务使用受管服务用户，当前 AUTH-13 主体端口尚未实现。
- `CurrentUser` 若将来增加站点/设备范围，必须版本化公共契约并更新所有消费者测试，不能让领域模块各自附加属性。

### 5.3 路由、模型和迁移所有权

- M2 只新增 `api/v1/documents.py`、`knowledge.py` 与 `domains/documents|knowledge/`。
- M3 只新增 `api/v1/devices.py`、`workflows.py` 与 `domains/devices|workflows/`。
- M4 只新增 `workers/`、`indexing/`；M5 只新增 `api/v1/search.py`、`rag.py` 与 `domains/rag/`。
- 上述模块名已在 M0 注册表预留，领域团队不得编辑 `api/v1/router.py`、`db/domain_models.py` 或把业务代码写入 `main.py`。
- 截至 2026-08-17 的已验证迁移基线为单一 head `20260814_0005`。领域模型和测试可以并行；正式 revision 前先执行 `alembic heads`，由 M0 指定集成人员基于当次最新 head 串行生成。任何人不得修改已经登记或应用的历史 revision；`0001`～`0005` 是该复核基线下的历史范围，不是未来唯一受保护范围。

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

`APP_ENV` 仅允许 `development|test|production`，未知值失败关闭。`live` 只表示进程存活，不检查外部依赖；规范路径 `/api/v1/health/ready` 决定代理和 Service 是否接收业务流量，Windows/Linux 包装层不得实现另一套预检规则。

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

以上文件均已创建并通过对应进程内/契约测试，对应实现状态为“单元已验证”；数据目录 preflight、OpenAPI 通用 500、AUTH-13 主体、真实 PostgreSQL、代理、Windows Service 和浏览器验收仍未完成。

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
D0 2026-08-17 / 7016029 代码基线
  -> D1 M0 readiness + 旧表面 + outbox 公共端口（单元已验证）
  -> D1.1 现行文档/追踪矩阵/事件目录收口
  -> D1.2 OpenAPI 通用 500 + AUTH-13 主体/bootstrap 契约
  -> D2 PostgreSQL 16 在线迁移与 M1 集成/并发验收
  -> D2A 允许 M2/M3/M5 后端写路由接入真实 M1（M5 仍等待其业务上游）
  -> D3 Windows Service、代理、配置和备份恢复验收
  -> D4 M6 登录前端 E2E / 产品发布
```

### D0：当前已具备但未完成

- 2026-08-17、提交 `7016029` 的基线为 `20260814_0005` 单一 head、15 个 v1 操作（14 个唯一路径）和 `259 passed, 25 skipped`。
- 允许 M2/M3/M5/M6 使用版本化 Mock 并行开发。

### D1/D1.1：公共代码单元验证与文档基线收口

- 记录 013、016、017 已搭建并单元验证 readiness contributor、当前代码已覆盖的生产不变量、旧表面保护和 `OutboxWriter`。
- M1 `AuditWriter` 返回不可变结果，OpenAPI 已声明 Cookie、CSRF、匿名面和权限扩展；通用 500 声明仍待 D1.2。
- `0005` 未修改 `0001`～`0004`；真实在线升级不属于本阶段证据。
- 记录 018 收口现行追踪矩阵、事件目录、状态、证据来源和后续执行顺序。

### D1.2：生产契约补缺

1. 补齐 OpenAPI 通用 500 响应、错误模型引用和契约测试。
2. 冻结并实现 AUTH-13 受管服务用户、登录失败记账主体和生产激活前 bootstrap 边界。
3. 在 D1.2 完成前，M6 不把当前 OpenAPI 当作完整错误契约，M2/M3/M5 不自行实现系统 actor。

### D2：真实 PostgreSQL 验收

1. 创建空的 `*_test` 数据库和最小权限账户。
2. 执行 `alembic heads`，记录实际 revision，再在线 `upgrade head`，检查 outbox 字段、表、种子、唯一约束和审计不可变触发器。
3. 在 AUTH-13 与生产激活前 bootstrap 契约完成后执行 bootstrap，运行 M1 API、事务、锁和并发测试。
4. 在隔离库验证受控 downgrade/再 upgrade；记录可逆性和数据影响。
5. 只有全部通过后，M1 状态才能升级为“PostgreSQL 集成已验证”；旧入口未关闭前仍不能标“系统完成”。

### D3：Windows 部署验收

- 使用生产配置运行 preflight、迁移、Service 安装和 HTTPS 代理。
- 验证重启恢复、ready 摘流、日志脱敏、备份/恢复、升级/回滚和卸载。
- Linux 只需要复用相同 Python/环境契约通过 Ubuntu CI；不阻塞 Windows 基础版，但平台差异必须记录。

### D2A/D4：领域接入与前端发布

- D1.2 与 D2 通过后，M2/M3/M5 后端写路由可从身份 Mock 切换到真实 `CurrentUser`/`AuditWriter`，并仅在事件目录已登记消费者时使用 `OutboxWriter`；不再错误等待 Windows Service 或 M6 前端。
- M6 完成登录、CSRF、权限守卫和错误信封 E2E，连同 D3 作为产品发布门槛，而不是后端领域接入前置。

## 10. 并行开发与合并条件

| 模块 | 现在可以并行 | 必须等待 | 禁止事项 |
| --- | --- | --- | --- |
| M0 | D1 公共端口已单元验证；补 OpenAPI 500并设计 M4 claim 端口 | D2 在线验证由 M7 提供环境 | 不加入领域业务；不修改 `0001`～`0005` |
| M1 | 实现 AUTH-13 主体/bootstrap 边界并补 PostgreSQL 集成测试 | D1.2 后进入 D2 在线验收 | 不再扩展私有接口给 M2/M3/M5；不修改 M0 root router/readiness 聚合器 |
| M2 | 领域模型、DTO、Service、存储端口和身份/outbox Mock 测试 | D1.2/D2 后接真实写路由；迁移基于执行时最新 head | 不扩展旧 `knowledge.py`/静态下载；不导入 M1 ORM/Repository |
| M3 | 设备/流程领域和 Mock 测试 | D1.2/D2 后接真实身份；迁移基于执行时最新 head | 不默认绑定流程；不修改 M2 表 |
| M4 | claim/lease 接口设计、事件消费者样例 | M0 claim 端口及事件目录中的对应生产者事件冻结 | 不轮询/修改 M2/M3/M5 私有表 |
| M5 | 基于版本化只读 Mock 重构证据与安全规则 | M2/M3 read port、M4 索引状态 | 不查询其他领域 ORM；mock 不进入生产 |
| M6 | 按已冻结 Cookie/CSRF/权限 DTO 开发 Mock 客户端 | D1.2 OpenAPI 500、D2/D3 后做真实浏览器 E2E | 不把当前 OpenAPI 当完整错误契约；不解析 Cookie 或传 reviewer/actor/roles 决定授权 |
| M7 | PostgreSQL、Windows 工件、CI、代理和备份测试 | 各模块公开契约 | 不在脚本复制领域逻辑；不把旧 mock readiness 当生产验收 |

合并共同门槛：

1. 每个逻辑变更有模块归属、本地日志、测试证据和回滚说明；
2. 公共契约变化由 M0 评审，消费者测试同批更新；
3. migration 创建前重查 head，正式编号串行集成；
4. 不修改其他模块私有目录；跨模块需求优先新增公开端口或事件；
5. `git diff --check`、模块测试、双导入路径和 OpenAPI 装配检查通过；
6. 缺真实依赖、存在 skip 或旧入口未关闭时，功能状态不得标记为“已完成”，产品也不得描述为“生产可用”。

## 11. 下一批可执行计划

D1 公共代码已由记录 013、016、017 达到“单元已验证”，D1.1 文档基线由记录 018 收口。下一批先完成 D1.2，再进入 D2：

1. M0 补 OpenAPI 通用 500 声明和契约测试；M1 实现 AUTH-13 受管服务用户、登录失败记账主体和生产激活前 bootstrap 边界；
2. M7 建立 PostgreSQL 16 专用 `*_test` 数据库和最小权限账户；
3. 执行 `alembic heads` 并记录 revision，在线空库 `upgrade head`、受控 downgrade/再 upgrade，核对 outbox、限流和审计触发器；
4. M1 执行 bootstrap、API、锁/并发、事务回滚和数据库中断/恢复测试；
5. D2 通过后，M2/M3/M5 才接入真实身份/审计端口，并仅在事件目录已登记消费者时接入 outbox 写端口；此前继续使用公开契约 Mock；
6. M7 另起变更实现 Windows Service/代理/备份恢复，M6 可并行开发 Mock 页面，但真实联调等待 D1.2/D2。

后续模块不得重复创建 readiness 聚合器、旧路由守卫或 outbox 写端口，也不得修改任何已经登记或应用的历史 revision。M4 的 `OutboxClaimPort` 是尚未搭建的新端口，需由 M0 另行冻结。
