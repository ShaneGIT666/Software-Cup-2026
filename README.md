# 轻量设备检修知识与作业辅助系统

本项目面向单个企业、工厂或设备运维部门，提供设备检修知识检索、标准作业指引、维修经验沉淀、知识审核和智能辅助建议。

系统采用 B/S 架构，用户通过现代浏览器访问。项目目标是在普通企业服务器上形成一套易安装、易维护、结果可追溯的小型知识辅助系统。

默认开发及目标交付平台为 Windows；业务代码保持跨平台，目标版本必须通过 Ubuntu Server 24.04 LTS x64 CI 验证 Linux 兼容性。Linux 生产发行包和 systemd 服务属于可选交付物，不是基础版本承诺；CI 与发行工件的当前状态只查现行需求追踪矩阵。

> 本 README 只维护产品入口、稳定开发约定和证据边界。当前实现状态、验证证据和未关闭问题只以现行需求追踪矩阵为准；带日期的执行事实只在修改日志中保存，本文不建立第二套当前状态。
> 本系统不能替代设备原厂手册、安全规程、作业票、现场负责人或专业人员的最终判断。

## 1. 文档适用范围

阅读项目资料时，必须区分目标要求、当前状态和历史材料：

1. 产品范围、功能要求和验收标准以 [`docs/requirements/software-requirements-spec.md`](docs/requirements/software-requirements-spec.md) 为准。
2. 当前模块状态、验证证据和未关闭问题只以 [`docs/requirements/current-traceability-matrix.md`](docs/requirements/current-traceability-matrix.md) 为准；修改日志保存带日期的执行事实，模块计划和本 README 不维护第二套当前状态。
3. 所有现行架构、模块、公共 API、数据、事件、部署与后续开发设计只在[统一软件设计与后续开发方案](docs/design/follow-up-development-plan.md)对应章节维护；公共 HTTP/事务契约从其 [M0 公共契约](docs/design/follow-up-development-plan.md#m0-public-contract)章节进入。不得另建新的设计文档文件。
4. 后端本地运行和组件边界参考 [`backend/README.md`](backend/README.md)；其中日期化状态不得覆盖现行追踪矩阵。
5. 版本化事件、生产者/消费者和 outbox 适用范围以统一方案的[领域事件目录](docs/design/follow-up-development-plan.md#event-catalog)为准。
6. 本地变更历史和带日期的执行证据以 [`docs/change-log/INDEX.md`](docs/change-log/INDEX.md) 及相关模块的最新记录为准；日志中的待续事项必须回写现行追踪矩阵后，才构成当前未关闭问题。
7. `docs/architecture/`、`docs/deployment/`、`docs/ppt-assets/`、`docs/product/`、`docs/project-management/`、`docs/research/`、`docs/submission/`、`docs/testing/` 和 `docs/superpowers/specs/` 当前均作为历史材料保存，不代表现行产品状态、开发顺序或交付承诺。
8. 此前分散的 API、数据、M0/M1、事件、部署和模块进度设计草案已经整合后删除，只能从 Git 历史追溯，不得恢复为现行设计文件；SRS 和现行追踪矩阵以外的早期 `docs/requirements/` 材料，以及根目录 `PRODUCT.md`、`findings.md`、`progress.md`、`task_plan.md` 同样属于历史快照。
9. 脚本的稳定用途分类和证据边界只在 [`scripts/README.md`](scripts/README.md) 维护；脚本名本身不构成状态或验收证据。
10. `frontend/README.md`、`data/external-test/README.md` 和 `data/evaluation/reports/README.md` 是当前辅助说明，但不得覆盖本节前述现行基线；`data/evaluation/reports/` 中带日期的生成报告按其目录 README 作为历史回归资产解释。
11. 标有“历史快照（非现行基线）”的文件只用于追溯当时事实；其中的“当前”“最终”“正式”“已完成”“必须”“一键部署”等词不具有现行效力，命令、测试数量和部署结论必须重新验证后才能引用。

当文档内容发生冲突时，应先核对文档日期、适用范围、需求编号、模块归属和修改日志。不得在没有验证证据的情况下，以较早文档覆盖当前基线。

## 2. 状态与证据边界

六级实现状态的枚举、严格含义与升级条件只以 [SRS 第 1 节](docs/requirements/software-requirements-spec.md)为准；当前状态结论只以现行需求追踪矩阵为准。README、设计方案和修改日志不得自行扩展、重定义或提升状态。

“原型代码存在”是仓库资产限定语，“待改造”是优先级限定语，“可选”是产品范围限定语，均不是实现状态。Mock、离线 SQL、进程内测试、跳过项或单个公共端口的证据只能支持其明确状态对象，不能外推为集成通过、模块完成或生产可用。

历史日志中的“变更已结束”只表示该次修改记录已经结束，不表示对应需求已经完成。任何状态结论都必须同时列明验证对象、环境、方法、结果、跳过项和未关闭问题。

发现新的冲突或验证缺口时，必须将状态降回实际层级，并通过新的修改日志记录更正。

## 3. 目标使用范围

基础版本按照以下规模设计：

- 单企业、单实例、单一逻辑知识域，不提供多租户 SaaS。
- 基础版本的已认证业务用户共享同一知识域，使用角色权限，不提供站点、班组或设备组级 ACL。
- 预计服务 10～100 名注册用户。
- 正常并发不超过 20 个交互请求。
- 支持至少 5,000 份文档和 50,000 个有效知识片段。
- 默认部署在单台 Windows 服务器，可按需要拆分 PostgreSQL 或模型服务。
- 支持云端或企业内网 OpenAI-compatible Provider。
- 外部模型不可用时，已审核知识的基本检索和来源查看仍应可用。

基础版本不包含：

- 微服务和 Kubernetes 集群。
- 多地域容灾或多租户隔离。
- 复杂 BPM 工作流平台。
- 自动控制、启停或调整现场设备。
- 无人值守执行维修操作。
- 完整工业图数据库平台。
- 移动原生 App 和离线移动客户端。

## 4. 迁移边界与状态入口

仓库同时保留迁移期原型资产和目标模块化单体代码。原型文件存在、页面可构建或进程内测试通过，都不能直接推导为生产能力。

本节不复制模块状态表或旧原型功能清单。请直接读取 [`docs/requirements/current-traceability-matrix.md`](docs/requirements/current-traceability-matrix.md) 获取当前模块状态、实现资产、验证证据和未关闭问题；引用历史测试或提交时，再沿 [`docs/change-log/INDEX.md`](docs/change-log/INDEX.md) 查看对应日期记录。

## 5. 目标业务流程

```text
描述设备和故障
  -> 检索已审核且当前生效的知识
  -> 查看来源、证据和适用作业流程
  -> 生成带引用和风险提示的辅助建议
  -> 人工复核并执行现场规定流程
  -> 提交维修结果、经验或知识修订
  -> 审核通过后形成新的生效版本
  -> 可靠触发索引更新
  -> 原子切换新索引世代并进入正式检索
```

目标版本遵循以下原则：

1. 正式检索只使用已审核且当前生效的知识版本。
2. 自动解析、OCR 和多模态结果默认作为待审核候选。
3. 已生效知识不得原地覆盖；修改必须创建新版本并重新审核。
4. 智能建议应尽可能追溯到文档、知识片段、页码、版本或维修案例。
5. 高风险操作、关键参数缺失或证据不足时，必须停止确定性结论并提示人工复核。
6. 模型输出只属于辅助建议，不能替代正式作业规程。
7. 索引更新失败不得破坏数据库中的审核结果，也不得暴露新旧版本混合结果。

## 6. 目标架构

项目采用模块化单体，避免引入不必要的微服务和中间件。

```text
浏览器
  -> Caddy（默认参考代理）或经选定并验收的 IIS
       - HTTPS
       - 反向代理
       - 静态前端
  -> FastAPI API Windows Service
       -> PostgreSQL 16
       -> 本地受控文件目录或企业 NAS
       -> 单一向量检索后端
       -> LLM / OCR / 文档解析 Provider
  -> 后台 Worker Windows Service
       -> 文档解析
       -> OCR
       -> 索引更新
       -> 失败重试与恢复
```

目标技术路线：

| 层级 | 目标方案 |
| --- | --- |
| 前端 | Vue 3、TypeScript、Vite、Element Plus、Vue Router |
| 后端 | FastAPI 模块化单体，生产 API 统一使用 `/api/v1` |
| 数据库 | PostgreSQL 16，使用 SQLAlchemy 和 Alembic |
| 文件存储 | 程序目录外的本地受控目录，可适配企业 NAS 或对象存储 |
| 后台任务 | PostgreSQL 任务/outbox + 单一 Worker |
| 检索 | 关键词 + 单一向量后端 + RRF/重排 |
| 身份 | 本地账户或 OIDC，采用 RBAC |
| 部署 | Windows Service 为默认目标；Linux systemd 和 OCI 容器为可选项 |
| 可观测性 | 结构化日志、请求 ID、健康检查、指标和告警 |

Caddy 是 Windows 基础版的默认参考代理。部署可以选用 IIS，但必须对选中的代理单独完成 HTTPS、静态前端、信任代理链和旧入口拒绝验收；未被选中和验收的代理不属于当次交付范围。

### 实现差距的维护位置

架构图只表达目标拓扑，不证明仓库已经具备其中任一生产工件。前端、旧 `/api`、JSON、PostgreSQL、Worker、文件目录和 Service 的实现差距统一维护在现行需求追踪矩阵；本节不复制会随开发进度变化的差距清单。

## 7. 目录结构

```text
backend/                 FastAPI 后端和领域服务
  alembic/               Alembic 环境和数据库迁移
  app/
    api/v1/              目标生产 API
    core/                配置、契约、中间件和 readiness
    db/                  SQLAlchemy、幂等和 outbox 公共端口
    domains/             目标领域模块
    retrieval/           旧检索、融合和重排实现
    evaluation/          检索评测
frontend/                Vue 网页前端
data/examples/           开发示例数据
docs/requirements/       现行 SRS/追踪矩阵及带声明的历史需求材料
docs/design/             现行公共契约/事件目录及带声明的历史设计材料
docs/change-log/         可追溯修改记录、索引和模板
docs/deployment/         历史部署资料（非现行产品部署基线）
scripts/                 开发、条件性验证和历史原型脚本；边界见 scripts/README.md
tests/                   后端自动化测试
deploy/                  目标交付工件目录；实现状态见现行追踪矩阵
```

运行数据、密钥、上传文件、数据库备份和生产日志不得提交到 Git。经过授权的测试样本和示例数据除外，但必须确保其中不包含真实秘密或未经许可的数据。

## 8. Windows 本地运行

以下步骤用于运行迁移期开发环境，不代表生产安装方式。

### 8.1 环境要求

推荐开发基线：

- Windows 11 x64。
- Python 3.11.x。
- Node.js 20.19+ 或 22.12+。
- npm。
- Git。

Python 3.11 是目标和推荐基线。其他 Python 版本只有在依赖安装和测试通过后才能作为开发环境使用，不因此改变目标验收版本。

目标 Windows 交付可以封装独立运行时，但其中的 Python 版本仍必须符合目标 Python 3.11.x 基线。

### 8.2 安装依赖

在仓库根目录执行：

```powershell
python -m venv backend\.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt

cd frontend
npm ci
npm run build
cd ..
```

MinerU 不属于基础依赖。只有需要本地 MinerU 解析时才安装：

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-mineru.txt
```

轻量开发环境未安装 MinerU 时，应在本地 `.env` 中显式设置：

```text
MINERU_ENABLED=false
```

`.env.example` 和代码当前默认 `MINERU_ENABLED=true`，离线初始化脚本也不会自动将其关闭。复制或生成配置后必须人工检查，不能直接把默认值视为轻量部署配置。

### 8.3 初始化离线开发配置

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\init-config.ps1 -Mode offline
```

离线模式使用 mock Provider，仅用于页面、接口和流程调试。mock 输出不能作为真实设备诊断、正式证据或生产数据。

PowerShell 初始化脚本只提示使用 `dev.bat start` 启动 Windows 旧原型开发环境；Shell 初始化脚本明确不提供受支持的 Linux 产品启动入口。两者都只生成迁移期 Provider/mock 配置，完成后仍必须人工检查 `.env`，不得作为生产配置或部署入口。

### 8.4 启动与停止

```powershell
.\dev.bat start
.\dev.bat status
.\dev.bat verify
.\dev.bat logs
.\dev.bat stop
```

访问地址：

```text
http://127.0.0.1:5173/
```

健康检查：

```text
GET http://127.0.0.1:8000/api/health
GET http://127.0.0.1:8000/api/v1/health/live
GET http://127.0.0.1:8000/api/v1/health/ready
```

`dev verify` 只检查旧后端健康接口和前端页面的 HTTP 可达性，不运行完整测试，也不验证生产 readiness。

部分旧脚本仍存在固定用户目录或 Windows 路径假设。新开发不得继续依赖这些固定路径。

## 9. Linux 兼容性

本 README 不维护第二套 Linux 启动流程。只有在 `deploy/linux/` 形成被选定的发行工件并按 SRS 验收后，才由该目录提供受支持的产品启动说明；工件状态见现行需求追踪矩阵。

Linux 兼容目标为：

- 同一业务代码通过 Ubuntu Server 24.04 LTS x64 CI。
- 领域代码不得依赖 PowerShell、Windows 盘符、注册表或固定用户目录。
- 路径处理统一使用跨平台路径 API。
- 文本默认使用 UTF-8，业务时间统一使用 UTC。
- Windows 与 Linux 的差异限制在启动、部署和运维脚本中。
- Linux systemd 服务和生产发行包属于可选交付物。

`init-config.sh` 只生成旧 Provider/mock 配置，不构成受支持的 Linux 产品启动入口；历史 Docker/Linux 材料也不能作为当前验收入口。脚本分类与证据边界统一见 [`scripts/README.md`](scripts/README.md)。

## 10. 配置约定

项目使用仓库根目录 `.env` 保存本地环境配置。可以从 `.env.example` 复制，但必须逐项审阅默认值。

重点配置：

| 配置 | 说明 |
| --- | --- |
| `APP_ENV` | 只允许 `development`、`test` 或 `production`；其他值必须拒绝启动 |
| `APP_DATABASE_URL` | PostgreSQL 连接串 |
| `APP_DATABASE_REQUIRED` | 开发期可选；生产环境不能降低 PostgreSQL 必需性 |
| `APP_LEGACY_SURFACE_MODE` | 旧接口和静态目录保护模式 |
| `APP_TRUSTED_ORIGINS` | 允许携带凭据的浏览器 Origin |
| `APP_AUTH_SECRET` | 会话认证密钥 |
| `APP_IDEMPOTENCY_SECRET` | 幂等请求指纹密钥 |
| `RAG_VECTOR_STORE` | 当前向量存储配置 |
| `MINERU_ENABLED` | 是否启用 MinerU |
| `LLM_PROVIDER` | LLM Provider |
| `OCR_PROVIDER` | OCR Provider |
| `MULTIMODAL_PROVIDER` | 多模态 Provider |

`APP_ENV` 是安全边界配置，不得对未知值降级为开发模式或继续启动。

### 10.1 密钥和敏感配置

受 Git 管理的配置、示例配置、日志、错误响应和前端代码不得包含：

- 密码。
- API Key。
- 会话或幂等密钥。
- 访问令牌。
- 完整数据库连接串。
- Cookie 或 Authorization 内容。

秘密只能存放在：

- 未提交到 Git 的本地 `.env`。
- Windows Service 环境。
- 企业密钥管理系统。
- 经审批的部署秘密存储。

生产环境至少满足：

- `APP_AUTH_SECRET` 不少于 32 字节。
- `APP_IDEMPOTENCY_SECRET` 不少于 32 字节。
- `APP_DATABASE_URL` 使用 PostgreSQL。
- 至少配置一个明确的 HTTPS `APP_TRUSTED_ORIGINS`。
- 不得使用通配符 Origin。
- 会话 Cookie 必须启用 `Secure` 并使用 `__Host-` 前缀。

### 10.2 旧接口保护

迁移期旧前端需要 `/api` 时可使用：

```text
APP_LEGACY_SURFACE_MODE=enabled
```

仅允许本机直连时可使用：

```text
APP_LEGACY_SURFACE_MODE=loopback
```

生产环境只允许：

```text
APP_LEGACY_SURFACE_MODE=disabled
```

生产模式应拒绝旧 `/api`、`/uploads` 和 `/knowledge` 表面。该保护只是迁移期纵深防护，不能替代后续的受控下载、旧挂载物理删除和反向代理拒绝规则。

### 10.3 向量存储

当前主配置示例和代码默认使用：

```text
RAG_VECTOR_STORE=sqlite
```

仓库中的部分历史脚本仍默认选择 Chroma，`docker-run.ps1` 则关闭向量存储。这些差异属于尚未统一的历史配置，不代表基础版本同时承诺三套生产向量后端。

基础版本应最终选择并验收一个向量后端。切换实现时必须记录数据重建、回滚和评测结果。

### 10.4 Provider

开发环境可以使用 mock Provider；生产环境不得使用 mock 生成诊断、OCR、视觉线索、证据或审核内容。

生产 Provider 不可用时，只能：

- 返回已审核的正式检索结果。
- 返回确定性证据模板。
- 明确提示相关智能能力不可用。

不得用固定模拟内容伪装成真实诊断结果。

## 11. API 约定

### 11.1 API 路径

新增生产接口统一放在：

```text
/api/v1
```

旧 `/api` 仅在迁移期保留，不再承载新的生产功能。新增代码不得通过扩展旧接口规避 `/api/v1` 的身份、权限、审计、幂等和响应契约。

### 11.2 响应格式

普通响应统一使用：

```json
{
  "success": true,
  "data": {},
  "error": null,
  "meta": {
    "requestId": "..."
  }
}
```

分页响应统一使用：

```json
{
  "success": true,
  "data": {
    "items": []
  },
  "error": null,
  "meta": {
    "requestId": "...",
    "nextCursor": null
  }
}
```

列表接口使用 `limit` 和不透明 `cursor`，不得自行新增第二套分页格式。

### 11.3 并发控制

资源修改使用强 ETag 和 `If-Match`：

```text
ETag: "v3"
If-Match: "v3"
```

不接受裸整数、弱 ETag、`*` 或多个 ETag。

后端 CORS 契约必须向浏览器暴露 `X-Request-ID` 和 `ETag`。这只证明响应头策略已搭建；在真实跨域浏览器场景完成读取与 `If-Match` 回传前，不得标记为“集成已验证”。

### 11.4 幂等

只有需要防止重复提交的关键写接口才要求：

```text
Idempotency-Key
```

幂等键规则、请求指纹、冲突和回放语义以 M0 公共契约为准。普通写操作不得为了形式统一而强制生成无意义的幂等记录。

### 11.5 生产事务

生产写操作按用途分类，不得为了形式统一向所有内部状态更新发布 outbox。会改变可对外观察业务事实、且对应事件满足[领域事件生产启用门禁](docs/design/follow-up-development-plan.md#event-production-enablement-gate)的关键领域写操作，必须在启用环境的同一数据库事务中提交：

- 业务状态。
- 审计事件。
- outbox 事件。
- 接口要求幂等时对应的幂等记录。

`AuditWriter` 和 `OutboxWriter` 只能向调用方持有的事务追加记录，不得自行 `commit`、`rollback` 或返回 ORM 实体。

身份管理等安全状态变更必须与审计同事务；只有在事件目录已冻结版本化消费者时才同事务追加 outbox。登录尝试、限流计数、会话签发/活动续期/注销、Worker 心跳与租约维护均不发布业务 outbox；它们仍必须遵守各自的短事务、认证主体、审计或运行日志契约。新增或变更分类必须先修改事件目录及对应事务测试；SRS 和 M0 契约只在需求语义或公共端口发生变化时修改，避免为每个具体事件重复改写需求文档。

## 12. 身份与安全

目标身份模式支持本地账户或 OIDC，基础授权采用 RBAC。

### 12.1 HTTP 认证规则

除以下入口外，所有业务 HTTP 接口必须要求认证：

- 存活和就绪健康检查。
- 当前启用认证模式用于建立身份的匿名登录入口。
- OIDC 登录发起和授权回调；只有启用并验收 OIDC 模式时适用，实现状态见现行追踪矩阵。

匿名入口只能用于建立身份，不得读取业务数据、下载附件或执行普通业务状态变更。

匿名登录虽然可以创建会话并写入必要的登录限流和安全审计数据，但仍必须：

- 校验请求来源。
- 使用统一、脱敏的认证错误。
- 防止账户枚举。
- 执行账号和来源两个独立维度的限流。
- 不接受客户端传入的用户、角色或权限作为授权依据。

首次管理员通过受控的本地 bootstrap CLI 创建，不提供 HTTP 注册或 HTTP bootstrap 接口。bootstrap 不属于匿名 HTTP 接口。

后台 Worker 通过内部任务、租约和服务边界运行，不属于匿名 HTTP 接口。不得为后台任务增加绕过认证的公开业务 API。

### 12.2 写操作身份与追踪

所有生产持久化写操作必须携带经过服务端认证且可审计的用户身份。普通业务 HTTP 写操作使用 `CurrentUser`；内部任务使用受管服务用户身份，不能以缺少用户身份的“系统事件”绕过本规则。

具体要求如下：

- 普通业务写操作的操作者、提交者和审核者必须由服务端身份上下文确定。
- 客户端不得通过传入 `actor`、`reviewer`、用户 ID、角色或权限范围决定服务端授权。
- 登录成功后的会话与安全审计写入归属到刚完成认证的用户；登录失败记账由认证子系统的固定受管服务用户执行。实现与数据库证据只查现行需求追踪矩阵。
- bootstrap 只允许在实例进入生产激活状态前，通过受控本地 CLI 在空交互用户库执行，并由固定 bootstrap 服务用户记账；bootstrap 创建必须改密的首次管理员。activation 契约接受任一有效、已完成强制改密且持有 `system_admin` 角色的本地账户；正常首次引导中通常就是首次管理员。独立 activation CLI 成功后 bootstrap 永久拒绝再次执行。
- 首次部署必须遵循 SRS 第 10.1 节和统一方案的[受限 provisioning](docs/design/follow-up-development-plan.md#restricted-provisioning)阶段：`bootstrapped` 期间 `ready=503` 是预期状态，只允许可信管理来源访问完成登录、CSRF、本人改密和登出所需的最小身份接口；激活且 `ready=200` 后才开放普通业务流量。未通过该流程验收时不得声称首次部署闭环已完成。
- 异步任务必须保留发起用户、原始请求 ID、任务 ID 和业务对象标识。
- 无法归属到普通业务用户的内部写入必须归属到受认证的服务用户，并记录事件类型、任务或请求 ID、来源、目标对象和执行结果。
- 服务用户不得伪装成普通用户，也不得使用前端提供的身份信息代替服务端认证结果。
- 所有授权判断必须由服务端根据认证身份和当前权限快照完成。

### 12.3 浏览器安全

- 建立或使用 Cookie 会话的浏览器写请求必须校验可信 Origin。
- 已登录状态变更还必须校验与会话绑定的 CSRF token。
- CORS 不能替代服务端授权或 CSRF 校验。
- 生产 Cookie 必须使用 `Secure`、`HttpOnly`、`SameSite=Lax`、`Path=/` 和 `__Host-` 名称，不设置 `Domain`。
- 身份相关响应必须使用 `Cache-Control: no-store`。

### 12.4 数据与内容安全

- 文件下载必须经过授权 API，不得直接暴露存储目录。
- 上传文件属于不可信输入，需要限制类型、大小、解析资源和安全文件名。
- 未审核内容不得进入正式检索、RAG 上下文或有效知识关系。
- 审核、版本切换、权限变化和安全配置变化必须记录审计事件。
- 响应和日志不得泄露堆栈、绝对路径、密钥或完整连接串。
- 建议提供病毒扫描适配接口；企业安全要求启用时，应接入实际扫描服务并显示扫描状态。

## 13. 文件与知识资料

### 13.1 迁移期资产边界

旧上传入口、静态下载、JSON 元数据、仓库内文件目录和可选解析器都只属于迁移期原型资产，不能据此推导目标生产格式、大小、授权或解析能力。它们的当前实现差距只在现行需求追踪矩阵维护；具体目标规则只以 SRS 的文档管理、文件安全和性能需求为准。

### 13.2 目标版本

目标版本要求：

- 单文件默认上限为 50 MB，管理员可以降低。
- 文件元数据、解析任务和知识版本进入 PostgreSQL。
- 原始文件存放在程序目录外的受控数据目录、企业 NAS 或经适配的对象存储。
- 原始文件只能通过授权下载接口访问。
- 上传后创建持久化解析任务，不在 Web 请求中执行长耗时解析。
- 任务支持超时、有限重试、手工重跑和服务重启恢复。
- 自动生成的知识片段默认进入 `pending_review`。
- 建议提供病毒扫描适配接口；未配置时应显示风险状态。
- 上传时校验扩展名、MIME、大小、空文件和安全文件名，并计算内容哈希。

“支持某格式”表示基础部署可以抽取可审核内容。只能保存文件或缺少解析依赖时，必须标记为 `needs_parser`。

## 14. 开发约定

本节属于强制开发约定。除非需求规格或已批准的公共契约明确变更，否则新增代码、缺陷修复、数据库变更和文档修改均应遵守本节。

### 14.1 API 与兼容接口

- 新增生产接口统一放在 `/api/v1`，旧 `/api` 仅在迁移期保留。
- 旧接口只允许进行必要的安全修复和迁移兼容，不得继续承载新的生产业务能力。
- 新接口必须复用统一响应信封、错误码、请求 ID、分页、并发和幂等契约。
- API 契约发生变化时，必须同步更新契约测试、OpenAPI 声明及相关文档。

### 14.2 数据库与迁移

- 所有数据库结构变更必须附带 Alembic 迁移脚本。
- 创建新 revision 前必须运行 `alembic heads` 并记录当次实际 migration head。
- 不得修改已经登记或应用的历史迁移。
- 出现多个 migration head 时，只能通过受控集成创建合并迁移。
- 数据库迁移必须记录升级、降级、数据影响和回滚边界。
- 离线 SQL 生成成功不等于在线迁移已经验证。
- 在线迁移、回滚和恢复未在 PostgreSQL 16 上验证前，不得标记为“集成已验证”或“已完成”。

### 14.3 身份与写操作

- 所有生产持久化写操作必须携带经过服务端认证且可审计的用户身份；普通业务使用 `CurrentUser`，内部任务使用受管服务用户，bootstrap 只允许在生产激活前执行。
- 授权必须由服务端根据认证身份和当前权限快照决定。
- 客户端不得通过传入用户、角色、审核人或操作者字段决定服务端授权。
- 异步延续任务必须保留发起身份和关联请求；系统任务必须使用可追溯的任务上下文。
- 生产写事务必须按操作分类遵循业务状态、审计和必要幂等契约；只有满足事件目录“生产启用门禁”的操作才在对应环境追加 outbox。

### 14.4 模块与平台边界

- 领域服务不得依赖具体操作系统命令。
- 领域服务不得依赖 PowerShell、Windows 盘符、注册表、固定用户名或固定绝对路径。
- 平台差异只能存在于启动、部署和运维适配层。
- 新业务代码进入对应 `domains/<domain>/` 和 `api/v1/`。
- 不得继续把生产业务逻辑写入旧 `main.py`、旧 `/api` 或单个前端 `App.vue`。
- 跨模块调用优先使用公共端口、DTO 或版本化事件。
- 领域模块不得直接导入其他领域的私有 ORM 或 Repository。
- Worker 不得通过轮询或直接修改其他领域私有表实现集成。
- Mock 只能用于开发和契约测试，不得进入生产数据、证据、索引或审核链路。

### 14.5 缺陷修复与测试

- 修复缺陷时必须增加能够覆盖该缺陷的自动化测试。
- 在条件允许时，新增回归测试应能够在未修复代码上失败，并在修复后通过。
- 无法形成自动化测试时，必须在修改日志中说明原因、人工验证方法和遗留风险。
- 不得通过删除测试、跳过测试、放宽断言或关闭安全检查使测试表面通过。
- 公共契约变化必须同步检查所有调用方和消费者测试。
- 每次逻辑修改至少运行与变更范围匹配的测试。
- 涉及真实数据库、浏览器、代理或 Provider 的完成结论，必须提供对应真实依赖验证证据。
- skip、Mock、离线 migration SQL、前端构建成功或进程内 HTTP 测试不能替代真实集成验收。

### 14.6 前端

- 新前端功能使用 `/api/v1`，不得继续扩展旧 `api.ts`。
- 前端只根据 OpenAPI、稳定 DTO 和错误码实现，不读取后端内部结构。
- Cookie 请求使用 `credentials: include`。
- 登录状态、权限守卫、CSRF、统一错误处理和请求 ID 应集中管理。
- 用户角色只用于界面展示，实际授权始终由服务端决定。
- 新页面逐步拆分到 router、view、component 和 service，不继续堆入单个 `App.vue`。

### 14.7 依赖管理

- Python 生产依赖必须写入对应 requirements/锁定文件并使用可复现的锁定版本；只有宽范围而无锁定快照时，不得作为生产交付证据。
- 前端依赖必须同时进入 `package.json` 和 `package-lock.json`。
- 不允许依赖开发者全局环境中恰好已经安装的包。
- 新增依赖前应评估 Windows/Linux 可用性、安装体积、维护状态和许可证。
- Python 生产/测试依赖、容器基础镜像和前端 E2E 工具都必须形成可复现锁定；具体缺口只在现行需求追踪矩阵维护，前端安装边界见 `frontend/README.md`。
- 未进入 manifest/lockfile 的临时下载依赖不得生成交付证据。

### 14.8 状态与验证证据

状态枚举、严格含义和禁止提升条件只以 SRS 第 1 节为准，当前状态结论只在现行需求追踪矩阵维护；本节不复制第二份状态定义。

使用状态时必须同时说明：

1. 验证对象。
2. 验证环境。
3. 执行命令或验证方法。
4. 验证结果。
5. 跳过项。
6. 仍未关闭的冲突和限制。

### 14.9 修改日志

每个逻辑变更单元完成后，必须在 `docs/change-log/` 新增修改日志，并同步更新 `docs/change-log/INDEX.md`。

“逻辑变更单元”是指具有同一修改目标、可以独立验证并具有明确回滚边界的一组代码、配置、迁移、测试、脚本或文档变化。一次逻辑变更单元可以尚未完成整个需求，但必须准确记录本次实现边界。

日志文件使用以下命名格式：

```text
YYYY-MM-DD-NNN-简短主题.md
```

修改日志必须遵循 [`docs/change-log/TEMPLATE.md`](docs/change-log/TEMPLATE.md)；字段、枚举与填写规则只由模板维护，本 README 不复制清单。

记录状态、状态对象与功能验证状态必须分开。“变更已结束”只表示本次修改记录已经结束，不表示对应需求已经完成。存在未关闭冲突时，功能验证状态不得填写为“已完成”。具体枚举和字段只以日志模板为准，本 README 不复制模板正文。

开始下一次修改前，必须：

1. 读取 `docs/change-log/INDEX.md`。
2. 检查相关模块最近的修改记录。
3. 检查关联需求、公共契约和当前 migration head。
4. 确认是否已有相同目标的进行中或已结束记录。
5. 确认不会重复实现已有公共端口、数据结构或安全机制。

文档更新遵循单一事实源：需求语义更新 SRS，动态完成状态更新[当前追踪矩阵](docs/requirements/current-traceability-matrix.md)，所有设计及具体事件原位更新[统一软件设计与后续开发方案](docs/design/follow-up-development-plan.md)，执行证据更新变更日志。除对应事实源的语义或结构确实变化外，不为同一实现进度反复修改多个说明文档，也不创建新的设计文件。

其他强制规则：

- 同一目标产生的代码、配置、迁移、测试、脚本和文档变化写入同一条记录。
- 日志、索引和模板本身不递归触发新的日志记录。
- 已结束记录不得静默改写。
- 需要纠正、替代或回滚时，必须新增记录并通过“关联记录”引用原记录。
- `INDEX.md` 中的标识、日期、模块、状态、简述和链接必须与日志正文一致。
- 提交说明、合并请求、交付记录和自动化代理的修改说明，应使用与本地日志相同的变更标识。
- 日志机制不替代 Git 历史、提交说明或需求追踪矩阵。

## 15. 测试与验证

### 15.1 本地综合验证

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-local-verification.ps1
```

该脚本当前执行：

- 后端 pytest。
- 前端生产构建。
- 使用临时目录和 mock Provider 的旧 `/api` 原型闭环检查。

脚本内部调用的 `production_readiness_check.py` 名称具有历史遗留性质。它不验证 `/api/v1/health/ready`、真实 PostgreSQL、真实代理、Windows Service、完整浏览器 E2E 或真实外部 Provider，因此不能作为生产 readiness 证据。

### 15.2 单独验证

后端完整测试：

```powershell
.\backend\.venv\Scripts\python.exe -m pytest -q
```

前端构建：

```powershell
cd frontend
npm run build
```

### 15.3 验证记录入口

README 不复制测试数量、工作区提交、迁移 head 或机器环境。带日期的执行事实只保存在 [`docs/change-log/INDEX.md`](docs/change-log/INDEX.md) 指向的对应日志，当前可采信的状态、证据与缺口只在现行需求追踪矩阵汇总；引用旧记录时必须保留其环境、skip 和适用范围，不得外推到未验证边界。

### 15.4 目标性能基线

性能环境、数据规模、持续时间、成功率、P95 和 Provider 超时只以 SRS 第 8 节为准；当前实现与目标的差距只在现行需求追踪矩阵维护。README 不复制这些数值，避免需求调整时形成第二套验收基线。

## 16. PostgreSQL 开发接入

PostgreSQL 16 是目标业务数据库。旧 JSON 原型仍会在迁移期间保留，但不能作为目标生产事实源。

开发接入步骤和 bootstrap 命令参考 [`backend/README.md`](backend/README.md)。

注意：

- 测试数据库名称必须以 `_test` 结尾。
- 应用账户使用最小权限。
- migration 账户与运行时账户应分离。
- 连接串只能保存在未提交的本地 `.env`、Windows Service 环境或企业密钥系统中。
- 本节命令只用于开发接入，不构成在线迁移、并发、回滚或生产部署证明；相关状态与证据见现行需求追踪矩阵。

## 17. 部署与脚本证据边界

部署状态、实现资产、验收证据和未关闭问题只在现行需求追踪矩阵维护。开发、条件性验证、历史 Docker/LoongArch 原型与未来生产工件的分类只在 [`scripts/README.md`](scripts/README.md) 维护；脚本或文件名中的 `production`、`readiness`、`final`、`deploy`、`docker` 不能单独证明生产就绪。

Mock、skip、离线 SQL、进程内测试、页面可构建或旧 `/api` 原型闭环都只能支持其明确覆盖的局部证据，不能替代真实 PostgreSQL、浏览器、代理、Service、备份恢复或发布验收。

## 18. 目标 Windows 交付

### 18.1 基础环境

目标基础交付环境：

- Windows Server 2022 x64。
- Python 3.11.x，允许以符合该版本的独立运行时封装。
- PostgreSQL 16。
- Caddy 作为默认参考配置提供 HTTPS、反向代理和静态前端；选用 IIS 时必须独立完成同等验收。
- FastAPI 作为独立 API Windows Service。
- 后台 Worker 作为独立 Windows Service。
- 程序、配置、数据、日志和备份目录相互分离。

### 18.2 目标交付工件

目标 `deploy/windows/` 至少应提供：

```text
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
```

目标交付流程应覆盖：

- 环境预检。
- 数据库迁移。
- 初始管理员创建。
- API 和 Worker Service 安装。
- 启动、停止和状态检查。
- 升级和受控回滚。
- 数据库及文件一致备份。
- 恢复验证。
- 诊断信息收集。
- 卸载。

客户或部署环境负责提供受支持的 Windows、PostgreSQL 实例、HTTPS 证书和可选企业 Provider。安装程序不得静默安装或修改客户现有 PostgreSQL、IIS/Caddy、证书或企业身份系统。

以上均为目标交付要求，不表示工件已经存在；实现状态只查现行需求追踪矩阵。

## 19. 开发顺序入口

动态完成状态和未关闭阻断只在现行需求追踪矩阵维护；尚未完成的依赖顺序和交付门禁只在统一方案的[后续开发路线](docs/design/follow-up-development-plan.md#remaining-roadmap)原位维护。README 不保存会随进度重排的任务清单。

在现行追踪矩阵尚有阻止发布的 MUST 或未关闭冲突时，项目不得宣称生产可用，也不得用于无人监督的现场检修决策。

## 20. 许可证

当前仓库未提供明确的开源许可证。

在许可证补充前，不能默认获得复制、修改、分发或商业使用授权。项目对外发布前应明确软件许可证、第三方依赖许可证和资料版权边界。
