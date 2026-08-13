# 关闭 M1 身份错误码与审计权限设计门槛

- 变更标识：`2026-08-13-005-m1-contract-gates`
- 日期：`2026-08-13`
- 状态：`已完成`
- 所属模块：`M1`；协作模块：`M0`
- 需求追踪：`AUTH-01`、`AUTH-03`、`AUTH-05`、`AUTH-09`、`API-02`、SRS 14.2～14.5
- 关联记录：`2026-08-13-003-m0-m1-prerequisites`、`2026-08-13-004-m1-design`

## 改动内容

- 将 M1 所需的九个身份与审计错误码登记到 M0 公共注册表和冻结契约；匿名登录仍只能用泛化的 `INVALID_CREDENTIALS` 表示账户、密码或锁定失败，避免账户枚举。
- 统一 SRS 权限矩阵与 AUTH-09：`auditor` 基线只拥有脱敏审计和运行报告读取权，读取业务知识必须显式叠加 `technician`；系统管理员也不再隐式获得业务读取权。
- 修正 M1 Cookie 设计：HTTP 开发模式使用无保留前缀的 Cookie 名，生产 HTTPS 模式才使用要求 `Secure` 的 `__Host-` 前缀。

## 文件与数据影响

- `backend/app/core/error_codes.py`；修改：登记 M1 稳定错误码。
- `docs/design/m0-public-contract.md`、`docs/design/m1-identity-audit-design.md`、`docs/requirements/software-requirements-spec.md`；修改：冻结错误码、权限和 Cookie 约束。
- `tests/test_module0_m1_prerequisites.py`；修改：增加错误码和 SRS 权限契约测试。
- API：尚未新增路由；DTO、事件、数据库和运行配置：无。

## 依赖与冲突检查

- 已检查：M0 公共契约与错误码实现、M1 设计 G1/G2、SRS 角色矩阵与 AUTH-09、M0 路由/模型发现和最新迁移头 `20260813_0002`。
- 结论：设计总体合理；本次关闭了公开 API 开工前的两个门槛，并纠正一项浏览器 Cookie 前缀约束。没有引入第二套权限、错误处理或 CORS 实现。

## 验证与回滚

- 验证：`backend\\.venv\\Scripts\\python.exe -m pytest tests/test_module0_m1_prerequisites.py -q` 通过；`git diff --check` 通过。
- 回滚：移除新增身份错误码和对应契约测试，恢复 SRS 权限矩阵及设计门槛状态；不涉及数据库降级或运行数据。

## 后续开发提示

- M1 可以开始公开 API 实现；登录失败不得直接返回 `ACCOUNT_LOCKED` 或 `ACCOUNT_DISABLED`。生产使用 `__Host-repair_session` 时必须同时启用 `Secure` 且不得设置 `Domain`。
