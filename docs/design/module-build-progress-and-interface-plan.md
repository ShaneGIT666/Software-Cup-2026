# 模块代码搭建进度与待建接口计划

> 审查日期：2026-08-13<br>
> 状态：当前代码审查基线；不构成功能完成或发布结论。<br>
> 主责：M7 状态与验证治理；协作：M0～M6。<br>
> 依据：SRS 第 1、14 节，M0 公共契约，M1 设计方案及修改日志 001～010。

## 1. 状态判定规则

本计划区分“代码已搭建”“单元已验证”“集成已验证”和“已完成”。只有目标环境真实依赖、公开接口闭环、安全/并发场景和需求验收全部通过，且没有未关闭冲突时，才能标为“已完成”。离线 Alembic SQL、SQL 编译、Mock、FastAPI `TestClient` 或单个函数测试只作为对应层级证据。

## 2. 当前代码状态

| 模块 | 代码证据 | 当前判定 | 未关闭问题 |
| --- | --- | --- | --- |
| M0 | `core/`、`db/`、`api/v1/`、迁移 `0001/0002`；健康/契约单元测试 | 基础代码已搭建，部分进程内 HTTP 已验证；模块未完成 | 无真实 PostgreSQL 在线升降级；请求 DB 失败尚无稳定 503 映射；无独立短事务公开端口和可信客户端地址解析 |
| M1 | `domains/identity/`、`domains/audit/`、迁移 `0003`、`test_m1_*` | 基础/持久化代码已搭建，单元已验证；功能未完成 | 无公开 API；共享 Session 被身份依赖提交；授权分步读取；签发前无并发复验；限流仅组合维度；无真实 PostgreSQL 验证 |
| M2 | 旧 `knowledge.py`/JSON 数据和旧 `/api` 路由 | 仅原型存在；目标模块未开始 | 无目标领域表/Repository/v1 路由；修订、审核、受控下载和 Worker 均不满足目标规则 |
| M3 | 旧种子流程及关联展示 | 仅原型存在；目标模块未开始 | 无设备/流程领域表、版本审核、CSV 导入或可靠匹配端口 |
| M4 | M0 `outbox_events` 表 | 仅共享表代码存在；Worker/索引模块未开始 | 无 claim/lease/retry/恢复、索引世代、缓存/图谱失效；M4 不能直接操作 M0 私有 ORM |
| M5 | 旧 `retrieval/`、`rag.py` 和旧 `/api` | 原型部分可运行；目标模块未开始 | 无授权只读端口、effective-only 数据源、v1 API、可靠证据约束和生产安全降级闭环 |
| M6 | 单页 Vue `App.vue`、旧 `api.ts` | 原型可构建路径存在；目标重构未开始 | 无 router/store/login/权限守卫/v1 客户端；仍传入 reviewer；E2E 很薄 |
| M7 | 本地 PowerShell/容器/历史验证脚本和原型测试 | 工具零散存在；生产交付未完成 | 无 Windows Service 工件、备份恢复闭环、双平台 CI、锁定 E2E、真实 PostgreSQL/Provider 验收 |

## 3. 待建公共接口与文件

### 3.1 M0：先于 M1 公开路由

| 文件 | 待建接口 | 消费方 | 冲突规避 |
| --- | --- | --- | --- |
| `backend/app/db/session.py` | `new_session()` 独立短事务上下文；统一 DB 请求错误映射 | M1、后续基础设施 | M1 不读取 `_session_factory`、不重建 Engine；领域 Repository 不提交业务事务 |
| `backend/app/core/client_address.py` | `ClientAddressResolver.resolve(request) -> str` | M1 登录审计/限流、M7 代理部署 | 默认直连地址；只有显式可信代理可解释代理头；M1 不直接读取 `X-Forwarded-For` |
| `backend/app/db/outbox.py` | `OutboxWriter` 与后续 `OutboxClaimPort` | M2/M3 写事务、M4 消费者 | outbox 表仍归 M0；M4 不直接导入/更新 `db.models.OutboxEvent` |
| `tests/test_module0_database_dependencies.py`、`test_module0_client_address.py` | 错误映射、事务所有权、代理欺骗测试 | 全模块 | 使用 M0 前缀，避免与 `test_m1_*` 同文件修改 |

### 3.2 M1：身份与审计

详细 P0～P2 文件清单见 `m1-identity-audit-design.md` 第 11 节。最先关闭：

1. `repository.py` 一致授权快照及签发前用户/凭据/版本复验。
2. `transactions.py` 独立活动续期，不提交请求业务 Session。
3. `dependencies.py` 零 commit/rollback，消费 M0 客户端地址和短事务端口。
4. 账号桶与来源桶限流模型；若现有表不能表达则新建最新 head 的迁移。
5. 之后才新增 `http_contracts.py`、`http_responses.py` 和预留路由 `auth.py`、`users.py`、`audit.py`。

公开给 M2/M3/M5 的端口仍仅限 `CurrentUser`、`require_permissions()`、`ensure_not_self_review()` 和 `AuditWriter`；Repository、ORM、Cookie、节流实现均为 M1 私有。

### 3.3 M2：文档与知识版本

| 目录/文件 | 待建接口 | 上游/下游契约 |
| --- | --- | --- |
| `domains/documents/{models,contracts,repository,service,storage}.py` | `DocumentStoragePort`、上传元数据、授权下载、解析任务命令 | 消费 M0 Session/outbox、M1 CurrentUser；向 M4 发布解析任务 |
| `domains/knowledge/{models,contracts,repository,service,read_port}.py` | 版本草稿/审核/发布、`EffectiveKnowledgeReadPort` | 消费 M1 审核身份；向 M4 发布 `KnowledgePublished/Retired`；供 M5 只读 |
| `api/v1/documents.py`、`knowledge.py` | `/documents`、受控下载、任务、版本/审核 API | 只用 M0 信封/游标/幂等/ETag；不扩展旧 `main.py` |
| 新 Alembic revision、`test_m2_*` | M2 表、单有效版本约束和事务测试 | 创建前重查 head；不编辑 `0003` |

### 3.4 M3：设备与作业流程

| 目录/文件 | 待建接口 | 上游/下游契约 |
| --- | --- | --- |
| `domains/devices/{models,contracts,repository,service}.py` | 设备类型/型号 CRUD、停用、UTF-8 CSV 导入 | 消费 M0/M1；供 M2/M3 适用范围引用 |
| `domains/workflows/{models,contracts,repository,service,read_port}.py` | 流程版本/审核、`EffectiveWorkflowReadPort`、确定性匹配 | 发布 `WorkflowPublished/Retired`；供 M5 只读 |
| `api/v1/devices.py`、`workflows.py`、新迁移、`test_m3_*` | v1 管理与查询 API | 不修改旧种子服务；不得无匹配时绑定默认流程 |

### 3.5 M4：Worker 与索引

| 目录/文件 | 待建接口 | 冲突规避 |
| --- | --- | --- |
| `workers/{models,repository,runner}.py` | claim/lease/heartbeat/retry/recovery | 通过 M0 `OutboxClaimPort`；不直接修改 M2/M3 表 |
| `indexing/{models,contracts,repository,service}.py` | `IndexGenerationPort`、原子世代切换、缓存/图谱失效 | 消费版本化事件；索引是派生数据，不反写领域状态 |
| Worker/索引迁移与 `test_m4_*` | 任务并发、宕机恢复、幂等消费 | 等 M2/M3 事件样例冻结后联调 |

### 3.6 M5：检索与 RAG

| 目录/文件 | 待建接口 | 冲突规避 |
| --- | --- | --- |
| `domains/rag/{contracts,evidence,safety,service,models}.py` | 授权查询、Evidence Pack、唯一最终回答、Provider 记录 | 只消费 M2/M3/M4 公开只读端口；不查询其 ORM |
| 重构 `retrieval/` 适配层 | effective-only、权限/设备范围过滤、统一知识/流程召回 | 旧算法可复用但不得继续以 JSON 为目标事实源 |
| `api/v1/search.py`、`rag.py`、迁移、`test_m5_*` | v1 检索/RAG API | 指定 evidence ID 在生成前过滤；mock 不进入生产链路 |

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

- M0 只修改 `core/`、`db/` 和公共契约；M1 只消费端口并修改 `domains/identity|audit` 与三个预留路由，不修改 `main.py` 或根 router。
- M2、M3 可同时开发各自领域表和契约 Mock；同一时间只允许一个集成人员基于最新 head 创建/重定迁移。
- M4 在事件 DTO 冻结前只写消费者契约测试；不得轮询 M2/M3 表。
- M5/M6 在真实端口交付前使用版本化 Mock；Mock 不进入生产 Provider、索引或审核数据。
- M7 只提供环境、脚本和共享夹具，不在测试夹具中复制领域业务实现。
- 当前 M1 身份依赖未关闭冲突，任何 M2/M3 生产写路由不得接入；这是阻止冲突扩散的硬门槛。

## 5. 下一步顺序

1. M0/M7 搭建独立 Session、稳定 DB 503 和可信客户端地址端口。
2. M1 修正共享事务、授权快照、登录签发竞态和独立限流维度，并用 PostgreSQL 16 验证。
3. M1 完成认证最小 HTTP 闭环后，M2/M3 才接入真实身份依赖；此前继续 Mock 并行。
4. M2/M3 冻结事件与只读端口后，M4/M5 切换真实依赖。
5. M6 联调，M7 执行 Windows/Ubuntu、恢复、安全和完整 E2E 验收。
