# 明确认证例外中的本地登录入口

- 变更标识：`2026-08-13-002-auth-entry-exception`
- 日期：`2026-08-13`
- 状态：`已完成`
- 所属模块：`M1`；协作模块：`无`
- 需求追踪：`AUTH-01`、`AUTH-06`、`FR-IAM-01`、`NFR-SEC-02`
- 关联记录：`2026-08-13-001-change-log`

## 改动内容

- 修正 AUTH-01 的认证例外：除健康检查和 OIDC 回调外，明确允许当前启用认证模式的匿名登录入口，其中包含本地账户登录、OIDC 登录发起和 OIDC 授权回调。
- 限定匿名例外只能用于建立身份，不能读取业务数据、下载附件或执行业务状态变更，避免为实现本地登录而意外扩大匿名访问范围。

## 文件与数据影响

- `docs/requirements/software-requirements-spec.md`；修改：更新文档日期并修订 AUTH-01 的认证边界。
- `docs/change-log/INDEX.md`；修改：登记本次需求澄清。
- `docs/change-log/2026-08-13-002-auth-entry-exception.md`；新增：记录本次需求澄清。
- 数据库表、迁移、API、DTO、事件、运行配置：无。后续 M1 实现将据此设计匿名 `POST /api/v1/auth/login` 与 OIDC 登录入口；具体路径和 DTO 仍须在 M1 实施日志中冻结。

## 依赖与冲突检查

- 已检查：`docs/change-log/INDEX.md`、`2026-08-13-001-change-log`、SRS 的 AUTH-01、AUTH-06、FR-IAM-01、API-01 和 NFR-SEC-02，以及当前 M0 `/api/v1/health/live`、`/api/v1/health/ready` 路由。
- 结论：现有 AUTH-01 把本地登录这一建立身份的必要匿名入口遗漏在外；本次仅补足该例外并限制其能力，不改变健康检查、角色矩阵、M0 v1 信封或旧 `/api` 的兼容行为，不存在重复实现或契约冲突。

## 验证与回滚

- 验证：检查 AUTH-01 同时覆盖本地账户与 OIDC 两种 SRS 允许的认证模式，且明确匿名入口的最小权限；执行 `git diff --check`。
- 回滚：回退 SRS 中 AUTH-01 和更新日期，并从索引移除本条记录、删除本文件；无数据库迁移或运行时数据影响。

## 后续开发提示

- M1 实现必须为匿名 `POST /api/v1/auth/login`、OIDC 登录发起和回调使用显式 allowlist；不得采用“`/api/v1/auth/*` 全部匿名”的宽泛规则。
- 除上述入口及 M0 健康检查外，新增 v1 业务路由默认应要求 `CurrentUser`；旧 `/api` 在迁移期仍为原型兼容层，不能被误认为已满足 AUTH-01。
