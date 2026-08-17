# 模块代码搭建进度与待建接口计划

> 审查日期：2026-08-17<br>
> 状态：当前代码审查基线；不构成功能完成或发布结论。<br>
> 主责：M7 状态与验证治理；协作：M0～M6。<br>
> 依据：SRS 第 1、14 节、现行需求追踪矩阵、M0 公共契约、M1 设计、事件目录、M0/M1 部署接入方案、修改日志索引及相关模块最新记录（当前为 016～018）。

本文中的进度表是审查日快照，用于解释模块边界和后续顺序；审查日之后的动态状态只更新现行需求追踪矩阵和修改日志。只有模块边界、接口所有权或集成顺序改变时才修改本计划。

## 1. 状态判定规则

本计划只使用“未开始”“已设计”“代码已搭建”“单元已验证”“集成已验证”和“已完成”六级实现状态。“原型代码存在”只是仓库资产限定语，“待改造”是优先级限定语，“可选”是范围限定语，均不代替实现状态。只有目标环境真实依赖、公开接口闭环、安全/并发场景和需求验收全部通过，且没有未关闭冲突时，才能标为“已完成”。离线 Alembic SQL、SQL 编译、Mock、FastAPI `TestClient` 或单个函数测试只属于进程内/单元证据，不能支持“集成已验证”。

## 2. 当前代码状态

| 模块 | 状态对象 | 实现状态 | 资产与证据限定 | 未关闭问题 |
| --- | --- | --- | --- | --- |
| M0 | 当前公共底座代码 | 单元已验证 | `core/`、`db/`、`api/v1/`、迁移 `0001/0002/0005` 及进程内/契约测试 | OpenAPI 通用 500、真实 PostgreSQL 在线升降级/中断恢复、真实代理链/跨域浏览器和生产部署验收；M4 claim 端口未搭建 |
| M1 | 本地账户与审计代码 | 单元已验证 | `domains/identity/`、`domains/audit/`、三个 v1 路由、迁移 `0003/0004`、identity readiness 和进程内单元/API 测试 | AUTH-13 服务用户/生产激活前 bootstrap、真实 PostgreSQL 触发器/锁/并发/API 集成、前端接入和旧表面物理退役 |
| M2 | 目标文档、知识与案例模块 | 已设计 | 旧 `knowledge.py`、JSON 和旧 `/api` 只作为原型资产 | 无目标领域表/Repository/v1 路由；修订、案例、审核、受控下载和 Worker 未搭建 |
| M3 | 目标设备与作业模块 | 已设计 | 旧种子流程及关联展示只作为原型资产 | 无设备/流程领域表、版本审核、CSV 导入或可靠匹配端口 |
| M4 | 目标 Worker 与索引模块 | 已设计 | M0 `OutboxWriter` 已单元验证，但不属于 M4 消费端实现 | 无 claim/lease/retry/恢复、索引世代、缓存/图谱失效 |
| M5 | 目标检索、RAG 与反馈模块 | 已设计 | 旧 `retrieval/`、`rag.py` 和旧 `/api` 只作为原型资产 | 无授权只读端口、effective-only 数据源、v1 API、查询/回答/反馈持久化、可靠证据约束和生产安全降级闭环 |
| M6 | 目标网页前端重构 | 已设计 | 单页 Vue 原型可构建但仍使用旧 `api.ts` | 无 router/store/login/权限守卫/v1 客户端；仍传入 reviewer；Playwright 依赖未锁定 |
| M7 | 目标部署与验证 | 已设计 | 本地脚本、历史容器材料和原型测试不属于生产工件 | `deploy/windows/` 当前无工件；无备份恢复闭环、双平台 CI、真实 PostgreSQL/Provider 验收 |

## 3. 待建公共接口与文件

### 3.1 M0：M1 已消费的公共端口

| 文件 | 当前端口/接口 | 消费方 | 冲突规避 |
| --- | --- | --- | --- |
| `backend/app/db/session.py` | 已搭建 `new_session()` 独立短事务上下文和统一 DB 请求错误映射 | M1、后续基础设施 | M1 未读取 `_session_factory`/重建 Engine；进程内测试已过，在线 PostgreSQL 待验收 |
| `backend/app/core/client_address.py` | 已搭建 `ClientAddressResolver.resolve(request, settings) -> str` | M1 登录审计/限流、M7 代理部署 | 默认直连地址；只有显式可信代理解释代理头；M1 未直接读取 `X-Forwarded-For`；真实代理链待验收 |
| `backend/app/core/readiness.py`、`legacy_surface.py` | 已搭建 M0-owned 必需策略、按环境发现 contributor 和旧表面集中保护 | M1/M2/M3/M4/M5、M7 | 八类目标模块生产必需；领域只新增 `readiness.py` 且无权降低 required 或扩展详情白名单 |
| `backend/app/db/outbox.py`、迁移 `20260814_0005` | 已搭建版本化 `OutboxWriter`；`OutboxClaimPort` 待建 | M2/M3/M5 已登记消费者的写事务、M4 消费者 | Writer 不 commit/返回 ORM；M4 不直接导入/更新 `db.models.OutboxEvent` |
| `tests/test_module0_foundation.py`、`test_module0_m1_prerequisites.py`、`test_module0_readiness.py`、`test_module0_outbox.py` | 已覆盖错误映射、事务所有权、代理欺骗、生产不变量、发现策略、旧表面和 Writer 契约 | 全模块 | 使用 M0 测试文件，未与 `test_m1_*` 重复实现 |

readiness 公共输出只允许 M0 `ReadinessDetails` 登记的字段和值，精确白名单见 M0 公共契约第 7.1 节；规范生产预检路径为 `/api/v1/health/ready`。预留 contributor 覆盖 identity、documents、knowledge、devices、workflows、workers、indexing 和 rag；开发环境可跳过未交付模块，生产环境八类目标模块均为必需。

### 3.2 M1：身份与审计

详细 P0～P2 文件及验收门槛见 `m1-identity-audit-design.md` 第 11 节。当前代码已搭建：

1. `repository.py` 一致授权快照及签发前用户/凭据/版本复验。
2. `transactions.py` 独立活动续期，不提交请求业务 Session。
3. `dependencies.py` 零 commit/rollback，消费 M0 客户端地址和短事务端口。
4. 账号桶与来源桶限流模型已经由 `0004` 表达；未来确有结构变化时先重新检查 migration head，再创建新的后继迁移，不得重复建表或修改 `0004`。
5. `http_contracts.py`、`http_responses.py` 和预留路由 `auth.py`、`users.py`、`audit.py` 已新增并通过进程内测试。

公开给 M2/M3/M5 的普通业务端口仍仅限 `CurrentUser`、`require_permissions()`、`ensure_not_self_review()` 和 `AuditWriter`；`AuditWriter.append()` 只返回不可变 `AuditAppendResult(event_id)`，不泄露 ORM。Repository、ORM、Cookie、节流实现均为 M1 私有。AUTH-13 所需受管服务用户和生产激活前 bootstrap 尚未实现，不得由领域模块自行补第二套主体。OpenAPI 已声明 Session Cookie、CSRF header、匿名登录面和权限扩展，但通用 500 响应仍待 M0 补齐后才能作为完整 M6 生成契约。

### 3.3 M2：文档、知识与案例版本

| 目录/文件 | 待建接口 | 上游/下游契约 |
| --- | --- | --- |
| `domains/documents/{models,contracts,repository,service,storage}.py` | `DocumentStoragePort`、上传元数据、授权下载、解析任务命令 | 消费 M0 Session/outbox、M1 CurrentUser；向 M4 发布解析任务 |
| `domains/knowledge/{models,contracts,repository,service,read_port}.py` | 版本草稿/审核/发布、`EffectiveKnowledgeReadPort` | 消费 M1 审核身份；只发布事件目录已登记事件；供 M5 只读 |
| `domains/knowledge/cases.py` 及 knowledge 模型/端口 | 维修案例提交/修订/审核、附件和 `EffectiveCaseReadPort` | 作为 M2 独占案例子域复用审核规则；供 M5 只读，不新增 M0 路由/模型注册项，不塞入旧 JSON 文件 |
| `api/v1/documents.py`、`knowledge.py` | `/documents`、受控下载、任务、版本/审核/案例 API | `/cases` 路径由 M2 已预留的 `knowledge.py` router 提供；只用 M0 信封/游标/幂等/ETag |
| 新 Alembic revision、`test_m2_*` | M2 表、单有效版本约束和事务测试 | 创建前重查 head；不编辑任何已经登记或应用的历史 revision |

### 3.4 M3：设备与作业流程

| 目录/文件 | 待建接口 | 上游/下游契约 |
| --- | --- | --- |
| `domains/devices/{models,contracts,repository,service}.py` | 设备类型/型号 CRUD、停用、UTF-8 CSV 导入 | 消费 M0/M1；供 M2/M3 适用范围引用 |
| `domains/workflows/{models,contracts,repository,service,read_port}.py` | 流程版本/审核、`EffectiveWorkflowReadPort`、确定性匹配 | 只发布事件目录已登记事件；供 M5 只读 |
| `api/v1/devices.py`、`workflows.py`、新迁移、`test_m3_*` | v1 管理与查询 API | 不修改旧种子服务；不得无匹配时绑定默认流程 |

### 3.5 M4：Worker 与索引

| 目录/文件 | 待建接口 | 冲突规避 |
| --- | --- | --- |
| `workers/{models,repository,runner}.py` | claim/lease/heartbeat/retry/recovery | 通过 M0 `OutboxClaimPort`；不直接修改 M2/M3/M5 表 |
| `indexing/{models,contracts,repository,service}.py` | `IndexGenerationPort`、原子世代切换、缓存/图谱失效 | 消费版本化事件；索引是派生数据，不反写领域状态 |
| Worker/索引迁移与 `test_m4_*` | 任务并发、宕机恢复、幂等消费 | 等事件目录中对应 M2/M3/M5 事件版本和样例冻结后联调 |

### 3.6 M5：检索、RAG 与回答反馈

| 目录/文件 | 待建接口 | 冲突规避 |
| --- | --- | --- |
| `domains/rag/{contracts,evidence,safety,service,models}.py` | 授权查询、Evidence Pack、查询/回答/反馈记录、唯一最终回答、Provider 记录 | 只消费 M2/M3/M4 公开端口；反馈审核后形成知识修订时调用 M2 修订提交端口，不查询或写入其 ORM |
| 重构 `retrieval/` 适配层 | effective-only、权限/设备范围过滤、统一知识/流程召回 | 旧算法可复用但不得继续以 JSON 为目标事实源 |
| `api/v1/search.py`、`rag.py`、迁移、`test_m5_*` | v1 检索/RAG/反馈 API | `/feedback` 路径由 M5 已预留的 `rag.py` router 提供；客户端不能伪造 reviewer；mock 不进入生产链路 |

### 3.7 M6：前端

| 目录/文件 | 待建接口 | 冲突规避 |
| --- | --- | --- |
| `frontend/src/router/`、`stores/auth.ts`、`views/` | 登录、权限守卫和领域页面 | 只使用 OpenAPI/DTO Mock，不导入后端内部结构 |
| `frontend/src/services/v1/` | `credentials: include`、CSRF、request ID/错误信封客户端 | 不继续把生产功能堆入旧 `api.ts`；不传 reviewer/actor/roles 作为授权 |
| `frontend/e2e/`、锁文件 | 登录/权限/审核/检索核心 E2E | Playwright 依赖必须锁定；认证 API 未完成前使用 Mock |

### 3.8 M7：部署与验证

| 目录/文件 | 待建接口/工件 | 冲突规避 |
| --- | --- | --- |
| `deploy/windows/` | install/start/stop/upgrade/backup/restore/diagnose/uninstall | Windows Server 2022 默认；密钥不写入包或日志 |
| CI 配置、PostgreSQL 16 服务和测试夹具 | Windows/Ubuntu 测试、迁移、前后端构建、E2E | M7 提供环境；领域模块拥有自己的 `test_m*_` 场景 |
| `deploy/` 可信代理与 TLS 说明 | 与 `ClientAddressResolver` 一致的代理范围 | 不把代理头信任范围硬编码在 M1 |
| 验收报告模板 | 区分单元、TestClient、在线 PostgreSQL、真实 Provider 和目标系统 E2E | skip/Mock/离线 SQL 不计作目标功能完成证据 |

## 4. 无冲突并行条件

- M0 只修改 `core/`、`db/`、全局基础中间件装配和公共契约；M1 只消费端口并修改 `domains/identity|audit` 与三个预留路由，不把业务逻辑写入 `main.py` 或根 router。第 011 号变更对 `main.py` 的修改归属 M0，仅安装敏感响应缓存中间件。
- M2、M3 可同时开发各自领域表和契约 Mock；正式迁移前执行 `alembic heads`，由指定集成人员基于当次最新 head 串行创建/重定 revision。
- M4 在事件目录冻结 DTO、版本、生产者和消费者前只写消费者契约测试；不得轮询 M2/M3/M5 表。
- M5/M6 在真实端口交付前使用版本化 Mock；Mock 不进入生产 Provider、索引或审核数据。
- M7 只提供环境、脚本和共享夹具，不在测试夹具中复制领域业务实现。
- 当前 M1 的进程内身份事务/快照冲突已关闭，旧入口已有生产 guard 但未物理退役；真实 PostgreSQL 并发仍未关闭，M2/M3/M5 生产写路由仍不得把 M1 标为已验收依赖。

## 5. 下一步顺序

1. D1.1 文档基线已经收口；D1.2 先补 OpenAPI 通用 500、AUTH-13 受管服务用户/生产激活前 bootstrap 契约及相应测试。
2. D2 使用 PostgreSQL 16 专用 `_test` 数据库执行 `upgrade head`、触发器、事务、锁/并发、回滚和中断恢复验收，并记录当次实际 revision。
3. D2 通过前，M2/M3/M5 只使用版本化身份/审计/outbox Mock 开发纯领域逻辑；通过后才接入真实身份和生产写事务。
4. M2/M3 先冻结领域事件与只读端口，M5 再冻结其实际异步事件（若有）；M4 只接入事件目录中已冻结的生产者契约，M5 只接入已冻结的上游只读端口。
5. M6 在 OpenAPI 错误契约补齐后联调；M7 最后执行 Windows/Ubuntu、恢复、安全和完整 E2E 验收。

M0/M1 的实际部署检查、readiness 扩展、旧表面隔离、Windows 工件和后续模块接入门槛详见 `m0-m1-deployment-readiness-plan.md`。其中 D1 公共端口对应代码为“单元已验证”，D1.2、D2～D4 尚未完成；不得据此提升 M0/M1 为“集成已验证”或“已完成”。
