# 搭建 M1 本地身份、用户与审计 HTTP 闭环

- 变更标识：`2026-08-13-011-m1-local-identity-http`
- 日期：`2026-08-13`
- 记录状态：`变更已结束`
- 功能验证状态：`代码已搭建、进程内单元/API 已验证；真实 PostgreSQL 集成未验证，M1 功能未完成`
- 所属模块：`M1`；协作模块：`M0`、`M7`
- 需求追踪：`AUTH-01`～`AUTH-12`、`FR-IAM-01`～`FR-IAM-05`、`DATA-02`～`DATA-08`、`API-01`～`API-07`、`NFR-SEC-02/04/07`、`NFR-OBS-01`～`NFR-OBS-03`
- 关联记录：`2026-08-13-003-m0-m1-prerequisites`、`2026-08-13-006-m1-core-foundation`、`2026-08-13-008-m0-http-concurrency-contract`、`2026-08-13-009-m1-identity-persistence`、`2026-08-13-010-module-progress-audit`

## 改动内容

### M0 协作项

- 在 `db/session.py` 提供拥有 commit/rollback/close 的 `new_session()`，并统一把数据库未配置、初始化、连接或连接池超时映射为脱敏 `DEPENDENCY_UNAVAILABLE/503`。
- 新增 `ClientAddressResolver` 与 `APP_TRUSTED_PROXY_CIDRS`：默认使用直连地址，只在直接上游可信时解析代理链；非法、过长和不可信代理头不能覆盖直连地址。
- 为身份、用户、角色和审计路径增加统一 `Cache-Control: no-store`；生产或强制数据库模式的 readiness 同时校验身份运行时密钥。
- 为幂等服务增加只读 replay 查询，使本人改密重试可以在昂贵 Argon2 验证前返回既有结果。

### M1 主体

- 将请求身份解析和活动续期拆为独立短事务；会话、用户状态、`auth_version` 与角色由一条聚合查询读取，不提交调用方业务 Session。
- 登录采用“最小凭据短读 → 事务外 Argon2 → 写事务内账号/凭据/安全版本/限流快照复验 → 会话与审计提交”，避免长事务和并发安全变更后误签发。
- 新增 `login_throttle_buckets` 独立账号主体桶和来源桶；历史 `login_throttles` 表不修改、不再作为新登录流程的数据源。
- 新增认证 HTTP：`POST /api/v1/auth/login`、`logout`，`GET /auth/me`、`csrf`，`PUT /auth/password`。
- 新增管理 HTTP：`GET/POST/PATCH /api/v1/users`、用户状态/角色/密码端点、`GET /api/v1/roles`、`GET /api/v1/audit-events`；复用 M0 cursor、ETag/`If-Match`、幂等、可信来源和响应信封。
- 新增 Cookie/no-store 响应帮助、M1 私有 HTTP DTO、用户管理服务、只读审计 Repository 和空用户库首个系统管理员 CLI；没有开放注册/bootstrap HTTP 接口。
- 用户禁用、角色变更、本人改密和管理员重设密码使用安全版本与会话撤销；本人改密保留当前会话并撤销其他会话，临时密码会话由服务端权限依赖限制到本人信息、CSRF、改密和登出；最后一个活动系统管理员受到行锁保护。真实 PostgreSQL 并发行为仍待验证。

## 文件与数据影响

- M0 修改：`.env.example`、`backend/app/main.py`、`backend/app/api/v1/system.py`、`backend/app/core/config.py`、`backend/app/db/session.py`、`backend/app/db/idempotency.py`、`backend/app/db/__init__.py`。
- M0 新增：`backend/app/core/client_address.py`、`backend/app/core/cache_control.py`。
- M1 修改：`backend/app/domains/identity/contracts.py`、`dependencies.py`、`models.py`、`repository.py`、`service.py`。
- M1 新增：`backend/app/domains/identity/transactions.py`、`login.py`、`commands.py`、`admin.py`、`http_contracts.py`、`http_responses.py`、`bootstrap.py`、`backend/app/domains/audit/repository.py`、`backend/app/api/v1/auth.py`、`users.py`、`audit.py`。
- 数据库：新增迁移 `backend/alembic/versions/20260813_0004_m1_login_throttle_buckets.py`，当前单一 head 为 `20260813_0004`；历史 `0003` 未编辑。
- 测试：修改 M0/M1 基础测试；新增认证、用户、审计、bootstrap 和专用 PostgreSQL 在线测试。
- 文档：更新根/后端 README、SRS、M0 公共契约、M1 设计和模块进度计划；只更正实施状态，不把功能标为完成。

## 依赖与冲突检查

- 已检查：日志 001～010、SRS、M0/M1 设计、路由/模型自动发现、迁移 `0001`～`0004`、旧 `/api` 与静态挂载、M1 ORM/Repository/Service/依赖和全部 `test_m1_*`。
- 复用结论：M1 路由通过 M0 预留注册表装配，未修改根 router；M1 Repository 只访问身份/审计私有表；公共短事务、错误、地址、缓存、幂等和 readiness 变更归属 M0，没有在 M1 复制第二套基础设施。
- 未关闭冲突：旧 `/api` 匿名写接口仍信任客户端 `reviewer`，`/uploads` 与 `/knowledge` 仍静态暴露；前端仍使用旧 API；真实 PostgreSQL 在线迁移、触发器、行锁/死锁恢复、并发限流/会话失效和 API 集成未验证。M2/M3 在这些数据库门槛关闭前继续使用身份契约 Mock。

## 验证与回滚

- 完整回归：`backend/.venv/Scripts/python.exe -m pytest -q` → `239 passed, 25 skipped`。其中 M1 PostgreSQL 3 项因未设置 `M1_TEST_POSTGRES_URL` 跳过，其余 skip 为现有外部手册测试；skip 不计为成功证据。
- 装配：从仓库根导入 `backend.app` 和从 `backend/` 导入 `app` 均发现 15 条 `/api/v1` 路由，其中 M1 路由 13 条、健康路由 2 条。
- 静态/迁移：`compileall` 通过；Alembic 单一 head 为 `20260813_0004`；显式占位 PostgreSQL URL 的离线 `upgrade head --sql` 通过。未执行真实数据库在线 upgrade/downgrade。
- 回滚：代码回滚须将本记录的 M1 路由/领域文件和 M0 协作修改作为同一逻辑单元恢复；若 `0004` 已在线应用，先停止登录写入并执行到 `20260813_0003` 的受控降级以删除独立限流桶，再部署兼容旧表的旧代码。当前未对任何真实数据库执行迁移。

## 后续开发提示

- 下一步由 M7 提供名称以 `_test` 结尾的专用 PostgreSQL 16 数据库，设置 `M1_TEST_POSTGRES_URL` 后执行在线迁移、触发器、锁/并发、回滚和 API 集成测试；通过前不得把 M1 或 SRS 对应能力标为“集成已验证/已完成”。
- M6 可以依据当前 OpenAPI/DTO 开发登录与权限客户端；M2/M3 继续只消费 `CurrentUser`、权限依赖和 `AuditWriter` 公开端口，不得导入 M1 ORM/Repository。
- 后续不得重新启用历史组合限流表、在路由直接信任 `X-Forwarded-For`、让身份依赖提交业务 Session，或绕开统一 Cookie/no-store/幂等帮助。
