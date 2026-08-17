# D1.2 生产契约补缺

- 变更标识：`2026-08-17-019-d1-2-production-contract-closure`
- 日期：`2026-08-17`
- 记录状态：`变更已结束`（只描述本次修改记录，不表示需求功能完成）
- 状态对象：`M0 v1 通用 500 OpenAPI 契约；M1 受管服务主体、审计主体约束与实例激活边界`
- 功能验证状态：`单元已验证`
- 所属模块：`M1`；协作模块：`M0、M7`
- 需求追踪：`AUTH-13、API-05、DATA-01～DATA-03、NFR-REL-01、NFR-OBS-01～NFR-OBS-03、NFR-MNT-01～NFR-MNT-04`
- 关联记录：`2026-08-17-016-stage0-contract-alignment`、`2026-08-17-017-m0-foundation-hardening`、`2026-08-17-018-current-document-baseline-closure`
- 规范来源影响：`动态状态、领域事件、公共契约`

## 改动内容

- 在 v1 根路由统一声明脱敏 `500/V1Response`，并以契约测试验证全部 15 个 v1 操作，不改变运行时错误信封语义。
- 新增 authentication、bootstrap、worker 三个固定受管服务账户目录和 `AuthenticatedActor` 公共主体值对象；空标识、无效主体类型和交互用户伪造 initiator 均失败关闭。
- 登录失败审计改由 authentication 服务用户记账；审计 actor 改为必填且数据库非空，增加可选 `initiator_user_id`，供后续异步延续保留原始发起用户。
- 新增单例身份实例生命周期。bootstrap 仅在 `uninitialized` 且无交互用户时创建必须改密的首次管理员，以 bootstrap 服务用户和独立请求标识记账，并推进到 `bootstrapped`。
- 新增独立 activation CLI：首次管理员改掉临时密码、重新验证凭据且仍持有 `system_admin` 后才能推进到 `active`；生产 identity readiness 在激活前保持不健康。
- 实例状态的单例 ID、生命周期、正版本及激活字段一致性由数据库/ORM 约束共同表达，避免后续模块另建激活状态。

## 文件与数据影响

- `backend/app/api/v1/router.py`、`backend/app/domains/identity/`、`backend/app/domains/audit/`：修改；`service_accounts.py`、`activation.py`：新增。
- `backend/alembic/versions/20260817_0006_managed_service_identity.py`：新增后继迁移；未修改 `0001`～`0005`。新增 `users.service_key`、三条服务用户种子、`identity_instance_state`、`audit_events.initiator_user_id`，回填历史空 actor 后把 `actor_user_id` 收紧为非空。
- API 路径和现有成功/错误 DTO 未变化；全部 `/api/v1` 操作新增通用 500 OpenAPI 响应声明。
- `tests/test_module0_foundation.py`、`tests/test_m1_*`：新增或更新主体、生命周期、OpenAPI、ORM、仓储和待执行 PostgreSQL 在线断言。
- 根/后端/前端 README、现行追踪矩阵、M0/M1 契约与部署计划、模块进度计划及事件目录：按同一证据边界同步。

## 依赖与冲突检查

- 已检查：`docs/change-log/INDEX.md`、记录 016～018、M0 公共契约、M1 身份审计设计、部署就绪计划、事件目录、现行追踪矩阵、迁移 `0001`～`0005`、全部 M1 audit 写入点和两种 Python 包导入路径。
- 结论：复用现有 `CurrentUser`、`AuditWriter`、M0 readiness 与迁移链；不在 M2～M5 建立重复系统 actor，不把实例激活逻辑放入部署脚本或 HTTP 接口。当前单一迁移 head 为 `20260817_0006`，后续只能基于执行时实际 head 新增迁移。
- 状态与证据：全量单元/契约测试、离线迁移 SQL、OpenAPI、CLI 导入和前端构建通过；真实 PostgreSQL 测试仍有 3 项因缺少专用 `_test` 数据库而跳过，故功能状态只到“单元已验证”，不标记为“集成已验证”或“已完成”。

## 验证与回滚

- 验证：`.\backend\.venv\Scripts\python.exe -m pytest -q`，结果 `271 passed, 25 skipped in 18.54s`；3 项 PostgreSQL 和 22 项外部手册测试跳过。
- 验证：从 `backend/` 执行 `.\.venv\Scripts\alembic.exe heads`，结果单一 head `20260817_0006`；设置不连接的占位 PostgreSQL URL 后，离线 `upgrade head --sql` 和 `downgrade 20260817_0006:20260814_0005 --sql` 均成功。
- 验证：OpenAPI 装配发现 15 个 v1 操作，15 个均引用 `#/components/schemas/V1Response` 作为通用 500；bootstrap/activation 在仓库根与 `backend/` 两种工作目录的 `--help` 均成功。
- 验证：`npm run build` 成功，保留约 1.05 MB 主 chunk 警告；`compileall` 与 `git diff --check` 通过。
- 回滚：代码和文档按本记录文件清单恢复；数据库在尚未产生依赖 `0006` 的后续数据前可受控降级到 `20260814_0005`。降级会把受管服务 actor 归属还原为空、删除 initiator/实例状态/服务用户并放宽旧约束，存在审计语义损失；生产数据环境必须先备份并在 D2 验证影响，不能把离线 SQL 成功视为可直接生产降级。

## 后续开发提示

- D2 必须在专用 PostgreSQL 16 `*_test` 数据库在线验证空库升级、已有用户升级、三条服务种子、历史 actor 回填、外键/非空/检查约束、审计不可变触发器、bootstrap/activation 行锁并发、production readiness、受控降级与再升级。
- M2～M5 普通 HTTP 写入只接收 `CurrentUser`；内部任务复用 M1 `AuthenticatedActor`/worker 服务账户并保留 initiator，不得复制固定 UUID、服务用户表或实例生命周期。
- M6 可以消费当前通用错误 OpenAPI 契约，但真实 Cookie/CSRF/错误处理仍须 D4 浏览器 E2E；不得据生成类型提升集成状态。
- 下一次修改前必须读取 `INDEX.md`、本记录、现行追踪矩阵和受影响模块最近日志，并重新执行 `alembic heads`。
