# 搭建 M1 身份持久化与请求依赖接缝

- 变更标识：`2026-08-13-009-m1-identity-persistence`
- 日期：`2026-08-13`
- 状态：`已完成`
- 所属模块：`M1`；协作模块：`M0`、`M7`
- 需求追踪：`AUTH-02`、`AUTH-05`、`AUTH-07`～`AUTH-10`、`FR-IAM-05`、`API-01`～`API-04`
- 关联记录：`2026-08-13-007-m1-completion-audit`、`2026-08-13-008-m0-http-concurrency-contract`

## 改动内容

- 增加唯一用户名规范化策略，统一执行 Unicode NFKC、去首尾空白、`casefold()`、长度与字符校验。
- 增加只访问 M1 表的身份 Repository：本地用户/角色读取、会话解析/创建/撤销、节流活动续期及用户全部会话撤销；Repository 不提交调用方事务。
- 增加登录限流 Repository：用户名和来源只保存带独立 purpose 的 HMAC；失败更新使用 PostgreSQL 单条 `INSERT ... ON CONFLICT DO UPDATE ... RETURNING`，Argon2 校验期间不持有数据库行锁。
- 增加身份服务：不存在、无效、禁用、锁定账号均执行同一 dummy Argon2id 路径并返回非异常验证结果；失败记录和匿名审计由后续端点先提交再返回泛化 401，成功会话和限流清除共用调用方事务。
- 增加 FastAPI 当前用户、权限、CSRF 和可信写来源依赖。每次从服务器端会话/用户/角色重算身份；检查撤销、绝对/空闲过期、启用状态和 `auth_version`；活动续期使用 5 分钟条件更新且不会缩短已有期限。

## 文件与数据影响

- `backend/app/domains/identity/usernames.py`、`repository.py`、`service.py`、`dependencies.py`；新增：M1 私有持久化、服务与 HTTP 依赖接缝。
- `tests/test_m1_identity_repository.py`、`tests/test_m1_identity_dependencies.py`；新增：规范化、HMAC、原子 SQL、事务所有权、dummy 校验、会话复验、权限和 CSRF 单元测试。
- `docs/design/m1-identity-audit-design.md`、`docs/requirements/software-requirements-spec.md`、`README.md`、`backend/README.md`；修改：只更新当前实现状态、剩余门槛和消费者边界。
- API 路径、请求/响应字段、数据库表、Alembic 迁移、配置键和审计事件类型均无变更；尚未公开任何 M1 HTTP 路由。

## 依赖与冲突检查

- 已检查 SRS、M1 设计第 3/4/5/7/8/10 节、M0 公共契约、现有身份/审计 ORM、会话/密码/授权原语、数据库 Session 所有权、领域路由/模型发现和迁移 head。
- 结论：实现仅进入 `domains/identity/` 私有目录并消费 M0 帮助函数，未修改 `main.py`、v1 根路由、M0 数据表、历史 `20260813_0003` 迁移或其他领域文件。M2/M3 只应依赖 `CurrentUser`、`dependencies.py`、授权断言和 `AuditWriter`，不得导入本次 Repository/ORM。
- 登录来源地址仍须等待 M0/M7 冻结可信代理解析结果；后续登录路由不得直接信任 `X-Forwarded-For`。真实 PostgreSQL 并发/触发器验证仍是发布门槛，当前 SQL 编译测试不等价于在线验收。

## 验证与回滚

- 验证：M0/M1 聚焦测试 `28 passed`；完整测试 `216 passed, 22 skipped`；从仓库根导入 `backend.app` 和从 `backend/` 导入 `app` 均通过；Alembic 保持单一 head `20260813_0003`，全量离线升级 SQL 生成成功；`git diff --check` 通过。
- 回滚：删除四个新增 M1 文件和两个测试文件，并恢复三份状态文档；没有新表、迁移或运行数据需要回滚。已消费该身份依赖的 M2/M3 路由在回滚前必须先移除依赖。

## 后续开发提示

- 下一逻辑批次新增 M1 DTO、统一 Cookie/`Cache-Control: no-store` 响应帮助及 `/api/v1/auth` 路由；失败登录必须先提交限流和白名单审计事件再返回 `INVALID_CREDENTIALS`。
- 用户、角色与审计查询 API 在其后接入 M0 cursor、强 ETag/`If-Match`、幂等服务、最后管理员行锁、`auth_version`/会话撤销及同事务审计。M7 可同时准备 PostgreSQL 16 和可信代理配置，不与 M1 私有文件重叠。
