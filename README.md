# 轻量设备检修知识与作业辅助系统

本项目面向单个企业、工厂或设备运维部门，提供设备检修知识检索、标准作业指引、维修经验沉淀、知识审核和智能辅助建议。

系统采用 B/S 架构，用户通过现代浏览器访问。项目目标是在普通企业服务器上形成一套易安装、易维护、结果可追溯的小型知识辅助系统。

默认开发及目标交付平台为 Windows；业务代码保持跨平台，并以 Ubuntu Server 24.04 LTS x64 CI 验证 Linux 兼容性。Linux 生产发行包和 systemd 服务属于可选交付物，不是当前基础版本承诺。

> 当前仓库仍处于开发和试点阶段。旧原型可以运行，M0/M1 公共底座代码已经搭建并通过进程内测试；M0 已对环境枚举、脱敏 500、CORS `ETag` 和 readiness 白名单增加回归保护。真实 PostgreSQL、前端认证接入、Windows Service、备份恢复和生产部署尚未完成。
> 本系统不能替代设备原厂手册、安全规程、作业票、现场负责人或专业人员的最终判断。

## 1. 文档适用范围

阅读项目资料时，必须区分目标要求、当前状态和历史材料：

1. 产品范围、功能要求和验收标准以 [`docs/requirements/software-requirements-spec.md`](docs/requirements/software-requirements-spec.md) 为准。
2. 当前模块状态以本 README、[`docs/design/module-build-progress-and-interface-plan.md`](docs/design/module-build-progress-and-interface-plan.md) 和最新修改日志为准。
3. 公共 API、分页、并发、幂等和数据库接入契约以 [`docs/design/m0-public-contract.md`](docs/design/m0-public-contract.md) 为准。
4. 后端运行与 M0/M1 状态参考 [`backend/README.md`](backend/README.md)。
5. 本地变更历史和未关闭事项以 [`docs/change-log/INDEX.md`](docs/change-log/INDEX.md) 及相关模块的最新记录为准。
6. `docs/architecture/`、`docs/deployment/`、`docs/ppt-assets/`、`docs/product/`、`docs/project-management/`、`docs/research/`、`docs/submission/`、`docs/testing/` 和 `docs/superpowers/specs/` 当前均作为历史材料保存，不代表现行产品状态、开发顺序或交付承诺。
7. `docs/design/api-contract-draft.md`、`docs/design/data-model-draft.md`、`docs/design/software-design-doc.md`，SRS 以外的早期 `docs/requirements/` 材料，以及根目录 `PRODUCT.md`、`findings.md`、`progress.md`、`task_plan.md` 同样属于历史快照。
8. 标有“历史快照（非现行基线）”的文件只用于追溯当时事实；其中的“当前”“最终”“正式”“已完成”“必须”“一键部署”等词不具有现行效力，命令、测试数量和部署结论必须重新验证后才能引用。

当文档内容发生冲突时，应先核对文档日期、适用范围、需求编号、模块归属和修改日志。不得在没有验证证据的情况下，以较早文档覆盖当前基线。

## 2. 状态定义

项目文档、修改日志和开发记录统一使用以下状态：

| 实现状态 | 严格含义 |
| --- | --- |
| 未开始 | 目标能力尚无现行设计或可执行实现 |
| 已设计 | 接口、边界和验收方式已记录，但尚无可执行实现 |
| 代码已搭建 | 已建立目标目录、接口、模型或基础实现，但不表示测试或集成已经通过 |
| 单元已验证 | 对应单元测试、契约测试或进程内测试已经通过 |
| 集成已验证 | 已按声明的集成边界连接真实数据库、代理、浏览器、文件系统或 Provider 完成约定场景；进程内 `TestClient` 不属于该层证据 |
| 已完成 | 功能、集成、安全、部署和需求验收全部通过，且不存在阻止交付的未关闭冲突 |

“原型代码存在”是仓库资产限定语，“待改造”是优先级限定语，“可选”是产品范围限定语；三者均不是实现状态，必须与上表六级状态分开记录。

状态使用遵循以下规则：

- “原型代码存在”不得简写为“功能可用”，也不得用来代替六级实现状态。
- “代码已搭建”不得简写为“功能已完成”。
- Mock、离线 SQL、FastAPI TestClient 或单个函数测试不能作为“集成已验证”的依据。
- 测试跳过、外部依赖缺失或旧入口尚未退役时，不得标记为“已完成”。
- 历史日志中的“变更已结束”只表示该次修改记录已经结束，不表示对应需求已经完成。
- 状态结论必须同时列明验证对象、环境、方法、结果、跳过项和未关闭问题。

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

## 4. 当前项目状态

仓库由比赛演示原型逐步向模块化单体迁移。当前可用于开发和原型验证，但尚未形成可验收的生产业务闭环。

| 模块 | 当前状态 | 主要未完成项 |
| --- | --- | --- |
| 公共底座 M0 | v1 响应/脱敏 500、请求 ID、严格环境枚举、CORS `ETag`、数据库 Session、强类型 readiness、旧表面保护、幂等和 outbox 写端口已搭建；进程内已验证 | 真实 PostgreSQL 在线迁移、中断恢复、真实代理/跨域浏览器和生产部署验收 |
| 身份与审计 M1 | 本地账户、会话、CSRF、用户/角色、审计、bootstrap 和 v1 路由已搭建；进程内已验证 | PostgreSQL 触发器、锁、并发、回滚、前端接入及目标生产事务闭环 |
| 文档与知识 M2 | 旧 JSON、上传和知识原型存在 | 目标领域表、版本审核、受控下载、v1 API 和异步解析 |
| 设备与作业 M3 | 旧种子流程和关联展示存在 | 设备/流程领域模型、版本审核、CSV 导入和可靠匹配 |
| Worker 与索引 M4 | outbox 生产者写端口存在 | claim、lease、heartbeat、retry、恢复和索引世代切换 |
| 检索与 RAG M5 | 旧检索和 RAG 原型部分可运行 | effective-only 数据源、授权过滤、v1 API、证据约束和安全降级 |
| 网页前端 M6 | Vue 单页原型可构建，使用旧 `/api` | Vue Router、登录、权限守卫、v1 客户端、领域页面和完整 E2E |
| 部署与验证 M7 | Windows 本地脚本和历史容器材料存在 | API/Worker Windows Service、安装升级、备份恢复、双平台 CI 和真实依赖验收 |

当前旧原型包含以下演示能力：

- 设备型号、故障描述和关键词检索。
- 轻量向量检索和结果融合。
- 资料上传、解析和知识切片。
- 来源引用、维修案例和种子作业流程展示。
- 原型级 OCR、多模态线索、RAG 建议和安全规则评估。
- 回答修正、知识审核及部分记录功能。

上述内容只表示原型代码存在，不表示目标版本已经完成或可以投入生产。

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
  -> IIS / Caddy
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

IIS 和 Caddy 是当前 Windows 基础验收范围。其他反向代理只有在另行完成配置、安全和真实代理链验证后才能作为可选适配。

### 当前实现与目标的区别

- 当前前端是单页 Vue 原型，尚未接入 Vue Router、登录和 `/api/v1`。
- 当前旧业务接口位于 `/api`，仅用于迁移期原型。
- 当前旧业务数据仍包含 JSON 原型链路。
- PostgreSQL 公共底座和 M1 代码已经搭建，但尚未完成真实 PostgreSQL 16 在线验收。
- 当前后台任务主要依赖 Web 进程内执行，尚不具备可靠重启恢复能力。
- 当前默认上传和知识目录位于仓库内的 `data/` 目录，尚未迁移到程序目录外的生产受控数据目录。
- 当前没有可验收的 API Windows Service、Worker Windows Service 或 Linux systemd 发行包。

## 7. 目录结构

```text
backend/                 FastAPI 后端和领域服务
  app/
    api/v1/              目标生产 API
    core/                配置、契约、中间件和 readiness
    db/                  SQLAlchemy、迁移、幂等和 outbox
    domains/             目标领域模块
    retrieval/           旧检索、融合和重排实现
    evaluation/          检索评测
frontend/                Vue 网页前端
data/examples/           开发示例数据
docs/requirements/       产品需求和验收标准
docs/design/             架构、模块和公共契约
docs/change-log/         可追溯修改记录、索引和模板
docs/deployment/         历史部署资料（非现行产品部署基线）
scripts/                 开发、验证和部署辅助脚本
tests/                   后端自动化测试
deploy/                  目标交付工件目录，当前尚未完成
```

运行数据、密钥、上传文件、数据库备份和生产日志不得提交到 Git。经过授权的测试样本和示例数据除外，但必须确保其中不包含真实秘密或未经许可的数据。

## 8. Windows 本地运行

以下步骤用于运行当前原型，不代表生产安装方式。

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
npm install
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

初始化脚本输出的直接 Uvicorn 命令不会自动读取仓库根目录 `.env`。完成初始化后，应使用 `dev.bat` 或 `scripts/start-backend.ps1` 启动后端。

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

当前仓库没有经过完整、可重复验证的 Linux 快速启动流程，因此本文不提供 Linux 启动命令。

Linux 兼容目标为：

- 同一业务代码通过 Ubuntu Server 24.04 LTS x64 CI。
- 领域代码不得依赖 PowerShell、Windows 盘符、注册表或固定用户目录。
- 路径处理统一使用跨平台路径 API。
- 文本默认使用 UTF-8，业务时间统一使用 UTC。
- Windows 与 Linux 的差异限制在启动、部署和运维脚本中。
- Linux systemd 服务和生产发行包属于可选交付物。

现有 `init-config.sh` 和历史 Docker/Linux 文档仍包含未清理的 Windows 路径或历史环境假设，不能作为当前验收入口。

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

生产写操作按用途分类，不得为了形式统一向所有内部状态更新发布 outbox。会改变可对外观察业务事实、并已在事件目录中登记下游消费者的关键领域写操作，必须在同一数据库事务中提交：

- 业务状态。
- 审计事件。
- outbox 事件。
- 接口要求幂等时对应的幂等记录。

`AuditWriter` 和 `OutboxWriter` 只能向调用方持有的事务追加记录，不得自行 `commit`、`rollback` 或返回 ORM 实体。

身份管理等安全状态变更必须与审计同事务；只有在版本化事件及其消费者已冻结时才同事务追加 outbox。登录尝试、限流计数、会话签发/活动续期/注销、Worker 心跳与租约维护均不发布业务 outbox；它们仍必须遵守各自的短事务、审计或运行日志契约。bootstrap 使用受控系统主体并写审计，在尚无登记消费者时不写 outbox。新增或变更分类必须同时修改 SRS、M0 公共契约、事件目录和事务测试。

## 12. 身份与安全

目标身份模式支持本地账户或 OIDC，基础授权采用 RBAC。

### 12.1 HTTP 认证规则

除以下入口外，所有业务 HTTP 接口必须要求认证：

- 存活和就绪健康检查。
- 当前启用认证模式用于建立身份的匿名登录入口。
- OIDC 登录发起和授权回调；当前版本尚未实现 OIDC。

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

除匿名登录、首次 bootstrap 和内部系统任务等明确登记的非普通业务流程外，生产业务写操作必须使用服务端认证得到的 `CurrentUser`。

具体要求如下：

- 普通业务写操作的操作者、提交者和审核者必须由服务端身份上下文确定。
- 客户端不得通过传入 `actor`、`reviewer`、用户 ID、角色或权限范围决定服务端授权。
- 匿名登录只能写入建立身份所必需的限流、会话和安全审计数据，不能借此修改普通业务对象。
- bootstrap 只能通过受控本地 CLI 在满足空用户库等前置条件时执行，并记录相应审计事件。
- 异步任务必须保留发起用户、原始请求 ID、任务 ID 和业务对象标识。
- 无法归属到普通用户的内部系统事件允许没有用户 actor，但必须记录明确的事件类型、任务或请求 ID、来源、目标对象和执行结果。
- 系统事件不得伪装成普通用户操作，也不得使用前端提供的身份信息代替服务端追踪信息。
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

### 13.1 当前原型限制

旧通用上传接口当前允许：

```text
PDF、JPG、JPEG、PNG、WEBP
```

限制为：

- 单文件上限 10 MB。
- 文件保存在仓库内默认 `data/uploads` 目录。
- 通过静态 `/uploads` 暴露，尚不满足目标受控下载要求。

当前知识资料代码允许上传：

```text
PDF、TXT、Markdown、DOCX、PPTX、XLSX、
JPG、JPEG、PNG、WEBP
```

限制为：

- 单文件上限 20 MB。
- 知识元数据和审核数据仍包含 JSON 原型存储。
- 文件默认保存在仓库内 `data/knowledge`。
- DOCX、PPTX 和 XLSX 依赖 MinerU 才能抽取可审核内容。
- 未安装或未启用 MinerU 时，Office 文件只能保存并标记为 `needs_parser`，不能报告解析成功。
- 允许列表已经包含 Office 文档，但当前部分错误提示尚未列出这些格式。

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
- 当前单一 migration head 为 `20260814_0005`。
- 不得修改已经登记的 `0001`～`0005`。
- 创建新 revision 前必须重新检查最新 migration head。
- 出现多个 migration head 时，只能通过受控集成创建合并迁移。
- 数据库迁移必须记录升级、降级、数据影响和回滚边界。
- 离线 SQL 生成成功不等于在线迁移已经验证。
- 在线迁移、回滚和恢复未在 PostgreSQL 16 上验证前，不得标记为“集成已验证”或“已完成”。

### 14.3 身份与写操作

- 除认证入口、bootstrap 和登记的系统任务外，生产业务写操作必须携带经过服务端认证的用户身份。
- 授权必须由服务端根据认证身份和当前权限快照决定。
- 客户端不得通过传入用户、角色、审核人或操作者字段决定服务端授权。
- 异步延续任务必须保留发起身份和关联请求；系统任务必须使用可追溯的任务上下文。
- 生产写事务必须遵循业务状态、审计、outbox 和必要幂等记录的公共契约。

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

- Python 依赖必须写入对应 requirements 文件，并尽量使用明确、可复现的版本范围。
- 前端依赖必须同时进入 `package.json` 和 `package-lock.json`。
- 不允许依赖开发者全局环境中恰好已经安装的包。
- 新增依赖前应评估 Windows/Linux 可用性、安装体积、维护状态和许可证。
- Playwright 配置和冒烟用例已经存在，但 `@playwright/test` 当前尚未写入 `package.json` 和 lockfile，因此 E2E 还不是可复现基线。
- 在 Playwright 依赖锁定前，不得把 `npm run test:e2e` 作为已通过的交付证据。

### 14.8 状态与验证证据

文档中的以下六级实现状态必须与实际验证证据和未关闭冲突一致：

- 未开始。
- 已设计。
- 代码已搭建。
- 单元已验证。
- 集成已验证。
- 已完成。

使用状态时必须同时说明：

1. 验证对象。
2. 验证环境。
3. 执行命令或验证方法。
4. 验证结果。
5. 跳过项。
6. 仍未关闭的冲突和限制。

存在下列任一情况时，不得标记为“已完成”：

- 必需的真实依赖尚未接入。
- 必需测试被跳过。
- 仅完成 Mock 或进程内验证。
- 旧匿名接口或不安全静态入口尚未退役。
- 数据库迁移、并发、回滚或恢复尚未验证。
- 仍存在会阻止目标功能验收的未关闭冲突。

### 14.9 修改日志

每个逻辑变更单元完成后，必须在 `docs/change-log/` 新增修改日志，并同步更新 `docs/change-log/INDEX.md`。

“逻辑变更单元”是指具有同一修改目标、可以独立验证并具有明确回滚边界的一组代码、配置、迁移、测试、脚本或文档变化。一次逻辑变更单元可以尚未完成整个需求，但必须准确记录本次实现边界。

日志文件使用以下命名格式：

```text
YYYY-MM-DD-NNN-简短主题.md
```

修改日志必须遵循 [`docs/change-log/TEMPLATE.md`](docs/change-log/TEMPLATE.md)，至少包含：

- 变更标识和日期。
- 记录状态。
- 功能验证状态。
- 所属模块和协作模块。
- 需求追踪和关联记录。
- 改动内容。
- 文件、数据库、API、DTO、事件和配置影响。
- 已检查的契约、迁移头、日志和冲突。
- 验证命令、环境和结果。
- 回滚方式。
- 未完成事项及后续开发提示。

记录状态与功能验证状态必须分开：

```text
记录状态：
计划中 | 执行中 | 变更已结束 | 已回滚 | 已替代

功能验证状态：
未开始 | 已设计 | 代码已搭建 | 单元已验证 | 集成已验证 | 已完成
```

“变更已结束”只表示本次修改记录已经结束，不表示对应需求已经完成。存在未关闭冲突时，功能验证状态不得填写为“已完成”。

开始下一次修改前，必须：

1. 读取 `docs/change-log/INDEX.md`。
2. 检查相关模块最近的修改记录。
3. 检查关联需求、公共契约和当前 migration head。
4. 确认是否已有相同目标的进行中或已结束记录。
5. 确认不会重复实现已有公共端口、数据结构或安全机制。

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

### 15.3 当前验证记录

截至 2026-08-17，阶段 0/1 工作区复核结果为：

- 代码基线：`main` 分支的 `f0064df0dc9c`；验证时工作区包含阶段 0/1 的未提交修改，因此本记录必须与第 016/017 号修改日志一起使用。
- 验证环境：Windows 10 Home China 25H2（NT `10.0.26200.0`）、Python `3.12.7`、Node `22.17.1`、npm `10.9.2`。这是本机开发证据，不代替目标 Python 3.11/Windows Server 2022 验收。
- 后端命令：`.\backend\.venv\Scripts\python.exe -m pytest -q`；结果 `259 passed, 25 skipped in 17.68s`。
- 跳过项：3 项真实 PostgreSQL 测试因未配置专用 `_test` 数据库而跳过，另有 22 项外部手册相关测试；skip 不计为成功。
- 数据库环境：`APP_DATABASE_URL` 未设置，未发现 `psql` 或 PostgreSQL 服务；未执行真实 PostgreSQL 在线 upgrade/downgrade。
- Alembic 命令：从 `backend/` 执行 `.\.venv\Scripts\alembic.exe heads`；结果为单一 head `20260814_0005`。本阶段无数据库结构变更，因此未新增迁移。
- 包导入检查：仓库根 `backend.app` 和 `backend/` 目录 `app` 两种方式均发现 14 个唯一 v1 路径（15 个路由操作）。
- 前端命令：从 `frontend/` 执行 `npm run build`；构建成功，主 JavaScript 为 `1,052.46 kB`，仍触发大 chunk 警告。
- 浏览器认证、真实跨域 ETag/`If-Match`、真实代理和核心业务 E2E 尚未形成锁定、可复现的验收基线。

以上结果是带日期的验证记录，不能替代后续提交重新运行验证。

### 15.4 目标性能基线

目标性能基线为：

- Windows Server 2022 x64。
- 8 核 x64 CPU。
- 16 GB 内存。
- SSD。
- PostgreSQL 16。
- 50,000 个有效知识片段。
- 目标版本选定的单一向量后端。
- 至少 10 分钟持续负载。
- 成功请求率不低于 99%。

目标性能要求：

| 场景 | 指标 |
| --- | --- |
| 20 个并发交互请求下的检索 API | P95 不高于 2 秒 |
| 普通非模型读写 API | P95 不高于 1 秒 |
| LLM 调用默认超时 | 不超过 30 秒 |
| 外部 LLM 网络延迟 | 单独报告，不计入本地检索指标 |

当前 `init-config.ps1` 的真实 LLM 模式使用 60 秒超时，与目标默认值不一致。完成 1.0 验收前必须调整为不超过 30 秒，或通过正式需求变更和基准测试统一修改需求、脚本、配置和验收口径。

## 16. PostgreSQL 开发接入

PostgreSQL 16 是目标业务数据库。旧 JSON 原型仍会在迁移期间保留，但不能作为目标生产事实源。

开发接入步骤和 bootstrap 命令参考 [`backend/README.md`](backend/README.md)。

注意：

- 测试数据库名称必须以 `_test` 结尾。
- 应用账户使用最小权限。
- migration 账户与运行时账户应分离。
- 连接串只能保存在未提交的本地 `.env`、Windows Service 环境或企业密钥系统中。
- 当前仓库尚未完成真实 PostgreSQL 16 在线验收，因此这些步骤属于开发接入说明，不是生产部署证明。

## 17. 部署状态

### 17.1 当前可用

- Windows 本地开发启动。
- 前后端原型运行。
- 离线配置和 mock Provider 调试。
- 后端单元及进程内测试。
- 前端类型检查和构建。
- Alembic 离线 SQL 检查。
- 旧 `/api` 原型闭环检查。

### 17.2 当前不可宣称

- 不可宣称已经具备生产部署能力。
- 不可宣称已经完成 API Windows Service。
- 不可宣称已经完成 Worker Windows Service。
- 不可宣称已经完成 Linux systemd 部署。
- 不可宣称已经完成真实 PostgreSQL 在线迁移。
- 不可宣称已经完成备份恢复、升级回滚或卸载闭环。
- 不可宣称已经完成浏览器登录和权限 E2E。
- 不可将 mock Provider、skip、离线 SQL 或旧原型闭环作为生产验收证据。

### 17.3 Docker 状态

当前 Dockerfile 和相关脚本属于历史原型资料，不能作为生产或验收入口。

现有 Dockerfile 同时设置生产环境和 mock Provider，且没有补齐生产数据库、认证密钥、幂等密钥和可信 HTTPS Origin。生产模式下旧 `/api` 又必须关闭，因此当前旧前端也不能通过该镜像形成产品闭环。

在 Docker 路径重新完成以下工作前，不得作为正式交付方式：

- 生产配置预检。
- PostgreSQL 16 连接和迁移。
- 非 mock Provider 或安全降级。
- 新版前端 `/api/v1` 接入。
- 程序目录外的受控数据目录。
- 健康检查、备份、恢复和升级。
- Linux 目标环境验收。

## 18. 目标 Windows 交付

### 18.1 基础环境

目标基础交付环境：

- Windows Server 2022 x64。
- Python 3.11.x，允许以符合该版本的独立运行时封装。
- PostgreSQL 16。
- IIS 或 Caddy 提供 HTTPS、反向代理和静态前端。
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

当前 `deploy/windows/` 工件尚未完成，以上均为目标交付要求。

## 19. 改造优先级

1. 完成 PostgreSQL 16 在线迁移、触发器、事务和并发验收。
2. 完成本地身份、RBAC、审计和受控文件访问闭环。
3. 建立知识版本审核、统一生产写事务、outbox 和索引一致性。
4. 建立持久化 Worker、失败重试和重启恢复。
5. 重构前端路由、登录、权限守卫和 `/api/v1` 客户端。
6. 完成 API/Worker Windows Service、代理、备份恢复和升级回滚。
7. 建立 Windows 与 Ubuntu Server 24.04 LTS CI。
8. 锁定 Playwright 依赖并完成核心浏览器 E2E。
9. 完成检索评测、安全降级、性能测试和发布验收。

在真实 PostgreSQL、身份与权限、知识版本、可靠任务和 Windows 部署闭环完成前，项目应保持“开发/试点”状态，不应用于无人监督的现场检修决策。

## 20. 许可证

当前仓库未提供明确的开源许可证。

在许可证补充前，不能默认获得复制、修改、分发或商业使用授权。项目对外发布前应明确软件许可证、第三方依赖许可证和资料版权边界。
