# 复核 M1 完成度并冻结后续搭建门槛

- 变更标识：`2026-08-13-007-m1-completion-audit`
- 日期：`2026-08-13`
- 状态：`已完成`
- 所属模块：`M1`；协作模块：`M0`、`M2`、`M3`、`M7`
- 需求追踪：`AUTH-01`～`AUTH-10`、`FR-IAM-01`～`FR-IAM-05`、`DATA-02`～`DATA-05`、`API-01`～`API-04`、`NFR-SEC-02/04/07`、`NFR-OBS-01`～`NFR-OBS-03`、SRS 14.1～14.5
- 关联记录：`2026-08-13-004-m1-design`、`2026-08-13-005-m1-contract-gates`、`2026-08-13-006-m1-core-foundation`；本记录纠正 006 中“全局生产配置立即强制认证密钥”的边界表述

## 改动内容

- 逐项对照 SRS、M1 设计、实际领域代码、M0 公共接缝、Alembic 迁移和测试，确认当前只完成基础内核，尚未交付可运行登录、用户管理或审计查询 API；在 SRS 和设计中增加可核验的完成度矩阵。
- 将认证运行时安全校验从 M0 全局配置解析中拆出为 M1 `validate_identity_runtime_settings()`：尚未交付 M1 路由时，现有 `APP_ENV=production` 兼容进程/Docker 不因缺少认证密钥而崩溃；任何后续登录或身份依赖入口必须调用该校验，在缺密钥或配置未交付的 OIDC 模式时失败关闭。
- 修正 CSRF 原语：使用原始会话令牌和认证密钥按独立 HMAC purpose 确定性派生 CSRF token，数据库仍只保存摘要，使设计中的 `GET /auth/csrf` 能在刷新后安全重建 token。
- 冻结后续结构门槛，包括不修改历史迁移、身份每请求复验、失败登录提交边界、最后管理员并发保护、会话同步失效、服务端可信来源检查、用户名规范化/固定成本校验、可信代理来源、空闲续期节流、审计事件白名单、M0 cursor/`If-Match` 协作、统一安全响应/Cookie、旧写入口下线和 M7 真实 PostgreSQL 验证。

## 文件与数据影响

- `backend/app/core/config.py`；修改：保留生产 Cookie 安全校验，移除全局装配阶段的认证密钥强制。该文件属 M0，本次由 M1 主责、M0 协作调整。
- `backend/app/domains/identity/runtime.py`、`backend/app/domains/identity/__init__.py`；新增/修改：M1 登录/身份依赖启用时的运行配置校验端口，认证密钥至少 32 字节。
- `backend/app/domains/identity/sessions.py`；修改：HMAC purpose 分离及可恢复 CSRF token。
- `tests/test_m1_identity_config.py`、`tests/test_m1_identity_sessions.py`；修改：生产兼容启动边界、M1 缺密钥失败关闭、OIDC 未交付和 CSRF 重建测试。
- `docs/requirements/software-requirements-spec.md`、`docs/design/m1-identity-audit-design.md`、`backend/README.md`；修改：完成度、事实差距、后续冲突和开发门槛。
- API、数据库表、迁移、事件：无变更；Python 公开端口新增 `validate_identity_runtime_settings()`；环境变量名称无变更。

## 依赖与冲突检查

- 已检查：日志 003～006、SRS 身份/数据/API/安全/审计/模块协作要求、M1 全部领域文件与测试、M0 路由/模型发现/CORS/错误/Session/幂等接缝、迁移链、Dockerfile、Windows/Linux 配置脚本、旧 `/api` 与前端 reviewer 字段。
- 结论：M1 可在现有结构继续实现 Repository、Service、FastAPI 依赖和路由，不需要修改 M0 根路由或重建 `0003`。旧 reviewer/静态目录只位于兼容层，未渗入 M1，但它们仍是生产认证旁路；M2/M3/M7 必须在 1.0 发布前迁移或禁用。M2/M3 可并行开发领域逻辑与契约 Mock，真实生产写路由必须等待 M1 身份依赖。CORS 不阻止简单跨站请求产生副作用，因此新增 AUTH-10，后续登录及 Cookie 写端点须实施服务端可信来源校验。

## 验证与回滚

- 验证：M1/M0 聚焦测试通过；`APP_ENV=production` 且无 `APP_AUTH_SECRET` 时 M0 兼容应用可装配 44 条现有路由；相同设置调用 M1 运行时校验返回 `DEPENDENCY_UNAVAILABLE`，少于 32 字节的密钥同样被拒绝；OIDC 模式返回 `AUTH_MODE_UNAVAILABLE`；CSRF token 可由会话令牌重建且伪造值校验失败。完整 `pytest -q` 为 `202 passed, 22 skipped`；Alembic 仍为单一 head `20260813_0003`，离线升级 SQL 保持不变；`git diff --check` 通过。
- 回滚：恢复 `get_settings()` 的全局认证密钥强制并删除 `runtime.py`，恢复随机一次性 CSRF token；这会重新引入 Docker/兼容进程启动冲突和 `/auth/csrf` 无法重建问题，不建议回滚。无数据库降级或运行数据处理。

## 后续开发提示

- 下一批先完成 M0 cursor/`If-Match` 小型协作契约，再实现 M1 Repository、登录限流状态机、会话持久化和 FastAPI 身份依赖；完成事务/并发测试后再新增 `api/v1/auth.py`。每个新逻辑批次继续新增日志，不得改写本记录或 `20260813_0003`。
- 登录失败不能直接在同一事务中写计数后抛异常导致回滚；用户/角色安全变更不能遗漏 `auth_version`、会话撤销、审计和幂等记录的同事务更新。
