# 当前需求追踪矩阵

> 文档性质：当前实现状态、验证证据和未关闭问题的唯一动态事实源<br>
> 审计日期：2026-08-29<br>
> 被审计运行时代码证据基线：提交 `4f67482`（`2026-08-29-023-m0-p0-contract-closure`）；本次统一设计治理未修改运行时代码，也未重跑该记录的测试<br>
> 数据库迁移基线：单一 head `20260817_0006`；仅有离线 SQL 证据，尚无专用 PostgreSQL 16 在线证据<br>
> 需求语义来源：[软件需求规格说明书](software-requirements-spec.md)<br>
> 唯一现行设计来源：[统一软件设计与后续开发方案](../design/follow-up-development-plan.md)<br>
> 历史证据入口：[变更日志索引](../change-log/INDEX.md)

## 1. 维护与判定规则

1. 本矩阵只维护“需求 ID—适用模块—状态对象—功能状态—实现资产—自动测试—验收证据—未关闭问题”的当前映射，不改变 SRS 的需求语义。
2. 功能状态只使用：`未开始`、`已设计`、`代码已搭建`、`单元已验证`、`集成已验证`、`已完成`。
3. 状态必须绑定可独立验证的对象。同一需求的公共底座、领域接入、前端接入和部署验收状态不同时，必须拆行，不能用局部测试提升整项需求或整个模块。
4. 原型代码、旧 `/api`、JSON 数据、Mock、设计稿、离线迁移 SQL 和测试夹具只能列为资产或局部证据，不能单独证明目标生产能力。
5. `单元已验证` 只表示记录所指代码边界具有受控自动化证据；`集成已验证` 必须另有真实 PostgreSQL、代理、浏览器、服务管理器或外部依赖证据。跳过的测试不计为通过。
6. 状态变化原则上只更新本矩阵并新增变更日志。只有需求语义、公共契约、模块所有权或验收口径变化时，才修改 SRS 或统一设计文件。
7. 所有设计、具体领域事件及其生命周期只在[统一软件设计与后续开发方案](../design/follow-up-development-plan.md)对应章节维护，不得新建设计文件。历史变更日志正文不可改写；历史结论与当前代码不一致时，在本矩阵和新的变更日志中纠正。

## 2. 当前基线与证据边界

- 记录 019 曾在其当时工作树上记录 `271 passed, 25 skipped`、15 个 v1 操作的通用 500 OpenAPI 声明、前端构建通过，以及迁移 `0006` 的离线升级/降级 SQL。该记录是历史证据，不等于本轮重新执行，也不等于真实 PostgreSQL、代理或浏览器集成通过。
- 当前 15 个 v1 操作的未捕获异常、显式 `HTTPException`/`AppError` 5xx 已统一归一化；只有固定 `DEPENDENCY_UNAVAILABLE/503` 可保留 503，其他外部 5xx 固定为 `INTERNAL_ERROR/500`。普通 4xx 不再透传内部 details，请求校验与 readiness 使用各自封闭白名单。
- 普通日志在结构化 `extra` 合并后执行集中失败关闭，覆盖异常/堆栈、请求体/载荷/headers、Cookie、令牌、连接串和绝对路径；现存先拼接异常原文的日志调用已改为固定事件。该证据仅覆盖当前应用代码与进程内回归，部署侧日志采集、保留和受控诊断通道仍待 M7 验收。
- 当前 15 个 v1 操作均使用命名的具体 success DTO；用户与审计分页分别绑定具体 item DTO，default/422/500/readiness 503 使用封闭错误模型。OpenAPI consumer-contract 测试递归拒绝空 schema、自由 object 和泛型分页项；实际 TypeScript 生成器、生成产物和浏览器消费仍归 M6。
- `AuthenticatedActor` 已存在，但 `AuditEventInput` 仍接受裸 `actor_user_id`/`initiator_user_id` 和任意 `Mapping` metadata，尚未形成由类型化 actor 到事件级白名单审计输入的生产门面。
- M1 identity readiness 目前主要校验配置与实例生命周期，尚未验证三类固定服务账户的稳定 ID/service key、`auth_source=service`、启用/未删除和无密码凭据等不变量。
- 当前权限枚举/角色种子缺少目标设备维护和运维写入所需的稳定权限（至少 `device:write`、`ops:write`）；也没有可供 M2/M3/M5 上线前检查“两名合格审核人”的 reviewer eligibility/capacity 公共端口。
- M0 已有 outbox append 写端口，并已在无 ORM 副作用的 `core/ports` 冻结 ClaimPort 的 claim、lease/heartbeat、success、retry、dead-letter、replay、fencing 和 operation-id 幂等语义；M0 数据库适配器、M4 Worker/实际消费者和 PostgreSQL 并发恢复证据仍未实现。当前事件目录只有“提议”事件，没有满足“生产启用门禁”的事件。
- 实例激活的合格主体是任一启用、未删除、`auth_source=local`、已完成临时密码更换且仍具 `system_admin` 的本地用户；不得把首次管理员写成唯一可激活主体。`bootstrapped` 阶段的受限 provisioning 暴露规则以 [SRS 10.1](software-requirements-spec.md#101-windows-默认部署)为准，目前尚无部署/代理实现证据。

## 3. 模块状态摘要

| 模块 | 状态对象 | 功能状态 | 当前实现/证据边界 | 主要未关闭问题 |
| --- | --- | --- | --- | --- |
| M0 | 公共 HTTP、事务、readiness、幂等、outbox append 与 ClaimPort 底座 | 代码已搭建 | P0 5xx/日志、15 个具体 v1 DTO、封闭错误 schema 与无 ORM ClaimPort 均有进程内/契约测试 | M0 整体仍无真实 PostgreSQL/代理/日志采集证据；ClaimPort 数据库适配器不在本次范围 |
| M1 | 本地账户、会话、RBAC、受管服务主体、实例生命周期与审计代码 | 单元已验证 | 记录 019 和现有 `test_m1_*` 提供进程内证据，迁移至 `0006` | 类型化 actor 未接入审计输入；服务账户 readiness、审核容量端口、权限码、OIDC、前端和 PostgreSQL 在线验收未关闭 |
| M2 | 文档、知识版本、案例与领域审核目标模块 | 已设计 | 旧知识/案例代码和 JSON 仅为原型资产 | 无目标领域表、迁移、v1 路由、审核容量门禁、受控附件和生产写事务 |
| M3 | 设备、设备类型与工作流目标模块 | 已设计 | 旧种子流程及展示仅为原型资产 | 无目标模型、迁移、`device:write`、CSV、版本审核和可靠匹配端口 |
| M4 | Worker、outbox 消费、解析、索引与运维任务接口 | 已设计 | 可依赖 M0 的无 ORM ClaimPort 契约；没有 M4 实现 | M0 数据库适配器与 M4 Runner/consumer 均未实现；原子 claim/lease/retry/恢复、实际消费者、索引世代和 `api/v1/operations.py` 均无证据 |
| M5 | 检索、RAG、查询附件与反馈目标模块 | 已设计 | 旧检索/RAG/反馈代码仅为原型资产 | 无授权只读端口、目标持久化、具体 v1 DTO、Provider 安全降级和反馈审核闭环 |
| M6 | 目标 Web 前端 | 已设计 | 旧单页原型可构建但仍依赖旧 `/api`；M0 已提供封闭的 v1 OpenAPI 生成输入 | 无 v1 客户端、生成器/生成产物、router/store、登录/权限守卫及锁定的核心 E2E |
| M7 | 部署、provisioning、服务管理、备份恢复与跨平台验收 | 已设计 | 本地脚本和历史容器材料不能作为生产工件 | 无 Windows 服务/Caddy/provisioning、PostgreSQL 16、备份恢复、双平台 CI 与发布证据 |

## 4. 需求追踪

### 4.1 业务目标与身份权限

| 需求编号 | 适用模块 | 状态对象 | 功能状态 | 实现资产/自动测试 | 验收证据 | 未关闭问题或升级条件 |
| --- | --- | --- | --- | --- | --- | --- |
| `BR-01`～`BR-13`（含 `BR-06A`、`BR-06B`） | M2～M7 | 目标业务闭环 | 已设计 | SRS、模块设计和旧原型资产；旧原型测试不覆盖目标架构 | 无 | 目标领域模型、审核/发布、授权检索、可追溯证据、降级与前端闭环均未形成 |
| `AUTH-01`～`AUTH-03` | M0、M1 | M1 v1 认证、会话与服务端授权基础 | 单元已验证 | `api/v1/auth.py`、身份依赖、会话/RBAC 及 `test_m1_*` | 无真实代理/浏览器证据 | 只覆盖 M1 v1；M2/M3/M5、附件、静态资源与旧 `/api` 退役未闭环 |
| `AUTH-01`～`AUTH-03` | M2～M7 | 全产品统一认证与旧表面关闭 | 已设计 | 接入规则和旧表面守卫设计 | 无 | 所有目标业务 API、下载、前端与代理尚未接入 |
| `AUTH-04` | M1 | 单对象“不得自审”断言 | 单元已验证 | `ensure_not_self_review()` 及授权测试 | 无真实领域审核链 | M2/M3/M5 必须传服务端提交者身份并在各审核事务复验 |
| `AUTH-04` | M1～M3、M5、M7 | 每类审核能力至少两名合格审核人容量门禁 | 已设计 | SRS 已冻结规则 | 无 | 缺 reviewer eligibility/capacity 公共端口、按领域权限统计、readiness/provisioning 门禁与并发测试；不足时不得上线该能力 |
| `AUTH-05` | M1 | system_admin 不隐含审核权和角色叠加 | 单元已验证 | 权限映射与授权测试 | 无真实业务链 | 当前权限集合仍缺 `device:write`、`ops:write`；新增权限必须附迁移/种子兼容和测试 |
| `AUTH-06` | M1、M6、M7 | OIDC 模式及 Web 登录闭环 | 未开始 | 只有配置枚举和扩展设计，不存在生产 OIDC 适配器/回调或前端入口 | 无 | 依赖锁定、state/nonce/PKCE、映射、路由、前端会话恢复、迁移和企业集成均未实现 |
| `AUTH-07` | M1 | 本地密码哈希 | 单元已验证 | Argon2id 代码与密码测试 | 无真实部署证据 | 密钥注入、升级策略和部署验收未关闭 |
| `AUTH-08` | M1 | 会话过期、禁用、角色变化和 auth_version | 单元已验证 | 会话/用户管理代码及测试 | 无 PostgreSQL 并发证据 | 在线锁、事务隔离和并发失效待验证 |
| `AUTH-09` | M1 | auditor 最小权限基线 | 单元已验证 | 角色映射和授权测试 | 无前端/真实数据证据 | 前端隐藏不替代后端授权；业务读取须显式叠加 technician 并审计 |
| `AUTH-10` | M0、M1 | Trusted Origin 与 CSRF | 单元已验证 | CORS、`require_trusted_browser_origin()`、CSRF 与路由测试 | 无真实浏览器/代理证据 | 代理配置、Cookie 属性与跨源 E2E 待验证 |
| `AUTH-11`、`NFR-SEC-07`（登录） | M0、M1 | 可信客户端地址与双维度登录限流 | 单元已验证 | client address、throttle bucket 迁移与测试 | 无真实代理/PostgreSQL 证据 | 可信代理链和原子限流更新待集成验证 |
| `AUTH-12`、`DATA-08` | M0、M1 | 事务外密码验证、签发前复验和独立会话续期 | 单元已验证 | 短事务/登录编排和受控测试 | 无 PostgreSQL 并发证据 | 一致性快照、并发禁用/改密及连接故障待在线验证；被动续期不逐次写业务审计 |
| `AUTH-13` | M1 | 固定服务主体、非空审计 actor、bootstrap/activation 生命周期 | 单元已验证 | `AuthenticatedActor`、服务账户、生命周期代码、迁移 `0006` 及记录 019 测试 | 仅离线迁移证据 | 服务账户 readiness 不变量、数据库回填/FK/触发器/锁/回滚和受限 provisioning 尚未验证；任一合格本地 system_admin 均可激活 |
| `AUTH-13`、`NFR-OBS-02` | M1～M5 | 类型化 actor 到事件级审计输入 | 已设计 | `AuthenticatedActor` 与低层 `AuditWriter` 分别存在 | 无 | `AuditEventInput` 仍收裸 ID 和任意 metadata；须冻结强类型桥接、白名单 DTO、initiator 规则和回归测试后才能接生产写链 |
| `FR-IAM-01`～`FR-IAM-05` | M1 | 本地账户后端 API | 单元已验证 | users/auth/audit v1 路由、服务、迁移和进程内 API 测试 | 无 PostgreSQL/前端证据 | reviewer capacity、目标权限码、OIDC、前端管理页与部署集成未闭环 |
| `FR-IAM-01`～`FR-IAM-05` | M6 | 身份与用户管理 Web 闭环 | 已设计 | 页面/客户端设计 | 无 | v1 客户端、权限守卫、错误恢复和浏览器 E2E 未实现 |

### 4.2 领域功能与运维

| 需求编号 | 适用模块 | 状态对象 | 功能状态 | 实现资产/自动测试 | 验收证据 | 未关闭问题或升级条件 |
| --- | --- | --- | --- | --- | --- | --- |
| `FR-QRY-01`～`FR-QRY-08` | M3、M5、M6 | 查询输入、设备选择与图片线索确认 | 已设计 | 旧多模态原型和目标设计 | 无 | 缺目标设备端口、`RagQueryAttachment`、受控上传、线索确认、v1 API 与 E2E |
| `FR-RET-01`～`FR-RET-09` | M2～M6 | 授权检索与证据链 | 已设计 | 旧检索原型/测试只作参考 | 无 | 缺 effective-only/权限只读端口、索引世代、确定性 Evidence Pack、具体 DTO 与浏览器验收 |
| `FR-WF-01`～`FR-WF-08` | M3～M6 | 版本化工作流与指引 | 已设计 | 旧流程种子和展示只作参考 | 无 | 缺领域表/迁移、审核容量、发布/退役、可靠匹配、事件消费者和前端闭环 |
| `FR-RAG-01`～`FR-RAG-08` | M5、M6 | RAG 编排与安全降级 | 已设计 | 旧 RAG/评测资产只作参考 | 无 | 缺生产 Provider、证据选择、唯一最终回答、持久化、注入防护与降级 E2E |
| `FR-DOC-01`～`FR-DOC-11` | M2、M4、M6 | 文档上传、授权下载与异步解析 | 已设计 | 旧上传/解析代码及外部手册夹具只作参考 | 无 | 缺目标表/迁移、限制、存储端口、冻结事件和实际消费者、任务恢复与前端 |
| `FR-KNW-01`～`FR-KNW-10` | M2、M4～M6 | 知识版本、审核、发布和退役 | 已设计 | 旧知识 JSON/原型只作参考 | 无 | 缺领域模型、两人容量门禁、事务切换、索引世代、授权只读端口和 E2E |
| `FR-CASE-01`～`FR-CASE-06` | M2、M4～M6 | 维修案例版本与审核 | 已设计 | 旧案例原型只作参考 | 无 | 缺 `RepairCaseVersion`、附件、领域审核表、重新修订、检索接入和前端 |
| `FR-FB-01`～`FR-FB-04` | M2、M5、M6 | 回答反馈、审核与知识修订提交 | 已设计 | 旧反馈/评测资产只作参考 | 无 | 缺查询/回答/反馈持久化、审核容量、M2 修订提交端口及前端 |
| `FR-OPS-01` | M0 | live/ready 公共探针与 contributor 聚合 | 单元已验证 | `core/readiness.py`、system 路由及 readiness 测试 | 无目标部署证据 | 不等于服务管理器重启；生产八类 contributor 和代理外部探测未验收 |
| `FR-OPS-01`、`AUTH-13` | M1、M7 | identity readiness 与受限 provisioning | 代码已搭建 | 配置和实例生命周期检查存在 | 无 | readiness 未验证固定服务账户不变量；`bootstrapped` 暴露白名单、可信管理来源、代理阻断和激活后放流未实现 |
| `FR-OPS-02`～`FR-OPS-07` | M4、M6、M7 | 状态、失败任务、备份恢复、诊断与升级 | 已设计 | 局部脚本/设计资产 | 无 | `api/v1/operations.py` 归 M4；M7 仅负责工件与验收。任务 API、`ops:write`、服务工件、备份恢复和双平台证据均缺失 |

### 4.3 数据与 API

| 需求编号 | 适用模块 | 状态对象 | 功能状态 | 实现资产/自动测试 | 验收证据 | 未关闭问题或升级条件 |
| --- | --- | --- | --- | --- | --- | --- |
| `DATA-01` | M0、M1 | 事务与数据库基础 | 单元已验证 | SQLAlchemy/Alembic、短事务、幂等/outbox append 及局部测试 | 无真实 PostgreSQL 证据 | 不能外推到仍使用 JSON/旧原型的全产品；在线事务和故障行为待验证 |
| `DATA-01` | M2～M5 | 目标领域数据库事实源 | 已设计 | 目标模型设计 | 无 | 领域表、Repository、迁移和派生索引重建尚未实现 |
| `DATA-02` | M0 | `OutboxEventInput` append 写端口 | 单元已验证 | `OutboxWriter`、迁移 `0005` 与写端口测试 | 无生产者/消费者证据 | append input 不含 `event_id`；Writer 持久化时生成 ID。现有 append 单测使用未版本化的 synthetic 事件名，R1 须改为明确的 `SyntheticTestEvent.<major>` 占位名或目录精确名；该夹具不是事件登记或消费者证据 |
| `DATA-02`、`NFR-REL-02` | M0 | outbox claim/lease/retry/dead-letter/replay 公共端口 | 单元已验证 | `core/ports/outbox_claim.py` 与不可变/并发/幂等/无 ORM 导入测试 | 无 PostgreSQL 适配器证据 | 只证明契约冻结；未实现数据表、数据库时钟、原子 claim、fencing 持久化或恢复 |
| `DATA-02`、`NFR-REL-02` | M0 | outbox delivery/lease/operation 持久化适配 | 未开始 | 已冻结 ClaimPort，可据此新增 M0 表、迁移和 PostgreSQL 适配器 | 无 | 适配器与数据库时钟、原子 claim、fencing、恢复证据均未实现；不得反向依赖 M4 事件列表 |
| `DATA-02`、`NFR-REL-02` | M4 | Worker、实际消费者与恢复 | 未开始 | 只能依赖 M0 ClaimPort；registry/Runner 尚不存在 | 无 | M4 拥有 consumer registry、handler、backoff 和 operations API，禁止直接导入或更新 M0 ORM；实际消费者和事件启用门禁仍未满足 |
| `DATA-02` | M2～M5 | 实际生产者与消费者闭环 | 已设计 | 事件目录只有“提议”事件 | 无 | 仅当事件满足目录“生产启用门禁”时才允许对应环境发布；预期消费者、Mock 或只有冻结契约均不满足条件 |
| `DATA-03` | M0、M1 | 稳定 ID 基础 | 单元已验证 | UUID/稳定服务账户 ID 与约束测试 | 无跨模块证据 | M2～M5 仍须采用节点/操作系统无关 ID |
| `DATA-03` | M2～M5 | 目标领域稳定 ID | 已设计 | 目标实体与事件聚合设计 | 无 | 领域模型/迁移尚未实现，禁止使用路径、显示名、节点 ID 或时间伪造主键/版本 |
| `DATA-04` | M1 | UTC 持久化基础 | 单元已验证 | M1 带时区模型与 Repository 测试 | 无真实 PostgreSQL 证据 | 数据库会话时区及在线升级待验证 |
| `DATA-04` | M2～M6 | 全产品 UTC 保存与用户时区展示 | 已设计 | SRS 和领域边界 | 无 | 领域时间模型、API DTO 和前端时区展示未实现 |
| `DATA-05` | M1 | 用户逻辑删除与审计保留基础 | 单元已验证 | M1 模型/Repository 测试 | 无真实 PostgreSQL 证据 | 审计不可变触发器和数据库权限待在线验证 |
| `DATA-05` | M2、M3、M5、M7 | 领域保留、物理清理与备份恢复策略 | 已设计 | SRS 与部署设计 | 无 | 领域逻辑删除、保留期、受控清理和恢复后一致性未实现 |
| `DATA-06` | M2、M4、M5、M7 | 数据库记录与受控文件的双向追溯 | 已设计 | Document/Case/RagQueryAttachment 所有权与存储端口设计 | 无 | 目标元数据表、文件引用完整性、孤儿检测和备份恢复验收未实现 |
| `DATA-07`、`NFR-MNT-03`（迁移） | 全局 | Alembic 迁移链 | 代码已搭建 | 单一 head `0006`；记录 019 有离线 upgrade/downgrade SQL | 无在线证据 | 所有后续结构变化须基于执行时实际 head 新增迁移；PostgreSQL 空库/存量/回滚未验证 |
| `API-01` | M0、M1 | `/api/v1` 根路由与 M1 API | 单元已验证 | v1 router、M1 路由与 OpenAPI/API 测试 | 无代理/真实客户端证据 | M2～M5 未接入，旧 `/api` 仍在迁移期 |
| `API-01` | M2～M7 | 目标业务 API、Web 客户端与代理接入 | 已设计 | 路由所有权和迁移设计 | 无 | 领域 v1 路由、M6 客户端、M7 代理和旧表面关闭尚未实现 |
| `API-02` | M0 | 稳定错误码、消息和 request ID 的 v1 运行时信封 | 单元已验证 | 显式/未捕获 5xx、普通 4xx details、验证错误与 request ID 回归测试 | 无代理/外部采集证据 | 新增错误码必须选择空 details 或另行冻结封闭 schema；不得绕过公共 handler/helper |
| `API-02`、`API-05` | M0、M1 | 当前 15 个操作的具体响应模型与安全 OpenAPI | 单元已验证 | 命名 success DTO、User/Audit item DTO、default/422/500/503 模型及 OpenAPI consumer-contract 测试 | 无生成客户端/浏览器证据 | 当前生成输入已闭合；后续每个新操作必须同时增加具体 DTO 与 consumer-contract 映射，M6 仍须锁定生成器并验证生成客户端 |
| `API-02`、`API-05` | M2～M6 | 后续领域响应模型与客户端消费 | 已设计 | 复用 M0 泛型基类和封闭模型规则 | 无 | M2～M5 尚无 v1 操作；M6 尚无生成产物或类型消费测试，禁止手写重复 DTO 源 |
| `API-03` | M0、M1 | 游标分页基础 | 单元已验证 | cursor codec、`v1_page()` 与测试 | 无目标列表证据 | 排序和允许过滤条件必须由各领域具体定义并测试 |
| `API-03` | M2、M3、M5、M6 | 目标领域列表排序/过滤与客户端 | 已设计 | 接入规则 | 无 | 各列表尚未冻结稳定排序、过滤白名单、cursor payload 与具体 item DTO |
| `API-04` | M0 | 幂等公共端口 | 单元已验证 | HMAC 指纹、幂等服务与契约测试 | 无跨进程/领域写链证据 | 创建、审核、重试等目标写操作尚未接入共享存储与事务 |
| `API-04` | M1 | 身份关键写操作幂等接入 | 单元已验证 | 改密、用户/状态/角色/重置密码写链及进程内测试 | 无 PostgreSQL/代理证据 | 跨进程冲突、回放和事务故障待在线验证 |
| `API-04` | M2～M5 | 创建、审核和任务重试幂等接入 | 已设计 | 目标事务规则 | 无 | 目标写链、共享存储与并发测试未实现 |
| `API-05` | M0、M1 | v1 错误与当前普通日志脱敏基础 | 单元已验证 | 显式/未捕获错误、验证白名单、结构化 extra、多词敏感内容、路径/连接串/堆栈回归测试 | 无部署采集证据 | 当前代码边界已关闭；代理、服务管理器、第三方 handler、日志保留与独立诊断通道仍须 M7 集成验收 |
| `API-06` | M1～M7 | 上传、下载和长任务大小/超时/速率限制 | 已设计 | 登录限流仅覆盖一个子边界 | 无 | 文档/图片、下载、模型和任务限制未实现或验收 |
| `API-07` | M0、M6、M7 | 旧 `/api` 迁移与退役 | 已设计 | 应用层 legacy surface 守卫有局部测试 | 无流量/代理/退役证据 | 旧前端和原型路由仍存在，须有兼容窗口、观测和物理退役门禁 |

### 4.4 非功能需求

| 需求编号 | 适用模块 | 状态对象 | 功能状态 | 实现资产/自动测试 | 验收证据 | 未关闭问题或升级条件 |
| --- | --- | --- | --- | --- | --- | --- |
| `NFR-PORT-01` | M7 | Windows Server 2022 默认生产与 Windows 11 开发基线 | 已设计 | 部署拓扑与工件设计 | 无 | 无 Windows Service、安装/升级/卸载工件和干净机验收 |
| `NFR-PORT-02`、`NFR-PORT-05` | M0～M7 | 同一业务代码的 Ubuntu 及 Windows/Ubuntu 双平台 CI | 已设计 | SRS 和部署方案 | 无 | `.github/` 不存在；尚无后端、前端、锁定核心 E2E 与 PostgreSQL 16 双平台门禁 |
| `NFR-PORT-03`、`NFR-PORT-04` | M0、M1 | 现有目标领域的 OS 无关配置、路径、UTF-8 与 UTC 基础 | 代码已搭建 | `core/`、`db/`、`domains/identity/`、`domains/audit/` 的分层代码 | 无双平台证据 | 只能限定为 M0/M1 目标领域；旧顶层原型和脚本仍有平台假设，Ubuntu CI 未建立 |
| `NFR-PORT-03`、`NFR-PORT-04` | M2～M7 | 后续领域和交付工件的可移植边界 | 已设计 | 模块所有权和基础设施适配规则 | 无 | 领域服务不得调用具体 OS 命令；存储、解析、Service 包装必须留在适配层并通过双平台测试 |
| `NFR-PORT-06` | M7 | 可选 OCI 容器交付 | 已设计 | 存在历史原型 Docker 资产，不属于目标工件 | 无 | 当前容器无 PostgreSQL/身份/v1 前端闭环；OCI 仅在另行完成同一配置、安全与发布门禁后可交付 |
| `NFR-PERF-01`、`NFR-PERF-02`、`NFR-PERF-05`、`NFR-PERF-06` | M2～M7 | API 时延、数据容量、持续负载与可配限流 | 已设计 | SRS 已冻结基准口径；旧评测不适用目标架构 | 无 | 缺目标数据集、负载脚本、10 分钟持续负载、P95/成功率、50k 片段和共享限流验收 |
| `NFR-PERF-03` | M5、M7 | LLM 可配超时与不超过 30 秒的默认值 | 已设计 | 旧适配器存在超时配置，只作原型资产 | 无 | `init-config.ps1` 的旧 LLM 模式仍写入 60 秒，与目标默认值冲突；目标 Provider 超时、取消、降级和独立外部延迟报告未实现 |
| `NFR-PERF-04` | M2、M5、M7 | 单文件默认 50 MB 上限及可下调策略 | 已设计 | 旧原型普通上传为 10 MB、知识文档为 20 MB，不是目标实现 | 无 | 目标文档/查询图片的统一限制端口、资源预检、管理配置和回归测试未实现 |
| `NFR-REL-01` | M7 | API/Worker 服务管理器自动重启 | 未开始 | 只有部署设计 | 无 | readiness 不能作为本需求证据；需 Windows Service 故障重启测试，Linux 生产单元仅在交付时验证 |
| `NFR-REL-02` | M0 | Worker 领取/过期重领公共语义 | 单元已验证 | ClaimPort lease token、fencing、attempt、retry/dead-letter/replay 与 operation-id 契约测试 | 无数据库证据 | 契约不是可靠投递实现；数据库时钟、原子性和多 Worker 并发须由后续适配器验证 |
| `NFR-REL-02` | M4 | Worker 真实重领与恢复 | 未开始 | 只有已冻结的 M0 端口可依赖 | 无 | 缺持久化 schema/适配器、实际消费者、故障恢复和 PostgreSQL 并发证据 |
| `NFR-REL-03` | M4～M7 | Provider 故障时关键词检索/流程可用 | 已设计 | 降级规则与旧原型资产 | 无 | 缺生产 Provider 隔离、故障注入、权限过滤和 E2E |
| `NFR-REL-04`～`NFR-REL-06` | M7 | 备份恢复、演练与可用性统计 | 已设计 | 部署计划 | 无 | 缺一致备份工件、RPO/RTO 演练、季度记录和代理外部探测 |
| `NFR-SEC-01` | M7 | HTTPS 生产入口 | 已设计 | 代理设计 | 无 | 证书、Caddy/IIS 配置和外部验收未实现 |
| `NFR-SEC-02` | M0、M1 | 认证、后端授权与会话安全基础 | 单元已验证 | M1 安全代码与进程内测试 | 无真实部署证据 | 权限缺口、审核容量、PostgreSQL/代理/浏览器仍待关闭 |
| `NFR-SEC-02` | M2～M7 | 全产品最小权限接入 | 已设计 | 领域接入与前端/部署规则 | 无 | 业务 API、下载、Worker、Web 和代理尚未形成统一生产授权链 |
| `NFR-SEC-03` | M2、M6、M7 | 授权文件下载与路径隐藏 | 已设计 | 存储端口/受控下载设计 | 无 | 旧静态表面需退役；目标下载、权限和路径泄露测试未实现 |
| `NFR-SEC-04`、`NFR-OBS-01` | M0、M1 | v1 API 与普通日志秘密/异常脱敏基础 | 单元已验证 | 统一错误边界、末端结构化日志白名单和安全回归测试 | 无部署日志链证据 | 当前进程代码已关闭 P0；M7 仍须验证 Uvicorn/代理/Windows Service/外部采集、保留策略和受控诊断通道 |
| `NFR-SEC-04`、`NFR-OBS-01` | M2～M7 | 全产品结构化日志与秘密边界 | 已设计 | 稳定日志/审计规则 | 无 | 领域、Worker、Provider、Web/代理和部署日志尚未接入统一字段、脱敏与保留策略 |
| `NFR-SEC-05`、`NFR-SEC-06` | M2、M4～M7 | 不可信上传与 Prompt Injection 防护 | 已设计 | 安全规则和旧测试只作参考 | 无 | 缺资源限制、隔离解析、内容/指令边界、恶意语料与 E2E |
| `NFR-SEC-07`（上传/模型/高成本接口） | M2、M4～M7 | 业务速率限制 | 已设计 | 仅 M1 登录限流已实现 | 无 | 缺用户级/接口级策略、共享存储和容量测试 |
| `NFR-SEC-08`、`NFR-SEC-09` | M0～M7 | 供应链扫描与企业安全集成 | 已设计 | 局部依赖文件；OIDC 仅设计 | 无 | 依赖锁定不完整，缺 SAST/SCA/密钥/许可证扫描及可选病毒扫描/集中密钥/OIDC |
| `NFR-OBS-02` | M1 | 身份安全动作审计基础 | 单元已验证 | AuditWriter、M1 事件构造和 API 测试 | 无真实触发器证据 | 类型化 actor 桥接与事件级 metadata 白名单未关闭；会话被动续期不逐次写业务审计 |
| `NFR-OBS-02` | M2～M5、M7 | 审核、版本、下载、删除与配置审计 | 已设计 | 目标事务规则 | 无 | 领域写链、强类型审计门面、运维配置审计和跨模块查询未实现 |
| `NFR-OBS-03` | M1 | 审计不可经业务接口修改 | 单元已验证 | 只读 API/Repository 与迁移触发器定义 | 无 PostgreSQL 在线证据 | UPDATE/DELETE/TRUNCATE 触发器和权限必须在线验证 |
| `NFR-OBS-04`、`NFR-OBS-05` | M0、M4、M5、M7 | 指标、告警、Trace 与企业输出 | 已设计 | 设计资产 | 无 | 请求/队列/Provider/索引指标及输出适配均未实现 |
| `NFR-UX-01`～`NFR-UX-05` | M6 | 五步主流程、真实长任务状态、可访问性 | 已设计 | 旧单页原型可构建 | 无目标 E2E/可访问性证据 | v1 前端、降级语义、request ID 恢复建议、键盘/颜色测试未实现 |
| `NFR-MNT-01`～`NFR-MNT-02` | M0、M1 | 模块端口与 OS 无关领域层基础 | 代码已搭建 | M0/M1 分层和局部静态检查 | 无全产品证据 | M2～M7 尚未实现；后续领域服务不得依赖具体 OS 命令或私有 ORM |
| `NFR-MNT-01`～`NFR-MNT-02` | M2～M7 | 全产品模块边界 | 已设计 | 所有权与公共端口设计 | 无 | 必须按模块端口实现并持续依赖方向检查 |
| `NFR-MNT-03`（依赖） | 全局 | 生产依赖锁定与供应链可复现 | 代码已搭建 | `package-lock.json` 和局部依赖文件存在；迁移治理另见 DATA-07 行 | 无发布门禁证据 | Python 生产/测试依赖未分层且仍有宽版本范围，OCR/RAG 可选依赖未锁定，Playwright 未进 manifest/lock，容器基础镜像未按 digest 固定，亦无发行 wheelhouse/SBOM 门禁 |
| `NFR-MNT-04` | M0、M1 | 已实现缺陷与关键规则测试门禁 | 代码已搭建 | P0 错误/日志/DTO/ClaimPort 与既有 M1 自动化测试资产 | 无完整 CI/集成证据 | M0 P0 回归已补；actor 桥接、服务 readiness、权限和审核容量仍属下一阶段，修复缺陷继续必须加测试 |
| `NFR-MNT-04` | M2～M7 | 后续模块自动化覆盖 | 已设计 | 测试计划 | 无 | 单元、PostgreSQL 集成、浏览器 E2E、双平台与故障测试尚未实现 |
| `NFR-MNT-05`～`NFR-MNT-06` | 全局 | 当前/目标区分与追踪治理 | 已设计 | SRS、现行矩阵、统一设计文件、日志模板/索引 | 本轮文档执行静态自检 | 文档治理不是运行时代码能力；后续每个逻辑变更须先读索引及相关最近记录，设计只原位更新统一文件，完成后新增日志并更新 `INDEX.md` |

## 5. 当前阻断项与状态升级门禁

### 5.1 已关闭的 P0 代码门禁与持续约束

1. 当前 15 个 v1 操作已经统一规范化未捕获异常及显式 5xx；`DEPENDENCY_UNAVAILABLE/503` 之外的 5xx 固定为 `INTERNAL_ERROR/500`，普通 4xx 不透传内部 details。新增路由、错误码或异常 handler 必须沿用并增加回归测试。
2. 普通日志已在结构化字段合并后执行白名单/失败关闭，现存异常拼接调用已收口。后续模块不得用 f-string/`str(exc)` 绕过边界；独立诊断通道、部署采集和保留策略仍是 M7 集成门禁。
3. 当前 v1 success、分页 item 与允许非空 details 的错误模型已经封闭，并由 OpenAPI consumer-contract 测试覆盖。R1 必须把全局固定 15 项清单改为动态公共门禁，并将具体 operation 映射下放到所属模块；后续操作必须提供具体模型。M6 只从 OpenAPI 生成一次 TypeScript 类型，不得手写第二套 DTO。

### 5.2 M1 接入生产写链前门禁

1. 冻结 `AuthenticatedActor -> AuditEventInput` 强类型桥接、initiator 继承规则和每类事件 metadata 白名单，禁止业务模块提交裸 actor ID 或任意请求映射。
2. identity readiness 校验三类固定服务账户的 ID、service key、`auth_source=service`、启用/未删除、无密码凭据及角色策略；在线迁移、种子、约束、触发器、锁、回滚全部在专用 PostgreSQL 16 验证。
3. 冻结 reviewer eligibility/capacity 端口和各审核能力所需权限；生产启用某审核能力前至少存在两名启用且合格的审核用户。
4. 补齐 `device:write`、`ops:write` 等稳定权限，完成代码角色映射、现有部署兼容和授权测试；当前权限不是独立数据库表，schema 未变化时不得为形式新增迁移。
5. 按 [SRS 10.1](software-requirements-spec.md#101-windows-默认部署)实现 `bootstrapped` provisioning 白名单与可信管理来源；激活接受任一合格本地 system_admin，`active` 且完整 readiness 成功后才放行正常业务流量。

### 5.3 异步与后续模块门禁

1. `OutboxEventInput` 是 append 调用输入，不含 `event_id`；持久化/投递 envelope 才包含 Writer 生成的 `event_id`。
2. 事件只有满足目录“生产启用门禁”时才能在对应环境进入生产写事务。预期消费者、Mock、仅冻结契约或尚未完成集成验证的 M4 不满足此条件；依赖该事件保持一致性的生产能力也必须继续关闭，不能省略 outbox 后先开放写入口。
3. M0 ClaimPort 的 claim/lease/heartbeat/retry/dead-letter/replay、fencing 与幂等语义已冻结在 `core/ports`；M0 下一步拥有 delivery/lease/operation 表、迁移和 PostgreSQL 适配器，M4 只通过该端口拥有 registry、Runner、消费者与恢复，不得依赖 M0 ORM。`api/v1/operations.py` 归 M4，M7 只负责部署和验收。

### 5.4 状态升级规则

- 升级到 `代码已搭建`：能定位当前目标架构中的代码或迁移，且未用旧原型/Mock 冒充。
- 升级到 `单元已验证`：当前代码基线上有覆盖该状态对象的自动化证据；测试跳过和离线 SQL 不能覆盖在线数据库声明。
- 升级到 `集成已验证`：记录真实依赖、环境、执行命令、结果、代码基线和剩余限制；不同环境证据不可相互替代。
- 升级到 `已完成`：适用 MUST、发布工件、迁移/回滚、测试、文档和未关闭阻断全部关闭；历史日志中的“变更已结束”不等于功能完成。
