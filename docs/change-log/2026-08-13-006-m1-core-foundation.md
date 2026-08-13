# 搭建 M1 身份与审计基础内核

- 变更标识：`2026-08-13-006-m1-core-foundation`
- 日期：`2026-08-13`
- 状态：`已完成`
- 所属模块：`M1`；协作模块：`M0`、`M7`
- 需求追踪：`AUTH-03`～`AUTH-09`、`FR-IAM-02`～`FR-IAM-05`、`DATA-02`～`DATA-05`、`NFR-SEC-02/04/07`、`NFR-OBS-01`～`NFR-OBS-03`、SRS 14.1～14.5
- 关联记录：`2026-08-13-003-m0-m1-prerequisites`、`2026-08-13-004-m1-design`、`2026-08-13-005-m1-contract-gates`

## 改动内容

- 新建 M1 身份和审计领域包，冻结角色/权限映射、`CurrentUser`、权限校验与禁止自审端口；系统管理员不隐式获得审核/业务读取权，审计查看者必须叠加业务角色才能读取知识。
- 增加 Argon2id 密码适配和基础密码策略；增加仅持久化 HMAC 摘要的随机会话令牌/CSRF 原语、绝对/空闲过期判断。
- 新建 `users`、`roles`、`user_roles`、`auth_sessions`、`login_throttles`、`audit_events` ORM 和 M1 迁移，写入五类固定角色种子，并用 PostgreSQL 触发器阻止审计事件更新、删除和截断。审计引用采用 `RESTRICT` 配合用户逻辑删除，避免外键置空与不可变触发器冲突。
- 增加同事务 `AuditWriter`；它只调用调用方 Session 的 `add()`，不自行提交，从而允许后续业务状态、审计和 outbox 原子提交，并按敏感键名递归脱敏密码、令牌、Cookie 和密钥元数据。
- 增加 M1 配置校验与锁定的 `argon2-cffi==23.1.0` 依赖；开发默认本地 HTTP Cookie，生产强制认证密钥、Secure 和 `__Host-` 前缀。

## 文件与数据影响

- `backend/app/domains/identity/`、`backend/app/domains/audit/`；新增：领域契约、授权、模型、密码、会话和审计写入。
- `backend/alembic/versions/20260813_0003_m1_identity_audit.py`；新增：M1 表、角色种子、索引、外键和不可变审计触发器；`down_revision=20260813_0002`。
- `backend/app/core/config.py`、`.env.example`、`backend/requirements.txt`；修改：增加 `APP_AUTH_*`/会话配置和 Argon2 依赖。`core/config.py` 属 M0 公共文件，本次由 M1 提案、M0 协作评审。
- `tests/test_m1_*.py`、`tests/test_module0_m1_prerequisites.py`、`tests/test_configuration_contract.py`；新增/修改：领域、配置、迁移发现和公共契约测试。
- `backend/README.md`、`docs/design/m1-identity-audit-design.md`；修改：标明已完成范围和未交付 HTTP 能力。
- API：无新增可调用路由；DTO：新增 Python `CurrentUser`/审计输入契约；事件：无；数据库：新增上述六表；配置：新增 M1 环境变量。

## 依赖与冲突检查

- 已检查：日志 003～005、M0 公共契约、领域路由/模型发现、M0 数据库基类和 Session、幂等服务、Alembic 最新 head、SRS 权限与事务规则、旧 `/api` reviewer DTO 和现有依赖。
- 结论：M1 仅在自己的领域目录和独立 revision 新增实现；未修改 `main.py`、根路由、M0 数据模型/迁移或旧 `/api`。共享配置变更经过契约测试，未新增第二套 CORS、响应、幂等或数据库基础设施。HTTP 路由留到领域服务完成后交付，避免暴露半成品认证入口。

## 验证与回滚

- 验证：`python -m compileall` 通过；M1/M0 聚焦测试 `38 passed`；完整 `pytest -q` 为 `199 passed, 22 skipped`；Alembic 单一 head 为 `20260813_0003`；PostgreSQL 离线 upgrade SQL 含六张表、角色种子、函数和触发器，离线 downgrade SQL 可删除触发器、函数与所有 M1 表；从仓库根目录 `backend.app` 和 `backend/` 目录 `app` 两种路径均发现六张表；真实 Argon2id 生成不同盐值哈希并正确验证；`git diff --check` 通过。
- 限制：当前机器未配置真实 `APP_DATABASE_URL`/PostgreSQL 服务，因此尚未执行在线 migration、约束并发或触发器集成测试；该项必须由 M7 提供 PostgreSQL 16 后完成，不能用 SQLite 替代。
- 回滚：若未写入 M1 运行数据，执行 `alembic downgrade 20260813_0002` 删除 M1 表与审计触发器，再移除领域包和 M1 配置；已写入数据时须先导出审计与身份数据并按正式变更窗口处理。

## 后续开发提示

- 下一批实现 Repository、登录限流状态机、Session 持久化与 FastAPI 身份依赖，再交付 `/api/v1/auth`；其后才实现用户/角色和审计查询 API。不得把旧 `/api` 的 `reviewer` 字段带入 v1，也不得让领域服务自行提交事务。
- M2/M3 当前可以仅依赖已冻结的 `CurrentUser`、`ensure_not_self_review()` 与 `AuditWriter` 端口开发 Mock/契约测试，但在 M1 发布真实 `get_current_user()` 前不得把生产写路由标记为完成。
